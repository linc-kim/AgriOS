"""
Greena — BSF Reporting Service (Module 16, Part 6)

Composes the deterministic engines and Part-5 services into the executive
dashboard, forecast bundle and CSV export (Spec Part 4 §16, Part 7 §11-19).

Per the Forecasting & Reporting Contract (see docs/MODULE_16_BSF_LEDGER.md):
  * it *composes* engine outputs — it never recalculates a figure an engine owns;
  * the dashboard exposes a ``recorded_facts`` block alongside the ``analytics``
    block so every derived figure traces back to stored rows;
  * forecasts are labelled ``forecast`` and never placed in a confirmed position;
  * it reuses the platform CSV ``Response`` export — no parallel reporting system.
"""

import csv
import io
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bsf import (
    BsfBatch,
    BsfFeedingEvent,
    BsfFeedstockLot,
    BsfFrassProduction,
    BsfHarvestEvent,
    BsfLifecycleEvent,
    BsfMortalityEvent,
)
from app.services import bsf_analytics_service, bsf_finance_service, growth_planner_service
from app.services import bsf_bottleneck_engine as bottleneck_eng
from app.services import bsf_feed_conversion_engine as fce
from app.services import bsf_forecast_engine as forecast_eng
from app.services import bsf_health_engine as health_eng
from app.services import bsf_production_engine as prod_eng
from app.services import bsf_score_engine as score_eng

_ACTIVE = "active"
_LBL_RECORDED = "recorded"


def _fact(value, detail: str) -> dict:
    return {"label": _LBL_RECORDED, "value": value, "detail": detail}


