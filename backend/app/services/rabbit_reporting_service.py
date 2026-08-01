"""
Greena — Rabbit Reporting Service (Module 17, Milestone 7)

Integration + computed-report layer (Spec Part 5 §3/§12, Part 7 §3/§16). It does
NOT re-implement any module's math (ledger CON-M7-2): the executive dashboard
COMPOSES the existing M3–M6 services (reproduction / health / finance / housing
summaries) and the PURE forecast + bottleneck engines. Only the population
roll-up is a rabbit-specific recorded aggregation.

Honesty: recorded facts sit in a ``recorded_facts`` block; every derived block is
labelled by its own engine; forecasts are always ``forecast``-labelled and never
placed in a confirmed position (Spec Part 9 §17). Nothing is stored — reports are
computed on demand. CSV export reuses the platform ``Response`` pattern.
"""

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rabbit import (
    Rabbit,
    RabbitFeedRecord,
    RabbitLitter,
    RabbitMortality,
    RabbitSale,
)
from app.services import (
    rabbit_bottleneck_engine as bottleneck_eng,
    rabbit_breeding_service,
    rabbit_finance_service,
    rabbit_forecast_engine as forecast_eng,
    rabbit_health_service,
    rabbit_housing_service,
)


def _fact(value, detail: str) -> dict:
    return {"label": "recorded", "value": value, "detail": detail}


# ── Population roll-up (rabbit-specific recorded facts) ─────────────────────────

async def _population_facts(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    async def _count(*conds) -> int:
        return (await db.execute(
            select(func.count(Rabbit.id)).where(
                Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None), *conds)
        )).scalar_one() or 0

    active = (Rabbit.status == "active",)
    return {
        "total_rabbits": _fact(await _count(*active), "Active rabbits in the herd."),
        "bucks": _fact(await _count(*active, Rabbit.sex == "buck"), "Active bucks."),
        "does": _fact(await _count(*active, Rabbit.sex == "doe"), "Active does."),
        "breeding_adults": _fact(await _count(*active, Rabbit.lifecycle_stage == "breeding_adult"),
                                 "Active breeding-adult rabbits."),
        "growers": _fact(await _count(*active, Rabbit.lifecycle_stage.in_(("weaner", "grower"))),
                         "Active weaners and growers."),
        "kits": _fact(await _count(*active, Rabbit.lifecycle_stage == "kit"), "Active kits."),
        "retired": _fact(await _count(*active, Rabbit.lifecycle_stage == "retired"), "Active retired stock."),
        "sold": _fact(await _count(Rabbit.status == "sold"), "Rabbits ever sold."),
        "deceased": _fact(await _count(Rabbit.status == "deceased"), "Rabbits ever deceased."),
    }


# ── Window helpers (for forecasts) ─────────────────────────────────────────────

async def _window_sum(db, farm_id, model, value_col, date_col, since: date) -> tuple[float, int]:
    total = (await db.execute(
        select(func.coalesce(func.sum(value_col), 0)).where(
            model.farm_id == farm_id, model.deleted_at.is_(None), date_col >= since)
    )).scalar_one()
    count = (await db.execute(
        select(func.count(model.id)).where(
            model.farm_id == farm_id, model.deleted_at.is_(None), date_col >= since)
    )).scalar_one()
    return float(total or 0), int(count or 0)


async def _forecast_bundle(db, farm_id, *, horizon_days: int, window_days: int, housing: dict) -> dict:
    since = date.today() - timedelta(days=window_days)
    since_dt = datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc)

    feed_kg, feed_obs = await _window_sum(db, farm_id, RabbitFeedRecord,
                                          RabbitFeedRecord.quantity_kg, RabbitFeedRecord.fed_on, since)
    revenue, rev_obs = await _window_sum(db, farm_id, RabbitSale,
                                         RabbitSale.total_price, RabbitSale.sale_date, since)
    kits, litter_obs = await _window_sum(db, farm_id, RabbitLitter,
                                         RabbitLitter.live_kits, RabbitLitter.kindling_date, since)

    # Herd stock: current active count; net change = registrations − exits in window.
    current = (await db.execute(
        select(func.count(Rabbit.id)).where(
            Rabbit.farm_id == farm_id, Rabbit.status == "active", Rabbit.deleted_at.is_(None))
    )).scalar_one() or 0
    registrations = (await db.execute(
        select(func.count(Rabbit.id)).where(
            Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None), Rabbit.created_at >= since_dt)
    )).scalar_one() or 0
    sales_exits = (await db.execute(
        select(func.count(RabbitSale.id)).where(
            RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None),
            RabbitSale.rabbit_id.is_not(None), RabbitSale.sale_date >= since)
    )).scalar_one() or 0
    deaths_exits = (await db.execute(
        select(func.count(RabbitMortality.id)).where(
            RabbitMortality.farm_id == farm_id, RabbitMortality.deleted_at.is_(None),
            RabbitMortality.occurred_on >= since)
    )).scalar_one() or 0
    net_change = registrations - sales_exits - deaths_exits
    herd_obs = registrations + sales_exits + deaths_exits

    herd = forecast_eng.project_stock(current, net_change, window_days, horizon_days,
                                      observations=herd_obs, quantity="herd size", unit="rabbits")
    capacity_value = (housing.get("capacity", {}).get("capacity", {}) or {}).get("value")
    return {
        "herd_size": herd,
        "kits_produced": forecast_eng.project_flow(kits, window_days, horizon_days,
                                                   observations=litter_obs, quantity="live kits", unit="kits"),
        "feed_requirement_kg": forecast_eng.project_flow(feed_kg, window_days, horizon_days,
                                                         observations=feed_obs, quantity="feed", unit="kg"),
        "revenue": forecast_eng.project_flow(revenue, window_days, horizon_days,
                                             observations=rev_obs, quantity="sale revenue", unit="currency"),
        "housing_capacity": forecast_eng.capacity_requirement(
            herd["forecast"]["value"], capacity_value, horizon_days=horizon_days),
        "window_days": window_days,
    }


