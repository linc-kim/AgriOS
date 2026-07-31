"""
Greena — BSF Environment API (Module 16, Part 3)

Environmental readings and deterministic threshold assessments. Farm-scoped and
permission-guarded.

Route map (prefix /farms/{farm_id}/bsf):
  GET/POST  /environment/readings                 list / record readings
  GET       /environment/units/{unit_id}/assessment  latest assessment + stability
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import (
    EnvironmentalReadingCreate,
    EnvironmentalReadingResponse,
    EnvironmentalReadingResult,
)
from app.services import bsf_environment_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf/environment", tags=["Black Soldier Fly"])


@router.get("/readings", response_model=SuccessResponse[list[EnvironmentalReadingResponse]])
async def list_readings(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_ENVIRONMENT_VIEW)),
    production_unit_id: UUID | None = Query(None),
    batch_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    rows = await svc.list_readings(
        db, farm_id, production_unit_id=production_unit_id, batch_id=batch_id, limit=limit,
    )
    return SuccessResponse(data=[EnvironmentalReadingResponse.model_validate(r) for r in rows])


@router.post("/readings", response_model=SuccessResponse[EnvironmentalReadingResult],
             status_code=status.HTTP_201_CREATED)
async def record_reading(
    farm_id: UUID, body: EnvironmentalReadingCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_ENVIRONMENT_RECORD)),
):
    reading, assessment = await svc.record_reading(db, farm_id, body, current_user)
    return SuccessResponse(data=EnvironmentalReadingResult(
        reading=EnvironmentalReadingResponse.model_validate(reading), assessment=assessment,
    ))


@router.get("/units/{unit_id}/assessment", response_model=SuccessResponse[dict])
async def unit_assessment(
    farm_id: UUID, unit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_ENVIRONMENT_VIEW)),
):
    data = await svc.unit_assessment(db, farm_id, unit_id)
    return SuccessResponse(data=data)
