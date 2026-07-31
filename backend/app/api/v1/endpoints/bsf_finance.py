"""
Greena — BSF Finance & Sustainability API (Module 16, Part 5)

Reuses the platform Finance ledger (no BSF finance table). Costs post to the
SHARED expenses ledger tagged for BSF; the P&L is computed on demand from recorded
facts (harvest revenue + tagged ledger costs) with confirmed figures kept distinct
from any projection. Sustainability is composed from recorded feeding/harvest/frass
facts. See docs/MODULE_16_BSF_LEDGER.md → Integration Contract.

Route map (prefix /farms/{farm_id}/bsf):
  POST /feedstock-lots/{lot_id}/post-expense   post a lot's cost to the ledger (idempotent)
  POST /finance/expenses                        post a BSF operational cost
  GET  /finance/summary                         computed BSF P&L
  GET  /analytics/sustainability                sustainability metrics
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import OperationalExpenseCreate
from app.services import bsf_analytics_service as analytics
from app.services import bsf_finance_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf", tags=["Black Soldier Fly"])

_MANAGER_ROLES = {"farm_owner", "farm_manager", "enterprise_owner"}


@router.post("/feedstock-lots/{lot_id}/post-expense", response_model=SuccessResponse[dict],
             status_code=status.HTTP_201_CREATED)
async def post_feedstock_expense(
    farm_id: UUID, lot_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.BSF_FEED_RECORD)),
):
    expense = await svc.post_feedstock_expense(db, farm_id, lot_id, current_user)
    return SuccessResponse(data={"expense_id": str(expense.id), "amount": str(expense.amount)})


@router.post("/finance/expenses", response_model=SuccessResponse[dict],
             status_code=status.HTTP_201_CREATED)
async def post_operational_expense(
    farm_id: UUID, body: OperationalExpenseCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.BSF_FEED_RECORD)),
):
    expense = await svc.post_operational_expense(db, farm_id, body, current_user)
    return SuccessResponse(data={"expense_id": str(expense.id), "amount": str(expense.amount)})


@router.get("/finance/summary", response_model=SuccessResponse[dict])
async def finance_summary(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FINANCE_VIEW)),
):
    data = await svc.finance_summary(db, farm_id)
    return SuccessResponse(data=data)


@router.get("/analytics/sustainability", response_model=SuccessResponse[dict])
async def sustainability(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_REPORT_VIEW)),
):
    data = await analytics.sustainability_summary(db, farm_id)
    return SuccessResponse(data=data)
