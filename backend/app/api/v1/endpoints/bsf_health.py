"""
Greena — BSF Mortality & Health API (Module 16, Part 5)

Mortality recording and the deterministic batch health picture (Spec Part 3 §17,
Part 4 §15). Farm-scoped and permission-guarded. The health engine flags abnormal
operational patterns; it never diagnoses disease.

Route map (prefix /farms/{farm_id}/bsf):
  POST /batches/{batch_id}/mortality           record mortality
  GET  /batches/{batch_id}/mortality           mortality history
  GET  /batches/{batch_id}/health              deterministic health summary
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import MortalityEventCreate, MortalityEventResponse
from app.services import bsf_mortality_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf", tags=["Black Soldier Fly"])


@router.post("/batches/{batch_id}/mortality", response_model=SuccessResponse[MortalityEventResponse],
             status_code=status.HTTP_201_CREATED)
async def record_mortality(
    farm_id: UUID, batch_id: UUID, body: MortalityEventCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    row = await svc.record_mortality(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=MortalityEventResponse.model_validate(row))


@router.get("/batches/{batch_id}/mortality", response_model=SuccessResponse[list[MortalityEventResponse]])
async def list_mortality(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
):
    rows = await svc.list_mortality(db, farm_id, batch_id)
    return SuccessResponse(data=[MortalityEventResponse.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/health", response_model=SuccessResponse[dict])
async def batch_health(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
):
    data = await svc.health_summary(db, farm_id, batch_id)
    return SuccessResponse(data=data)
