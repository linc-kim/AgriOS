"""
Greena — Small Ruminant Wool API (Modules 18/19, Milestone 7, Sheep wool).

Shearing sessions + per-animal fleece records for wool sheep. Availability is gated
by the species ``produces_wool`` capability — the service returns 422 for a
non-wool workspace (goats). Wool writes require SR_WOOL_RECORD; reads SR_WOOL_VIEW.
Clean weight / value / micron grade are computed deterministically.

Route map (prefix /farms/{farm_id}/sr/{species}/wool):
    GET/POST  /shearings                      shearing sessions (+ optional fleeces)
    POST      /shearings/{shearing_id}/fleeces add a fleece to a session
    GET       /fleeces                          fleece records
    GET       /fleeces/{fleece_id}/analysis     per-fleece analysis (clean/value/grade)
    GET       /summary                          flock wool-clip roll-up
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    FleeceCreate,
    FleeceResponse,
    ShearingCreate,
    ShearingResponse,
)
from app.services import small_ruminant_wool_service as wsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/wool", tags=["Small Ruminant Wool"])

_RECORD = Depends(require_permission(Permission.SR_WOOL_RECORD))
_VIEW = Depends(require_permission(Permission.SR_WOOL_VIEW))


@router.get("/shearings", response_model=SuccessResponse[list[ShearingResponse]])
async def list_shearings(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await wsvc.list_shearings(db, farm.id, species)
    return SuccessResponse(data=[ShearingResponse.model_validate(r) for r in rows])


@router.post("/shearings", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def record_shearing(
    farm_id: str, body: ShearingCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_RECORD,
):
    farm, _ = access
    sh, fleeces = await wsvc.record_shearing(db, farm, species, body, current_user)
    return SuccessResponse(data={"shearing": ShearingResponse.model_validate(sh).model_dump(mode="json"),
                                 "fleeces_created": fleeces})


@router.post("/shearings/{shearing_id}/fleeces", response_model=SuccessResponse[FleeceResponse],
             status_code=status.HTTP_201_CREATED)
async def add_fleece(
    farm_id: str, shearing_id: UUID, body: FleeceCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_RECORD,
):
    farm, _ = access
    fleece = await wsvc.add_fleece(db, farm, species, shearing_id, body, current_user)
    return SuccessResponse(data=FleeceResponse.model_validate(fleece))


@router.get("/fleeces", response_model=SuccessResponse[list[FleeceResponse]])
async def list_fleeces(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    animal_id: UUID | None = None, shearing_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await wsvc.list_fleeces(db, farm.id, species, animal_id=animal_id, shearing_id=shearing_id)
    return SuccessResponse(data=[FleeceResponse.model_validate(r) for r in rows])


@router.get("/fleeces/{fleece_id}/analysis", response_model=SuccessResponse[dict])
async def fleece_analysis(
    farm_id: str, fleece_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    price_per_kg: float | None = Query(None, ge=0),
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await wsvc.fleece_analysis(db, farm.id, species, fleece_id, price_per_kg))


@router.get("/summary", response_model=SuccessResponse[dict])
async def wool_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    price_per_kg: float | None = Query(None, ge=0),
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await wsvc.wool_summary(db, farm.id, species, price_per_kg))
