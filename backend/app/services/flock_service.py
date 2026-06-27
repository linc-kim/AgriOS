"""
AGRIOS — Flock Service
Business logic for:
  - Flock creation with plan limit enforcement
  - Flock lifecycle state machine (active → sold | closed | culled)
  - One active flock per house (application-layer enforcement)
  - Daily log upsert (DB-06 Frozen: UNIQUE(flock_id, log_date))
  - Operational metrics computation (FCR, survival rate, mortality)
  - Production records (eggs)
  - Weigh-in records
  - Feed purchases
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    ConflictException,
    NotFoundException,
    PlanLimitException,
    ValidationException,
)
from app.models.auth import User
from app.models.farm import Farm, ProductionHouse, SubscriptionPlan
from app.models.flock import (
    DailyLog,
    FeedPurchase,
    Flock,
    ProductionRecord,
    WeighinRecord,
)
from app.schemas.flock import (
    DailyLogCorrect,
    DailyLogSubmit,
    FeedPurchaseCreate,
    FlockClose,
    FlockCreate,
    FlockMetrics,
    ProductionRecordSubmit,
    WeighinSubmit,
)
from app.services.farm_service import _check_limit


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_flock_or_404(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
) -> Flock:
    result = await db.execute(
        select(Flock).where(
            Flock.id == flock_id,
            Flock.farm_id == farm_id,
            Flock.deleted_at.is_(None),
        )
    )
    flock = result.scalar_one_or_none()
    if flock is None:
        raise NotFoundException(f"Flock {flock_id} not found on this farm.")
    return flock


async def _get_active_flock_count(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> int:
    result = await db.execute(
        select(func.count(Flock.id)).where(
            Flock.farm_id == farm_id,
            Flock.status == "active",
            Flock.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def _get_total_feed_for_flock(
    db: AsyncSession,
    flock_id: uuid.UUID,
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(DailyLog.feed_consumed_kg), 0)).where(
            DailyLog.flock_id == flock_id,
            DailyLog.deleted_at.is_(None),
        )
    )
    return Decimal(str(result.scalar_one()))


# ── Flock CRUD ────────────────────────────────────────────────────────────────

async def create_flock(
    db: AsyncSession,
    farm: Farm,
    data: FlockCreate,
    current_user: User,
) -> Flock:
    """
    Create a new flock with plan limit and house-occupancy checks.

    Guards:
    1. Plan limit: farm.plan.max_active_flocks
    2. House occupancy: one active flock per house
    3. House belongs to this farm
    """
    # Load plan for limit check
    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == farm.plan_id)
    )
    plan = plan_result.scalar_one()

    # Guard 1: plan limit
    active_count = await _get_active_flock_count(db, farm.id)
    _check_limit(active_count, plan.max_active_flocks, "active flocks")

    # Guard 2/3: house belongs to farm and is not occupied
    house_result = await db.execute(
        select(ProductionHouse).where(
            ProductionHouse.id == data.house_id,
            ProductionHouse.farm_id == farm.id,
            ProductionHouse.deleted_at.is_(None),
        )
    )
    house = house_result.scalar_one_or_none()
    if house is None:
        raise NotFoundException(
            f"Production house {data.house_id} not found on this farm."
        )
    if house.is_occupied:
        raise ConflictException(
            f"House '{house.name}' already has an active flock. "
            "Close the current flock before starting a new one."
        )

    expected_close = None
    if data.placement_date and data.expected_cycle_days:
        from datetime import timedelta
        expected_close = data.placement_date + timedelta(days=data.expected_cycle_days)

    flock = Flock(
        id=uuid.uuid4(),
        farm_id=farm.id,
        house_id=data.house_id,
        species_key=data.species_key,
        name=data.name,
        breed=data.breed,
        batch_number=data.batch_number,
        initial_count=data.initial_count,
        placement_date=data.placement_date,
        expected_cycle_days=data.expected_cycle_days,
        expected_close_date=expected_close,
        status="active",
        created_by=current_user.id,
    )
    db.add(flock)

    # Mark house as occupied
    house.current_flock_id = flock.id

    await db.commit()
    await db.refresh(flock)
    return flock


async def list_flocks(
    db: AsyncSession,
    farm_id: uuid.UUID,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Flock]:
    """List flocks for a farm, optionally filtered by status."""
    query = select(Flock).where(
        Flock.farm_id == farm_id,
        Flock.deleted_at.is_(None),
    )
    if status:
        query = query.where(Flock.status == status)
    query = query.order_by(Flock.placement_date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_flock_detail(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
) -> tuple[Flock, FlockMetrics]:
    """Fetch flock with computed operational metrics."""
    flock = await _get_flock_or_404(db, farm_id, flock_id)

    # Compute metrics from daily logs
    mortality_result = await db.execute(
        select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
            DailyLog.flock_id == flock_id,
            DailyLog.deleted_at.is_(None),
        )
    )
    total_mortality = int(mortality_result.scalar_one())

    total_feed_kg = await _get_total_feed_for_flock(db, flock_id)

    current_count = flock.initial_count - total_mortality
    survival_rate = (
        (current_count / flock.initial_count * 100) if flock.initial_count > 0 else 0.0
    )
    days_alive = (date.today() - flock.placement_date).days if flock.is_active else (
        (flock.close_date - flock.placement_date).days if flock.close_date else 0
    )

    # Latest weighin
    weighin_result = await db.execute(
        select(WeighinRecord)
        .where(
            WeighinRecord.flock_id == flock_id,
            WeighinRecord.deleted_at.is_(None),
        )
        .order_by(WeighinRecord.weighed_at.desc())
        .limit(1)
    )
    latest_weighin = weighin_result.scalar_one_or_none()

    latest_avg_weight = latest_weighin.average_weight_kg if latest_weighin else None
    total_biomass = latest_weighin.total_biomass_kg if latest_weighin else None
    fcr = latest_weighin.fcr_to_date if latest_weighin else None

    # Egg production (layer flocks)
    eggs_result = await db.execute(
        select(func.coalesce(func.sum(ProductionRecord.eggs_collected), 0)).where(
            ProductionRecord.flock_id == flock_id,
            ProductionRecord.deleted_at.is_(None),
        )
    )
    total_eggs = int(eggs_result.scalar_one())

    # Hen-day production average
    hdp_result = await db.execute(
        select(func.avg(ProductionRecord.hen_day_production)).where(
            ProductionRecord.flock_id == flock_id,
            ProductionRecord.hen_day_production.isnot(None),
            ProductionRecord.deleted_at.is_(None),
        )
    )
    avg_hdp_raw = hdp_result.scalar_one_or_none()
    avg_hdp = float(avg_hdp_raw) if avg_hdp_raw is not None else None

    metrics = FlockMetrics(
        days_alive=days_alive,
        total_mortality=total_mortality,
        current_count=current_count,
        survival_rate=round(survival_rate, 2),
        total_feed_kg=total_feed_kg,
        latest_avg_weight_kg=latest_avg_weight,
        total_biomass_kg=total_biomass,
        fcr=fcr,
        total_eggs_collected=total_eggs if total_eggs > 0 else None,
        hen_day_production=round(avg_hdp * 100, 2) if avg_hdp is not None else None,
    )
    return flock, metrics


async def close_flock(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    data: FlockClose,
    current_user: User,
) -> Flock:
    """
    Close a flock (sold, closed, or culled).
    Releases the house for a new flock.
    """
    flock = await _get_flock_or_404(db, farm_id, flock_id)

    if flock.status != "active":
        raise ConflictException(
            f"Flock is already closed (status={flock.status})."
        )

    if data.close_date < flock.placement_date:
        raise ValidationException(
            "close_date cannot be before placement_date."
        )

    flock.status = data.status
    flock.close_date = data.close_date
    flock.close_reason = data.close_reason
    flock.sale_price_per_kg = data.sale_price_per_kg
    flock.total_birds_sold = data.total_birds_sold
    flock.closing_weight_kg = data.closing_weight_kg

    # Release the house
    house_result = await db.execute(
        select(ProductionHouse).where(
            ProductionHouse.id == flock.house_id,
            ProductionHouse.deleted_at.is_(None),
        )
    )
    house = house_result.scalar_one_or_none()
    if house and house.current_flock_id == flock.id:
        house.current_flock_id = None

    await db.commit()
    await db.refresh(flock)
    return flock


# ── Daily Logs ────────────────────────────────────────────────────────────────

async def submit_daily_log(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    data: DailyLogSubmit,
    current_user: User,
) -> DailyLog:
    """
    Submit or update a daily log.
    DB-06 Frozen: UNIQUE(flock_id, log_date) — upsert on conflict.
    Flock must be active to accept new logs.
    """
    flock = await _get_flock_or_404(db, farm_id, flock_id)

    if flock.status != "active":
        raise ConflictException(
            f"Cannot log to a closed flock (status={flock.status})."
        )

    # Upsert: INSERT ... ON CONFLICT (flock_id, log_date) DO UPDATE
    stmt = (
        pg_insert(DailyLog)
        .values(
            id=uuid.uuid4(),
            farm_id=farm_id,
            flock_id=flock_id,
            log_date=data.log_date,
            morning_count=data.morning_count,
            mortality_count=data.mortality_count,
            mortality_cause=data.mortality_cause,
            feed_consumed_kg=data.feed_consumed_kg,
            water_litres=data.water_litres,
            house_temp_am=data.house_temp_am,
            house_temp_pm=data.house_temp_pm,
            notes=data.notes,
            logged_by=current_user.id,
            is_corrected=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_daily_logs_flock_date",
            set_={
                "morning_count": data.morning_count,
                "mortality_count": data.mortality_count,
                "mortality_cause": data.mortality_cause,
                "feed_consumed_kg": data.feed_consumed_kg,
                "water_litres": data.water_litres,
                "house_temp_am": data.house_temp_am,
                "house_temp_pm": data.house_temp_pm,
                "notes": data.notes,
                "logged_by": current_user.id,
                "updated_at": datetime.now(timezone.utc),
            },
        )
        .returning(DailyLog)
    )
    result = await db.execute(stmt)
    await db.commit()

    # Fetch the upserted row
    log_result = await db.execute(
        select(DailyLog).where(
            DailyLog.flock_id == flock_id,
            DailyLog.log_date == data.log_date,
            DailyLog.deleted_at.is_(None),
        )
    )
    return log_result.scalar_one()


async def list_daily_logs(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    limit: int = 30,
    offset: int = 0,
) -> list[DailyLog]:
    await _get_flock_or_404(db, farm_id, flock_id)
    result = await db.execute(
        select(DailyLog)
        .where(
            DailyLog.flock_id == flock_id,
            DailyLog.farm_id == farm_id,
            DailyLog.deleted_at.is_(None),
        )
        .order_by(DailyLog.log_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_daily_log_by_date(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    log_date: date,
) -> DailyLog:
    await _get_flock_or_404(db, farm_id, flock_id)
    result = await db.execute(
        select(DailyLog).where(
            DailyLog.flock_id == flock_id,
            DailyLog.farm_id == farm_id,
            DailyLog.log_date == log_date,
            DailyLog.deleted_at.is_(None),
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise NotFoundException(f"No daily log found for {log_date}.")
    return log


async def correct_daily_log(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    log_date: date,
    data: DailyLogCorrect,
    current_user: User,
) -> DailyLog:
    """Correct a previously submitted daily log. Requires OPS_LOG_CORRECT permission."""
    log = await get_daily_log_by_date(db, farm_id, flock_id, log_date)

    update_fields = {
        "is_corrected": True,
        "corrected_by": current_user.id,
        "corrected_at": datetime.now(timezone.utc),
    }
    for field in [
        "morning_count", "mortality_count", "mortality_cause",
        "feed_consumed_kg", "water_litres", "house_temp_am",
        "house_temp_pm", "notes",
    ]:
        val = getattr(data, field, None)
        if val is not None:
            update_fields[field] = val

    # Append correction reason to notes
    correction_note = f"\n[CORRECTION by {current_user.id}: {data.correction_reason}]"
    existing_notes = log.notes or ""
    update_fields["notes"] = existing_notes + correction_note

    for k, v in update_fields.items():
        setattr(log, k, v)

    await db.commit()
    await db.refresh(log)
    return log


# ── Production Records ────────────────────────────────────────────────────────

async def submit_production_record(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    data: ProductionRecordSubmit,
    current_user: User,
) -> ProductionRecord:
    """Log daily egg production. Upsert on (flock_id, record_date) conflict."""
    flock = await _get_flock_or_404(db, farm_id, flock_id)

    if flock.status != "active":
        raise ConflictException("Cannot log production to a closed flock.")

    saleable = data.eggs_collected - data.broken_eggs

    # Compute hen-day production if we can
    # We need current_count = initial_count - total_mortality
    mortality_result = await db.execute(
        select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
            DailyLog.flock_id == flock_id,
            DailyLog.deleted_at.is_(None),
        )
    )
    total_mortality = int(mortality_result.scalar_one())
    current_count = flock.initial_count - total_mortality
    hdp = (
        Decimal(str(data.eggs_collected)) / Decimal(str(current_count))
        if current_count > 0 else None
    )

    stmt = (
        pg_insert(ProductionRecord)
        .values(
            id=uuid.uuid4(),
            farm_id=farm_id,
            flock_id=flock_id,
            record_date=data.record_date,
            eggs_collected=data.eggs_collected,
            broken_eggs=data.broken_eggs,
            saleable_eggs=saleable,
            hen_day_production=hdp,
            notes=data.notes,
            logged_by=current_user.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_production_records_flock_date",
            set_={
                "eggs_collected": data.eggs_collected,
                "broken_eggs": data.broken_eggs,
                "saleable_eggs": saleable,
                "hen_day_production": hdp,
                "notes": data.notes,
                "logged_by": current_user.id,
                "updated_at": datetime.now(timezone.utc),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    result = await db.execute(
        select(ProductionRecord).where(
            ProductionRecord.flock_id == flock_id,
            ProductionRecord.record_date == data.record_date,
            ProductionRecord.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def list_production_records(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    limit: int = 30,
    offset: int = 0,
) -> list[ProductionRecord]:
    await _get_flock_or_404(db, farm_id, flock_id)
    result = await db.execute(
        select(ProductionRecord)
        .where(
            ProductionRecord.flock_id == flock_id,
            ProductionRecord.farm_id == farm_id,
            ProductionRecord.deleted_at.is_(None),
        )
        .order_by(ProductionRecord.record_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ── Weigh-In Records ──────────────────────────────────────────────────────────

async def submit_weighin(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    data: WeighinSubmit,
    current_user: User,
) -> WeighinRecord:
    """Record a weigh-in. Computes total_biomass and FCR."""
    flock = await _get_flock_or_404(db, farm_id, flock_id)

    if flock.status != "active":
        raise ConflictException("Cannot weigh-in on a closed flock.")

    # current_count for biomass
    mortality_result = await db.execute(
        select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
            DailyLog.flock_id == flock_id,
            DailyLog.deleted_at.is_(None),
        )
    )
    total_mortality = int(mortality_result.scalar_one())
    current_count = flock.initial_count - total_mortality

    total_biomass = (
        data.average_weight_kg * Decimal(str(current_count))
        if current_count > 0 else None
    )

    # FCR = total_feed_consumed / total_biomass
    total_feed = await _get_total_feed_for_flock(db, flock_id)
    fcr = (
        (total_feed / total_biomass).quantize(Decimal("0.001"))
        if total_biomass and total_biomass > 0 and total_feed > 0
        else None
    )

    record = WeighinRecord(
        id=uuid.uuid4(),
        farm_id=farm_id,
        flock_id=flock_id,
        weighed_at=data.weighed_at,
        sample_size=data.sample_size,
        average_weight_kg=data.average_weight_kg,
        min_weight_kg=data.min_weight_kg,
        max_weight_kg=data.max_weight_kg,
        total_biomass_kg=total_biomass,
        fcr_to_date=fcr,
        notes=data.notes,
        logged_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_weighins(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[WeighinRecord]:
    await _get_flock_or_404(db, farm_id, flock_id)
    result = await db.execute(
        select(WeighinRecord)
        .where(
            WeighinRecord.flock_id == flock_id,
            WeighinRecord.farm_id == farm_id,
            WeighinRecord.deleted_at.is_(None),
        )
        .order_by(WeighinRecord.weighed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ── Feed Purchases ────────────────────────────────────────────────────────────

async def create_feed_purchase(
    db: AsyncSession,
    farm_id: uuid.UUID,
    data: FeedPurchaseCreate,
    current_user: User,
) -> FeedPurchase:
    """Record a feed purchase. total_cost is computed and stored at insert time."""
    # If flock_id supplied, verify it belongs to this farm
    if data.flock_id is not None:
        flock_result = await db.execute(
            select(Flock).where(
                Flock.id == data.flock_id,
                Flock.farm_id == farm_id,
                Flock.deleted_at.is_(None),
            )
        )
        if flock_result.scalar_one_or_none() is None:
            raise NotFoundException(
                f"Flock {data.flock_id} not found on this farm."
            )

    total_cost = (data.quantity_kg * data.price_per_kg).quantize(Decimal("0.01"))

    purchase = FeedPurchase(
        id=uuid.uuid4(),
        farm_id=farm_id,
        flock_id=data.flock_id,
        purchase_date=data.purchase_date,
        feed_type=data.feed_type,
        quantity_kg=data.quantity_kg,
        price_per_kg=data.price_per_kg,
        total_cost=total_cost,
        supplier=data.supplier,
        notes=data.notes,
        recorded_by=current_user.id,
    )
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)
    return purchase


async def list_feed_purchases(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedPurchase]:
    query = select(FeedPurchase).where(
        FeedPurchase.farm_id == farm_id,
        FeedPurchase.deleted_at.is_(None),
    )
    if flock_id is not None:
        query = query.where(FeedPurchase.flock_id == flock_id)
    query = query.order_by(FeedPurchase.purchase_date.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())