async def _facts(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Raw recorded facts, straight from stored rows (no derivation)."""
    total_batches = (await db.execute(select(func.count(BsfBatch.id)).where(
        BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None)))).scalar_one()
    active_batches = (await db.execute(select(func.count(BsfBatch.id)).where(
        BsfBatch.farm_id == farm_id, BsfBatch.status == _ACTIVE, BsfBatch.deleted_at.is_(None)))).scalar_one()
    active_biomass_g = (await db.execute(select(func.coalesce(func.sum(BsfBatch.biomass_estimate_g), 0)).where(
        BsfBatch.farm_id == farm_id, BsfBatch.status == _ACTIVE, BsfBatch.deleted_at.is_(None)))).scalar_one()
    active_population = (await db.execute(select(func.coalesce(func.sum(BsfBatch.population_estimate), 0)).where(
        BsfBatch.farm_id == farm_id, BsfBatch.status == _ACTIVE, BsfBatch.deleted_at.is_(None)))).scalar_one()

    # Initial population = sum of batch birth snapshots (previous_stage IS NULL).
    initial_population = (await db.execute(
        select(func.coalesce(func.sum(BsfLifecycleEvent.population_estimate), 0))
        .select_from(BsfLifecycleEvent).join(BsfBatch, BsfBatch.id == BsfLifecycleEvent.batch_id)
        .where(BsfBatch.farm_id == farm_id, BsfLifecycleEvent.previous_stage.is_(None),
               BsfLifecycleEvent.deleted_at.is_(None)))).scalar_one()

    total_harvest_kg = (await db.execute(select(func.coalesce(func.sum(BsfHarvestEvent.quantity_kg), 0)).where(
        BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None)))).scalar_one()
    total_revenue = (await db.execute(select(func.coalesce(func.sum(BsfHarvestEvent.revenue_amount), 0)).where(
        BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None)))).scalar_one()
    total_frass_kg = (await db.execute(select(func.coalesce(func.sum(BsfFrassProduction.weight_kg), 0)).where(
        BsfFrassProduction.farm_id == farm_id, BsfFrassProduction.deleted_at.is_(None)))).scalar_one()
    total_mortality = (await db.execute(select(func.coalesce(func.sum(BsfMortalityEvent.estimated_loss), 0)).where(
        BsfMortalityEvent.farm_id == farm_id, BsfMortalityEvent.deleted_at.is_(None)))).scalar_one()
    total_feed_kg = (await db.execute(
        select(func.coalesce(func.sum(BsfFeedingEvent.quantity_kg), 0))
        .select_from(BsfFeedingEvent).join(BsfBatch, BsfBatch.id == BsfFeedingEvent.batch_id)
        .where(BsfBatch.farm_id == farm_id, BsfFeedingEvent.deleted_at.is_(None)))).scalar_one()
    feedstock_available_kg = (await db.execute(
        select(func.coalesce(func.sum(BsfFeedstockLot.remaining_kg), 0)).where(
            BsfFeedstockLot.farm_id == farm_id, BsfFeedstockLot.deleted_at.is_(None),
            BsfFeedstockLot.status.in_(("available", "in_use"))))).scalar_one()

    return {
        "total_batches": int(total_batches), "active_batches": int(active_batches),
        "active_biomass_g": float(active_biomass_g or 0), "active_population": int(active_population or 0),
        "initial_population": int(initial_population or 0),
        "total_harvest_kg": float(total_harvest_kg or 0), "total_revenue": float(total_revenue or 0),
        "total_frass_kg": float(total_frass_kg or 0), "total_mortality": int(total_mortality or 0),
        "total_feed_kg": float(total_feed_kg or 0), "feedstock_available_kg": float(feedstock_available_kg or 0),
    }


async def _window_sum(db, farm_id, model, column, date_col, since: date, *, join_batch=False) -> tuple[float, int]:
    stmt = select(func.coalesce(func.sum(column), 0), func.count()).where(
        model.deleted_at.is_(None), date_col >= since)
    if join_batch:
        stmt = stmt.select_from(model).join(BsfBatch, BsfBatch.id == model.batch_id).where(BsfBatch.farm_id == farm_id)
    else:
        stmt = stmt.where(model.farm_id == farm_id)
    row = (await db.execute(stmt)).one()
    return float(row[0] or 0), int(row[1] or 0)


async def executive_dashboard(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Executive dashboard: recorded facts + derived analytics + scores + forecast
    + bottlenecks. Every derived figure traces to the facts block (Spec Part 7 §19)."""
    facts = await _facts(db, farm_id)

    # ── Derived analytics (composed from engines) ─────────────────────────────
    survival = prod_eng.survival_rate_pct(facts["initial_population"] or None, facts["active_population"] or None)
    capacity = prod_eng.capacity_utilisation_pct(facts["active_biomass_g"] or None, None)  # farm-wide capacity n/a
    fcr = fce.feed_conversion_ratio(facts["total_feed_kg"] or None, facts["total_harvest_kg"] or None)
    health = health_eng.health_summary(
        facts["total_mortality"] or None, facts["initial_population"] or None, [facts["total_mortality"]])
    finance = await bsf_finance_service.finance_summary(db, farm_id)
    sustainability = await bsf_analytics_service.sustainability_summary(db, farm_id)

    # ── Composite scores (calculated, bounded, unknown-safe) ──────────────────
    prod_score = score_eng.production_score(survival["value"], capacity["value"])
    fin_score = score_eng.financial_score(finance["gross_margin_pct"]["value"])
    sus_score = score_eng.sustainability_score(sustainability["waste_conversion_efficiency_pct"]["value"])
    hp_score = score_eng.health_score(health["mortality_rate_pct"]["value"])
    # Growth score from the primary growth plan's progress (recorded actuals), if any.
    growth_progress = await growth_planner_service.primary_overall_progress(db, farm_id, "bsf")
    growth_score = score_eng.growth_score(growth_progress)
    scores = {
        "production": prod_score, "financial": fin_score, "sustainability": sus_score,
        "health": hp_score, "growth": growth_score,
        "business_health": score_eng.business_health_score([prod_score, fin_score, sus_score, hp_score]),
    }

    # ── Forecast (30-day flow projections) — always labelled forecast ─────────
    forecast = await _forecast_bundle(db, farm_id, horizon_days=30, window_days=30)

    # ── Bottlenecks (ranked) ──────────────────────────────────────────────────
    bottlenecks = bottleneck_eng.analyze(
        survival_rate_pct=survival["value"], capacity_utilisation_pct=capacity["value"],
        feedstock_available_kg=facts["feedstock_available_kg"],
        feed_conversion_ratio=fcr["value"],
    )

    return {
        "recorded_facts": {
            "total_batches": _fact(facts["total_batches"], "Count of BSF batches."),
            "active_batches": _fact(facts["active_batches"], "Batches currently in production."),
            "active_biomass_g": _fact(facts["active_biomass_g"], "Recorded biomass in active batches."),
            "active_population": _fact(facts["active_population"], "Recorded population in active batches."),
            "initial_population": _fact(facts["initial_population"], "Sum of batch birth-population snapshots."),
            "total_harvest_kg": _fact(facts["total_harvest_kg"], "Sum of recorded harvests."),
            "total_revenue": _fact(facts["total_revenue"], "Sum of recorded harvest revenue facts."),
            "total_frass_kg": _fact(facts["total_frass_kg"], "Sum of recorded frass collections."),
            "total_feed_kg": _fact(facts["total_feed_kg"], "Sum of recorded feeding."),
            "total_mortality": _fact(facts["total_mortality"], "Sum of recorded mortality."),
            "feedstock_available_kg": _fact(facts["feedstock_available_kg"], "Remaining feedstock on hand."),
        },
        "analytics": {
            "production": {"survival_rate_pct": survival, "capacity_utilisation_pct": capacity,
                           "feed_conversion_ratio": fcr},
            "health": health, "finance": finance, "sustainability": sustainability,
        },
        "scores": scores,
        "forecast": forecast,
        "bottlenecks": bottlenecks,
        "top_bottleneck": bottleneck_eng.top_bottleneck(bottlenecks),
    }


async def _forecast_bundle(db, farm_id, *, horizon_days: int, window_days: int) -> dict:
    since = date.today() - timedelta(days=window_days)
    harvest_kg, harvest_n = await _window_sum(
        db, farm_id, BsfHarvestEvent, BsfHarvestEvent.quantity_kg, BsfHarvestEvent.harvested_on, since)
    revenue, revenue_n = await _window_sum(
        db, farm_id, BsfHarvestEvent, BsfHarvestEvent.revenue_amount, BsfHarvestEvent.harvested_on, since)
    feed_kg, feed_n = await _window_sum(
        db, farm_id, BsfFeedingEvent, BsfFeedingEvent.quantity_kg, BsfFeedingEvent.fed_on, since, join_batch=True)
    return {
        "window_days": window_days, "horizon_days": horizon_days,
        "harvest_kg": forecast_eng.project_flow(harvest_kg, window_days, horizon_days,
                                                observations=harvest_n, quantity="harvest", unit="kg"),
        "feed_requirement_kg": forecast_eng.project_flow(feed_kg, window_days, horizon_days,
                                                         observations=feed_n, quantity="feed use", unit="kg"),
        "revenue": forecast_eng.project_flow(revenue, window_days, horizon_days,
                                             observations=revenue_n, quantity="revenue", unit="currency"),
    }


async def forecast(db: AsyncSession, farm_id: uuid.UUID, *, horizon_days: int = 90, window_days: int = 90) -> dict:
    return await _forecast_bundle(db, farm_id, horizon_days=horizon_days, window_days=window_days)


async def export_production_rows(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Per-batch production summary as CSV text (reuses platform Response export)."""
    batches = (await db.execute(
        select(BsfBatch).where(BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None))
        .order_by(BsfBatch.batch_number))).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["batch_number", "batch_type", "lifecycle_stage", "status",
                     "population_estimate", "biomass_estimate_g", "started_on", "completed_on"])
    for b in batches:
        writer.writerow([
            b.batch_number, b.batch_type, b.lifecycle_stage, b.status,
            b.population_estimate if b.population_estimate is not None else "",
            b.biomass_estimate_g if b.biomass_estimate_g is not None else "",
            b.started_on.isoformat() if b.started_on else "",
            b.completed_on.isoformat() if b.completed_on else "",
        ])
    return buf.getvalue()
