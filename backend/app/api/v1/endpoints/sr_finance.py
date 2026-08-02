"""
Greena — Small Ruminant Finance API (Modules 18/19, Milestone 8).

Sales (revenue facts) + operating-cost posting to the shared ledger + computed
P&L. Sale revenue is a recorded fact (DB-07); costs reuse the platform Finance
ledger tagged by species. Sales write → SR_SALES_RECORD; cost posting → platform
FINANCE_RECORD (owner/manager); reads → SR_SALES_VIEW / SR_FINANCE_VIEW.

Route map (prefix /farms/{farm_id}/sr/{species}/finance):
    GET/POST  /sales               list / record sales
    POST      /expenses            post an operating cost (shared ledger)
    GET       /summary             computed P&L + unit economics
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    OperationalExpenseCreate,
    SaleCreate,
    SaleResponse,
)
from app.services import small_ruminant_finance_service as fsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam, _MANAGER_ROLES

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/finance", tags=["Small Ruminant Finance"])


@router.get("/sales", response_model=SuccessResponse[list[SaleResponse]])
async def list_sales(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    sale_type: str | None = None, animal_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_SALES_VIEW)),
):
    farm, _ = access
    rows, _total = await fsvc.list_sales(db, farm.id, species, sale_type=sale_type, animal_id=animal_id,
                                         limit=limit, offset=offset)
    return SuccessResponse(data=[SaleResponse.model_validate(r) for r in rows])


@router.post("/sales", response_model=SuccessResponse[SaleResponse], status_code=status.HTTP_201_CREATED)
async def record_sale(
    farm_id: str, body: SaleCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_SALES_RECORD)),
):
    farm, _ = access
    sale = await fsvc.record_sale(db, farm, species, body, current_user)
    return SuccessResponse(data=SaleResponse.model_validate(sale))


@router.post("/expenses", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def post_expense(
    farm_id: str, body: OperationalExpenseCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.FINANCE_RECORD)),
):
    farm, _ = access
    expense = await fsvc.post_operational_expense(db, farm, species, body, current_user)
    return SuccessResponse(data={"expense_id": str(expense.id), "amount": str(expense.amount),
                                 "category_id": str(expense.category_id)})


@router.get("/summary", response_model=SuccessResponse[dict])
async def finance_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_FINANCE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await fsvc.finance_summary(db, farm.id, species))
