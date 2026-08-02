"""
Greena — Small Ruminant Reporting Service (Modules 18/19, Milestone 9)

Composes the deterministic picture for a goat or sheep workspace. It COMPOSES the
existing milestone summaries (reproduction, health, housing, dairy, wool, finance)
and adds only a species population roll-up — it never re-implements another
module's math. The short-range forecast and bottleneck detection come from the
PURE M9 engines. Nothing is stored; everything is computed on demand from recorded
facts (mirrors the avi/bsf/rabbit reporting pattern). CSV export reuses the
platform ``Response`` pattern.
"""

import csv
import io
from datetime import date, timedelta

from sqlalchemy import func, select

from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantBirth,
    SmallRuminantMortality,
    SmallRuminantSale,
)
from app.services import small_ruminant_bottleneck_engine as bottleneck
from app.services import small_ruminant_breeding_service as breeding
from app.services import small_ruminant_dairy_service as dairy
from app.services import small_ruminant_feed_service as feed
from app.services import small_ruminant_finance_service as finance
from app.services import small_ruminant_forecast_engine as forecast
from app.services import small_ruminant_health_service as health
from app.services import small_ruminant_housing_service as housing
from app.services import small_ruminant_species_config as cfg
from app.services import small_ruminant_wool_service as wool


# ── Population roll-up (the only rebuilt aggregation) ──────────────────────────

async def _population(db, farm_id, species) -> dict:
    async def _group(col):
        rows = await db.execute(
            select(col, func.count(SmallRuminant.id)).where(
                SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
                SmallRuminant.deleted_at.is_(None),
            ).group_by(col)
        )
        return {k: v for k, v in rows}

    by_status = await _group(SmallRuminant.status)
    by_sex = await _group(SmallRuminant.sex)
    by_stage = await _group(SmallRuminant.lifecycle_stage)
    total = sum(by_status.values())
    active = by_status.get("active", 0)
    return {
        "total_ever": {"label": "recorded", "value": total},
        "active": {"label": "recorded", "value": active},
        "by_status": {k: {"label": "recorded", "value": v} for k, v in by_status.items()},
        "by_sex": {k: {"label": "recorded", "value": v} for k, v in by_sex.items()},
        "by_lifecycle_stage": {k: {"label": "recorded", "value": v} for k, v in by_stage.items()},
    }


# ── Forecast bundle (recent run-rates → the pure forecast engine) ──────────────

async def _forecast_bundle(db, farm_id, species, months: int, window_months: int = 6) -> dict:
    since = date.today() - timedelta(days=window_months * 30)

    async def _count(model, date_col, *extra):
        r = await db.execute(select(func.count(model.id)).where(
            model.farm_id == farm_id, model.species == species, model.deleted_at.is_(None),
            date_col >= since, *extra))
        return r.scalar_one() or 0

    active = (await db.execute(select(func.count(SmallRuminant.id)).where(
        SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
        SmallRuminant.status == "active", SmallRuminant.deleted_at.is_(None)))).scalar_one() or 0

    births_off = (await db.execute(select(func.coalesce(func.sum(SmallRuminantBirth.live_born), 0)).where(
        SmallRuminantBirth.farm_id == farm_id, SmallRuminantBirth.species == species,
        SmallRuminantBirth.deleted_at.is_(None), SmallRuminantBirth.birth_date >= since))).scalar_one() or 0
    deaths = await _count(SmallRuminantMortality, SmallRuminantMortality.occurred_on)
    sales = await _count(SmallRuminantSale, SmallRuminantSale.sale_date)

    monthly_births = births_off / window_months
    monthly_deaths = deaths / window_months
    monthly_sales = sales / window_months

    return {
        "window_months": window_months,
        "projection_months": months,
        "projected_head": forecast.project_stock(active, monthly_births, monthly_deaths, monthly_sales, months),
        "projected_offspring": forecast.project_flow(monthly_births, months, metric="offspring"),
    }


# ── Composed dashboards ────────────────────────────────────────────────────────

async def executive_dashboard(db, farm_id, species, forecast_months: int = 6) -> dict:
    population = await _population(db, farm_id, species)
    reproduction = await breeding.reproduction_summary(db, farm_id, species)
    health_summary = await health.health_summary(db, farm_id, species)
    housing_summary = await housing.housing_summary(db, farm_id, species)
    finance_summary = await finance.finance_summary(db, farm_id, species)
    feed_summary = (await feed.feed_summary(db, farm_id, species)).get("summary")

    dashboard = {
        "species": species,
        "workspace": cfg.get_config(species)["display_name"],
        "population": population,
        "reproduction": reproduction,
        "health": health_summary,
        "housing": housing_summary,
        "finance": finance_summary,
        "feed": feed_summary,
        "forecast": await _forecast_bundle(db, farm_id, species, forecast_months),
    }
    if cfg.produces_milk(species):
        dashboard["dairy"] = await dairy.dairy_summary(db, farm_id, species)
    if cfg.produces_wool(species):
        dashboard["wool"] = await wool.wool_summary(db, farm_id, species)

    dashboard["bottlenecks"] = bottleneck.analyze(
        reproduction=reproduction, health=health_summary, housing=housing_summary,
        feed=feed_summary, finance=finance_summary,
    )
    return dashboard


async def forecast_report(db, farm_id, species, months: int = 6) -> dict:
    return await _forecast_bundle(db, farm_id, species, months)


async def bottlenecks(db, farm_id, species) -> list[dict]:
    return bottleneck.analyze(
        reproduction=await breeding.reproduction_summary(db, farm_id, species),
        health=await health.health_summary(db, farm_id, species),
        housing=await housing.housing_summary(db, farm_id, species),
        feed=(await feed.feed_summary(db, farm_id, species)).get("summary"),
        finance=await finance.finance_summary(db, farm_id, species),
    )


# ── CSV export (reuse the platform Response pattern) ───────────────────────────

async def export_registry_csv(db, farm_id, species) -> str:
    rows = await db.execute(
        select(SmallRuminant).where(
            SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
            SmallRuminant.deleted_at.is_(None),
        ).order_by(SmallRuminant.internal_ref)
    )
    animals = list(rows.scalars().all())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["internal_ref", "name", "ear_tag", "species", "sex", "purpose", "breed_id",
                     "lifecycle_stage", "status", "reproductive_status", "date_of_birth",
                     "current_weight_kg", "sire_id", "dam_id"])
    for a in animals:
        writer.writerow([a.internal_ref, a.name or "", a.ear_tag or "", a.species, a.sex, a.purpose,
                         a.breed_id or "", a.lifecycle_stage, a.status, a.reproductive_status,
                         a.date_of_birth or "", a.current_weight_kg if a.current_weight_kg is not None else "",
                         a.sire_id or "", a.dam_id or ""])
    return buf.getvalue()
