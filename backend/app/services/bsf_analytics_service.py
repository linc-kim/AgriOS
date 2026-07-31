"""
Greena — BSF Analytics Service (Module 16, Part 5)

Composes recorded facts into farm-level analytics via the pure deterministic
engines. This milestone provides the sustainability view (Spec Part 4 §14, Part 7
§20); the executive/forecast/bottleneck dashboards follow in a later milestone.

No calculations live here — the service only reads stored facts and hands them to
the pure engines, which own the maths and the honesty labels.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bsf import BsfBatch, BsfFeedingEvent, BsfFrassProduction, BsfHarvestEvent
from app.services import bsf_sustainability_engine as sus_eng


async def sustainability_summary(db: AsyncSession, farm_id: uuid.UUID, carbon_factor=None) -> dict:
    """Farm-level sustainability metrics from recorded feeding/harvest/frass facts."""
    # Feed consumed = recorded feeding across the farm's batches.
    feed_consumed = (await db.execute(
        select(func.coalesce(func.sum(BsfFeedingEvent.quantity_kg), 0))
        .select_from(BsfFeedingEvent)
        .join(BsfBatch, BsfBatch.id == BsfFeedingEvent.batch_id)
        .where(BsfBatch.farm_id == farm_id, BsfFeedingEvent.deleted_at.is_(None))
    )).scalar_one()

    # Harvested animal biomass (larvae/prepupae/…) — frass harvests excluded.
    biomass = (await db.execute(
        select(func.coalesce(func.sum(BsfHarvestEvent.quantity_kg), 0))
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None),
               BsfHarvestEvent.harvest_type != "frass")
    )).scalar_one()

    # Frass = dedicated frass production + any frass-typed harvests.
    frass_production = (await db.execute(
        select(func.coalesce(func.sum(BsfFrassProduction.weight_kg), 0))
        .where(BsfFrassProduction.farm_id == farm_id, BsfFrassProduction.deleted_at.is_(None))
    )).scalar_one()
    frass_harvested = (await db.execute(
        select(func.coalesce(func.sum(BsfHarvestEvent.quantity_kg), 0))
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None),
               BsfHarvestEvent.harvest_type == "frass")
    )).scalar_one()
    frass = (frass_production or 0) + (frass_harvested or 0)

    return sus_eng.sustainability_summary(feed_consumed, biomass, frass, carbon_factor)
