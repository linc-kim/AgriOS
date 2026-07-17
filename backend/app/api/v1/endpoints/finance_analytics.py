"""
Greena — Finance Analytics & Reporting Endpoints (Module 5).

Farm-level financial intelligence that complements the existing per-flock
Finance endpoints. All read-only (FINANCE_VIEW).

  GET /farms/{farm_id}/finance/overview         dashboard (today/30d/cash/charts)
  GET /farms/{farm_id}/finance/analytics        rolling windows + per-unit + centres
  GET /farms/{farm_id}/finance/transactions     unified search/filter/sort/paginate
  GET /farms/{farm_id}/finance/cashflow         monthly inflow/outflow/net
  GET /farms/{farm_id}/finance/reports          monthly/quarterly/yearly report
  GET /farms/{farm_id}/finance/reports/csv      CSV export of transactions
  GET /farms/{farm_id}/finance/ai-context       structured AI context
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi import status as http_status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.finance_analytics import (
    CashflowResponse,
    FinanceAIContext,
    FinanceAnalytics,
    FinanceOverview,
    FinanceReport,
    TransactionPage,
)
from app.services import finance_analytics_service

router = APIRouter()


@router.get(
    "/farms/{farm_id}/finance/overview",
    response_model=SuccessResponse[FinanceOverview],
    summary="Farm financial dashboard (today, 30-day, cash balance, charts)",
    tags=["Finance"],
)
async def finance_overview(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[FinanceOverview]:
    farm, _ = access
    return SuccessResponse(data=await finance_analytics_service.get_overview(db, farm.id))


@router.get(
    "/farms/{farm_id}/finance/analytics",
    response_model=SuccessResponse[FinanceAnalytics],
    summary="Rolling analytics (7d/30d/90d/YTD/lifetime), per-unit economics, cost centres",
    tags=["Finance"],
)
async def finance_analytics(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[FinanceAnalytics]:
    farm, _ = access
    return SuccessResponse(data=await finance_analytics_service.get_analytics(db, farm.id))


@router.get(
    "/farms/{farm_id}/finance/transactions",
    response_model=SuccessResponse[TransactionPage],
    summary="Unified revenue + expense transactions (search / filter / sort / paginate)",
    tags=["Finance"],
)
async def finance_transactions(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
    q: str | None = Query(default=None),
    kind: str | None = Query(default=None, description="revenue | expense"),
    category_id: str | None = Query(default=None),
    revenue_type: str | None = Query(default=None),
    flock_id: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    min_amount: Decimal | None = Query(default=None),
    max_amount: Decimal | None = Query(default=None),
    sort: str = Query(default="date_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> SuccessResponse[TransactionPage]:
    farm, _ = access
    result = await finance_analytics_service.search_transactions(
        db, farm.id, q=q, kind=kind,
        category_id=UUID(category_id) if category_id else None,
        revenue_type=revenue_type,
        flock_id=UUID(flock_id) if flock_id else None,
        date_from=date_from, date_to=date_to,
        min_amount=min_amount, max_amount=max_amount,
        sort=sort, page=page, page_size=page_size,
    )
    return SuccessResponse(data=result)


@router.get(
    "/farms/{farm_id}/finance/cashflow",
    response_model=SuccessResponse[CashflowResponse],
    summary="Monthly cash flow (inflow / outflow / net / running balance)",
    tags=["Finance"],
)
async def finance_cashflow(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
    months: int = Query(default=12, ge=1, le=60),
) -> SuccessResponse[CashflowResponse]:
    farm, _ = access
    return SuccessResponse(data=await finance_analytics_service.get_cashflow(db, farm.id, months))


@router.get(
    "/farms/{farm_id}/finance/reports",
    response_model=SuccessResponse[FinanceReport],
    summary="Period report (monthly / quarterly / yearly)",
    tags=["Finance"],
)
async def finance_report(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
    period_type: str = Query(default="monthly", description="monthly | quarterly | yearly"),
    year: int = Query(default=date.today().year, ge=2000, le=2100),
    index: int = Query(default=date.today().month, ge=1, le=12,
                       description="Month (1-12) or quarter (1-4); ignored for yearly"),
) -> SuccessResponse[FinanceReport]:
    farm, _ = access
    report = await finance_analytics_service.get_report(db, farm.id, period_type, year, index)
    return SuccessResponse(data=report)


@router.get(
    "/farms/{farm_id}/finance/reports/csv",
    summary="Export transactions as CSV",
    tags=["Finance"],
)
async def finance_report_csv(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> Response:
    farm, _ = access
    csv_text = await finance_analytics_service.export_transactions_csv(db, farm.id, date_from, date_to)
    return Response(
        content=csv_text,
        media_type="text/csv",
        status_code=http_status.HTTP_200_OK,
        headers={"Content-Disposition": 'attachment; filename="finance_transactions.csv"'},
    )


@router.get(
    "/farms/{farm_id}/finance/ai-context",
    response_model=SuccessResponse[FinanceAIContext],
    summary="Structured finance intelligence for ARIA / Gemini",
    tags=["Finance"],
)
async def finance_ai_context(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FINANCE_VIEW)),
) -> SuccessResponse[FinanceAIContext]:
    farm, _ = access
    return SuccessResponse(data=await finance_analytics_service.get_ai_context(db, farm.id))
