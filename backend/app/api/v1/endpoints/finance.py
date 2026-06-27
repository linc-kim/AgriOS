"""
AGRIOS — Finance Module API Endpoints

Route map:
  --- Expense Categories ---
  GET    /farms/{farm_id}/finance/categories            → list categories (system + custom)
  POST   /farms/{farm_id}/finance/categories            → create custom category

  --- Expenses ---
  POST   /farms/{farm_id}/expenses                      → log expense
  GET    /farms/{farm_id}/expenses                      → list expenses (paginated)
  GET    /farms/{farm_id}/expenses/{expense_id}         → single expense
  PATCH  /farms/{farm_id}/expenses/{expense_id}         → correct expense
  DELETE /farms/{farm_id}/expenses/{expense_id}         → soft-delete

  --- Revenue ---
  POST   /farms/{farm_id}/revenue                       → log revenue
  GET    /farms/{farm_id}/revenue                       → list revenue (paginated)
  GET    /farms/{farm_id}/revenue/{record_id}           → single revenue record
  PATCH  /farms/{farm_id}/revenue/{record_id}           → correct revenue record
  DELETE /farms/{farm_id}/revenue/{record_id}           → soft-delete

  --- Financial Snapshot ---
  GET    /farms/{farm_id}/flocks/{flock_id}/finance     → flock P&L snapshot
  POST   /farms/{farm_id}/flocks/{flock_id}/finance/refresh  → force recompute snapshot

  --- Dashboard ---
  GET    /farms/{farm_id}/finance                       → farm finance dashboard
  GET    /farms/{farm_id}/finance/categories/breakdown  → expense category breakdown

  --- Calculators (pure, no DB) ---
  POST   /calculators/fcr                               → FCR calculator
  POST   /calculators/profit-projection                 → profit projection
  POST   /calculators/break-even                        → break-even price
  POST   /calculators/feed-needs                        → feed needs estimate

RBAC:
  FINANCE_RECORD → farm_owner, farm_manager
  FINANCE_VIEW   → all roles (farm_owner, farm_manager, farm_worker, vet_consultant, viewer)
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.finance import (
    BreakEvenInput,
    BreakEvenResult,
    ExpenseCategoryBreakdown,
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdate,
    FCRCalculatorInput,
    FCRCalculatorResult,
    FeedNeedsInput,
    FeedNeedsResult,
    FinanceDashboardResponse,
    FinancialSnapshotResponse,
    ProfitProjectionInput,
    ProfitProjectionResult,
    RevenueListResponse,
    RevenueRecordCreate,
    RevenueRecordResponse,
    RevenueRecordUpdate,
)
from app.services import finance_service

router = APIRouter()


# ── Expense Categories ────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/finance/categories",
    response_model=SuccessResponse[list[ExpenseCategoryResponse]],
    summary="List expense categories available to this farm",
    tags=["Finance"],
)
async def list_expense_categories(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[list[ExpenseCategoryResponse]]:
    categories = await finance_service.list_expense_categories(db, farm_id)
    return SuccessResponse(data=categories)


@router.post(
    "/farms/{farm_id}/finance/categories",
    response_model=SuccessResponse[ExpenseCategoryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom expense category for this farm",
    tags=["Finance"],
)
async def create_expense_category(
    farm_id: UUID,
    body: ExpenseCategoryCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[ExpenseCategoryResponse]:
    category = await finance_service.create_expense_category(db, farm_id, body, current_user)
    return SuccessResponse(data=category)


# ── Expenses ──────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/expenses",
    response_model=SuccessResponse[ExpenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a new expense",
    tags=["Finance"],
)
async def log_expense(
    farm_id: UUID,
    body: ExpenseCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[ExpenseResponse]:
    expense = await finance_service.log_expense(db, farm_id, body, current_user)
    return SuccessResponse(data=expense)


@router.get(
    "/farms/{farm_id}/expenses",
    response_model=SuccessResponse[ExpenseListResponse],
    summary="List expenses for a farm",
    tags=["Finance"],
)
async def list_expenses(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    flock_id: Optional[UUID] = Query(None),
    category_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[ExpenseListResponse]:
    result = await finance_service.list_expenses(
        db, farm_id,
        flock_id=flock_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse(data=result)


@router.get(
    "/farms/{farm_id}/expenses/{expense_id}",
    response_model=SuccessResponse[ExpenseResponse],
    summary="Get a single expense",
    tags=["Finance"],
)
async def get_expense(
    farm_id: UUID,
    expense_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[ExpenseResponse]:
    expense = await finance_service.get_expense(db, farm_id, expense_id)
    return SuccessResponse(data=expense)


@router.patch(
    "/farms/{farm_id}/expenses/{expense_id}",
    response_model=SuccessResponse[ExpenseResponse],
    summary="Correct an existing expense",
    tags=["Finance"],
)
async def update_expense(
    farm_id: UUID,
    expense_id: UUID,
    body: ExpenseUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[ExpenseResponse]:
    expense = await finance_service.update_expense(db, farm_id, expense_id, body, current_user)
    return SuccessResponse(data=expense)


@router.delete(
    "/farms/{farm_id}/expenses/{expense_id}",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Soft-delete an expense",
    tags=["Finance"],
)
async def delete_expense(
    farm_id: UUID,
    expense_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[None]:
    await finance_service.delete_expense(db, farm_id, expense_id)
    return SuccessResponse(data=None, message="Expense deleted")


# ── Revenue Records ───────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/revenue",
    response_model=SuccessResponse[RevenueRecordResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a new revenue event",
    tags=["Finance"],
)
async def log_revenue(
    farm_id: UUID,
    body: RevenueRecordCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[RevenueRecordResponse]:
    record = await finance_service.log_revenue(db, farm_id, body, current_user)
    return SuccessResponse(data=record)


@router.get(
    "/farms/{farm_id}/revenue",
    response_model=SuccessResponse[RevenueListResponse],
    summary="List revenue records for a farm",
    tags=["Finance"],
)
async def list_revenue(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    flock_id: Optional[UUID] = Query(None),
    revenue_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[RevenueListResponse]:
    result = await finance_service.list_revenue(
        db, farm_id,
        flock_id=flock_id,
        revenue_type=revenue_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return SuccessResponse(data=result)


@router.get(
    "/farms/{farm_id}/revenue/{record_id}",
    response_model=SuccessResponse[RevenueRecordResponse],
    summary="Get a single revenue record",
    tags=["Finance"],
)
async def get_revenue_record(
    farm_id: UUID,
    record_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[RevenueRecordResponse]:
    record = await finance_service.get_revenue_record(db, farm_id, record_id)
    return SuccessResponse(data=record)


@router.patch(
    "/farms/{farm_id}/revenue/{record_id}",
    response_model=SuccessResponse[RevenueRecordResponse],
    summary="Correct a revenue record",
    tags=["Finance"],
)
async def update_revenue_record(
    farm_id: UUID,
    record_id: UUID,
    body: RevenueRecordUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[RevenueRecordResponse]:
    record = await finance_service.update_revenue_record(
        db, farm_id, record_id, body, current_user
    )
    return SuccessResponse(data=record)


@router.delete(
    "/farms/{farm_id}/revenue/{record_id}",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a revenue record",
    tags=["Finance"],
)
async def delete_revenue_record(
    farm_id: UUID,
    record_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[None]:
    await finance_service.delete_revenue_record(db, farm_id, record_id)
    return SuccessResponse(data=None, message="Revenue record deleted")


# ── Flock Financial Snapshot ──────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/finance",
    response_model=SuccessResponse[FinancialSnapshotResponse],
    summary="Get pre-computed P&L snapshot for a flock",
    tags=["Finance"],
)
async def get_flock_snapshot(
    farm_id: UUID,
    flock_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[FinancialSnapshotResponse]:
    snapshot = await finance_service.get_financial_snapshot(db, farm_id, flock_id)
    return SuccessResponse(data=snapshot)


@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/finance/refresh",
    response_model=SuccessResponse[FinancialSnapshotResponse],
    summary="Force recompute the financial snapshot for a flock",
    tags=["Finance"],
)
async def refresh_flock_snapshot(
    farm_id: UUID,
    flock_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
) -> SuccessResponse[FinancialSnapshotResponse]:
    snapshot = await finance_service.recompute_snapshot(db, farm_id, flock_id)
    from app.core.exceptions import NotFoundException
    if not snapshot:
        raise NotFoundException("Flock not found")
    from app.schemas.finance import FinancialSnapshotResponse
    return SuccessResponse(data=FinancialSnapshotResponse.model_validate(snapshot))


# ── Finance Dashboard ─────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/finance",
    response_model=SuccessResponse[FinanceDashboardResponse],
    summary="Farm-level finance dashboard (reads from pre-computed snapshots)",
    tags=["Finance"],
)
async def get_finance_dashboard(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[FinanceDashboardResponse]:
    farm, _ = access
    dashboard = await finance_service.get_finance_dashboard(db, farm, current_user)
    return SuccessResponse(data=dashboard)


@router.get(
    "/farms/{farm_id}/finance/categories/breakdown",
    response_model=SuccessResponse[list[ExpenseCategoryBreakdown]],
    summary="Expense breakdown by category for a date range",
    tags=["Finance"],
)
async def get_category_breakdown(
    farm_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    flock_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker", "vet_consultant", "viewer"})),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[list[ExpenseCategoryBreakdown]]:
    breakdown = await finance_service.get_category_breakdown(
        db, farm_id,
        flock_id=flock_id,
        date_from=date_from,
        date_to=date_to,
    )
    return SuccessResponse(data=breakdown)


# ── Financial Calculators ─────────────────────────────────────────────────────

@router.post(
    "/calculators/fcr",
    response_model=SuccessResponse[FCRCalculatorResult],
    summary="Calculate Feed Conversion Ratio (FCR)",
    tags=["Finance", "Calculators"],
)
async def calculate_fcr(
    body: FCRCalculatorInput,
    current_user: CurrentUser,
) -> SuccessResponse[FCRCalculatorResult]:
    """Pure calculation — no DB access required. Available to any authenticated user."""
    result = finance_service.calculate_fcr(body)
    return SuccessResponse(data=result)


@router.post(
    "/calculators/profit-projection",
    response_model=SuccessResponse[ProfitProjectionResult],
    summary="Project flock profit at sale",
    tags=["Finance", "Calculators"],
)
async def calculate_profit_projection(
    body: ProfitProjectionInput,
    current_user: CurrentUser,
) -> SuccessResponse[ProfitProjectionResult]:
    result = finance_service.calculate_profit_projection(body)
    return SuccessResponse(data=result)


@router.post(
    "/calculators/break-even",
    response_model=SuccessResponse[BreakEvenResult],
    summary="Calculate break-even sale price",
    tags=["Finance", "Calculators"],
)
async def calculate_break_even(
    body: BreakEvenInput,
    current_user: CurrentUser,
) -> SuccessResponse[BreakEvenResult]:
    result = finance_service.calculate_break_even(body)
    return SuccessResponse(data=result)


@router.post(
    "/calculators/feed-needs",
    response_model=SuccessResponse[FeedNeedsResult],
    summary="Estimate feed needed to reach target weight",
    tags=["Finance", "Calculators"],
)
async def calculate_feed_needs(
    body: FeedNeedsInput,
    current_user: CurrentUser,
) -> SuccessResponse[FeedNeedsResult]:
    result = finance_service.calculate_feed_needs(body)
    return SuccessResponse(data=result)
