"""
Greena — BSF Feedstock & Feeding Service (Module 16, Part 3)

Owns writes for feedstock lots and feeding events (Spec Part 2 §8-9, Part 3
§11-12). Feedstock is a first-class resource tracked as lots; a feeding event
consumes a quantity from a lot and is immutable. Feed-conversion metrics are
delegated to the pure :mod:`bsf_feed_conversion_engine`.

Farm-scoped, soft-delete, audit-logged. No calculations live here.
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
    BsfFeedingEvent,
    BsfFeedstockLot,
    BsfLifecycleEvent,
)
from app.schemas.bsf import (
    FeedingEventCreate,
    FeedstockLotCreate,
    FeedstockLotUpdate,
)
from app.services import audit_service
from app.services import bsf_feed_conversion_engine as fce

_TERMINAL_STATUSES = ("harvested", "completed", "split", "merged", "terminated", "archived")


# ── Feedstock lots ────────────────────────────────────────────────────────────

async def _get_lot_or_404(db: AsyncSession, farm_id: uuid.UUID, lot_id: uuid.UUID) -> BsfFeedstockLot:
    result = await db.execute(
        select(BsfFeedstockLot).where(
            BsfFeedstockLot.id == lot_id,
            BsfFeedstockLot.farm_id == farm_id,
            BsfFeedstockLot.deleted_at.is_(None),
        )
    )
    lot = result.scalar_one_or_none()
    if lot is None:
        raise NotFoundException(f"Feedstock lot {lot_id} not found on this farm.")
    return lot


async def list_feedstock_lots(
    db: AsyncSession, farm_id: uuid.UUID, status: str | None = None,
) -> list[BsfFeedstockLot]:
    stmt = select(BsfFeedstockLot).where(
        BsfFeedstockLot.farm_id == farm_id, BsfFeedstockLot.deleted_at.is_(None),
    )
    if status:
        stmt = stmt.where(BsfFeedstockLot.status == status)
    stmt = stmt.order_by(BsfFeedstockLot.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


async def create_feedstock_lot(
    db: AsyncSession, farm_id: uuid.UUID, data: FeedstockLotCreate, user: User
) -> BsfFeedstockLot:
    if data.code:
        dup = (await db.execute(select(func.count(BsfFeedstockLot.id)).where(
            BsfFeedstockLot.farm_id == farm_id, BsfFeedstockLot.code == data.code,
            BsfFeedstockLot.deleted_at.is_(None),
        ))).scalar_one()
        if dup > 0:
            raise ConflictException(f"Feedstock code {data.code!r} is already in use on this farm.")
    remaining = data.remaining_kg if data.remaining_kg is not None else data.weight_kg
    lot = BsfFeedstockLot(
        id=uuid.uuid4(),
        farm_id=farm_id,
        name=data.name,
        code=data.code,
        category=data.category,
        source=data.source,
        supplier=data.supplier,
        collection_date=data.collection_date,
        delivery_date=data.delivery_date,
        weight_kg=data.weight_kg,
        remaining_kg=remaining,
        moisture_pct=data.moisture_pct,
        quality=data.quality,
        storage_location=data.storage_location,
        cost=data.cost,
        currency=data.currency,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(lot)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.feedstock.create", resource_type="bsf_feedstock_lot",
        resource_id=lot.id, farm_id=farm_id, user_id=user.id,
        new_value={"name": lot.name, "weight_kg": str(lot.weight_kg)},
    )
    await db.commit()
    await db.refresh(lot)
    return lot


async def update_feedstock_lot(
    db: AsyncSession, farm_id: uuid.UUID, lot_id: uuid.UUID,
    data: FeedstockLotUpdate, user: User,
) -> BsfFeedstockLot:
    lot = await _get_lot_or_404(db, farm_id, lot_id)
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(lot, key, value)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.feedstock.update", resource_type="bsf_feedstock_lot",
        resource_id=lot.id, farm_id=farm_id, user_id=user.id,
        new_value={k: str(v) for k, v in fields.items()},
    )
    await db.commit()
    await db.refresh(lot)
    return lot


async def get_feedstock_lot(db: AsyncSession, farm_id: uuid.UUID, lot_id: uuid.UUID) -> BsfFeedstockLot:
    return await _get_lot_or_404(db, farm_id, lot_id)


# ── Feeding events (immutable; consume a lot) ─────────────────────────────────

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


async def record_feeding(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
    data: FeedingEventCreate, user: User,
) -> BsfFeedingEvent:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {batch.batch_number} is {batch.status}; it cannot be fed.")
    if data.quantity_kg <= 0:
        raise ValidationException("Feeding quantity must be greater than zero.")

    lot = None
    if data.feedstock_lot_id is not None:
        lot = await _get_lot_or_404(db, farm_id, data.feedstock_lot_id)
        if data.quantity_kg > lot.remaining_kg:
            raise ValidationException(
                f"Feeding {data.quantity_kg}kg exceeds the {lot.remaining_kg}kg remaining in lot "
                f"{lot.name!r}."
            )

    fed_on = data.fed_on or date.today()
    event = BsfFeedingEvent(
        id=uuid.uuid4(),
        batch_id=batch_id,
        feedstock_lot_id=data.feedstock_lot_id,
        quantity_kg=data.quantity_kg,
        feeding_method=data.feeding_method,
        fed_on=fed_on,
        observations=data.observations,
        operator_id=user.id,
    )
    db.add(event)

    if lot is not None:
        lot.remaining_kg = lot.remaining_kg - Decimal(data.quantity_kg)
        if lot.remaining_kg <= 0:
            lot.remaining_kg = Decimal(0)
            lot.status = "depleted"
        elif lot.status == "available":
            lot.status = "in_use"

    db.add(BsfBatchEvent(
        id=uuid.uuid4(), batch_id=batch_id, event_type="note",
        occurred_at=datetime.now(timezone.utc),
        summary=f"Fed {data.quantity_kg}kg ({data.feeding_method}).",
        details={"kind": "feeding", "quantity_kg": str(data.quantity_kg),
                 "feedstock_lot_id": str(data.feedstock_lot_id) if data.feedstock_lot_id else None},
        operator_id=user.id,
    ))
    await audit_service.log_action(
        db, action="bsf.feeding.record", resource_type="bsf_feeding_event",
        resource_id=event.id, farm_id=farm_id, user_id=user.id,
        new_value={"batch": batch.batch_number, "quantity_kg": str(data.quantity_kg)},
    )
    await db.commit()
    await db.refresh(event)
    return event


async def list_feeding_events(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
) -> list[BsfFeedingEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfFeedingEvent)
        .where(BsfFeedingEvent.batch_id == batch_id, BsfFeedingEvent.deleted_at.is_(None))
        .order_by(BsfFeedingEvent.fed_on.desc(), BsfFeedingEvent.created_at.desc())
    )).scalars().all()
    return list(rows)


# ── Feed conversion summary (composes the pure engine) ────────────────────────

async def feed_conversion_summary(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> dict:
    """Deterministic feed-conversion picture for a batch (Spec Part 4 §7).

    Feed consumed = sum of recorded feeding quantities; biomass gained = current
    biomass − initial recorded biomass (grams → kg). Honesty-labelled throughout.
    """
    batch = await _get_batch_or_404(db, farm_id, batch_id)

    total_feed_kg = (await db.execute(
        select(func.coalesce(func.sum(BsfFeedingEvent.quantity_kg), 0))
        .where(BsfFeedingEvent.batch_id == batch_id, BsfFeedingEvent.deleted_at.is_(None))
    )).scalar_one()
    feed_events = (await db.execute(
        select(func.count(BsfFeedingEvent.id))
        .where(BsfFeedingEvent.batch_id == batch_id, BsfFeedingEvent.deleted_at.is_(None))
    )).scalar_one()

    first = (await db.execute(
        select(BsfLifecycleEvent)
        .where(BsfLifecycleEvent.batch_id == batch_id, BsfLifecycleEvent.deleted_at.is_(None))
        .order_by(BsfLifecycleEvent.occurred_on, BsfLifecycleEvent.created_at)
        .limit(1)
    )).scalar_one_or_none()
    initial_g = first.biomass_estimate_g if first else None

    biomass_gained_kg = None
    if batch.biomass_estimate_g is not None and initial_g is not None:
        biomass_gained_kg = (Decimal(batch.biomass_estimate_g) - Decimal(initial_g)) / Decimal(1000)

    feed_consumed = total_feed_kg if feed_events else None
    summary = fce.conversion_summary(feed_consumed, biomass_gained_kg)
    summary["feed_events"] = {"label": "recorded", "value": int(feed_events), "detail": "Count of feeding events."}
    return summary
