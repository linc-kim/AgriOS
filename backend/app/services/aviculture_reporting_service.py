"""
Greena — Aviculture Reporting Service (Module 15, Part 8)

Evidence-backed, computed-not-stored reports (Doc 09, Doc 05 §10). This service
does NOT recompute domain logic — it composes the existing deterministic engines
and services (aviary occupancy, incubation stats, health analytics, finance /
valuation) into a farm-level aviculture dashboard, a population forecast, and
exports. Every figure carries the honesty label its source engine assigned.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aviculture import (
    AviBird, AviBirdEvent, AviBreedingProgram, AviEgg, AviHatchEvent, AviIncubationBatch, AviPair,
)
from app.services import (
    analytics_engine, aviary_service, aviculture_finance_service, aviculture_health_service,
    incubation_engine,
)


async def _birds(db, farm_id, *, active_only=False) -> list[dict]:
    conds = [AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None)]
    if active_only:
        conds.append(AviBird.status == "active")
    rows = await db.execute(
        select(AviBird.id, AviBird.internal_ref, AviBird.name, AviBird.status, AviBird.sex,
               AviBird.lifecycle_stage, AviBird.species_id).where(*conds))
    return [{"id": r[0], "internal_ref": r[1], "name": r[2], "status": r[3], "sex": r[4],
             "lifecycle_stage": r[5], "species_id": r[6]} for r in rows]


async def _species_names(db, species_ids) -> dict:
    from app.models.aviculture import AviSpecies
    if not species_ids:
        return {}
    rows = await db.execute(select(AviSpecies.id, AviSpecies.common_name).where(AviSpecies.id.in_(species_ids)))
    return {r[0]: r[1] for r in rows}


async def dashboard(db: AsyncSession, farm) -> dict:
    """Compose the aviculture dashboard from the existing engines/services."""
    birds = await _birds(db, farm.id)
    names = await _species_names(db, {b["species_id"] for b in birds if b["species_id"]})
    for b in birds:
        b["species_name"] = names.get(b["species_id"], "unknown")
    composition = analytics_engine.collection_composition(birds)

    infrastructure = await aviary_service.infrastructure_summary(db, farm.id)

    active_pairs = (await db.execute(select(func.count(AviPair.id)).where(
        AviPair.farm_id == farm.id, AviPair.status == "active", AviPair.deleted_at.is_(None)))).scalar_one()
    programs = (await db.execute(select(func.count(AviBreedingProgram.id)).where(
        AviBreedingProgram.farm_id == farm.id, AviBreedingProgram.status == "active",
        AviBreedingProgram.deleted_at.is_(None)))).scalar_one()

    active_batches = (await db.execute(select(func.count(AviIncubationBatch.id)).where(
        AviIncubationBatch.farm_id == farm.id,
        AviIncubationBatch.status.in_(("setting", "incubating", "lockdown")),
        AviIncubationBatch.deleted_at.is_(None)))).scalar_one()
    egg_rows = await db.execute(
        select(AviEgg.status, AviEgg.fertility_status).where(
            AviEgg.farm_id == farm.id, AviEgg.deleted_at.is_(None)))
    hatch_stats = incubation_engine.hatch_statistics(
        [{"status": s, "fertility_status": f} for s, f in egg_rows])

    health = await aviculture_health_service.health_summary(db, farm.id)
    finance = await aviculture_finance_service.finance_summary(db, farm.id)

    return {
        "collection": composition,
        "infrastructure": infrastructure,
        "breeding": {"active_pairs": active_pairs, "active_programs": programs},
        "incubation": {"active_batches": active_batches, "statistics": hatch_stats},
        "health": health,
        "finance": finance,
    }


async def population_forecast(db: AsyncSession, farm, *, horizon_days: int = 90, window_days: int = 90) -> dict:
    """Deterministic population forecast from recorded births (hatches) and deaths."""
    since = date.today() - timedelta(days=window_days)
    current_active = (await db.execute(select(func.count(AviBird.id)).where(
        AviBird.farm_id == farm.id, AviBird.status == "active", AviBird.deleted_at.is_(None)))).scalar_one()

    births = (await db.execute(
        select(func.count(AviHatchEvent.id)).select_from(AviHatchEvent)
        .join(AviEgg, AviEgg.id == AviHatchEvent.egg_id)
        .where(AviEgg.farm_id == farm.id, AviHatchEvent.outcome.in_(("hatched", "assisted")),
               AviHatchEvent.hatched_on >= since, AviHatchEvent.deleted_at.is_(None)))).scalar_one()

    deaths = (await db.execute(
        select(func.count(AviBirdEvent.id)).select_from(AviBirdEvent)
        .join(AviBird, AviBird.id == AviBirdEvent.bird_id)
        .where(AviBird.farm_id == farm.id, AviBirdEvent.event_type == "died",
               AviBirdEvent.occurred_on >= since, AviBirdEvent.deleted_at.is_(None)))).scalar_one()

    return analytics_engine.population_forecast(
        current_active=current_active, births_in_window=births, deaths_in_window=deaths,
        window_days=window_days, horizon_days=horizon_days)


async def export_collection_rows(db: AsyncSession, farm) -> list[dict]:
    """Flat rows for CSV/JSON export of the collection (evidence, not analysis)."""
    birds = await _birds(db, farm.id)
    names = await _species_names(db, {b["species_id"] for b in birds if b["species_id"]})
    rows = []
    for b in birds:
        rows.append({
            "reference": b["internal_ref"], "name": b["name"] or "",
            "species": names.get(b["species_id"], ""), "sex": b["sex"],
            "lifecycle_stage": b["lifecycle_stage"], "status": b["status"],
        })
    rows.sort(key=lambda r: r["reference"])
    return rows
