"""
Greena — Aviculture Finance API (Module 15, Part 7)

Collection valuations and the computed aviculture finance summary. Operational
costs post to the SHARED finance ledger (reuse — no aviculture expense table);
feed/medication/equipment/suppliers reuse the existing Inventory module. Every
derived figure is honesty-labelled by the pure valuation engine.

Prefix: /farms/{farm_id}/aviculture
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.aviculture_finance import (
    CollectionValuationResponse, FinanceSummaryResponse, PurchaseExpenseCreate,
    ValuationCreate, ValuationResponse,
)
from app.services import aviculture_finance_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture — Finance"])

_MANAGE = {"farm_owner", "farm_manager"}


@router.post("/valuations", response_model=SuccessResponse[ValuationResponse], status_code=status.HTTP_201_CREATED)
async def record_valuation(farm_id: str, body: ValuationCreate, db: DBSession, current_user: CurrentUser,
                           access: tuple = Depends(require_farm_access(_MANAGE)),
                           _perm=Depends(require_permission(Permission.AVI_FINANCE_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=ValuationResponse.model_validate(await svc.record_valuation(db, farm, body, current_user)))


@router.get("/valuations", response_model=SuccessResponse[list[ValuationResponse]])
async def list_valuations(farm_id: str, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _perm=Depends(require_permission(Permission.AVI_FINANCE_VIEW)),
                          bird_id: UUID | None = Query(None)):
    farm, _ = access
    rows = await svc.list_valuations(db, farm.id, bird_id)
    return SuccessResponse(data=[ValuationResponse.model_validate(v) for v in rows])


@router.post("/expenses", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def post_expense(farm_id: str, body: PurchaseExpenseCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_MANAGE)),
                       _perm=Depends(require_permission(Permission.AVI_FINANCE_MANAGE))):
    farm, _ = access
    expense = await svc.record_purchase_expense(db, farm, body, current_user)
    return SuccessResponse(data={"expense_id": str(expense.id), "amount": str(expense.amount),
                                 "category_id": str(expense.category_id)})


@router.get("/finance/valuation", response_model=SuccessResponse[CollectionValuationResponse])
async def collection_valuation(farm_id: str, db: DBSession, current_user: CurrentUser,
                               access: tuple = Depends(require_farm_access()),
                               _perm=Depends(require_permission(Permission.AVI_FINANCE_VIEW))):
    farm, _ = access
    return SuccessResponse(data=CollectionValuationResponse.model_validate(await svc.collection_valuation(db, farm.id)))


@router.get("/finance/summary", response_model=SuccessResponse[FinanceSummaryResponse])
async def finance_summary(farm_id: str, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _perm=Depends(require_permission(Permission.AVI_FINANCE_VIEW))):
    farm, _ = access
    return SuccessResponse(data=FinanceSummaryResponse.model_validate(await svc.finance_summary(db, farm.id)))
