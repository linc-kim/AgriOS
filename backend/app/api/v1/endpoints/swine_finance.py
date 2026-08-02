"""
Greena — Swine Sales & Finance API (Module 20, Milestone 8).

Swine finance is an analytics layer over the shared Finance engine. Sales are
recorded revenue facts (multiple sale types) that update the pig's status; operating
costs post to the shared expenses ledger (tagged module=swine); the P&L / unit
economics are computed on demand and never stored. Recording sales/expenses requires
SWINE_SALES_RECORD; sale reads SWINE_SALES_VIEW; the finance summary SWINE_FINANCE_VIEW.

Route map (prefix /farms/{farm_id}/swine/finance):
    GET/POST /sales        list / record sales (market/breeding/cull/piglet/transfer/…)
    POST     /expenses     post an operating cost to the shared ledger (tagged swine)
    GET      /summary      computed P&L + unit economics (cost/pig, cost/kg, ROI)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.swine import (
    OperationalExpenseCreate,
    SaleCreate,
    SaleResponse,
)
from app.services import swine_finance_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/finance", tags=["Swine Finance"])


@router.get("/sales", response_model=ListResponse[SaleResponse])
async def list_sales(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    sale_type: str | None = None, pig_id: UUID | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_SALES_VIEW)),
):
    farm, _ = access
    rows, total = await svc.list_sales(db, farm.id, sale_type=sale_type, pig_id=pig_id,
                                       limit=page_size, offset=(page - 1) * page_size)
    meta = PaginationMeta(total=total, page=page, limit=page_size,
                          pages=ceil(total / page_size) if page_size else 0)
    return ListResponse(data=[SaleResponse.model_validate(r) for r in rows], meta=meta)


@router.post("/sales", response_model=SuccessResponse[SaleResponse], status_code=status.HTTP_201_CREATED)
async def record_sale(
    farm_id: str, body: SaleCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_SALES_RECORD)),
):
    farm, _ = access
    row = await svc.record_sale(db, farm, body, current_user)
    return SuccessResponse(data=SaleResponse.model_validate(row))


@router.post("/expenses", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def post_expense(
    farm_id: str, body: OperationalExpenseCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_SALES_RECORD)),
):
    farm, _ = access
    expense = await svc.post_operational_expense(db, farm, body, current_user)
    return SuccessResponse(data={"id": str(expense.id), "amount": str(expense.amount),
                                 "category_id": str(expense.category_id) if expense.category_id else None,
                                 "module": "swine"})


@router.get("/summary", response_model=SuccessResponse[dict])
async def finance_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FINANCE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.finance_summary(db, farm.id))
