"""
Greena — BSF Growth Metric Provider (Module 16)

Supplies the Growth Planner's "actual" values for BSF goals from **recorded
operational facts only** (Growth Planner Contract → planned-vs-actual). Registered
with the platform ``growth_planner_service`` under module ``'bsf'``; an unknown
metric key returns ``None`` (the engine then reports ``unknown`` — never invented).

Supported metric keys:
  monthly_harvest_kg   — harvest mass in the last 30 days
  total_harvest_kg     — cumulative harvest mass
  monthly_revenue      — recorded harvest revenue in the last 30 days
  total_revenue        — cumulative recorded harvest revenue
  active_biomass_g     — current biomass across active batches
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bsf import BsfBatch, BsfHarvestEvent
from app.services import growth_planner_service

_WINDOW_DAYS = 30


async def _sum(db, column, *filters) -> float:
    return float((await db.execute(select(func.coalesce(func.sum(column), 0)).where(*filters))).scalar_one() or 0)


async def provide(db: AsyncSession, farm_id: uuid.UUID, metric_key: str) -> float | None:
    """Return the recorded actual for a BSF metric, or None if unsupported."""
    not_deleted = BsfHarvestEvent.deleted_at.is_(None)
    farm = BsfHarvestEvent.farm_id == farm_id
    since = date.today() - timedelta(days=_WINDOW_DAYS)

    if metric_key == "monthly_harvest_kg":
        return await _sum(db, BsfHarvestEvent.quantity_kg, farm, not_deleted, BsfHarvestEvent.harvested_on >= since)
    if metric_key == "total_harvest_kg":
        return await _sum(db, BsfHarvestEvent.quantity_kg, farm, not_deleted)
    if metric_key == "monthly_revenue":
        return await _sum(db, BsfHarvestEvent.revenue_amount, farm, not_deleted, BsfHarvestEvent.harvested_on >= since)
    if metric_key == "total_revenue":
        return await _sum(db, BsfHarvestEvent.revenue_amount, farm, not_deleted)
    if metric_key == "active_biomass_g":
        return await _sum(db, BsfBatch.biomass_estimate_g,
                          BsfBatch.farm_id == farm_id, BsfBatch.status == "active", BsfBatch.deleted_at.is_(None))
    return None


# Register at import time (the bsf_growth endpoint imports this module).
growth_planner_service.register_metric_provider("bsf", provide)
