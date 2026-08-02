"""
Greena — Small Ruminant Growth & Feed API (Modules 18/19, Milestone 4).

Immutable weight history (kg) + deterministic growth analysis, and a feeding log
that reuses platform Inventory. Weight writes require SR_WEIGHT_LOG; feed writes
SR_FEED_RECORD; reads SR_VIEW / SR_FEED_VIEW.

Route map (prefix /farms/{farm_id}/sr/{species}):
    POST   /animals/{animal_id}/weights        record a weight
    GET    /animals/{animal_id}/weights        weight history
    GET    /animals/{animal_id}/growth         deterministic growth analysis
    POST   /feed                               record a feeding (optional Inventory)
    GET    /feed                               feeding log
    GET    /feed/summary                       feed summary + FCR
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    FeedRecordCreate,
    FeedRecordResponse,
    WeightCreate,
    WeightResponse,
)
from app.services import small_ruminant_feed_service as fsvc
from app.services import small_ruminant_growth_service as gsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}", tags=["Small Ruminant Growth & Feed"])


@router.post("/animals/{animal_id}/weights", response_model=SuccessResponse[WeightResponse],
             status_code=status.HTTP_201_CREATED)
async def record_weight(
    farm_id: str, animal_id: UUID, body: WeightCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_WEIGHT_LOG)),
):
    farm, _ = access
    w = await gsvc.record_weight(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=WeightResponse.model_validate(w))


@router.get("/animals/{animal_id}/weights", response_model=SuccessResponse[list[WeightResponse]])
async def list_weights(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    rows = await gsvc.list_weights(db, farm.id, species, animal_id)
    return SuccessResponse(data=[WeightResponse.model_validate(r) for r in rows])


@router.get("/animals/{animal_id}/growth", response_model=SuccessResponse[dict])
async def growth_analysis(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await gsvc.growth_analysis(db, farm.id, species, animal_id))


@router.post("/feed", response_model=SuccessResponse[FeedRecordResponse], status_code=status.HTTP_201_CREATED)
async def record_feeding(
    farm_id: str, body: FeedRecordCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_FEED_RECORD)),
):
    farm, _ = access
    r = await fsvc.record_feeding(db, farm, species, body, current_user)
    return SuccessResponse(data=FeedRecordResponse.model_validate(r))


@router.get("/feed", response_model=SuccessResponse[list[FeedRecordResponse]])
async def list_feeding(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    animal_id: UUID | None = None, group_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_FEED_VIEW)),
):
    farm, _ = access
    rows, _total = await fsvc.list_feeding(db, farm.id, species, animal_id=animal_id, group_id=group_id,
                                           limit=limit, offset=offset)
    return SuccessResponse(data=[FeedRecordResponse.model_validate(r) for r in rows])


@router.get("/feed/summary", response_model=SuccessResponse[dict])
async def feed_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    animal_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_FEED_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await fsvc.feed_summary(db, farm.id, species, animal_id))
