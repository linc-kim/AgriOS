"""
ARIA intelligence — the data gatherer.

The only part of the intelligence engine that touches the database. It reads
from the services that already own each domain — production dashboard, vaccination
schedule, finance, disease risk, daily logs, reminders — assembles a plain
`FarmFacts` snapshot, and hands it to the pure functions in `aria_intelligence`.

Keeping this separate from the reasoning is what lets the reasoning be tested
without a database, and it means the intelligence can only ever see numbers a
real service computed from real records. Nothing here computes farm metrics
itself; it composes existing, trusted ones. Every read is wrapped so that a
single unavailable source degrades one field to "not recorded" rather than
failing the whole briefing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.automation import Reminder
from app.models.farm import Farm
from app.models.flock import DailyLog, Flock, ProductionRecord, WeighinRecord
from app.models.inventory import InventoryItem
from app.services import (
    aria_intelligence as engine,
    automation_service,
    flock_service,
    health_service,
)
from app.services.aria_intelligence import FarmFacts, FlockStage


async def _safe(coro, default=None):
    """Run a gather step; a failure degrades one field, never the whole brief."""
    try:
        return await coro
    except Exception:
        return default


async def gather_facts(db: AsyncSession, farm: Farm, user: User) -> FarmFacts:
    """Assemble a FarmFacts snapshot for `farm` from the existing services."""
    today = date.today()
    facts = FarmFacts(farm_name=farm.name, as_of=today)

    # ── Active flocks & stages ────────────────────────────────────────────
    flocks = (
        await db.execute(
            select(Flock).where(
                Flock.farm_id == str(farm.id),
                Flock.status == "active",
                Flock.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    facts.active_flocks = len(flocks)
    facts.initial_birds = sum(int(fl.initial_count or 0) for fl in flocks)
    facts.flock_stages = [
        FlockStage(
            name=fl.name,
            age_days=(today - fl.placement_date).days if fl.placement_date else None,
            species=getattr(fl, "species_key", "poultry"),
        )
        for fl in flocks
    ]
    flock_ids = [str(fl.id) for fl in flocks]

    # ── Production dashboard (eggs, feed, mortality this week, birds) ──────
    dash = await _safe(flock_service.get_farm_production_dashboard(db, farm.id))
    if dash is not None:
        facts.total_birds = dash.total_birds
        facts.avg_bird_age_days = dash.avg_bird_age_days
        facts.eggs_today = dash.eggs_today
        facts.eggs_this_week = dash.eggs_this_week
        facts.hen_day_pct = dash.avg_hen_day_production
        facts.feed_today_kg = Decimal(str(dash.feed_today_kg))
        facts.feed_this_week_kg = Decimal(str(dash.feed_this_week_kg))
        facts.mortality_this_week = dash.mortality_this_week

    # ── Prior-week comparisons (for trends) — one bounded query each ───────
    if flock_ids:
        facts.eggs_prev_week = await _prev_week_sum(
            db, ProductionRecord, ProductionRecord.eggs_collected,
            ProductionRecord.record_date, flock_ids, today,
        )
        facts.mortality_prev_week = await _prev_week_sum(
            db, DailyLog, DailyLog.mortality_count, DailyLog.log_date, flock_ids, today,
        )
        facts.feed_prev_week_kg = Decimal(str(await _prev_week_sum(
            db, DailyLog, DailyLog.feed_consumed_kg, DailyLog.log_date, flock_ids, today,
        )))

        # ── Recency of each record kind ───────────────────────────────────
        facts.days_since_feed_log = await _days_since(
            db, DailyLog, DailyLog.log_date, flock_ids, today,
            extra=DailyLog.feed_consumed_kg > 0,
        )
        facts.days_since_mortality_log = await _days_since(
            db, DailyLog, DailyLog.log_date, flock_ids, today,
            extra=DailyLog.mortality_count > 0,
        )
        facts.days_since_egg_log = await _days_since(
            db, ProductionRecord, ProductionRecord.record_date, flock_ids, today,
        )
        facts.days_since_weighin = await _days_since(
            db, WeighinRecord, WeighinRecord.weighed_at, flock_ids, today,
        )
        facts.days_since_any_log = await _days_since(
            db, DailyLog, DailyLog.log_date, flock_ids, today,
        )

        # ── Water (Part 5) ────────────────────────────────────────────────
        # water_litres is nullable on the daily log, so "no water recorded" and
        # "recorded zero" are different facts. SUM over no rows yields None
        # here rather than 0, and the monitor treats None as unmeasured.
        facts.water_today_litres = await _nullable_sum(
            db, DailyLog, DailyLog.water_litres, DailyLog.log_date, flock_ids, today, today,
        )
        facts.water_this_week_litres = await _nullable_sum(
            db, DailyLog, DailyLog.water_litres, DailyLog.log_date, flock_ids,
            today - timedelta(days=6), today,
        )
        facts.water_prev_week_litres = await _nullable_sum(
            db, DailyLog, DailyLog.water_litres, DailyLog.log_date, flock_ids,
            today - timedelta(days=13), today - timedelta(days=7),
        )
        facts.days_since_water_log = await _days_since(
            db, DailyLog, DailyLog.log_date, flock_ids, today,
            extra=DailyLog.water_litres.isnot(None),
        )

    # ── Inventory (Part 5) ────────────────────────────────────────────────
    items = (
        await db.execute(
            select(InventoryItem).where(
                InventoryItem.farm_id == str(farm.id),
                InventoryItem.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    facts.inventory_tracked = len(items)
    # `is_low` / `is_out` are the model's own definitions — reuse them rather
    # than re-deriving a threshold the inventory module already owns.
    facts.inventory_out = [i.name for i in items if i.is_out]
    facts.inventory_low = [i.name for i in items if i.is_low and not i.is_out]

    # ── Vaccination schedule ──────────────────────────────────────────────
    schedule = await _safe(health_service.get_upcoming_vaccinations(db, farm.id))
    if schedule is not None:
        facts.vaccinations_overdue = len(schedule.overdue)
        facts.vaccinations_due_today = len(schedule.due_today)
        facts.vaccinations_due_week = len(schedule.due_this_week)
        first = (
            (schedule.overdue or []) + (schedule.due_today or []) + (schedule.due_this_week or [])
        )
        if first:
            item = first[0]
            facts.next_vaccination = {
                "vaccine": item.next_vaccine_name or item.vaccine_name,
                "flock": item.flock_name,
                "days_until_due": item.days_until_due,
            }

    # ── Disease risk (deterministic scorer) ───────────────────────────────
    from app.services import ai_platform_service

    risk = await _safe(ai_platform_service.disease_risk(db, farm))
    if risk is not None:
        facts.disease_score = risk.score
        facts.disease_level = risk.level
        facts.disease_factors = [
            {"factor": x.factor, "impact": x.impact, "detail": x.detail} for x in risk.factors
        ]
        facts.disease_recommendation = risk.recommendation

    # ── Finance ───────────────────────────────────────────────────────────
    from app.services import finance_service

    fin = await _safe(finance_service.get_finance_dashboard(db, farm, user))
    if fin is not None:
        facts.is_profitable = fin.is_profitable
        facts.gross_profit = Decimal(str(fin.gross_profit_kes))
        facts.feed_cost = Decimal(str(fin.feed_cost_kes))
        facts.feed_cost_pct = Decimal(str(fin.feed_cost_pct)) if fin.feed_cost_pct is not None else None
        facts.revenue = Decimal(str(fin.total_revenue_kes))
        facts.expenses = Decimal(str(fin.total_expenses_kes))

    # ── Reminders ─────────────────────────────────────────────────────────
    reminders = await _safe(automation_service.list_reminders(db, farm.id, include_done=False), default=[])
    now = datetime.now(tz=timezone.utc)
    facts.reminders_open = len(reminders)
    facts.reminders_overdue = sum(
        1 for r in reminders if r.due_at and _aware(r.due_at) < now
    )
    # Titles let auto-generation skip anything the farmer already has open;
    # the upcoming list feeds the briefing and the priority ranking.
    facts.reminder_titles = [r.title for r in reminders if r.title]
    horizon = now + timedelta(days=7)
    facts.upcoming_reminders = sorted(
        (
            {
                "title": r.title,
                "due_at": _aware(r.due_at).isoformat(),
                "overdue": _aware(r.due_at) < now,
            }
            for r in reminders
            if r.due_at and _aware(r.due_at) <= horizon
        ),
        key=lambda x: x["due_at"],
    )

    return facts


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _prev_week_sum(db, model, column, date_col, flock_ids, today) -> int:
    """Sum of `column` over the week *before* the current 7-day window."""
    start = today - timedelta(days=13)
    end = today - timedelta(days=7)
    result = await db.execute(
        select(func.coalesce(func.sum(column), 0)).where(
            model.flock_id.in_(flock_ids),
            date_col >= start,
            date_col <= end,
            model.deleted_at.is_(None),
        )
    )
    value = result.scalar_one()
    return int(value) if value is not None else 0


async def _nullable_sum(db, model, column, date_col, flock_ids, start, end) -> Decimal | None:
    """
    Sum a nullable measure over a window, preserving "never recorded" as None.

    Deliberately does NOT coalesce to zero. For water, "no reading" and "drank
    nothing" are opposite facts — one is a gap in the records, the other is an
    emergency — and collapsing them would have the supervisor either cry wolf
    or miss a real one.
    """
    result = await db.execute(
        select(func.sum(column)).where(
            model.flock_id.in_(flock_ids),
            date_col >= start,
            date_col <= end,
            model.deleted_at.is_(None),
        )
    )
    value = result.scalar_one()
    return Decimal(str(value)) if value is not None else None


async def _days_since(db, model, date_col, flock_ids, today, extra=None) -> int | None:
    """Days since the most recent matching record, or None if there is none."""
    conditions = [model.flock_id.in_(flock_ids), model.deleted_at.is_(None)]
    if extra is not None:
        conditions.append(extra)
    result = await db.execute(select(func.max(date_col)).where(*conditions))
    latest = result.scalar_one()
    if latest is None:
        return None
    return (today - latest).days


# ── Orchestrators ────────────────────────────────────────────────────────────


async def daily_briefing(db: AsyncSession, farm: Farm, user: User) -> engine.Briefing:
    facts = await gather_facts(db, farm, user)
    health = engine.compute_health_score(facts)
    insights = engine.build_insights(facts)
    return engine.build_briefing(facts, health, insights)


async def full_report(db: AsyncSession, farm: Farm, user: User) -> dict:
    """Everything at once — used by the workspace's intelligence panel."""
    facts = await gather_facts(db, farm, user)
    health = engine.compute_health_score(facts)
    insights = engine.build_insights(facts)
    checklist = engine.build_checklist(facts)
    trends = engine.explain_trends(facts)
    briefing = engine.build_briefing(facts, health, insights)
    return {
        "briefing": briefing,
        "health": health,
        "insights": insights,
        "checklist": checklist,
        "trends": trends,
    }
