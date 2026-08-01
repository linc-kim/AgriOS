"""
Greena — Rabbit Sales & Finance API (Module 17, Milestone 6).

Sales (revenue as a recorded fact) and the computed rabbit P&L. Operational costs
reuse the SHARED Finance ledger; no rabbit finance table for costs (ledger CON-M6).

Route map (prefix /farms/{farm_id}/rabbit):
  POST   /sales                 record a sale (RABBIT_SALES_RECORD)
  GET    /sales                 list sales (RABBIT_SALES_VIEW)
  POST   /finance/expenses      post an operating cost to the shared ledger (FINANCE_RECORD)
  GET    /finance/summary       computed P&L + unit economics (RABBIT_FINANCE_VIEW)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.rabbit import (
    OperationalExpenseCreate,
    SaleCreate,
    SaleResponse,
)
from app.services import rabbit_finance_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit", tags=["Rabbit Finance"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}


# ── Sales ────────────────────────────────────────────────────────────────────────

@router.post("/sales", response_model=SuccessResponse[SaleResponse], status_code=status.HTTP_201_CREATED)
async def record_sale(
    farm_id: str, body: SaleCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_SALES_RECORD)),
):
    farm, _ = access
    row = await svc.record_sale(db, farm, body, current_user)
    return SuccessResponse(data=SaleResponse.model_validate(row))


@router.get("/sales", response_model=ListResponse[SaleResponse])
async def list_sales(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_SALES_VIEW)),
    sale_type: str | None = Query(None),
    rabbit_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    farm, _ = access
    rows, total = await svc.list_sales(
        db, farm.id, sale_type=sale_type, rabbit_id=rabbit_id, limit=limit, offset=(page - 1) * limit
    )
    return ListResponse(
        data=[SaleResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 1),
    )


# ── Finance (shared-ledger reuse) ──────────────────────────────────────────────

@router.post("/finance/expenses", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def post_operational_expense(
    farm_id: str, body: OperationalExpenseCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
):
    farm, _ = access
    expense = await svc.post_operational_expense(db, farm, body, current_user)
    return SuccessResponse(data={"expense_id": str(expense.id), "amount": str(expense.amount),
                                 "category_id": str(expense.category_id)})


@router.get("/finance/summary", response_model=SuccessResponse[dict])
async def finance_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_FINANCE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.finance_summary(db, farm.id))
