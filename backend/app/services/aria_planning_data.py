"""
ARIA planner — the data layer.

The only part of the planner that touches the database, and it does very little:
`aria_intelligence_data.gather_facts` already assembles the snapshot, so this
module exists to run the pure engines over it and to sync the operational
calendar into the reminder system.

The calendar sync follows the same discipline as Part 5's supervisor: it is
idempotent. A plan regenerated every morning must not deposit a fresh copy of
"Buy feed" each time, so entries are matched against open and recently-completed
reminder titles before anything is written. Duplicate reminders are how a farmer
learns to ignore reminders.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.automation import Reminder
from app.models.farm import Farm
from app.schemas.automation import ReminderCreate
from app.services import (
    aria_intelligence as engine,
    aria_intelligence_data,
    aria_planning as planner,
    automation_service,
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def gather(db: AsyncSession, farm: Farm, user: User) -> engine.FarmFacts:
    """Facts for planning — the Part 4 gatherer, unchanged."""
    return await aria_intelligence_data.gather_facts(db, farm, user)


async def plan_everything(
    db: AsyncSession,
    farm: Farm,
    user: User,
    *,
    horizon_days: int = 30,
    sync_calendar: bool = False,
) -> dict:
    """
    One full planning pass.

    Read-only by default: opening the planning dashboard must not create
    reminders. `sync_calendar=True` also writes the calendar into the reminder
    system, and doing so twice creates nothing the second time.
    """
    facts = await gather(db, farm, user)

    result = {
        "facts": facts,
        "feed": planner.forecast_feed(facts),
        "production": planner.forecast_production(facts),
        "capacity": planner.plan_capacity(facts),
        "budget": planner.plan_budget(facts, "monthly"),
        "cashflow": planner.project_cashflow(facts, days=horizon_days),
        "calendar": planner.build_calendar(facts, days=horizon_days),
        "created_reminders": [],
    }

    if sync_calendar:
        result["created_reminders"] = await sync_calendar_reminders(
            db, farm, user, result["calendar"]
        )
    return result


async def sync_calendar_reminders(
    db: AsyncSession,
    farm: Farm,
    user: User,
    calendar: list[planner.CalendarEntry],
) -> list[Reminder]:
    """
    Turn calendar entries into reminders, skipping anything already there.

    Matched on title against open reminders and ones completed in the last
    three days, so a task the farmer just ticked off is not immediately
    recreated by the next planning run.
    """
    if not calendar:
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

    # Daily-recording nudges are handled by the supervisor's own routine
    # priority; turning them into dated reminders would produce one row per day
    # and bury everything else.
    skip_kinds = {"recording"}

    created: list[Reminder] = []
    for entry in calendar:
        if entry.kind in skip_kinds:
            continue
        key = entry.title.strip().lower()
        if key in taken:
            continue
        due = datetime.combine(date.fromisoformat(entry.on), datetime.min.time()).replace(hour=6)
        reminder = await automation_service.create_reminder(
            db, farm,
            ReminderCreate(
                title=entry.title[:200],
                notes=entry.why,
                due_at=due,
                recurrence="none",
                priority="high" if entry.kind == "vaccination" else "normal",
            ),
            user,
        )
        created.append(reminder)
        taken.add(key)

    return created
