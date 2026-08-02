"""
Greena — Small Ruminant Growth Metric Providers (Modules 18/19, Milestone 10)

Supplies the platform Growth Planner's "actual" values for goat and sheep goals
from **recorded operational facts only**. Two providers are registered with the
platform ``growth_planner_service`` — one per species-module ('goat' and 'sheep')
— so each workspace's plans track its own recorded actuals. An unknown metric key
returns ``None`` (the planner then reports ``unknown`` — never invented). No module
planner is built; the platform planner + versioning are reused.

Supported metric keys (per species):
  herd_size          — current active animals
  breeding_females   — current active does / ewes
  monthly_offspring  — live offspring born in the last 30 days
  total_offspring    — cumulative live offspring
  monthly_births     — birth events in the last 30 days
  monthly_revenue    — recorded sale revenue in the last 30 days
  total_revenue      — cumulative recorded sale revenue
  monthly_milk_litres — recorded milk in the last 30 days (dairy species)
  total_wool_kg      — cumulative recorded greasy fleece (wool species)
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantBirth,
    SmallRuminantFleece,
    SmallRuminantMilkRecord,
    SmallRuminantSale,
)
from app.services import growth_planner_service
from app.services import small_ruminant_species_config as cfg

_WINDOW_DAYS = 30


async def _sum(db, column, *filters) -> float:
    return float((await db.execute(select(func.coalesce(func.sum(column), 0)).where(*filters))).scalar_one() or 0)


async def _count(db, model, *filters) -> float:
    return float((await db.execute(select(func.count(model.id)).where(*filters))).scalar_one() or 0)


async def _provide(db: AsyncSession, farm_id: uuid.UUID, metric_key: str, species: str) -> float | None:
    since = date.today() - timedelta(days=_WINDOW_DAYS)
    female = cfg.get_config(species)["female_term"]

    if metric_key == "herd_size":
        return await _count(db, SmallRuminant, SmallRuminant.farm_id == farm_id,
                            SmallRuminant.species == species, SmallRuminant.status == "active",
                            SmallRuminant.deleted_at.is_(None))
    if metric_key == "breeding_females":
        return await _count(db, SmallRuminant, SmallRuminant.farm_id == farm_id,
                            SmallRuminant.species == species, SmallRuminant.status == "active",
                            SmallRuminant.sex == female, SmallRuminant.deleted_at.is_(None))
    if metric_key == "monthly_offspring":
        return await _sum(db, SmallRuminantBirth.live_born, SmallRuminantBirth.farm_id == farm_id,
                          SmallRuminantBirth.species == species, SmallRuminantBirth.deleted_at.is_(None),
                          SmallRuminantBirth.birth_date >= since)
    if metric_key == "total_offspring":
        return await _sum(db, SmallRuminantBirth.live_born, SmallRuminantBirth.farm_id == farm_id,
                          SmallRuminantBirth.species == species, SmallRuminantBirth.deleted_at.is_(None))
    if metric_key == "monthly_births":
        return await _count(db, SmallRuminantBirth, SmallRuminantBirth.farm_id == farm_id,
                            SmallRuminantBirth.species == species, SmallRuminantBirth.deleted_at.is_(None),
                            SmallRuminantBirth.birth_date >= since)
    if metric_key == "monthly_revenue":
        return await _sum(db, SmallRuminantSale.total_price, SmallRuminantSale.farm_id == farm_id,
                          SmallRuminantSale.species == species, SmallRuminantSale.deleted_at.is_(None),
                          SmallRuminantSale.sale_date >= since)
    if metric_key == "total_revenue":
        return await _sum(db, SmallRuminantSale.total_price, SmallRuminantSale.farm_id == farm_id,
                          SmallRuminantSale.species == species, SmallRuminantSale.deleted_at.is_(None))
    if metric_key == "monthly_milk_litres" and cfg.produces_milk(species):
        return await _sum(db, SmallRuminantMilkRecord.quantity_liters,
                          SmallRuminantMilkRecord.farm_id == farm_id,
                          SmallRuminantMilkRecord.species == species,
                          SmallRuminantMilkRecord.deleted_at.is_(None),
                          SmallRuminantMilkRecord.recorded_on >= since)
    if metric_key == "total_wool_kg" and cfg.produces_wool(species):
        return await _sum(db, SmallRuminantFleece.greasy_weight_kg,
                          SmallRuminantFleece.farm_id == farm_id, SmallRuminantFleece.species == species,
                          SmallRuminantFleece.deleted_at.is_(None))
    return None


def _make_provider(species: str):
    async def provide(db: AsyncSession, farm_id: uuid.UUID, metric_key: str) -> float | None:
        return await _provide(db, farm_id, metric_key, species)
    return provide


# Register one provider per species-module at import time.
for _species in cfg.SPECIES_VALUES:
    growth_planner_service.register_metric_provider(_species, _make_provider(_species))
