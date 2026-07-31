"""
Greena — BSF Harvest & Frass Service (Module 16, Part 4)

Owns writes for harvest events and frass production (Spec Part 2 §11-12, Part 3
§15-16). Deterministic maths is delegated to the pure
:mod:`bsf_harvest_engine` / :mod:`bsf_frass_engine`.

Cross-module integration (see docs/MODULE_16_BSF_LEDGER.md → Integration Contract):
  * Inventory — harvested/frass output optionally enters the platform Inventory
    module via ``inventory_service.record_movement`` with ``movement_type=
    "adjustment"`` (an inbound type that books NO purchase expense — harvest is
    produced output, not a purchase). BSF stores only a soft reference
    (``inventory_movement_id``) and never a parallel stock table.
  * Finance — harvest revenue is a RECORDED FACT on the harvest row
    (``revenue_amount``), because the platform revenue ledger is flock-scoped.
    No ``revenue_records`` row and no expense are written here.
Idempotency: the BSF harvest/frass record is the key — a movement is created at
most once per record (only when an item is supplied and no movement is linked yet).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.bsf import (
    BsfBatch,
    BsfBatchEvent,
    BsfFrassProduction,
    BsfHarvestEvent,
)
from app.models.farm import Farm
from app.schemas.bsf import FrassProductionCreate, HarvestEventCreate
from app.schemas.inventory import MovementCreate
from app.services import audit_service, inventory_service
from app.services import bsf_harvest_engine as harvest_eng

_TERMINAL_STATUSES = ("harvested", "completed", "split", "merged", "terminated", "archived")


async def _get_batch_or_404(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> BsfBatch:
    result = await db.execute(
        select(BsfBatch).where(
            BsfBatch.id == batch_id, BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None),
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(f"Batch {batch_id} not found on this farm.")
    return batch


def _append_event(db: AsyncSession, batch_id: uuid.UUID, summary: str, details: dict,
                  operator_id: uuid.UUID | None) -> None:
    db.add(BsfBatchEvent(
        id=uuid.uuid4(), batch_id=batch_id, event_type="note",
        occurred_at=datetime.now(timezone.utc), summary=summary, details=details,
        operator_id=operator_id,
    ))


async def _route_to_inventory(
    db: AsyncSession, farm: Farm, user: User, *,
    item_id: uuid.UUID, quantity_kg: Decimal, reference: str, reason: str,
) -> uuid.UUID:
    """Add produced output to platform Inventory as an inbound adjustment.

    Reuses ``inventory_service.record_movement`` unchanged. ``adjustment`` is an
    inbound movement type that books NO expense (unlike ``stock_in``) — harvest is
    output, not a purchase. Returns the movement id.
    """
    _, move = await inventory_service.record_movement(
        db, farm,
        MovementCreate(
            item_id=item_id,
            movement_type="adjustment",
            quantity=quantity_kg,
            reason=reason,
            reference=reference,
        ),
        user,
    )
    return move.id


# ── Harvest ───────────────────────────────────────────────────────────────────

async def record_harvest(
    db: AsyncSession, farm: Farm, batch_id: uuid.UUID, data: HarvestEventCreate, user: User,
) -> BsfHarvestEvent:
    batch = await _get_batch_or_404(db, farm.id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {batch.batch_number} is {batch.status}; it cannot be harvested.")

    check = harvest_eng.validate_harvest_quantity(
        data.quantity_kg, batch.biomass_estimate_g, is_complete=data.is_complete,
    )
    if not check["valid"]:
        raise ValidationException(check["reason"])

    harvested_on = data.harvested_on or date.today()
    harvest = BsfHarvestEvent(
        id=uuid.uuid4(),
        farm_id=farm.id,
        batch_id=batch_id,
        harvest_type=data.harvest_type,
        is_complete=data.is_complete,
        harvested_on=harvested_on,
        quantity_kg=data.quantity_kg,
        population_estimate=data.population_estimate,
        quality_grade=data.quality_grade,
        destination=data.destination,
        revenue_amount=data.revenue_amount,
        unit_price=data.unit_price,
        currency=data.currency,
        buyer_name=data.buyer_name,
        inventory_item_id=data.inventory_item_id,
        observations=data.observations,
        operator_id=user.id,
    )
    db.add(harvest)
    await db.flush()

    # Reduce the batch's recorded biomass by what was taken (partial); complete
    # harvest closes the batch.
    if batch.biomass_estimate_g is not None:
        remaining = Decimal(batch.biomass_estimate_g) - (Decimal(data.quantity_kg) * Decimal(1000))
        batch.biomass_estimate_g = max(Decimal(0), remaining)
    if data.is_complete:
        batch.status = "harvested"
        batch.completed_on = harvested_on

    _append_event(
        db, batch_id,
        f"Harvested {data.quantity_kg}kg ({data.harvest_type}){' — complete' if data.is_complete else ''}.",
        {"kind": "harvest", "quantity_kg": str(data.quantity_kg), "type": data.harvest_type,
         "is_complete": data.is_complete}, user.id,
    )
    await audit_service.log_action(
        db, action="bsf.harvest.record", resource_type="bsf_harvest_event",
        resource_id=harvest.id, farm_id=farm.id, user_id=user.id,
        new_value={"batch": batch.batch_number, "quantity_kg": str(data.quantity_kg),
                   "revenue": str(data.revenue_amount) if data.revenue_amount else None},
    )

    # Optional Inventory reuse — add the harvested stock (once).
    if data.inventory_item_id is not None:
        move_id = await _route_to_inventory(
            db, farm, user, item_id=data.inventory_item_id, quantity_kg=Decimal(data.quantity_kg),
            reference=batch.batch_number, reason=f"BSF harvest ({data.harvest_type})",
        )
        harvest.inventory_movement_id = move_id

    await db.commit()
    await db.refresh(harvest)
    return harvest


async def list_harvests(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> list[BsfHarvestEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfHarvestEvent)
        .where(BsfHarvestEvent.batch_id == batch_id, BsfHarvestEvent.deleted_at.is_(None))
        .order_by(BsfHarvestEvent.harvested_on.desc(), BsfHarvestEvent.created_at.desc())
    )).scalars().all()
    return list(rows)


async def harvest_readiness(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> dict:
    """Deterministic harvest-readiness signal + recorded totals for a batch."""
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    total_kg = (await db.execute(
        select(func.coalesce(func.sum(BsfHarvestEvent.quantity_kg), 0))
        .where(BsfHarvestEvent.batch_id == batch_id, BsfHarvestEvent.deleted_at.is_(None))
    )).scalar_one()
    return {
        "batch_id": str(batch_id),
        "lifecycle_stage": batch.lifecycle_stage,
        "readiness": harvest_eng.harvest_readiness(batch.lifecycle_stage),
        "total_harvested_kg": {"label": "recorded", "value": float(total_kg),
                               "detail": "Sum of recorded harvests for this batch."},
    }


# ── Frass ─────────────────────────────────────────────────────────────────────

async def record_frass(
    db: AsyncSession, farm: Farm, batch_id: uuid.UUID, data: FrassProductionCreate, user: User,
) -> BsfFrassProduction:
    batch = await _get_batch_or_404(db, farm.id, batch_id)
    if data.weight_kg <= 0:
        raise ValidationException("Frass weight must be greater than zero.")

    frass = BsfFrassProduction(
        id=uuid.uuid4(),
        farm_id=farm.id,
        batch_id=batch_id,
        collected_on=data.collected_on or date.today(),
        weight_kg=data.weight_kg,
        moisture_pct=data.moisture_pct,
        quality=data.quality,
        storage_location=data.storage_location,
        inventory_item_id=data.inventory_item_id,
        notes=data.notes,
        operator_id=user.id,
    )
    db.add(frass)
    await db.flush()
    _append_event(
        db, batch_id, f"Collected {data.weight_kg}kg frass.",
        {"kind": "frass", "weight_kg": str(data.weight_kg)}, user.id,
    )
    await audit_service.log_action(
        db, action="bsf.frass.record", resource_type="bsf_frass_production",
        resource_id=frass.id, farm_id=farm.id, user_id=user.id,
        new_value={"batch": batch.batch_number, "weight_kg": str(data.weight_kg)},
    )
    if data.inventory_item_id is not None:
        move_id = await _route_to_inventory(
            db, farm, user, item_id=data.inventory_item_id, quantity_kg=Decimal(data.weight_kg),
            reference=batch.batch_number, reason="BSF frass collection",
        )
        frass.inventory_movement_id = move_id

    await db.commit()
    await db.refresh(frass)
    return frass


async def list_frass(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> list[BsfFrassProduction]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfFrassProduction)
        .where(BsfFrassProduction.batch_id == batch_id, BsfFrassProduction.deleted_at.is_(None))
        .order_by(BsfFrassProduction.collected_on.desc(), BsfFrassProduction.created_at.desc())
    )).scalars().all()
    return list(rows)
