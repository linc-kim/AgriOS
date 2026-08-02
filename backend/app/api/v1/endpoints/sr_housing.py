"""
Greena — Small Ruminant Housing API (Modules 18/19, Milestone 2).

Herd/Flock → Group (species-scoped) and Pen / Pasture (species-neutral physical
infrastructure). Occupancy is derived on read via the pure engine; the farm
summary aggregates capacity vs recorded occupancy and surfaces overcrowding.

Route map (prefix /farms/{farm_id}/sr/{species}/housing):
    GET/POST   /herds                     list / create herds (flocks)
    PATCH      /herds/{herd_id}           edit a herd
    GET/POST   /groups                    list / create groups
    PATCH      /groups/{group_id}         edit a group
    GET        /groups/{group_id}         group + head count
    GET/POST   /pens                      list / create pens
    PATCH      /pens/{pen_id}             edit a pen
    GET        /pens/{pen_id}             pen + derived occupancy
    GET/POST   /pastures                  list / create pastures
    PATCH      /pastures/{pasture_id}     edit a pasture
    GET        /pastures/{pasture_id}     pasture + derived occupancy
    GET        /summary                   farm-wide housing roll-up
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    HerdCreate,
    HerdResponse,
    HerdUpdate,
    PastureCreate,
    PastureDetailResponse,
    PastureResponse,
    PastureUpdate,
    PenCreate,
    PenDetailResponse,
    PenResponse,
    PenUpdate,
)
from app.services import small_ruminant_housing_service as hsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam, _MANAGER_ROLES

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/housing", tags=["Small Ruminant Housing"])


# ── Herds / Flocks ──────────────────────────────────────────────────────────────

@router.get("/herds", response_model=SuccessResponse[list[HerdResponse]])
async def list_herds(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_herds(db, farm.id, species)
    return SuccessResponse(data=[HerdResponse.model_validate(r) for r in rows])


@router.post("/herds", response_model=SuccessResponse[HerdResponse], status_code=status.HTTP_201_CREATED)
async def create_herd(
    farm_id: str, body: HerdCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_herd(db, farm, species, body, current_user)
    return SuccessResponse(data=HerdResponse.model_validate(row))


@router.patch("/herds/{herd_id}", response_model=SuccessResponse[HerdResponse])
async def update_herd(
    farm_id: str, herd_id: UUID, body: HerdUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_herd(db, farm.id, species, herd_id, body, current_user)
    return SuccessResponse(data=HerdResponse.model_validate(row))


# ── Groups ──────────────────────────────────────────────────────────────────────

@router.get("/groups", response_model=SuccessResponse[list[GroupResponse]])
async def list_groups(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    herd_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_groups(db, farm.id, species, herd_id=herd_id)
    return SuccessResponse(data=[GroupResponse.model_validate(r) for r in rows])


@router.post("/groups", response_model=SuccessResponse[GroupResponse], status_code=status.HTTP_201_CREATED)
async def create_group(
    farm_id: str, body: GroupCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_group(db, farm, species, body, current_user)
    return SuccessResponse(data=GroupResponse.model_validate(row))


@router.patch("/groups/{group_id}", response_model=SuccessResponse[GroupResponse])
async def update_group(
    farm_id: str, group_id: UUID, body: GroupUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_group(db, farm.id, species, group_id, body, current_user)
    return SuccessResponse(data=GroupResponse.model_validate(row))


@router.get("/groups/{group_id}", response_model=SuccessResponse[dict])
async def get_group(
    farm_id: str, group_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    group, occupancy = await hsvc.get_group_detail(db, farm.id, species, group_id)
    return SuccessResponse(data={"group": GroupResponse.model_validate(group).model_dump(mode="json"),
                                 "occupancy": occupancy})


# ── Pens (species-neutral) ───────────────────────────────────────────────────────

@router.get("/pens", response_model=SuccessResponse[list[PenResponse]])
async def list_pens(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    pen_type: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_pens(db, farm.id, pen_type=pen_type)
    return SuccessResponse(data=[PenResponse.model_validate(r) for r in rows])


@router.post("/pens", response_model=SuccessResponse[PenResponse], status_code=status.HTTP_201_CREATED)
async def create_pen(
    farm_id: str, body: PenCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_pen(db, farm, body, current_user)
    return SuccessResponse(data=PenResponse.model_validate(row))


@router.patch("/pens/{pen_id}", response_model=SuccessResponse[PenResponse])
async def update_pen(
    farm_id: str, pen_id: UUID, body: PenUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_pen(db, farm.id, pen_id, body, current_user)
    return SuccessResponse(data=PenResponse.model_validate(row))


@router.get("/pens/{pen_id}", response_model=SuccessResponse[PenDetailResponse])
async def get_pen(
    farm_id: str, pen_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    pen, occupancy = await hsvc.get_pen_detail(db, farm.id, pen_id)
    return SuccessResponse(data=PenDetailResponse(**PenResponse.model_validate(pen).model_dump(),
                                                  occupancy=occupancy))


# ── Pastures (species-neutral) ───────────────────────────────────────────────────

@router.get("/pastures", response_model=SuccessResponse[list[PastureResponse]])
async def list_pastures(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    status_: str | None = Query(None, alias="status"),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_pastures(db, farm.id, status=status_)
    return SuccessResponse(data=[PastureResponse.model_validate(r) for r in rows])


@router.post("/pastures", response_model=SuccessResponse[PastureResponse], status_code=status.HTTP_201_CREATED)
async def create_pasture(
    farm_id: str, body: PastureCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_pasture(db, farm, body, current_user)
    return SuccessResponse(data=PastureResponse.model_validate(row))


@router.patch("/pastures/{pasture_id}", response_model=SuccessResponse[PastureResponse])
async def update_pasture(
    farm_id: str, pasture_id: UUID, body: PastureUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_pasture(db, farm.id, pasture_id, body, current_user)
    return SuccessResponse(data=PastureResponse.model_validate(row))


@router.get("/pastures/{pasture_id}", response_model=SuccessResponse[PastureDetailResponse])
async def get_pasture(
    farm_id: str, pasture_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    pasture, occupancy = await hsvc.get_pasture_detail(db, farm.id, pasture_id)
    return SuccessResponse(data=PastureDetailResponse(**PastureResponse.model_validate(pasture).model_dump(),
                                                      occupancy=occupancy))


# ── Summary ──────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[dict])
async def housing_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_HOUSING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await hsvc.housing_summary(db, farm.id, species))
