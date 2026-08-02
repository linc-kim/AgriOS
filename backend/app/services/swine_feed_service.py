"""
Greena — Swine Feed Service (Module 20, Milestone 5)

Feed catalog, feed plans by production stage, and a feeding log that **reuses the
platform Inventory module**. When a feeding references an Inventory feed item the
service posts a ``consumption`` movement (stock decrement; no new expense — feed is
expensed once at ``stock_in``) and snapshots the movement's cost onto the feed record
for cost analytics. Feeding without an Inventory item is allowed for hobby-scale
farms. All efficiency math is delegated to the PURE :mod:`swine_feed_engine`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import SwineFeed, SwineFeedPlan, SwineFeedRecord, SwineGroup
from app.schemas.inventory import MovementCreate
from app.schemas.swine import (
    FeedCreate,
    FeedPlanCreate,
    FeedPlanUpdate,
    FeedRecordCreate,
    FeedUpdate,
)
from app.services import audit_service, inventory_service
from app.services import swine_feed_engine as eng
from app.services.swine_service import _append_event, _get_pig_or_404


# ── Feed catalog (data-driven, org-scoped) ─────────────────────────────────────

async def list_feeds(db, org_id: uuid.UUID | None) -> list[SwineFeed]:
    conds = [SwineFeed.deleted_at.is_(None)]
    if org_id is not None:
        conds.append(or_(SwineFeed.organization_id.is_(None), SwineFeed.organization_id == org_id))
    else:
        conds.append(SwineFeed.organization_id.is_(None))
    r = await db.execute(select(SwineFeed).where(*conds).order_by(SwineFeed.name))
    return list(r.scalars().all())


async def create_feed(db, org_id: uuid.UUID | None, data: FeedCreate, user: User) -> SwineFeed:
    feed = SwineFeed(
        id=uuid.uuid4(), organization_id=org_id, name=data.name, category=data.category,
        form=data.form, profile=data.profile, is_medicated=data.is_medicated,
        withdrawal_days=data.withdrawal_days, is_system=False, created_by=user.id,
    )
    db.add(feed)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.feed.create", resource_type="swine_feed",
        resource_id=feed.id, user_id=user.id, new_value={"name": feed.name})
    await db.commit()
    await db.refresh(feed)
    return feed


async def update_feed(db, org_id: uuid.UUID | None, feed_id: uuid.UUID, data: FeedUpdate, user: User) -> SwineFeed:
    r = await db.execute(select(SwineFeed).where(SwineFeed.id == feed_id, SwineFeed.deleted_at.is_(None)))
    feed = r.scalar_one_or_none()
    if feed is None:
        raise NotFoundException(f"Feed {feed_id} not found.")
    if feed.organization_id is None:
        raise ConflictException("System feeds cannot be edited.")
    if feed.organization_id != org_id:
        raise NotFoundException(f"Feed {feed_id} not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(feed, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.feed.update", resource_type="swine_feed",
        resource_id=feed.id, user_id=user.id)
    await db.commit()
    await db.refresh(feed)
    return feed


# ── Feed plans (by production stage) ───────────────────────────────────────────

async def list_plans(db, farm_id, plan_name: str | None = None) -> list[SwineFeedPlan]:
    conds = [SwineFeedPlan.farm_id == farm_id, SwineFeedPlan.deleted_at.is_(None)]
    if plan_name:
        conds.append(SwineFeedPlan.plan_name == plan_name)
    r = await db.execute(select(SwineFeedPlan).where(*conds)
                         .order_by(SwineFeedPlan.plan_name, SwineFeedPlan.age_start_days.asc().nulls_last()))
    return list(r.scalars().all())


async def create_plan_entry(db, farm: Farm, data: FeedPlanCreate, user: User) -> SwineFeedPlan:
    entry = SwineFeedPlan(
        id=uuid.uuid4(), farm_id=farm.id, plan_name=data.plan_name,
        production_stage=data.production_stage, phase_label=data.phase_label, feed_id=data.feed_id,
        daily_amount_kg=data.daily_amount_kg, age_start_days=data.age_start_days,
        age_end_days=data.age_end_days, target_weight_start_kg=data.target_weight_start_kg,
        target_weight_end_kg=data.target_weight_end_kg, notes=data.notes, created_by=user.id,
    )
    db.add(entry)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.feed_plan.create", resource_type="swine_feed_plan",
        resource_id=entry.id, farm_id=farm.id, user_id=user.id, new_value={"plan": data.plan_name})
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_plan_entry(db, farm_id, entry_id, data: FeedPlanUpdate, user: User) -> SwineFeedPlan:
    r = await db.execute(select(SwineFeedPlan).where(
        SwineFeedPlan.id == entry_id, SwineFeedPlan.farm_id == farm_id, SwineFeedPlan.deleted_at.is_(None)))
    entry = r.scalar_one_or_none()
    if entry is None:
        raise NotFoundException(f"Feed plan entry {entry_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.feed_plan.update", resource_type="swine_feed_plan",
        resource_id=entry.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(entry)
    return entry


# ── Feeding log (Inventory-integrated) ─────────────────────────────────────────

async def record_feeding(db: AsyncSession, farm: Farm, data: FeedRecordCreate, user: User):
    if data.pig_id is not None:
        await _get_pig_or_404(db, farm.id, data.pig_id)
    if data.group_id is not None:
        exists = await db.execute(select(SwineGroup.id).where(
            SwineGroup.id == data.group_id, SwineGroup.farm_id == farm.id, SwineGroup.deleted_at.is_(None)))
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
                quantity=data.quantity_kg, movement_date=data.fed_on, reason="Swine feeding",
                reference=str(data.pig_id or data.group_id or farm.id), notes=data.notes,
            ),
            user,
        )
        movement_id = movement.id
        if cost is None and movement.total_cost is not None:
            cost = movement.total_cost
        if currency is None:
            currency = getattr(item, "currency", None)

    record = SwineFeedRecord(
        id=uuid.uuid4(), farm_id=farm.id, pig_id=data.pig_id, group_id=data.group_id,
        feed_id=data.feed_id, inventory_item_id=data.inventory_item_id, inventory_movement_id=movement_id,
        feed_name=data.feed_name, quantity_kg=data.quantity_kg, fed_on=data.fed_on,
        cost=cost, currency=currency, supplier=data.supplier, notes=data.notes, recorded_by=user.id,
    )
    db.add(record)
    await db.flush()

    if data.pig_id is not None:
        await _append_event(
            db, data.pig_id, "feed_recorded", f"Fed {data.quantity_kg} kg {data.feed_name or ''}".strip(),
            occurred_at=datetime.combine(data.fed_on, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"quantity_kg": str(data.quantity_kg), "feed": data.feed_name})
    await audit_service.log_action(
        db, action="swine.feed.record", resource_type="swine_feed_record",
        resource_id=record.id, farm_id=farm.id, user_id=user.id,
        new_value={"quantity_kg": str(data.quantity_kg), "inventory_linked": movement_id is not None})
    await db.commit()
    await db.refresh(record)
    return record


async def list_feeding(db, farm_id, *, pig_id=None, group_id=None, limit=100, offset=0):
    conds = [SwineFeedRecord.farm_id == farm_id, SwineFeedRecord.deleted_at.is_(None)]
    if pig_id:
        conds.append(SwineFeedRecord.pig_id == pig_id)
    if group_id:
        conds.append(SwineFeedRecord.group_id == group_id)
    total = (await db.execute(select(func.count(SwineFeedRecord.id)).where(*conds))).scalar_one()
    r = await db.execute(select(SwineFeedRecord).where(*conds)
                         .order_by(SwineFeedRecord.fed_on.desc(), SwineFeedRecord.created_at.desc())
                         .limit(limit).offset(offset))
    return list(r.scalars().all()), total


async def feed_summary(db, farm_id, *, pig_id=None, group_id=None) -> dict:
    """Deterministic feed summary + FCR (FCR unavailable until weight is recorded in
    the Growth milestone)."""
    conds = [SwineFeedRecord.farm_id == farm_id, SwineFeedRecord.deleted_at.is_(None)]
    if pig_id:
        await _get_pig_or_404(db, farm_id, pig_id)
        conds.append(SwineFeedRecord.pig_id == pig_id)
    if group_id:
        conds.append(SwineFeedRecord.group_id == group_id)
    rows = await db.execute(select(SwineFeedRecord.quantity_kg, SwineFeedRecord.cost).where(*conds))
    records = [{"quantity_kg": r[0], "cost": r[1]} for r in rows]
    return {
        "pig_id": str(pig_id) if pig_id else None,
        "group_id": str(group_id) if group_id else None,
        "summary": eng.feed_summary(records),
    }
