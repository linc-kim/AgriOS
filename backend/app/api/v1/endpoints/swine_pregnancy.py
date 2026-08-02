"""
Greena — Swine Pregnancy API (Module 20, Milestone 3).

Pregnancy is a lifecycle stage confirmed from a breeding — its own workspace, not a
breeding event. Confirmation happens via the breeding pregnancy-check; this endpoint
manages the ongoing pregnancy: the due calendar, rechecks, and loss / false
pregnancy. Reads require SWINE_BREEDING_VIEW; writes SWINE_BREEDING_MANAGE.

Route map (prefix /farms/{farm_id}/swine/pregnancy):
    GET   /                          list pregnancies (default active; filter status/risk)
    GET   /{pregnancy_id}            detail + deterministic gestation progress
    POST  /{pregnancy_id}/recheck    update risk / expected date
    POST  /{pregnancy_id}/loss       record loss / abortion / false pregnancy
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    PregnancyLossInput,
    PregnancyRecheckInput,
    PregnancyResponse,
)
from app.services import swine_pregnancy_service as psvc

router = APIRouter(prefix="/farms/{farm_id}/swine/pregnancy", tags=["Swine Pregnancy"])


@router.get("", response_model=SuccessResponse[list[PregnancyResponse]])
async def list_pregnancies(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    status_: str | None = None, risk_level: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await psvc.list_pregnancies(db, farm.id, status=status_, risk_level=risk_level)
    return SuccessResponse(data=[PregnancyResponse.model_validate(r) for r in rows])


@router.get("/{pregnancy_id}", response_model=SuccessResponse[dict])
async def get_pregnancy(
    farm_id: str, pregnancy_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    pregnancy, progress = await psvc.get_pregnancy_detail(db, farm.id, pregnancy_id)
    return SuccessResponse(data={
        "pregnancy": PregnancyResponse.model_validate(pregnancy).model_dump(mode="json"),
        "gestation_progress": progress,
    })


@router.post("/{pregnancy_id}/recheck", response_model=SuccessResponse[PregnancyResponse])
async def recheck(
    farm_id: str, pregnancy_id: UUID, body: PregnancyRecheckInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    p = await psvc.recheck(db, farm.id, pregnancy_id, body, current_user)
    return SuccessResponse(data=PregnancyResponse.model_validate(p))


@router.post("/{pregnancy_id}/loss", response_model=SuccessResponse[PregnancyResponse])
async def record_loss(
    farm_id: str, pregnancy_id: UUID, body: PregnancyLossInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    p = await psvc.record_loss(db, farm.id, pregnancy_id, body, current_user)
    return SuccessResponse(data=PregnancyResponse.model_validate(p))
