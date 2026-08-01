"""
Greena — Rabbit Feed Service (Module 17, Milestone 4)

Feeding log that **reuses the platform Inventory module** (ledger CON-M4-1). When
a feeding references an Inventory feed item, the service posts a ``consumption``
movement (decrement; no new expense — feed is expensed once at ``stock_in``) and
snapshots the movement's cost onto the feed record for cost analytics. Feeding
without an Inventory item is allowed for hobby-scale farms (CON-M4-2). All
efficiency math is delegated to the PURE :mod:`rabbit_feed_engine`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.rabbit import RabbitCage, RabbitFeedRecord
from app.schemas.inventory import MovementCreate
from app.schemas.rabbit import FeedRecordCreate
from app.services import (
    audit_service,
    inventory_service,
    rabbit_feed_engine as eng,
    rabbit_growth_service,
    rabbit_service,
)


async def record_feeding(db: AsyncSession, farm: Farm, data: FeedRecordCreate, user: User) -> RabbitFeedRecord:
    if data.rabbit_id is not None:
        await rabbit_service._get_rabbit_or_404(db, farm.id, data.rabbit_id)
    if data.cage_id is not None:
        exists = await db.execute(
            select(RabbitCage.id).where(
                RabbitCage.id == data.cage_id, RabbitCage.farm_id == farm.id, RabbitCage.deleted_at.is_(None)
            )
        )
        if exists.scalar_one_or_none() is None:
            raise NotFoundException(f"Cage {data.cage_id} not found on this farm.")

    cost = data.cost
    currency = data.currency
    movement_id: uuid.UUID | None = None

    # Inventory reuse: post a consumption movement (decrement stock; no new
    # expense — feed was expensed at purchase). Cost snapshot from the movement.
    if data.inventory_item_id is not None:
        try:
            item, movement = await inventory_service.record_movement(
                db, farm,
                MovementCreate(
                    item_id=data.inventory_item_id, movement_type="consumption",
                    quantity=data.quantity_kg, movement_date=data.fed_on,
                    reason="Rabbit feeding",
                    reference=str(data.rabbit_id or data.cage_id or farm.id),
                    notes=data.notes,
                ),
                user,
            )
        except ValidationException:
            raise
        movement_id = movement.id
        if cost is None and movement.total_cost is not None:
            cost = movement.total_cost
        if currency is None:
            currency = getattr(item, "currency", None)

    record = RabbitFeedRecord(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=data.rabbit_id, cage_id=data.cage_id,
        inventory_item_id=data.inventory_item_id, inventory_movement_id=movement_id,
        feed_type=data.feed_type, quantity_kg=data.quantity_kg, fed_on=data.fed_on,
        cost=cost, currency=currency, supplier=data.supplier, notes=data.notes, recorded_by=user.id,
    )
    db.add(record)
    await db.flush()

    if data.rabbit_id is not None:
        await rabbit_service._append_event(
            db, data.rabbit_id, "note", f"Fed {data.quantity_kg} kg",
            occurred_at=datetime.combine(data.fed_on, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"quantity_kg": str(data.quantity_kg), "feed_type": data.feed_type},
        )
    await audit_service.log_action(
        db, action="rabbit.feed.record", resource_type="rabbit_feed_record",
        resource_id=record.id, farm_id=farm.id, user_id=user.id,
        new_value={"quantity_kg": str(data.quantity_kg), "inventory_linked": movement_id is not None},
    )
    await db.commit()
    await db.refresh(record)
    return record


async def list_feeding(
    db: AsyncSession, farm_id: uuid.UUID, *, rabbit_id=None, cage_id=None, limit=100, offset=0
) -> tuple[list[RabbitFeedRecord], int]:
    conds = [RabbitFeedRecord.farm_id == farm_id, RabbitFeedRecord.deleted_at.is_(None)]
    if rabbit_id:
        conds.append(RabbitFeedRecord.rabbit_id == rabbit_id)
    if cage_id:
        conds.append(RabbitFeedRecord.cage_id == cage_id)
    total = (await db.execute(select(func.count(RabbitFeedRecord.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(RabbitFeedRecord).where(*conds)
        .order_by(RabbitFeedRecord.fed_on.desc(), RabbitFeedRecord.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def feed_summary(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID | None = None) -> dict:
    """Deterministic feed summary + FCR (rabbit-scoped when ``rabbit_id`` given).
    FCR needs a positive recorded weight gain for the rabbit, else unavailable."""
    conds = [RabbitFeedRecord.farm_id == farm_id, RabbitFeedRecord.deleted_at.is_(None)]
    if rabbit_id:
        await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
        conds.append(RabbitFeedRecord.rabbit_id == rabbit_id)
    rows = await db.execute(
        select(RabbitFeedRecord.quantity_kg, RabbitFeedRecord.cost, RabbitFeedRecord.fed_on).where(*conds)
    )
    records = [{"quantity_kg": r[0], "cost": r[1], "fed_on": r[2]} for r in rows]

    gain_g = await rabbit_growth_service.latest_weight_gain_g(db, rabbit_id) if rabbit_id else None
    summary = eng.feed_summary(records, weight_gain_g=gain_g)
    return {"rabbit_id": str(rabbit_id) if rabbit_id else None, "summary": summary}
