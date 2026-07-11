"""
Greena — Finance Service
Business logic for the Finance Module (Migrations 019-022).

Core functions:
  list_expense_categories()   — system + farm custom categories
  create_expense_category()   — custom category per farm
  log_expense()               — record an expense; triggers snapshot recompute
  list_expenses()             — paginated expense list with total
  get_expense()               — single expense
  update_expense()            — correct an expense; triggers snapshot recompute
  delete_expense()            — soft delete; triggers snapshot recompute
  log_revenue()               — record a revenue event; triggers snapshot recompute
  list_revenue()              — paginated revenue list with total
  get_revenue_record()        — single revenue record
  update_revenue_record()     — correct a revenue record; triggers snapshot recompute
  delete_revenue_record()     — soft delete; triggers snapshot recompute
  get_financial_snapshot()    — read pre-computed P&L for a flock
  recompute_snapshot()        — PRIVATE — recompute and upsert snapshot (DB-07 Frozen)
  get_finance_dashboard()     — farm-level dashboard (aggregates from snapshots)
  get_category_breakdown()    — expense breakdown by category for date range

Calculators (pure, no DB):
  calculate_fcr()
  calculate_profit_projection()
  calculate_break_even()
  calculate_feed_needs()

IMPORTANT — DB-07 Frozen:
  financial_snapshots are NEVER computed in real-time in API responses.
  All P&L data is served from the snapshot table.
  recompute_snapshot() is the ONLY place aggregate queries run.
  It must be called (awaited) after every expense/revenue mutation.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.farm import Farm
from app.models.flock import Flock, DailyLog
from app.models.finance import (
    Expense,
    ExpenseCategory,
    FinancialSnapshot,
    RevenueRecord,
)
from app.models.auth import User
from app.schemas.finance import (
    BreakEvenInput,
    BreakEvenResult,
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseSummaryItem,
    ExpenseUpdate,
    ExpenseCategoryBreakdown,
    FCRCalculatorInput,
    FCRCalculatorResult,
    FeedNeedsInput,
    FeedNeedsResult,
    FinanceDashboardResponse,
    FinancialSnapshotResponse,
    FlockPnLCard,
    ProfitProjectionInput,
    ProfitProjectionResult,
    RevenueListResponse,
    RevenueRecordCreate,
    RevenueRecordResponse,
    RevenueRecordUpdate,
    RevenueSummaryItem,
)

# Feed and nutrition category slugs — used for cost breakdown
FEED_SLUGS = {"feed_purchase", "feed_supplements"}
DOC_SLUGS = {"doc_purchase"}
VET_SLUGS = {"vaccination", "medication", "vet_fees"}
LABOUR_SLUGS = {"labour"}


# ── Expense Categories ────────────────────────────────────────────────────────

async def list_expense_categories(
    db: AsyncSession,
    farm_id: UUID,
) -> list[ExpenseCategoryResponse]:
    """
    Return all active expense categories available to a farm:
    system categories (farm_id IS NULL) + custom categories for this farm.
    """
    result = await db.execute(
        select(ExpenseCategory)
        .where(
            ExpenseCategory.deleted_at.is_(None),
            or_(
                ExpenseCategory.farm_id.is_(None),   # system
                ExpenseCategory.farm_id == str(farm_id),  # farm custom
            ),
        )
        .order_by(ExpenseCategory.is_system.desc(), ExpenseCategory.name)
    )
    categories = result.scalars().all()
    return [ExpenseCategoryResponse.model_validate(c) for c in categories]


async def create_expense_category(
    db: AsyncSession,
    farm_id: UUID,
    data: ExpenseCategoryCreate,
    current_user: User,
) -> ExpenseCategoryResponse:
    """Create a custom expense category for a farm."""
    # Check slug uniqueness within this farm
    existing = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.farm_id == str(farm_id),
            ExpenseCategory.slug == data.slug,
            ExpenseCategory.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"Category slug '{data.slug}' already exists for this farm")

    category = ExpenseCategory(
        farm_id=farm_id,
        name=data.name,
        slug=data.slug,
        icon=data.icon,
        color=data.color,
        is_system=False,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return ExpenseCategoryResponse.model_validate(category)


# ── Expenses ──────────────────────────────────────────────────────────────────

async def log_expense(
    db: AsyncSession,
    farm_id: UUID,
    data: ExpenseCreate,
    current_user: User,
) -> ExpenseResponse:
    """Record a new expense. Triggers snapshot recompute if flock-linked."""
    # Validate category belongs to this farm or is system
    cat_result = await db.execute(
        select(ExpenseCategory).where(
            ExpenseCategory.id == str(data.category_id),
            ExpenseCategory.deleted_at.is_(None),
            or_(
                ExpenseCategory.farm_id.is_(None),
                ExpenseCategory.farm_id == str(farm_id),
            ),
        )
    )
    category = cat_result.scalar_one_or_none()
    if not category:
        raise NotFoundException("Expense category not found or not available to this farm")

    # Validate flock if provided
    if data.flock_id:
        flock_result = await db.execute(
            select(Flock).where(
                Flock.id == str(data.flock_id),
                Flock.farm_id == str(farm_id),
                Flock.deleted_at.is_(None),
            )
        )
        if not flock_result.scalar_one_or_none():
            raise NotFoundException("Flock not found on this farm")

    expense = Expense(
        farm_id=farm_id,
        flock_id=data.flock_id,
        category_id=data.category_id,
        expense_date=data.expense_date,
        amount=data.amount,
        description=data.description,
        payment_method=data.payment_method,
        receipt_url=data.receipt_url,
        supplier=data.supplier,
        quantity=data.quantity,
        unit=data.unit,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    # Trigger snapshot recompute if flock-linked
    if data.flock_id:
        await recompute_snapshot(db, farm_id, data.flock_id)

    # Re-fetch with category joined
    return await get_expense(db, farm_id, expense.id)


async def list_expenses(
    db: AsyncSession,
    farm_id: UUID,
    flock_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> ExpenseListResponse:
    """Paginated expense list with running total."""
    filters = [
        Expense.farm_id == str(farm_id),
        Expense.deleted_at.is_(None),
    ]
    if flock_id:
        filters.append(Expense.flock_id == str(flock_id))
    if category_id:
        filters.append(Expense.category_id == str(category_id))
    if date_from:
        filters.append(Expense.expense_date >= date_from)
    if date_to:
        filters.append(Expense.expense_date <= date_to)

    # Total count + sum
    count_q = await db.execute(
        select(func.count(Expense.id), func.sum(Expense.amount))
        .where(*filters)
    )
    total, total_kes = count_q.one()
    total_kes = total_kes or Decimal("0")

    # Paginated rows
    offset = (page - 1) * page_size
    rows_q = await db.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    expenses = rows_q.scalars().all()

    items = [
        ExpenseSummaryItem(
            id=e.id,
            expense_date=e.expense_date,
            amount=e.amount,
            description=e.description,
            category_name=e.category.name,
            category_icon=e.category.icon,
            category_color=e.category.color,
            payment_method=e.payment_method,
            flock_id=e.flock_id,
        )
        for e in expenses
    ]

    return ExpenseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_kes=total_kes,
    )


async def get_expense(
    db: AsyncSession,
    farm_id: UUID,
    expense_id: UUID,
) -> ExpenseResponse:
    """Fetch a single expense with category."""
    result = await db.execute(
        select(Expense).where(
            Expense.id == str(expense_id),
            Expense.farm_id == str(farm_id),
            Expense.deleted_at.is_(None),
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise NotFoundException("Expense not found")
    return ExpenseResponse.model_validate(expense)


async def update_expense(
    db: AsyncSession,
    farm_id: UUID,
    expense_id: UUID,
    data: ExpenseUpdate,
    current_user: User,
) -> ExpenseResponse:
    """Correct an expense. Appends correction note. Triggers snapshot recompute."""
    result = await db.execute(
        select(Expense).where(
            Expense.id == str(expense_id),
            Expense.farm_id == str(farm_id),
            Expense.deleted_at.is_(None),
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise NotFoundException("Expense not found")

    original_flock_id = expense.flock_id

    if data.category_id is not None:
        expense.category_id = data.category_id
    if data.flock_id is not None:
        expense.flock_id = data.flock_id
    if data.expense_date is not None:
        expense.expense_date = data.expense_date
    if data.amount is not None:
        expense.amount = data.amount
    if data.description is not None:
        expense.description = data.description
    if data.payment_method is not None:
        expense.payment_method = data.payment_method
    if data.supplier is not None:
        expense.supplier = data.supplier
    if data.quantity is not None:
        expense.quantity = data.quantity
    if data.unit is not None:
        expense.unit = data.unit
    if data.notes is not None:
        expense.notes = data.notes
    # correction_reason is required on updates — always append the audit trail.
    if data.correction_reason:
        existing_notes = expense.notes or ""
        expense.notes = (
            f"{existing_notes}\n[Corrected by {current_user.id} at "
            f"{datetime.now(tz=timezone.utc).isoformat()}: {data.correction_reason}]"
        ).strip()

    await db.commit()
    await db.refresh(expense)

    # Recompute for both old and new flock if flock changed
    if original_flock_id:
        await recompute_snapshot(db, farm_id, original_flock_id)
    if expense.flock_id and expense.flock_id != original_flock_id:
        await recompute_snapshot(db, farm_id, expense.flock_id)

    return await get_expense(db, farm_id, expense_id)


async def delete_expense(
    db: AsyncSession,
    farm_id: UUID,
    expense_id: UUID,
) -> None:
    """Soft delete an expense. Triggers snapshot recompute."""
    result = await db.execute(
        select(Expense).where(
            Expense.id == str(expense_id),
            Expense.farm_id == str(farm_id),
            Expense.deleted_at.is_(None),
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise NotFoundException("Expense not found")

    flock_id = expense.flock_id
    expense.soft_delete()
    await db.commit()

    if flock_id:
        await recompute_snapshot(db, farm_id, flock_id)


# ── Revenue Records ───────────────────────────────────────────────────────────

async def log_revenue(
    db: AsyncSession,
    farm_id: UUID,
    data: RevenueRecordCreate,
    current_user: User,
) -> RevenueRecordResponse:
    """Record a new revenue event. Triggers snapshot recompute."""
    # Validate flock belongs to farm
    flock_result = await db.execute(
        select(Flock).where(
            Flock.id == str(data.flock_id),
            Flock.farm_id == str(farm_id),
            Flock.deleted_at.is_(None),
        )
    )
    flock = flock_result.scalar_one_or_none()
    if not flock:
        raise NotFoundException("Flock not found on this farm")

    record = RevenueRecord(
        farm_id=farm_id,
        flock_id=data.flock_id,
        revenue_type=data.revenue_type,
        revenue_date=data.revenue_date,
        amount=data.amount,
        quantity=data.quantity,
        unit=data.unit,
        unit_price=data.unit_price,
        birds_sold=data.birds_sold,
        avg_weight_kg=data.avg_weight_kg,
        eggs_count=data.eggs_count,
        trays_count=data.trays_count,
        buyer_name=data.buyer_name,
        buyer_phone=data.buyer_phone,
        payment_method=data.payment_method,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    await recompute_snapshot(db, farm_id, data.flock_id)

    return RevenueRecordResponse.model_validate(record)


async def list_revenue(
    db: AsyncSession,
    farm_id: UUID,
    flock_id: Optional[UUID] = None,
    revenue_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> RevenueListResponse:
    """Paginated revenue list with total."""
    filters = [
        RevenueRecord.farm_id == str(farm_id),
        RevenueRecord.deleted_at.is_(None),
    ]
    if flock_id:
        filters.append(RevenueRecord.flock_id == str(flock_id))
    if revenue_type:
        filters.append(RevenueRecord.revenue_type == revenue_type)
    if date_from:
        filters.append(RevenueRecord.revenue_date >= date_from)
    if date_to:
        filters.append(RevenueRecord.revenue_date <= date_to)

    count_q = await db.execute(
        select(func.count(RevenueRecord.id), func.sum(RevenueRecord.amount))
        .where(*filters)
    )
    total, total_kes = count_q.one()
    total_kes = total_kes or Decimal("0")

    offset = (page - 1) * page_size
    rows_q = await db.execute(
        select(RevenueRecord)
        .where(*filters)
        .order_by(RevenueRecord.revenue_date.desc(), RevenueRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    records = rows_q.scalars().all()

    items = [
        RevenueSummaryItem(
            id=r.id,
            revenue_date=r.revenue_date,
            revenue_type=r.revenue_type,
            amount=r.amount,
            quantity=r.quantity,
            unit=r.unit,
            buyer_name=r.buyer_name,
            payment_method=r.payment_method,
            flock_id=r.flock_id,
        )
        for r in records
    ]

    return RevenueListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_kes=total_kes,
    )


async def get_revenue_record(
    db: AsyncSession,
    farm_id: UUID,
    record_id: UUID,
) -> RevenueRecordResponse:
    """Fetch a single revenue record."""
    result = await db.execute(
        select(RevenueRecord).where(
            RevenueRecord.id == str(record_id),
            RevenueRecord.farm_id == str(farm_id),
            RevenueRecord.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException("Revenue record not found")
    return RevenueRecordResponse.model_validate(record)


async def update_revenue_record(
    db: AsyncSession,
    farm_id: UUID,
    record_id: UUID,
    data: RevenueRecordUpdate,
    current_user: User,
) -> RevenueRecordResponse:
    """Correct a revenue record. Triggers snapshot recompute."""
    result = await db.execute(
        select(RevenueRecord).where(
            RevenueRecord.id == str(record_id),
            RevenueRecord.farm_id == str(farm_id),
            RevenueRecord.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException("Revenue record not found")

    if data.revenue_type is not None:
        record.revenue_type = data.revenue_type
    if data.revenue_date is not None:
        record.revenue_date = data.revenue_date
    if data.amount is not None:
        record.amount = data.amount
    if data.quantity is not None:
        record.quantity = data.quantity
    if data.unit is not None:
        record.unit = data.unit
    if data.unit_price is not None:
        record.unit_price = data.unit_price
    if data.birds_sold is not None:
        record.birds_sold = data.birds_sold
    if data.avg_weight_kg is not None:
        record.avg_weight_kg = data.avg_weight_kg
    if data.eggs_count is not None:
        record.eggs_count = data.eggs_count
    if data.trays_count is not None:
        record.trays_count = data.trays_count
    if data.buyer_name is not None:
        record.buyer_name = data.buyer_name
    if data.payment_method is not None:
        record.payment_method = data.payment_method
    if data.notes is not None:
        record.notes = data.notes
    # correction_reason is required on updates — always append the audit trail.
    if data.correction_reason:
        existing = record.notes or ""
        record.notes = (
            f"{existing}\n[Corrected by {current_user.id} at "
            f"{datetime.now(tz=timezone.utc).isoformat()}: {data.correction_reason}]"
        ).strip()

    await db.commit()
    await db.refresh(record)
    await recompute_snapshot(db, farm_id, record.flock_id)
    return RevenueRecordResponse.model_validate(record)


async def delete_revenue_record(
    db: AsyncSession,
    farm_id: UUID,
    record_id: UUID,
) -> None:
    """Soft delete a revenue record. Triggers snapshot recompute."""
    result = await db.execute(
        select(RevenueRecord).where(
            RevenueRecord.id == str(record_id),
            RevenueRecord.farm_id == str(farm_id),
            RevenueRecord.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException("Revenue record not found")

    flock_id = record.flock_id
    record.soft_delete()
    await db.commit()
    await recompute_snapshot(db, farm_id, flock_id)


# ── Financial Snapshot ─────────────────────────────────────────────────────────

async def get_financial_snapshot(
    db: AsyncSession,
    farm_id: UUID,
    flock_id: UUID,
) -> FinancialSnapshotResponse:
    """
    Read the pre-computed P&L snapshot for a flock (DB-07 Frozen).
    If no snapshot exists yet, compute and persist it on first access.
    """
    result = await db.execute(
        select(FinancialSnapshot).where(
            FinancialSnapshot.flock_id == str(flock_id),
            FinancialSnapshot.farm_id == str(farm_id),
        )
    )
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        # First access — initialise snapshot
        snapshot = await recompute_snapshot(db, farm_id, flock_id)

    if not snapshot:
        raise NotFoundException("Flock not found or snapshot could not be computed")

    return FinancialSnapshotResponse.model_validate(snapshot)


async def recompute_snapshot(
    db: AsyncSession,
    farm_id: UUID,
    flock_id: UUID,
) -> Optional[FinancialSnapshot]:
    """
    PRIVATE — Compute and upsert the financial snapshot for a flock.

    This is the ONLY place aggregate P&L queries run (DB-07 Frozen).
    Called after every expense/revenue mutation.

    Steps:
    1. Validate flock exists
    2. Aggregate revenue by type
    3. Aggregate expenses by category slug group
    4. Aggregate total feed from daily logs
    5. Compute P&L metrics
    6. Upsert snapshot row
    """
    # Validate flock
    flock_result = await db.execute(
        select(Flock).where(
            Flock.id == str(flock_id),
            Flock.farm_id == str(farm_id),
            Flock.deleted_at.is_(None),
        )
    )
    flock = flock_result.scalar_one_or_none()
    if not flock:
        return None

    # ── Aggregate revenue ────────────────────────────────────────────────────
    rev_q = await db.execute(
        select(RevenueRecord.revenue_type, func.sum(RevenueRecord.amount))
        .where(
            RevenueRecord.flock_id == str(flock_id),
            RevenueRecord.farm_id == str(farm_id),
            RevenueRecord.deleted_at.is_(None),
        )
        .group_by(RevenueRecord.revenue_type)
    )
    revenue_by_type: dict[str, Decimal] = {}
    for rtype, total in rev_q.all():
        revenue_by_type[rtype] = total or Decimal("0")

    total_revenue = sum(revenue_by_type.values(), Decimal("0"))
    rev_eggs = revenue_by_type.get("eggs", Decimal("0"))
    rev_birds = revenue_by_type.get("birds", Decimal("0"))
    rev_manure = revenue_by_type.get("manure", Decimal("0"))
    rev_other = revenue_by_type.get("other", Decimal("0"))

    # ── Aggregate expenses with category slugs ───────────────────────────────
    exp_q = await db.execute(
        select(ExpenseCategory.slug, func.sum(Expense.amount))
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(
            Expense.flock_id == str(flock_id),
            Expense.farm_id == str(farm_id),
            Expense.deleted_at.is_(None),
        )
        .group_by(ExpenseCategory.slug)
    )
    expense_by_slug: dict[str, Decimal] = {}
    for slug, total in exp_q.all():
        expense_by_slug[slug] = total or Decimal("0")

    total_expenses = sum(expense_by_slug.values(), Decimal("0"))
    feed_cost = sum(expense_by_slug.get(s, Decimal("0")) for s in FEED_SLUGS)
    doc_cost = sum(expense_by_slug.get(s, Decimal("0")) for s in DOC_SLUGS)
    vet_cost = sum(expense_by_slug.get(s, Decimal("0")) for s in VET_SLUGS)
    labour_cost = sum(expense_by_slug.get(s, Decimal("0")) for s in LABOUR_SLUGS)
    other_cost = total_expenses - feed_cost - doc_cost - vet_cost - labour_cost
    if other_cost < 0:
        other_cost = Decimal("0")

    # ── Aggregate total feed from daily logs ─────────────────────────────────
    feed_q = await db.execute(
        select(func.sum(DailyLog.feed_consumed_kg))
        .where(
            DailyLog.flock_id == str(flock_id),
            DailyLog.deleted_at.is_(None),
        )
    )
    total_feed_kg = feed_q.scalar_one_or_none() or Decimal("0")

    # ── P&L Metrics ──────────────────────────────────────────────────────────
    gross_profit = total_revenue - total_expenses
    is_profitable = gross_profit > 0

    gross_margin_pct: Optional[Decimal] = None
    if total_revenue > 0:
        gross_margin_pct = (gross_profit / total_revenue * 100).quantize(Decimal("0.0001"))

    # Per-bird metrics
    initial_count = flock.initial_count
    cost_per_bird: Optional[Decimal] = None
    if initial_count and initial_count > 0:
        cost_per_bird = (total_expenses / initial_count).quantize(Decimal("0.01"))

    # Revenue per bird — based on birds sold from revenue records
    birds_sold_result = await db.execute(
        select(func.sum(RevenueRecord.birds_sold))
        .where(
            RevenueRecord.flock_id == str(flock_id),
            RevenueRecord.revenue_type == "birds",
            RevenueRecord.deleted_at.is_(None),
        )
    )
    birds_sold_total = birds_sold_result.scalar_one_or_none() or 0

    revenue_per_bird: Optional[Decimal] = None
    break_even_per_bird: Optional[Decimal] = None
    if birds_sold_total > 0:
        revenue_per_bird = (rev_birds / birds_sold_total).quantize(Decimal("0.01"))
        break_even_per_bird = (total_expenses / birds_sold_total).quantize(Decimal("0.01"))
    elif initial_count and initial_count > 0:
        break_even_per_bird = (total_expenses / initial_count).quantize(Decimal("0.01"))

    # FCR: total_feed_kg / total_live_weight_sold
    live_weight_sold_q = await db.execute(
        select(func.sum(RevenueRecord.birds_sold * RevenueRecord.avg_weight_kg))
        .where(
            RevenueRecord.flock_id == str(flock_id),
            RevenueRecord.revenue_type == "birds",
            RevenueRecord.avg_weight_kg.is_not(None),
            RevenueRecord.deleted_at.is_(None),
        )
    )
    live_weight_sold = live_weight_sold_q.scalar_one_or_none() or Decimal("0")
    fcr_computed: Optional[Decimal] = None
    if total_feed_kg > 0 and live_weight_sold > 0:
        fcr_computed = (total_feed_kg / live_weight_sold).quantize(Decimal("0.001"))

    # Feed cost %
    feed_cost_pct: Optional[Decimal] = None
    if total_expenses > 0:
        feed_cost_pct = (feed_cost / total_expenses * 100).quantize(Decimal("0.0001"))

    # Bird count for the snapshot. The Flock model tracks initial_count only
    # (there is no stored current/live count), so use it here.
    bird_count_snapshot = flock.initial_count

    # ── Upsert Snapshot ────────────────────────────────────────────────────────
    snap_result = await db.execute(
        select(FinancialSnapshot).where(
            FinancialSnapshot.flock_id == str(flock_id),
        )
    )
    snapshot = snap_result.scalar_one_or_none()

    now = datetime.now(tz=timezone.utc)

    if snapshot:
        # Update existing
        snapshot.snapshot_at = now
        snapshot.total_revenue_kes = total_revenue
        snapshot.revenue_eggs_kes = rev_eggs
        snapshot.revenue_birds_kes = rev_birds
        snapshot.revenue_manure_kes = rev_manure
        snapshot.revenue_other_kes = rev_other
        snapshot.total_expenses_kes = total_expenses
        snapshot.feed_cost_kes = feed_cost
        snapshot.doc_cost_kes = doc_cost
        snapshot.vet_health_cost_kes = vet_cost
        snapshot.labour_cost_kes = labour_cost
        snapshot.other_cost_kes = other_cost
        snapshot.gross_profit_kes = gross_profit
        snapshot.gross_margin_pct = gross_margin_pct
        snapshot.is_profitable = is_profitable
        snapshot.cost_per_bird_kes = cost_per_bird
        snapshot.revenue_per_bird_kes = revenue_per_bird
        snapshot.break_even_price_kes = break_even_per_bird
        snapshot.total_feed_kg = total_feed_kg
        snapshot.fcr_computed = fcr_computed
        snapshot.bird_count_snapshot = bird_count_snapshot
        snapshot.birds_sold_snapshot = birds_sold_total if birds_sold_total else None
        snapshot.feed_cost_pct = feed_cost_pct
    else:
        # Create new
        snapshot = FinancialSnapshot(
            farm_id=farm_id,
            flock_id=flock_id,
            snapshot_at=now,
            total_revenue_kes=total_revenue,
            revenue_eggs_kes=rev_eggs,
            revenue_birds_kes=rev_birds,
            revenue_manure_kes=rev_manure,
            revenue_other_kes=rev_other,
            total_expenses_kes=total_expenses,
            feed_cost_kes=feed_cost,
            doc_cost_kes=doc_cost,
            vet_health_cost_kes=vet_cost,
            labour_cost_kes=labour_cost,
            other_cost_kes=other_cost,
            gross_profit_kes=gross_profit,
            gross_margin_pct=gross_margin_pct,
            is_profitable=is_profitable,
            cost_per_bird_kes=cost_per_bird,
            revenue_per_bird_kes=revenue_per_bird,
            break_even_price_kes=break_even_per_bird,
            total_feed_kg=total_feed_kg,
            fcr_computed=fcr_computed,
            bird_count_snapshot=bird_count_snapshot,
            birds_sold_snapshot=birds_sold_total if birds_sold_total else None,
            feed_cost_pct=feed_cost_pct,
        )
        db.add(snapshot)

    await db.commit()
    await db.refresh(snapshot)
    return snapshot


# ── Finance Dashboard ─────────────────────────────────────────────────────────

async def get_finance_dashboard(
    db: AsyncSession,
    farm: Farm,
    current_user: User,
) -> FinanceDashboardResponse:
    """
    Farm-level finance dashboard. Aggregates from financial_snapshots only
    (DB-07 Frozen). No real-time aggregate queries.

    Shows data for all active flocks on the farm.
    """
    from datetime import date as dt_date

    # Get all active flock snapshots for this farm
    snaps_q = await db.execute(
        select(FinancialSnapshot, Flock)
        .join(Flock, FinancialSnapshot.flock_id == Flock.id)
        .where(
            FinancialSnapshot.farm_id == str(farm.id),
            Flock.deleted_at.is_(None),
        )
        .order_by(Flock.placement_date.desc())
    )
    snap_flock_pairs = snaps_q.all()

    total_revenue = Decimal("0")
    total_expenses = Decimal("0")
    feed_cost = Decimal("0")
    doc_cost = Decimal("0")
    vet_cost = Decimal("0")
    labour_cost = Decimal("0")
    other_cost = Decimal("0")
    flock_cards: list[FlockPnLCard] = []

    today = dt_date.today()

    for snap, flock in snap_flock_pairs:
        total_revenue += snap.total_revenue_kes
        total_expenses += snap.total_expenses_kes
        feed_cost += snap.feed_cost_kes
        doc_cost += snap.doc_cost_kes
        vet_cost += snap.vet_health_cost_kes
        labour_cost += snap.labour_cost_kes
        other_cost += snap.other_cost_kes

        days_alive = (today - flock.placement_date).days if flock.placement_date else None

        flock_cards.append(FlockPnLCard(
            flock_id=flock.id,
            flock_name=flock.name,
            flock_status=flock.status,
            snapshot_at=snap.snapshot_at,
            total_revenue_kes=snap.total_revenue_kes,
            total_expenses_kes=snap.total_expenses_kes,
            gross_profit_kes=snap.gross_profit_kes,
            gross_margin_pct=snap.gross_margin_pct,
            is_profitable=snap.is_profitable,
            days_alive=days_alive,
        ))

    gross_profit = total_revenue - total_expenses
    is_profitable = gross_profit > 0

    gross_margin_pct: Optional[Decimal] = None
    if total_revenue > 0:
        gross_margin_pct = (gross_profit / total_revenue * 100).quantize(Decimal("0.0001"))

    feed_cost_pct: Optional[Decimal] = None
    if total_expenses > 0:
        feed_cost_pct = (feed_cost / total_expenses * 100).quantize(Decimal("0.0001"))

    # Recent expenses (last 5)
    recent_exp_q = await db.execute(
        select(Expense)
        .where(
            Expense.farm_id == str(farm.id),
            Expense.deleted_at.is_(None),
        )
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        .limit(5)
    )
    recent_exp = recent_exp_q.scalars().all()
    recent_expenses = [
        ExpenseSummaryItem(
            id=e.id,
            expense_date=e.expense_date,
            amount=e.amount,
            description=e.description,
            category_name=e.category.name,
            category_icon=e.category.icon,
            category_color=e.category.color,
            payment_method=e.payment_method,
            flock_id=e.flock_id,
        )
        for e in recent_exp
    ]

    # Recent revenue (last 5)
    recent_rev_q = await db.execute(
        select(RevenueRecord)
        .where(
            RevenueRecord.farm_id == str(farm.id),
            RevenueRecord.deleted_at.is_(None),
        )
        .order_by(RevenueRecord.revenue_date.desc(), RevenueRecord.created_at.desc())
        .limit(5)
    )
    recent_rev = recent_rev_q.scalars().all()
    recent_revenue = [
        RevenueSummaryItem(
            id=r.id,
            revenue_date=r.revenue_date,
            revenue_type=r.revenue_type,
            amount=r.amount,
            quantity=r.quantity,
            unit=r.unit,
            buyer_name=r.buyer_name,
            payment_method=r.payment_method,
            flock_id=r.flock_id,
        )
        for r in recent_rev
    ]

    return FinanceDashboardResponse(
        period_label="All flocks",
        total_revenue_kes=total_revenue,
        total_expenses_kes=total_expenses,
        gross_profit_kes=gross_profit,
        gross_margin_pct=gross_margin_pct,
        is_profitable=is_profitable,
        feed_cost_kes=feed_cost,
        feed_cost_pct=feed_cost_pct,
        doc_cost_kes=doc_cost,
        vet_health_cost_kes=vet_cost,
        labour_cost_kes=labour_cost,
        other_cost_kes=other_cost,
        flock_cards=flock_cards,
        recent_expenses=recent_expenses,
        recent_revenue=recent_revenue,
    )


async def get_category_breakdown(
    db: AsyncSession,
    farm_id: UUID,
    flock_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> list[ExpenseCategoryBreakdown]:
    """Expense breakdown by category for a date range."""
    filters = [
        Expense.farm_id == str(farm_id),
        Expense.deleted_at.is_(None),
    ]
    if flock_id:
        filters.append(Expense.flock_id == str(flock_id))
    if date_from:
        filters.append(Expense.expense_date >= date_from)
    if date_to:
        filters.append(Expense.expense_date <= date_to)

    rows_q = await db.execute(
        select(
            ExpenseCategory.id,
            ExpenseCategory.name,
            ExpenseCategory.icon,
            ExpenseCategory.color,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*filters)
        .group_by(
            ExpenseCategory.id,
            ExpenseCategory.name,
            ExpenseCategory.icon,
            ExpenseCategory.color,
        )
        .order_by(func.sum(Expense.amount).desc())
    )
    rows = rows_q.all()

    grand_total = sum((r.total or Decimal("0")) for r in rows)

    return [
        ExpenseCategoryBreakdown(
            category_id=r.id,
            category_name=r.name,
            category_icon=r.icon,
            category_color=r.color,
            total_kes=r.total or Decimal("0"),
            pct_of_total=(
                ((r.total or Decimal("0")) / grand_total * 100).quantize(Decimal("0.0001"))
                if grand_total > 0 else None
            ),
            transaction_count=r.count,
        )
        for r in rows
    ]


# ── Financial Calculators (pure, no DB) ──────────────────────────────────────

def calculate_fcr(data: FCRCalculatorInput) -> FCRCalculatorResult:
    """
    FCR = total feed consumed (kg) / total live weight gained (kg).
    Kenyan broiler benchmarks:
      < 1.7  — Excellent
      1.7-1.9 — Good
      1.9-2.1 — Average
      2.1-2.5 — Below average
      > 2.5  — Poor
    """
    fcr = (data.total_feed_kg / data.total_live_weight_kg).quantize(Decimal("0.001"))

    if fcr < Decimal("1.7"):
        interpretation = "Excellent (< 1.7) — outstanding feed efficiency"
    elif fcr < Decimal("1.9"):
        interpretation = "Good (1.7–1.9) — above average efficiency"
    elif fcr < Decimal("2.1"):
        interpretation = "Average (1.9–2.1) — meeting Kenya broiler benchmark"
    elif fcr < Decimal("2.5"):
        interpretation = "Below average (2.1–2.5) — review feed quality and management"
    else:
        interpretation = "Poor (> 2.5) — investigate feed waste, disease, or stocking density"

    return FCRCalculatorResult(
        fcr=fcr,
        interpretation=interpretation,
        feed_kg=data.total_feed_kg,
        live_weight_kg=data.total_live_weight_kg,
    )


def calculate_profit_projection(data: ProfitProjectionInput) -> ProfitProjectionResult:
    """
    Project total profit at sale given current flock metrics.
    """
    # Expected mortality
    mortality_pct = data.expected_mortality_pct / 100
    birds_at_sale = int(data.current_bird_count * (1 - mortality_pct))
    if birds_at_sale < 1:
        birds_at_sale = 1

    total_live_weight = (
        Decimal(str(birds_at_sale)) * data.expected_close_weight_kg
    ).quantize(Decimal("0.01"))

    projected_revenue = (
        total_live_weight * data.expected_sale_price_per_kg
    ).quantize(Decimal("0.01"))

    projected_total_expenses = (
        data.total_expenses_so_far_kes + data.expected_additional_expenses_kes
    ).quantize(Decimal("0.01"))

    projected_profit = (projected_revenue - projected_total_expenses).quantize(Decimal("0.01"))

    projected_margin_pct = Decimal("0")
    if projected_revenue > 0:
        projected_margin_pct = (
            projected_profit / projected_revenue * 100
        ).quantize(Decimal("0.01"))

    revenue_per_bird = (projected_revenue / birds_at_sale).quantize(Decimal("0.01"))
    cost_per_bird = (projected_total_expenses / data.current_bird_count).quantize(Decimal("0.01"))

    return ProfitProjectionResult(
        birds_at_sale=birds_at_sale,
        total_live_weight_kg=total_live_weight,
        projected_revenue_kes=projected_revenue,
        projected_total_expenses_kes=projected_total_expenses,
        projected_profit_kes=projected_profit,
        projected_margin_pct=projected_margin_pct,
        revenue_per_bird_kes=revenue_per_bird,
        cost_per_bird_kes=cost_per_bird,
        is_profitable=projected_profit > 0,
    )


def calculate_break_even(data: BreakEvenInput) -> BreakEvenResult:
    """
    Compute the minimum sale price per kg and per bird to break even.
    """
    total_live_weight = (
        Decimal(str(data.expected_birds_sold)) * data.expected_avg_weight_kg
    ).quantize(Decimal("0.001"))

    break_even_per_kg = (data.total_expenses_kes / total_live_weight).quantize(Decimal("0.01"))
    break_even_per_bird = (data.total_expenses_kes / data.expected_birds_sold).quantize(Decimal("0.01"))

    return BreakEvenResult(
        break_even_per_kg_kes=break_even_per_kg,
        break_even_per_bird_kes=break_even_per_bird,
        total_live_weight_kg=total_live_weight,
        total_expenses_kes=data.total_expenses_kes,
    )


def calculate_feed_needs(data: FeedNeedsInput) -> FeedNeedsResult:
    """
    Estimate total feed needed to reach target weight.
    Uses target FCR: feed_needed = weight_gain_needed * target_fcr
    """
    weight_gain_needed_per_bird = data.target_weight_kg - data.current_avg_weight_kg
    if weight_gain_needed_per_bird <= 0:
        weight_gain_needed_per_bird = Decimal("0")

    current_biomass = (
        Decimal(str(data.current_bird_count)) * data.current_avg_weight_kg
    ).quantize(Decimal("0.001"))
    target_biomass = (
        Decimal(str(data.current_bird_count)) * data.target_weight_kg
    ).quantize(Decimal("0.001"))

    weight_gain_needed = (target_biomass - current_biomass).quantize(Decimal("0.001"))
    if weight_gain_needed < 0:
        weight_gain_needed = Decimal("0")

    total_feed_needed = (weight_gain_needed * data.target_fcr).quantize(Decimal("0.001"))

    feed_per_day: Optional[Decimal] = None
    if data.days_remaining and data.days_remaining > 0 and total_feed_needed > 0:
        feed_per_day = (
            total_feed_needed / data.days_remaining
        ).quantize(Decimal("0.001"))

    return FeedNeedsResult(
        total_feed_needed_kg=total_feed_needed,
        feed_per_day_kg=feed_per_day,
        estimated_feed_cost_kes=None,  # caller multiplies by price/kg
        weight_gain_needed_kg=weight_gain_needed,
        current_biomass_kg=current_biomass,
        target_biomass_kg=target_biomass,
    )
