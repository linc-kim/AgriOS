"""
Greena — Small Ruminant Feed Service (Modules 18/19, Milestone 4)

Feeding log that **reuses the platform Inventory module**. When a feeding
references an Inventory feed item, the service posts a ``consumption`` movement
(decrement; no new expense — feed is expensed once at ``stock_in``) and snapshots
the movement's cost onto the feed record for cost analytics. Feeding without an
Inventory item is allowed for hobby-scale farms. All efficiency math is delegated
to the PURE :mod:`small_ruminant_feed_engine`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import SmallRuminantFeedRecord, SmallRuminantGroup
from app.schemas.inventory import MovementCreate
from app.schemas.small_ruminant import FeedRecordCreate
from app.services import audit_service, inventory_service
from app.services import small_ruminant_feed_engine as eng
from app.services import small_ruminant_growth_service
from app.services.small_ruminant_service import _append_event, _get_animal_or_404


async def record_feeding(db: AsyncSession, farm: Farm, species: str, data: FeedRecordCreate, user: User):
    if data.animal_id is not None:
        await _get_animal_or_404(db, farm.id, species, data.animal_id)
    if data.group_id is not None:
        exists = await db.execute(
            select(SmallRuminantGroup.id).where(
                SmallRuminantGroup.id == data.group_id, SmallRuminantGroup.farm_id == farm.id,
                SmallRuminantGroup.species == species, SmallRuminantGroup.deleted_at.is_(None),
            )
        )
        if exists.scalar_one_or_none() is None:
            raise NotFoundException(f"Group {data.group_id} not found on this farm.")

    cost = data.cost
    currency = data.currency
    movement_id: uuid.UUID | None = None

    if data.inventory_item_id is not None:
        item, movement = await inventory_service.record_movement(
            db, farm,
            MovementCreate(
                item_id=data.inventory_item_id, movement_type="consumption",
                quantity=data.quantity_kg, movement_date=data.fed_on,
                reason=f"{species.capitalize()} feeding",
                reference=str(data.animal_id or data.group_id or farm.id),
                notes=data.notes,
            ),
            user,
        )
        movement_id = movement.id
        if cost is None and movement.total_cost is not None:
            cost = movement.total_cost
        if currency is None:
            currency = getattr(item, "currency", None)

    record = SmallRuminantFeedRecord(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=data.animal_id, group_id=data.group_id,
        inventory_item_id=data.inventory_item_id, inventory_movement_id=movement_id,
        feed_type=data.feed_type, quantity_kg=data.quantity_kg, fed_on=data.fed_on,
        is_mineral=data.is_mineral, cost=cost, currency=currency, supplier=data.supplier,
        notes=data.notes, recorded_by=user.id,
    )
    db.add(record)
    await db.flush()

    if data.animal_id is not None:
        await _append_event(
            db, data.animal_id, "note", f"Fed {data.quantity_kg} kg {data.feed_type or ''}".strip(),
            occurred_at=datetime.combine(data.fed_on, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"quantity_kg": str(data.quantity_kg), "feed_type": data.feed_type},
        )
    await audit_service.log_action(
        db, action=f"sr.{species}.feed.record", resource_type="sr_feed_record",
        resource_id=record.id, farm_id=farm.id, user_id=user.id,
        new_value={"quantity_kg": str(data.quantity_kg), "inventory_linked": movement_id is not None},
    )
    await db.commit()
    await db.refresh(record)
    return record


async def list_feeding(db, farm_id, species, *, animal_id=None, group_id=None, limit=100, offset=0):
    conds = [SmallRuminantFeedRecord.farm_id == farm_id, SmallRuminantFeedRecord.species == species,
             SmallRuminantFeedRecord.deleted_at.is_(None)]
    if animal_id:
        conds.append(SmallRuminantFeedRecord.animal_id == animal_id)
    if group_id:
        conds.append(SmallRuminantFeedRecord.group_id == group_id)
    total = (await db.execute(select(func.count(SmallRuminantFeedRecord.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(SmallRuminantFeedRecord).where(*conds)
        .order_by(SmallRuminantFeedRecord.fed_on.desc(), SmallRuminantFeedRecord.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def feed_summary(db, farm_id, species, animal_id=None) -> dict:
    """Deterministic feed summary + FCR (animal-scoped when ``animal_id`` given).
    FCR needs a positive recorded weight gain for the animal, else unavailable."""
    conds = [SmallRuminantFeedRecord.farm_id == farm_id, SmallRuminantFeedRecord.species == species,
             SmallRuminantFeedRecord.deleted_at.is_(None)]
    if animal_id:
        await _get_animal_or_404(db, farm_id, species, animal_id)
        conds.append(SmallRuminantFeedRecord.animal_id == animal_id)
    rows = await db.execute(
        select(SmallRuminantFeedRecord.quantity_kg, SmallRuminantFeedRecord.cost).where(*conds)
    )
    records = [{"quantity_kg": r[0], "cost": r[1]} for r in rows]
    gain_kg = await small_ruminant_growth_service.latest_weight_gain_kg(db, animal_id) if animal_id else None
    summary = eng.feed_summary(records, weight_gain_kg=gain_kg)
    return {"animal_id": str(animal_id) if animal_id else None, "summary": summary}
