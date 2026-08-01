"""
Greena — Rabbit Growth Metric Provider (Module 17, Milestone 8)

Supplies the Growth Planner's "actual" values for rabbit goals from **recorded
operational facts only** (ledger CON-M8-1). Registered with the platform
``growth_planner_service`` under module ``'rabbit'``; an unknown metric key returns
``None`` (the planner engine then reports ``unknown`` — never invented).

Supported metric keys:
  herd_size        — current active rabbits
  breeding_does    — current active does
  monthly_kits     — live kits from litters kindled in the last 30 days
  total_kits       — cumulative live kits
  monthly_litters  — litters kindled in the last 30 days
  monthly_revenue  — recorded sale revenue in the last 30 days
  total_revenue    — cumulative recorded sale revenue
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rabbit import Rabbit, RabbitLitter, RabbitSale
from app.services import growth_planner_service

_WINDOW_DAYS = 30


async def _sum(db, column, *filters) -> float:
    return float((await db.execute(select(func.coalesce(func.sum(column), 0)).where(*filters))).scalar_one() or 0)


async def _count(db, model, *filters) -> float:
    return float((await db.execute(select(func.count(model.id)).where(*filters))).scalar_one() or 0)


async def provide(db: AsyncSession, farm_id: uuid.UUID, metric_key: str) -> float | None:
    """Return the recorded actual for a rabbit metric, or None if unsupported."""
    since = date.today() - timedelta(days=_WINDOW_DAYS)

    if metric_key == "herd_size":
        return await _count(db, Rabbit, Rabbit.farm_id == farm_id,
                            Rabbit.status == "active", Rabbit.deleted_at.is_(None))
    if metric_key == "breeding_does":
        return await _count(db, Rabbit, Rabbit.farm_id == farm_id, Rabbit.status == "active",
                            Rabbit.sex == "doe", Rabbit.deleted_at.is_(None))
    if metric_key == "monthly_kits":
        return await _sum(db, RabbitLitter.live_kits, RabbitLitter.farm_id == farm_id,
                          RabbitLitter.deleted_at.is_(None), RabbitLitter.kindling_date >= since)
    if metric_key == "total_kits":
        return await _sum(db, RabbitLitter.live_kits, RabbitLitter.farm_id == farm_id,
                          RabbitLitter.deleted_at.is_(None))
    if metric_key == "monthly_litters":
        return await _count(db, RabbitLitter, RabbitLitter.farm_id == farm_id,
                            RabbitLitter.deleted_at.is_(None), RabbitLitter.kindling_date >= since)
    if metric_key == "monthly_revenue":
        return await _sum(db, RabbitSale.total_price, RabbitSale.farm_id == farm_id,
                          RabbitSale.deleted_at.is_(None), RabbitSale.sale_date >= since)
    if metric_key == "total_revenue":
        return await _sum(db, RabbitSale.total_price, RabbitSale.farm_id == farm_id,
                          RabbitSale.deleted_at.is_(None))
    return None


# Register at import time (the rabbit growth-planner endpoint imports this module).
growth_planner_service.register_metric_provider("rabbit", provide)
