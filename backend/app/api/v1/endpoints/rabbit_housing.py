"""
Greena — Rabbit Housing API (Module 17): the 5-level housing hierarchy.

Rabbitry → Building → Room → Row → Cage (Spec Part 1 §6). Every route is
farm-scoped and permission-guarded. Occupancy/capacity figures come from the
pure Housing Capacity engine — never stored (Spec Part 3 §14).

Route map (prefix /farms/{farm_id}/rabbit/housing):
  GET/POST   /rabbitries              PATCH /rabbitries/{id}
  GET/POST   /buildings               PATCH /buildings/{id}
  GET/POST   /rooms                   PATCH /rooms/{id}
  GET/POST   /rows                    PATCH /rows/{id}
  GET/POST   /cages                   PATCH /cages/{id}
  GET        /cages/{id}              cage + deterministic occupancy
  GET        /summary                 farm-wide capacity roll-up & overcrowding
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.rabbit import (
    BuildingCreate,
    BuildingResponse,
    BuildingUpdate,
    CageCreate,
    CageDetailResponse,
    CageResponse,
    CageUpdate,
    RabbitryCreate,
    RabbitryResponse,
    RabbitryUpdate,
    RoomCreate,
    RoomResponse,
    RoomUpdate,
    RowCreate,
    RowResponse,
    RowUpdate,
)
from app.services import rabbit_housing_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit/housing", tags=["Rabbit Housing"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}
_VIEW = Permission.RABBIT_HOUSING_VIEW
_MANAGE = Permission.RABBIT_HOUSING_MANAGE


# ── Rabbitries ──────────────────────────────────────────────────────────────────

@router.get("/rabbitries", response_model=SuccessResponse[list[RabbitryResponse]])
async def list_rabbitries(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    rows = await svc.list_rabbitries(db, farm.id)
    return SuccessResponse(data=[RabbitryResponse.model_validate(r) for r in rows])


@router.post("/rabbitries", response_model=SuccessResponse[RabbitryResponse], status_code=status.HTTP_201_CREATED)
async def create_rabbitry(
    farm_id: str, body: RabbitryCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_rabbitry(db, farm, body, current_user)
    return SuccessResponse(data=RabbitryResponse.model_validate(row))


@router.patch("/rabbitries/{obj_id}", response_model=SuccessResponse[RabbitryResponse])
async def update_rabbitry(
    farm_id: str, obj_id: UUID, body: RabbitryUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.update_rabbitry(db, farm.id, obj_id, body, current_user)
    return SuccessResponse(data=RabbitryResponse.model_validate(row))


# ── Buildings ────────────────────────────────────────────────────────────────────

@router.get("/buildings", response_model=SuccessResponse[list[BuildingResponse]])
async def list_buildings(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    rabbitry_id: UUID | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_buildings(db, farm.id, rabbitry_id)
    return SuccessResponse(data=[BuildingResponse.model_validate(r) for r in rows])


@router.post("/buildings", response_model=SuccessResponse[BuildingResponse], status_code=status.HTTP_201_CREATED)
async def create_building(
    farm_id: str, body: BuildingCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_building(db, farm, body, current_user)
    return SuccessResponse(data=BuildingResponse.model_validate(row))


@router.patch("/buildings/{obj_id}", response_model=SuccessResponse[BuildingResponse])
async def update_building(
    farm_id: str, obj_id: UUID, body: BuildingUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.update_building(db, farm.id, obj_id, body, current_user)
    return SuccessResponse(data=BuildingResponse.model_validate(row))


# ── Rooms ─────────────────────────────────────────────────────────────────────────

@router.get("/rooms", response_model=SuccessResponse[list[RoomResponse]])
async def list_rooms(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    building_id: UUID | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_rooms(db, farm.id, building_id)
    return SuccessResponse(data=[RoomResponse.model_validate(r) for r in rows])


@router.post("/rooms", response_model=SuccessResponse[RoomResponse], status_code=status.HTTP_201_CREATED)
async def create_room(
    farm_id: str, body: RoomCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_room(db, farm, body, current_user)
    return SuccessResponse(data=RoomResponse.model_validate(row))


@router.patch("/rooms/{obj_id}", response_model=SuccessResponse[RoomResponse])
async def update_room(
    farm_id: str, obj_id: UUID, body: RoomUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.update_room(db, farm.id, obj_id, body, current_user)
    return SuccessResponse(data=RoomResponse.model_validate(row))


# ── Rows ───────────────────────────────────────────────────────────────────────────

@router.get("/rows", response_model=SuccessResponse[list[RowResponse]])
async def list_rows(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    room_id: UUID | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_rows(db, farm.id, room_id)
    return SuccessResponse(data=[RowResponse.model_validate(r) for r in rows])


@router.post("/rows", response_model=SuccessResponse[RowResponse], status_code=status.HTTP_201_CREATED)
async def create_row(
    farm_id: str, body: RowCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_row(db, farm, body, current_user)
    return SuccessResponse(data=RowResponse.model_validate(row))


@router.patch("/rows/{obj_id}", response_model=SuccessResponse[RowResponse])
async def update_row(
    farm_id: str, obj_id: UUID, body: RowUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.update_row(db, farm.id, obj_id, body, current_user)
    return SuccessResponse(data=RowResponse.model_validate(row))


# ── Cages ──────────────────────────────────────────────────────────────────────────

@router.get("/cages", response_model=SuccessResponse[list[CageResponse]])
async def list_cages(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    row_id: UUID | None = Query(None),
    cage_type: str | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_cages(db, farm.id, row_id, cage_type)
    return SuccessResponse(data=[CageResponse.model_validate(r) for r in rows])


@router.post("/cages", response_model=SuccessResponse[CageResponse], status_code=status.HTTP_201_CREATED)
async def create_cage(
    farm_id: str, body: CageCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_cage(db, farm, body, current_user)
    return SuccessResponse(data=CageResponse.model_validate(row))


@router.get("/cages/{obj_id}", response_model=SuccessResponse[CageDetailResponse])
async def get_cage(
    farm_id: str, obj_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    cage, occupancy = await svc.get_cage_detail(db, farm.id, obj_id)
    return SuccessResponse(data=CageDetailResponse(**CageResponse.model_validate(cage).model_dump(), occupancy=occupancy))


@router.patch("/cages/{obj_id}", response_model=SuccessResponse[CageResponse])
async def update_cage(
    farm_id: str, obj_id: UUID, body: CageUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.update_cage(db, farm.id, obj_id, body, current_user)
    return SuccessResponse(data=CageResponse.model_validate(row))


# ── Summary (Housing workspace + Mission Control) ────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[dict])
async def housing_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.housing_summary(db, farm.id))
