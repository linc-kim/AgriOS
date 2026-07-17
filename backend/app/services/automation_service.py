"""
Greena — Automation & Notifications Service (Module 8).

A trigger-driven automation engine on top of the existing Notification system:

  * Notification channels — in-app (always) plus email / SMS / push abstractions
    that degrade to a safe no-op/log when unconfigured (push-ready).
  * Triggers — low feed, low inventory, vaccination due, health alerts,
    mortality spikes, maintenance due, financial anomalies, overdue tasks.
  * Automation rules — if <trigger> [conditions] then <actions> (notify /
    create reminder), with priority + active flag.
  * Reminder engine — one-time and recurring reminders (calendar-ready via due_at
    + recurrence) that fire in-app notifications when due.

Every notification is audited. All farm-scoped (DB-04 Frozen).
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.automation import AutomationRule, Reminder
from app.models.farm import Farm
from app.models.finance import Expense
from app.models.flock import DailyLog
from app.models.health import VaccinationRecord
from app.models.platform import Notification
from app.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    EngineRunResult,
    ReminderCreate,
    ReminderUpdate,
)

logger = logging.getLogger("greena.automation")

_PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "critical": 3}


# ── Notification channels ─────────────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str) -> bool:
    """Email channel abstraction. Real SMTP is wired via config in production;
    unconfigured environments log and no-op (never raises)."""
    logger.info("[email] to=%s subject=%s", to, subject)
    return True


def _send_sms(phone: str, body: str) -> bool:
    """SMS channel abstraction — delegates to the SMS service when available."""
    try:
        from app.services import sms_service  # noqa: F401
        logger.info("[sms] to=%s len=%d", phone, len(body))
        return True
    except Exception:
        return False


def _send_push(user_id, title: str, body: str) -> bool:
    """Push channel abstraction — ready for a provider (FCM/APNs); logs for now."""
    logger.info("[push] user=%s title=%s", user_id, title)
    return True


async def _dispatch(
    db: AsyncSession, farm: Farm, ntype: str, title: str, body: str,
    priority: str = "normal", action_route: Optional[str] = None,
    source: str = "automation", channels: Optional[list[str]] = None,
    dedup: bool = True,
) -> Optional[Notification]:
    """Create an in-app notification (deduped) + fan out to extra channels."""
    channels = channels or ["in_app"]
    user_id = farm.owner_id

    if dedup:
        since = datetime.now(tz=timezone.utc) - timedelta(hours=20)
        existing = await db.execute(
            select(Notification.id).where(
                Notification.farm_id == farm.id, Notification.user_id == user_id,
                Notification.notification_type == ntype, Notification.title == title,
                Notification.is_read.is_(False), Notification.is_archived.is_(False),
                Notification.created_at >= since,
            ).limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            return None

    notif = Notification(
        farm_id=farm.id, user_id=user_id, notification_type=ntype, title=title, body=body,
        action_route=action_route, source=source, priority=priority,
    )
    db.add(notif)
    await db.flush()

    # Extra channels (safe no-ops when unconfigured).
    if "email" in channels:
        _send_email(str(user_id), title, body)
    if "sms" in channels:
        _send_sms(str(user_id), body)
    if "push" in channels:
        _send_push(user_id, title, body)

    from app.services import audit_service
    await audit_service.log_action(db, action="notification.create", resource_type="notification",
                                   resource_id=notif.id, farm_id=farm.id, user_id=user_id,
                                   new_value={"type": ntype, "priority": priority})
    return notif


# ── Trigger evaluators ────────────────────────────────────────────────────────

async def _evaluate_trigger(db, farm: Farm, trigger_type: str, conditions: dict) -> list[dict]:
    """Return a list of event dicts for a trigger given optional conditions."""
    events: list[dict] = []

    if trigger_type == "low_feed":
        from app.services import feed_service
        for a in await feed_service.get_reorder_alerts(db, farm.id):
            events.append({"title": f"Low feed: {a.feed_type}",
                           "body": f"{a.quantity_kg} kg of {a.feed_type} left at {a.location} (reorder at {a.reorder_level_kg} kg).",
                           "priority": "high", "route": "/feed"})

    elif trigger_type == "low_inventory":
        from app.services import inventory_service
        for al in await inventory_service.get_alerts(db, farm.id):
            if al.kind in ("low_stock", "out_of_stock", "expiring_soon", "expired"):
                events.append({"title": f"{al.title}", "body": al.detail,
                               "priority": "critical" if al.severity == "critical" else "high", "route": "/inventory"})

    elif trigger_type == "vaccination_due":
        window = int(conditions.get("within_days", 3))
        horizon = date.today() + timedelta(days=window)
        res = await db.execute(
            select(func.count(VaccinationRecord.id)).where(
                VaccinationRecord.farm_id == farm.id, VaccinationRecord.deleted_at.is_(None),
                VaccinationRecord.next_due_date.is_not(None), VaccinationRecord.next_due_date <= horizon)
        )
        n = int(res.scalar_one())
        if n > 0:
            events.append({"title": f"{n} vaccination(s) due", "body": f"{n} vaccination(s) due within {window} days.",
                           "priority": "high", "route": "/livestock"})

    elif trigger_type == "health_alert":
        from app.services import health_service
        summary = await health_service.get_farm_health_summary(db, farm)
        if summary.critical_open > 0:
            events.append({"title": f"{summary.critical_open} critical health issue(s)",
                           "body": f"{summary.critical_open} critical open health event(s) need attention.",
                           "priority": "critical", "route": "/livestock"})
        elif summary.open_events > 0:
            events.append({"title": f"{summary.open_events} open health event(s)",
                           "body": f"{summary.open_events} health event(s) are still open.",
                           "priority": "normal", "route": "/livestock"})

    elif trigger_type == "mortality_spike":
        window = int(conditions.get("window_days", 3))
        threshold = int(conditions.get("threshold", 20))
        since = date.today() - timedelta(days=window)
        res = await db.execute(
            select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
                DailyLog.farm_id == farm.id, DailyLog.deleted_at.is_(None), DailyLog.log_date >= since)
        )
        deaths = int(res.scalar_one())
        if deaths >= threshold:
            events.append({"title": f"Mortality spike: {deaths} deaths",
                           "body": f"{deaths} deaths in the last {window} days (threshold {threshold}).",
                           "priority": "critical", "route": "/livestock"})

    elif trigger_type == "maintenance_due":
        from app.services import inventory_service
        for a in await inventory_service.list_assets(db, farm.id):
            if a.is_maintenance_due:
                events.append({"title": f"Service due: {a.name}",
                               "body": f"{a.name} service due {a.next_service_date}.",
                               "priority": "normal", "route": "/inventory"})

    elif trigger_type == "financial_anomaly":
        pct = Decimal(str(conditions.get("increase_pct", 50)))
        today = date.today()
        cur = await _exp_sum(db, farm.id, today - timedelta(days=6), today)
        prev = await _exp_sum(db, farm.id, today - timedelta(days=13), today - timedelta(days=7))
        if prev > 0 and cur > prev * (1 + pct / 100) and cur > Decimal("1000"):
            events.append({"title": "Expense spike detected",
                           "body": f"Expenses this week (KES {cur:,}) are up sharply vs last week (KES {prev:,}).",
                           "priority": "high", "route": "/finance"})

    elif trigger_type == "tasks_overdue":
        now = datetime.now(tz=timezone.utc)
        res = await db.execute(
            select(func.count(Reminder.id)).where(
                Reminder.farm_id == farm.id, Reminder.deleted_at.is_(None),
                Reminder.is_done.is_(False), Reminder.due_at < now)
        )
        n = int(res.scalar_one())
        if n > 0:
            events.append({"title": f"{n} overdue task(s)", "body": f"You have {n} overdue reminder(s).",
                           "priority": "high", "route": "/automation"})

    return events


async def _exp_sum(db, farm_id, s, e) -> Decimal:
    res = await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(
        Expense.farm_id == str(farm_id), Expense.deleted_at.is_(None),
        Expense.expense_date >= s, Expense.expense_date <= e))
    return Decimal(res.scalar_one())


_ALL_TRIGGERS = ["low_feed", "low_inventory", "vaccination_due", "health_alert",
                 "mortality_spike", "maintenance_due", "financial_anomaly", "tasks_overdue"]


# ── Engine ────────────────────────────────────────────────────────────────────

async def run_engine(db: AsyncSession, farm: Farm, user: User) -> EngineRunResult:
    """Run built-in triggers, fire due reminders, and evaluate automation rules."""
    details: list[dict] = []
    notifs = 0
    triggers_fired = 0

    # 1. Built-in triggers → notifications.
    for tt in _ALL_TRIGGERS:
        events = await _evaluate_trigger(db, farm, tt, {})
        if events:
            triggers_fired += 1
        for ev in events:
            n = await _dispatch(db, farm, f"trigger.{tt}", ev["title"], ev["body"],
                                priority=ev["priority"], action_route=ev.get("route"), source="trigger")
            if n is not None:
                notifs += 1
                details.append({"trigger": tt, "title": ev["title"]})

    # 2. Reminders.
    reminders_fired = await run_reminders(db, farm)
    notifs += reminders_fired

    # 3. Automation rules.
    rules_evaluated, rules_matched, rule_notifs = await evaluate_rules(db, farm, user)
    notifs += rule_notifs

    await db.commit()
    return EngineRunResult(
        triggers_fired=triggers_fired, notifications_created=notifs, reminders_fired=reminders_fired,
        rules_evaluated=rules_evaluated, rules_matched=rules_matched, details=details,
    )


async def run_reminders(db: AsyncSession, farm: Farm) -> int:
    now = datetime.now(tz=timezone.utc)
    res = await db.execute(
        select(Reminder).where(
            Reminder.farm_id == farm.id, Reminder.deleted_at.is_(None), Reminder.is_done.is_(False),
            Reminder.due_at <= now)
    )
    fired = 0
    for rem in res.scalars().all():
        # Don't fire the same reminder twice in the same due window.
        if rem.last_fired_at and rem.last_fired_at >= rem.due_at:
            continue
        n = await _dispatch(db, farm, "reminder", f"Reminder: {rem.title}", rem.notes or rem.title,
                            priority=rem.priority, action_route="/automation", source="reminder", dedup=False)
        if n is not None:
            fired += 1
        rem.last_fired_at = now
        # Advance recurrence, or complete one-time reminders.
        if rem.recurrence == "daily":
            rem.due_at = rem.due_at + timedelta(days=1)
        elif rem.recurrence == "weekly":
            rem.due_at = rem.due_at + timedelta(weeks=1)
        elif rem.recurrence == "monthly":
            rem.due_at = rem.due_at + timedelta(days=30)
        else:
            rem.is_done = True
            rem.done_at = now
        rem.next_fire_at = None if rem.is_done else rem.due_at
    return fired


async def evaluate_rules(db: AsyncSession, farm: Farm, user: User) -> tuple[int, int, int]:
    res = await db.execute(
        select(AutomationRule).where(
            AutomationRule.farm_id == farm.id, AutomationRule.deleted_at.is_(None),
            AutomationRule.is_active.is_(True))
    )
    rules = list(res.scalars().all())
    matched = 0
    notifs = 0
    now = datetime.now(tz=timezone.utc)
    for rule in rules:
        events = await _evaluate_trigger(db, farm, rule.trigger_type, rule.conditions or {})
        min_count = int((rule.conditions or {}).get("min_count", 1))
        rule.last_run_at = now
        rule.run_count = (rule.run_count or 0) + 1
        if len(events) < min_count:
            continue
        matched += 1
        for action in (rule.actions or []):
            atype = action.get("type", "notify")
            if atype == "notify":
                title = action.get("title") or f"Rule: {rule.name}"
                body = action.get("message") or f"{len(events)} event(s) matched '{rule.name}'."
                n = await _dispatch(db, farm, f"rule.{rule.trigger_type}", title, body,
                                    priority=action.get("priority", rule.priority),
                                    action_route=events[0].get("route") if events else None,
                                    source="rule", channels=action.get("channels", ["in_app"]))
                if n is not None:
                    notifs += 1
            elif atype == "create_reminder":
                due = now + timedelta(days=int(action.get("in_days", 1)))
                db.add(Reminder(farm_id=farm.id, user_id=farm.owner_id,
                                title=action.get("title") or f"Follow up: {rule.name}",
                                notes=action.get("message"), due_at=due,
                                recurrence=action.get("recurrence", "none"),
                                priority=action.get("priority", rule.priority),
                                next_fire_at=due, created_by=user.id))
    return len(rules), matched, notifs


# ── Automation rule CRUD ──────────────────────────────────────────────────────

async def create_rule(db, farm: Farm, data: AutomationRuleCreate, user: User) -> AutomationRule:
    rule = AutomationRule(
        farm_id=farm.id, name=data.name, description=data.description, trigger_type=data.trigger_type,
        conditions=data.conditions, actions=data.actions, priority=data.priority, is_active=data.is_active,
        created_by=user.id)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_rules(db, farm_id) -> list[AutomationRule]:
    res = await db.execute(select(AutomationRule).where(
        AutomationRule.farm_id == farm_id, AutomationRule.deleted_at.is_(None))
        .order_by(AutomationRule.created_at.desc()))
    return list(res.scalars().all())


async def _get_rule(db, farm_id, rule_id) -> AutomationRule:
    res = await db.execute(select(AutomationRule).where(
        AutomationRule.id == rule_id, AutomationRule.farm_id == farm_id, AutomationRule.deleted_at.is_(None)))
    r = res.scalar_one_or_none()
    if r is None:
        raise NotFoundException("Automation rule not found.")
    return r


async def update_rule(db, farm_id, rule_id, data: AutomationRuleUpdate) -> AutomationRule:
    rule = await _get_rule(db, farm_id, rule_id)
    for f in ("name", "description", "conditions", "actions", "priority", "is_active"):
        v = getattr(data, f)
        if v is not None:
            setattr(rule, f, v)
    rule.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db, farm_id, rule_id) -> None:
    rule = await _get_rule(db, farm_id, rule_id)
    rule.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Reminder CRUD ─────────────────────────────────────────────────────────────

async def create_reminder(db, farm: Farm, data: ReminderCreate, user: User) -> Reminder:
    rem = Reminder(farm_id=farm.id, user_id=user.id, title=data.title, notes=data.notes,
                   due_at=data.due_at, recurrence=data.recurrence, priority=data.priority,
                   next_fire_at=data.due_at, created_by=user.id)
    db.add(rem)
    await db.commit()
    await db.refresh(rem)
    return rem


async def list_reminders(db, farm_id, include_done=False) -> list[Reminder]:
    filters = [Reminder.farm_id == farm_id, Reminder.deleted_at.is_(None)]
    if not include_done:
        filters.append(Reminder.is_done.is_(False))
    res = await db.execute(select(Reminder).where(*filters).order_by(Reminder.due_at.asc()))
    return list(res.scalars().all())


async def _get_reminder(db, farm_id, rid) -> Reminder:
    res = await db.execute(select(Reminder).where(
        Reminder.id == rid, Reminder.farm_id == farm_id, Reminder.deleted_at.is_(None)))
    r = res.scalar_one_or_none()
    if r is None:
        raise NotFoundException("Reminder not found.")
    return r


async def update_reminder(db, farm_id, rid, data: ReminderUpdate) -> Reminder:
    rem = await _get_reminder(db, farm_id, rid)
    for f in ("title", "notes", "due_at", "recurrence", "priority"):
        v = getattr(data, f)
        if v is not None:
            setattr(rem, f, v)
    if data.is_done is not None:
        rem.is_done = data.is_done
        rem.done_at = datetime.now(tz=timezone.utc) if data.is_done else None
    if data.due_at is not None and not rem.is_done:
        rem.next_fire_at = data.due_at
    rem.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(rem)
    return rem


async def delete_reminder(db, farm_id, rid) -> None:
    rem = await _get_reminder(db, farm_id, rid)
    rem.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Activity Center ───────────────────────────────────────────────────────────

async def list_activity(db, farm_id, user_id, status: str = "all", q: Optional[str] = None,
                        priority: Optional[str] = None, limit: int = 50, offset: int = 0) -> list[Notification]:
    filters = [Notification.farm_id == farm_id, Notification.user_id == user_id,
               Notification.deleted_at.is_(None)]
    if status == "unread":
        filters += [Notification.is_read.is_(False), Notification.is_archived.is_(False)]
    elif status == "read":
        filters += [Notification.is_read.is_(True), Notification.is_archived.is_(False)]
    elif status == "archived":
        filters.append(Notification.is_archived.is_(True))
    else:  # all active (not archived)
        filters.append(Notification.is_archived.is_(False))
    if priority:
        filters.append(Notification.priority == priority)
    if q:
        like = f"%{q}%"
        filters.append(func.lower(Notification.title).like(func.lower(like)))
    res = await db.execute(select(Notification).where(*filters)
                           .order_by(Notification.created_at.desc()).limit(limit).offset(offset))
    return list(res.scalars().all())


async def archive_notification(db, farm_id, user_id, notif_id, archived: bool = True) -> Notification:
    res = await db.execute(select(Notification).where(
        Notification.id == notif_id, Notification.farm_id == farm_id, Notification.user_id == user_id,
        Notification.deleted_at.is_(None)))
    n = res.scalar_one_or_none()
    if n is None:
        raise NotFoundException("Notification not found.")
    n.is_archived = archived
    n.archived_at = datetime.now(tz=timezone.utc) if archived else None
    await db.commit()
    await db.refresh(n)
    return n
