"""
Greena — Swine Housing API (Module 20, Milestone 2).

Herd → Group (dynamic membership) and Pen (physical, housed infrastructure).
Occupancy is derived on read via the pure engine; the farm summary aggregates
capacity vs recorded occupancy and surfaces overcrowding and flagged biosecurity.

Route map (prefix /farms/{farm_id}/swine/housing):
    GET/POST   /herds                     list / create herds
    PATCH      /herds/{herd_id}           edit a herd
    GET/POST   /groups                    list / create groups
    PATCH      /groups/{group_id}         edit a group
    GET        /groups/{group_id}         group + head count
    GET/POST   /pens                      list / create pens
    PATCH      /pens/{pen_id}             edit a pen
    GET        /pens/{pen_id}             pen + derived occupancy
    GET        /summary                   farm-wide housing roll-up
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    GroupCreate,
    GroupResponse,
    GroupUpdate,
    HerdCreate,
    HerdResponse,
    HerdUpdate,
    PenCreate,
    PenDetailResponse,
    PenResponse,
    PenUpdate,
)
from app.services import swine_housing_service as hsvc
from app.api.v1.endpoints.swine_animals import _MANAGER_ROLES

router = APIRouter(prefix="/farms/{farm_id}/swine/housing", tags=["Swine Housing"])


# ── Herds ────────────────────────────────────────────────────────────────────────

@router.get("/herds", response_model=SuccessResponse[list[HerdResponse]])
async def list_herds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_herds(db, farm.id)
    return SuccessResponse(data=[HerdResponse.model_validate(r) for r in rows])


@router.post("/herds", response_model=SuccessResponse[HerdResponse], status_code=status.HTTP_201_CREATED)
async def create_herd(
    farm_id: str, body: HerdCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_herd(db, farm, body, current_user)
    return SuccessResponse(data=HerdResponse.model_validate(row))


@router.patch("/herds/{herd_id}", response_model=SuccessResponse[HerdResponse])
async def update_herd(
    farm_id: str, herd_id: UUID, body: HerdUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_herd(db, farm.id, herd_id, body, current_user)
    return SuccessResponse(data=HerdResponse.model_validate(row))


# ── Groups ──────────────────────────────────────────────────────────────────────

@router.get("/groups", response_model=SuccessResponse[list[GroupResponse]])
async def list_groups(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    herd_id: UUID | None = None, group_type: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_groups(db, farm.id, herd_id=herd_id, group_type=group_type)
    return SuccessResponse(data=[GroupResponse.model_validate(r) for r in rows])


@router.post("/groups", response_model=SuccessResponse[GroupResponse], status_code=status.HTTP_201_CREATED)
async def create_group(
    farm_id: str, body: GroupCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_group(db, farm, body, current_user)
    return SuccessResponse(data=GroupResponse.model_validate(row))


@router.patch("/groups/{group_id}", response_model=SuccessResponse[GroupResponse])
async def update_group(
    farm_id: str, group_id: UUID, body: GroupUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_group(db, farm.id, group_id, body, current_user)
    return SuccessResponse(data=GroupResponse.model_validate(row))


@router.get("/groups/{group_id}", response_model=SuccessResponse[dict])
async def get_group(
    farm_id: str, group_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    group, occupancy = await hsvc.get_group_detail(db, farm.id, group_id)
    return SuccessResponse(data={"group": GroupResponse.model_validate(group).model_dump(mode="json"),
                                 "occupancy": occupancy})


# ── Pens ──────────────────────────────────────────────────────────────────────

@router.get("/pens", response_model=SuccessResponse[list[PenResponse]])
async def list_pens(
    farm_id: str, db: DBSession, current_user: CurrentUser, pen_type: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    rows = await hsvc.list_pens(db, farm.id, pen_type=pen_type)
    return SuccessResponse(data=[PenResponse.model_validate(r) for r in rows])


@router.post("/pens", response_model=SuccessResponse[PenResponse], status_code=status.HTTP_201_CREATED)
async def create_pen(
    farm_id: str, body: PenCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.create_pen(db, farm, body, current_user)
    return SuccessResponse(data=PenResponse.model_validate(row))


@router.patch("/pens/{pen_id}", response_model=SuccessResponse[PenResponse])
async def update_pen(
    farm_id: str, pen_id: UUID, body: PenUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_MANAGE)),
):
    farm, _ = access
    row = await hsvc.update_pen(db, farm.id, pen_id, body, current_user)
    return SuccessResponse(data=PenResponse.model_validate(row))


@router.get("/pens/{pen_id}", response_model=SuccessResponse[PenDetailResponse])
async def get_pen(
    farm_id: str, pen_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    pen, occupancy = await hsvc.get_pen_detail(db, farm.id, pen_id)
    return SuccessResponse(data=PenDetailResponse(**PenResponse.model_validate(pen).model_dump(),
                                                  occupancy=occupancy))


# ── Summary ──────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[dict])
async def housing_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HOUSING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await hsvc.housing_summary(db, farm.id))