def _bottlenecks(*, reproduction: dict, health: dict, finance: dict, housing: dict) -> list[dict]:
    def _v(block, *keys):
        cur = block
        for k in keys:
            cur = (cur or {}).get(k, {})
        return cur.get("value") if isinstance(cur, dict) else None

    return bottleneck_eng.analyze(
        kindling_rate_pct=_v(reproduction, "kindling_rate_pct"),
        mortality_rate_pct=_v(health, "mortality_rate_pct"),
        weaning_survival_pct=_v(reproduction, "kit_survival_pct"),
        capacity_utilisation_pct=_v(housing, "capacity", "utilization_pct"),
        overcrowded_cages=len(housing.get("overcrowded_cages", [])),
        overdue_vaccinations=_v(health, "vaccination_compliance", "overdue"),
        gross_margin_pct=_v(finance, "pnl", "gross_margin_pct"),
    )


# ── Public API ─────────────────────────────────────────────────────────────────

async def executive_dashboard(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Recorded population facts + composed analytics + forecast + bottlenecks
    (Spec Part 5 §3, Part 7 §3). Every block is honesty-labelled by its source."""
    population = await _population_facts(db, farm_id)
    reproduction = await rabbit_breeding_service.reproduction_summary(db, farm_id)
    health = await rabbit_health_service.health_summary(db, farm_id)
    finance = await rabbit_finance_service.finance_summary(db, farm_id)
    housing = await rabbit_housing_service.housing_summary(db, farm_id)
    forecast = await _forecast_bundle(db, farm_id, horizon_days=30, window_days=30, housing=housing)
    bottlenecks = _bottlenecks(reproduction=reproduction, health=health, finance=finance, housing=housing)

    return {
        "recorded_facts": {"population": population},
        "reproduction": reproduction,
        "health": health,
        "finance": finance,
        "housing": housing,
        "forecast": forecast,
        "bottlenecks": bottlenecks,
    }


async def forecast(db: AsyncSession, farm_id: uuid.UUID, *, horizon_days: int = 90, window_days: int = 90) -> dict:
    housing = await rabbit_housing_service.housing_summary(db, farm_id)
    return await _forecast_bundle(db, farm_id, horizon_days=horizon_days, window_days=window_days, housing=housing)


async def bottlenecks(db: AsyncSession, farm_id: uuid.UUID) -> list[dict]:
    reproduction = await rabbit_breeding_service.reproduction_summary(db, farm_id)
    health = await rabbit_health_service.health_summary(db, farm_id)
    finance = await rabbit_finance_service.finance_summary(db, farm_id)
    housing = await rabbit_housing_service.housing_summary(db, farm_id)
    return _bottlenecks(reproduction=reproduction, health=health, finance=finance, housing=housing)


async def executive_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """A concise, deterministic executive summary (Spec Part 7 §12). Headline
    recorded/calculated figures + the top bottlenecks + a forecast highlight —
    no narrative generation (that is ARIA, a later milestone)."""
    dash = await executive_dashboard(db, farm_id)
    pnl = dash["finance"]["pnl"]
    return {
        "herd_size": dash["recorded_facts"]["population"]["total_rabbits"],
        "revenue": pnl["revenue"],
        "gross_profit": pnl["gross_profit"],
        "total_litters": dash["reproduction"]["total_litters"],
        "mortality_rate_pct": dash["health"]["mortality_rate_pct"],
        "herd_forecast_30d": dash["forecast"]["herd_size"]["forecast"],
        "top_bottlenecks": dash["bottlenecks"][:3],
        "disclaimer": "Recorded and calculated facts with clearly-labelled forecasts; "
                      "forecasts are projections, not guarantees.",
    }


async def export_herd_csv(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Herd inventory as CSV text (Spec Part 7 §13; reuses platform Response export)."""
    rows = (await db.execute(
        select(Rabbit).where(Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None))
        .order_by(Rabbit.internal_ref)
    )).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["internal_ref", "name", "ear_tag", "sex", "purpose",
                     "lifecycle_stage", "status", "date_of_birth", "current_weight_g"])
    for r in rows:
        writer.writerow([
            r.internal_ref, r.name or "", r.ear_tag or "", r.sex, r.purpose,
            r.lifecycle_stage, r.status,
            r.date_of_birth.isoformat() if r.date_of_birth else "",
            r.current_weight_g if r.current_weight_g is not None else "",
        ])
    return buf.getvalue()
