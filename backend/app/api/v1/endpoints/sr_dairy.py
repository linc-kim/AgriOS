"""
Greena — Small Ruminant Dairy API (Modules 18/19, Milestone 6, Goat dairy).

Lactation cycles + milk records for dairy females. Availability is gated by the
species ``produces_milk`` capability (goats primarily; dairy sheep too) — the
service returns 422 for a non-dairy workspace. Dairy writes require
SR_DAIRY_RECORD; reads SR_DAIRY_VIEW.

Route map (prefix /farms/{farm_id}/sr/{species}/dairy):
    GET       /lactations                                lactation cycles
    POST      /animals/{animal_id}/lactations            start a lactation
    POST      /lactations/{lactation_id}/dry-off         dry off
    GET       /lactations/{lactation_id}/metrics         yield/stage/dry-off advisory
    POST      /animals/{animal_id}/milk                  record milk
    GET       /milk                                      milk records
    GET       /summary                                   herd dairy roll-up
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    LactationDryOffInput,
    LactationResponse,
    LactationStartInput,
    MilkRecordCreate,
    MilkRecordResponse,
)
from app.services import small_ruminant_dairy_service as dsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/dairy", tags=["Small Ruminant Dairy"])

_RECORD = Depends(require_permission(Permission.SR_DAIRY_RECORD))
_VIEW = Depends(require_permission(Permission.SR_DAIRY_VIEW))


@router.get("/lactations", response_model=SuccessResponse[list[LactationResponse]])
async def list_lactations(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    animal_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await dsvc.list_lactations(db, farm.id, species, animal_id)
    return SuccessResponse(data=[LactationResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/lactations", response_model=SuccessResponse[LactationResponse],
             status_code=status.HTTP_201_CREATED)
async def start_lactation(
    farm_id: str, animal_id: UUID, body: LactationStartInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_RECORD,
):
    farm, _ = access
    lac = await dsvc.start_lactation(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=LactationResponse.model_validate(lac))


@router.post("/lactations/{lactation_id}/dry-off", response_model=SuccessResponse[LactationResponse])
async def dry_off(
    farm_id: str, lactation_id: UUID, body: LactationDryOffInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_RECORD,
):
    farm, _ = access
    lac = await dsvc.dry_off(db, farm, species, lactation_id, body.dry_off_date, current_user)
    return SuccessResponse(data=LactationResponse.model_validate(lac))


@router.get("/lactations/{lactation_id}/metrics", response_model=SuccessResponse[dict])
async def lactation_metrics(
    farm_id: str, lactation_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await dsvc.lactation_metrics(db, farm.id, species, lactation_id))


@router.post("/animals/{animal_id}/milk", response_model=SuccessResponse[MilkRecordResponse],
             status_code=status.HTTP_201_CREATED)
async def record_milk(
    farm_id: str, animal_id: UUID, body: MilkRecordCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_RECORD,
):
    farm, _ = access
    rec = await dsvc.record_milk(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=MilkRecordResponse.model_validate(rec))


@router.get("/milk", response_model=SuccessResponse[list[MilkRecordResponse]])
async def list_milk(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    animal_id: UUID | None = None, lactation_id: UUID | None = None,
    limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await dsvc.list_milk(db, farm.id, species, animal_id=animal_id, lactation_id=lactation_id,
                                limit=limit, offset=offset)
    return SuccessResponse(data=[MilkRecordResponse.model_validate(r) for r in rows])


@router.get("/summary", response_model=SuccessResponse[dict])
async def dairy_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await dsvc.dairy_summary(db, farm.id, species))
