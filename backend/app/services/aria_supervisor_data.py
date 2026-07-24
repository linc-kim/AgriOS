"""
ARIA supervisor — the data layer.

The only part of the supervisor that touches the database. It gathers the
timeline from existing tables, runs the pure engine, and syncs its conclusions
into the two systems that already exist for them: notifications and reminders.

Nothing here re-implements a domain. Notifications go through
`notification_service`, reminders through `automation_service`, and the facts
come from `aria_intelligence_data.gather_facts` — the supervisor adds
supervision, not a parallel copy of the farm.

The one hard requirement of an unattended process is that running it twice
changes nothing the second time. Both sync functions are therefore idempotent:
alerts carry a stable key that is embedded in the notification and matched
before writing, and reminder proposals are matched against open titles. A
supervisor that duplicated its own alerts every run would be worse than no
supervisor at all.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.automation import Reminder
from app.models.farm import Farm
from app.models.flock import DailyLog, Flock, ProductionRecord, WeighinRecord
from app.models.health import VaccinationRecord
from app.models.platform import Notification
from app.schemas.automation import ReminderCreate
from app.schemas.platform import NotificationCreate
from app.services import (
    aria_intelligence as engine,
    aria_intelligence_data,
    aria_supervisor as supervisor,
    automation_service,
    notification_service,
)
from app.services.aria_supervisor import Alert, MonitorState, TimelineEvent

#: Marks every notification this supervisor creates, so its own rows can be
#: recognised later without colliding with other producers.
SOURCE = "aria_supervisor"

#: Severity → the Notification.priority vocabulary already in the model.
_PRIORITY = {
    MonitorState.CRITICAL: "critical",
    MonitorState.WARNING: "high",
    MonitorState.WATCH: "normal",
}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Timeline ─────────────────────────────────────────────────────────────────


async def gather_timeline(
    db: AsyncSession, farm: Farm, *, days: int = 30, limit: int = 50
) -> list[TimelineEvent]:
    """
    Build the activity feed from what was actually recorded.

    Reads the operational tables directly rather than inventing an event log:
    every row here is something the farmer entered, so the timeline is a true
    history rather than a reconstruction.
    """
    since = date.today() - timedelta(days=days)
    events: list[TimelineEvent] = []

    flock_ids = [
        str(r) for r in (
            await db.execute(
                select(Flock.id).where(
                    Flock.farm_id == str(farm.id), Flock.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    ]
    if not flock_ids:
        return []

    names = {
        str(fid): name for fid, name in (
            await db.execute(
                select(Flock.id, Flock.name).where(Flock.id.in_(flock_ids))
            )
        ).all()
    }

    def flock_of(fid) -> str:
        return names.get(str(fid), "flock")

    # Vaccinations.
    for v in (await db.execute(
        select(VaccinationRecord).where(
            VaccinationRecord.flock_id.in_(flock_ids),
            VaccinationRecord.administered_date >= since,
            VaccinationRecord.deleted_at.is_(None),
        )
    )).scalars().all():
        events.append(TimelineEvent(
            at=datetime.combine(v.administered_date, datetime.min.time()),
            kind="vaccination",
            title=f"{v.vaccine_name} given",
            detail=flock_of(v.flock_id),
        ))

    # Egg production.
    for p in (await db.execute(
        select(ProductionRecord).where(
            ProductionRecord.flock_id.in_(flock_ids),
            ProductionRecord.record_date >= since,
            ProductionRecord.deleted_at.is_(None),
        )
    )).scalars().all():
        events.append(TimelineEvent(
            at=datetime.combine(p.record_date, datetime.min.time()),
            kind="production",
            title=f"{p.eggs_collected} eggs collected",
            detail=flock_of(p.flock_id),
        ))

    # Daily logs — feed and mortality are separate stories on one row.
    for lg in (await db.execute(
        select(DailyLog).where(
            DailyLog.flock_id.in_(flock_ids),
            DailyLog.log_date >= since,
            DailyLog.deleted_at.is_(None),
        )
    )).scalars().all():
        at = datetime.combine(lg.log_date, datetime.min.time())
        if lg.mortality_count:
            events.append(TimelineEvent(
                at=at, kind="mortality",
                title=f"{lg.mortality_count} bird(s) lost",
                detail=flock_of(lg.flock_id),
            ))
        if lg.feed_consumed_kg:
            events.append(TimelineEvent(
                at=at, kind="feed",
                title=f"{lg.feed_consumed_kg}kg feed used",
                detail=flock_of(lg.flock_id),
            ))

    # Weigh-ins.
    for w in (await db.execute(
        select(WeighinRecord).where(
            WeighinRecord.flock_id.in_(flock_ids),
            WeighinRecord.weighed_at >= since,
            WeighinRecord.deleted_at.is_(None),
        )
    )).scalars().all():
        events.append(TimelineEvent(
            at=datetime.combine(w.weighed_at, datetime.min.time()),
            kind="weighin",
            title=f"Weigh-in: {w.average_weight_kg}kg average",
            detail=flock_of(w.flock_id),
        ))

    # Completed reminders.
    for r in (await db.execute(
        select(Reminder).where(
            Reminder.farm_id == str(farm.id),
            Reminder.is_done.is_(True),
            Reminder.deleted_at.is_(None),
        )
    )).scalars().all():
        if r.done_at:
            events.append(TimelineEvent(
                at=_aware(r.done_at).replace(tzinfo=None),
                kind="reminder",
                title=f"Reminder completed: {r.title}",
            ))

    return supervisor.build_timeline(events, limit=limit)


# ── Notification sync ────────────────────────────────────────────────────────


def _alert_marker(alert: Alert) -> str:
    """
    The dedupe token embedded in a notification body.

    Stored in the body rather than a new column so the supervisor can be
    idempotent without a migration — the Notification model already carries
    everything else it needs.
    """
    return f"[{SOURCE}:{alert.key}]"


async def sync_alert_notifications(
    db: AsyncSession,
    farm: Farm,
    user: User,
    alerts: list[Alert],
    *,
    dedupe_window_hours: int = 20,
) -> list[Notification]:
    """
    Persist alerts as notifications, without duplicating.

    An alert that is still true tomorrow should not produce a second row today,
    so an alert whose marker already appears in a recent unarchived notification
    is skipped. The window is just under a day: a condition that persists across
    days is worth re-surfacing each morning, one that persists across an hour is
    not.
    """
    if not alerts:
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=dedupe_window_hours)
    recent = (
        await db.execute(
            select(Notification).where(
                Notification.farm_id == str(farm.id),
                Notification.user_id == str(user.id),
                Notification.source == SOURCE,
                Notification.is_archived.is_(False),
                Notification.created_at >= cutoff,
            )
        )
    ).scalars().all()
    seen = {n.body for n in recent}

    created: list[Notification] = []
    for alert in alerts:
        marker = _alert_marker(alert)
        if any(marker in body for body in seen):
            continue
        body = f"{alert.reason}\n\nEvidence: {'; '.join(alert.evidence)}\nAction: {alert.action}\n{marker}"
        notification = await notification_service.create_notification(
            db,
            NotificationCreate(
                farm_id=farm.id,
                user_id=user.id,
                notification_type=f"aria_{alert.monitor}",
                title=alert.title,
                body=body,
                action_route="/ai",
                source=SOURCE,
            ),
        )
        # `priority` isn't on NotificationCreate, so set it after the fact —
        # severity is what lets the centre group by urgency.
        notification.priority = _PRIORITY.get(alert.severity, "normal")
        await db.commit()
        await db.refresh(notification)
        created.append(notification)
        seen.add(body)

    return created


# ── Reminder sync ────────────────────────────────────────────────────────────


async def sync_auto_reminders(
    db: AsyncSession, farm: Farm, user: User, facts: engine.FarmFacts
) -> list[Reminder]:
    """
    Create the reminders the supervisor proposes, skipping any that exist.

    `propose_reminders` already filters against open titles; this re-checks
    against the database, including reminders completed recently, so a task the
    farmer just ticked off is not immediately recreated.
    """
    proposals = supervisor.propose_reminders(facts)
    if not proposals:
        return []

    existing = (
        await db.execute(
            select(Reminder).where(
                Reminder.farm_id == str(farm.id),
                Reminder.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=3)
    taken = {
        r.title.strip().lower()
        for r in existing
        if not r.is_done or (r.done_at and _aware(r.done_at) >= cutoff)
    }

    created: list[Reminder] = []
    for p in proposals:
        if p.title.strip().lower() in taken:
            continue
        due = datetime.combine(
            date.today() + timedelta(days=p.due_in_days), datetime.min.time()
        ).replace(hour=6)
        reminder = await automation_service.create_reminder(
            db, farm,
            ReminderCreate(title=p.title, notes=p.reason, due_at=due,
                           recurrence="none", priority="normal"),
            user,
        )
        created.append(reminder)
        taken.add(p.title.strip().lower())

    return created


# ── Orchestration ────────────────────────────────────────────────────────────


async def gather_facts_for_report(db: AsyncSession, farm: Farm, user: User) -> engine.FarmFacts:
    """
    Facts for a report, without running the monitors.

    A thin pass-through to the Part 4 gatherer — named separately so the report
    endpoint reads clearly and so reports never accidentally acquire the
    side-effecting supervision path.
    """
    return await aria_intelligence_data.gather_facts(db, farm, user)


async def supervise(
    db: AsyncSession,
    farm: Farm,
    user: User,
    *,
    sync: bool = False,
) -> dict:
    """
    One full supervision pass.

    `sync=False` (the default for reads) evaluates and reports without writing.
    `sync=True` also persists notifications and auto-reminders — kept opt-in so
    a dashboard refresh never has side effects, and only the explicit run does.
    """
    facts = await aria_intelligence_data.gather_facts(db, farm, user)
    health = engine.compute_health_score(facts)
    monitors = supervisor.run_monitors(facts)
    now = datetime.now()
    alerts = supervisor.build_alerts(facts, now=now, monitors=monitors)
    priorities = supervisor.build_priorities(facts, alerts=alerts, now=now)
    briefing = supervisor.build_supervisor_briefing(
        facts, health_score=health.score, monitors=monitors, priorities=priorities,
    )

    created_notifications: list[Notification] = []
    created_reminders: list[Reminder] = []
    if sync:
        created_notifications = await sync_alert_notifications(db, farm, user, alerts)
        created_reminders = await sync_auto_reminders(db, farm, user, facts)

    return {
        "facts": facts,
        "health": health,
        "monitors": monitors,
        "alerts": alerts,
        "priorities": priorities,
        "briefing": briefing,
        "created_notifications": created_notifications,
        "created_reminders": created_reminders,
    }
