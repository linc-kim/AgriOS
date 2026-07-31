"""
Greena — Black Soldier Fly API (Module 16)

Batch-centric insect-farming operations. Every route is farm-scoped and
permission-guarded, reusing the platform's ``require_farm_access`` +
``require_permission`` dependencies. The species catalog is organisation-level
and derives the org from the farm.

Route map (prefix /farms/{farm_id}/bsf):
  Catalog
    GET/POST  /species                          list / create BSF species
  Production units
    GET/POST  /production-units                 list / create
    GET/PATCH /production-units/{unit_id}        detail / edit
  Colonies
    GET/POST  /colonies                          list / create
    GET/PATCH /colonies/{colony_id}              detail / edit
  Batches
    POST      /batches                           create
    GET       /batches                           list (filters + pagination)
    GET       /batches/{batch_id}                detail (+ metrics, pacing)
    PATCH     /batches/{batch_id}                edit
    POST      /batches/{batch_id}/advance        advance lifecycle stage
    POST      /batches/{batch_id}/move           move to a production unit
    POST      /batches/{batch_id}/split          split into child batches
    POST      /batches/merge                     merge batches
    POST      /batches/{batch_id}/terminate      terminate
    GET       /batches/{batch_id}/lifecycle      lifecycle history
    GET       /batches/{batch_id}/timeline       batch event timeline
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.bsf import (
    BatchAdvanceInput,
    BatchCreate,
    BatchDetailResponse,
    BatchEventResponse,
    BatchMergeInput,
    BatchMoveInput,
    BatchResponse,
    BatchSplitInput,
    BatchTerminateInput,
    BatchUpdate,
    ColonyCreate,
    ColonyResponse,
    ColonyUpdate,
    LifecycleEventResponse,
    ProductionUnitCreate,
    ProductionUnitResponse,
    ProductionUnitUpdate,
    SpeciesCreate,
    SpeciesResponse,
)
from app.services import bsf_batch_service as batch_svc
from app.services import bsf_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf", tags=["Black Soldier Fly"])

_MANAGER_ROLES = {"farm_owner", "farm_manager", "enterprise_owner"}


# ── Catalog ───────────────────────────────────────────────────────────────────

@router.get("/species", response_model=SuccessResponse[list[SpeciesResponse]])
async def list_species(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_species(db, farm.organization_id)
    return SuccessResponse(data=[SpeciesResponse.model_validate(r) for r in rows])


@router.post("/species", response_model=SuccessResponse[SpeciesResponse], status_code=status.HTTP_201_CREATED)
async def create_species(
    farm_id: str, body: SpeciesCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.BSF_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_species(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=SpeciesResponse.model_validate(row))


# ── Production units ──────────────────────────────────────────────────────────

@router.get("/production-units", response_model=SuccessResponse[list[ProductionUnitResponse]])
async def list_units(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_UNIT_VIEW)),
    unit_status: str | None = Query(None, alias="status"),
):
    rows = await svc.list_units(db, farm_id, unit_status)
    return SuccessResponse(data=[ProductionUnitResponse.model_validate(r) for r in rows])


@router.post("/production-units", response_model=SuccessResponse[ProductionUnitResponse],
             status_code=status.HTTP_201_CREATED)
async def create_unit(
    farm_id: UUID, body: ProductionUnitCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_UNIT_MANAGE)),
):
    row = await svc.create_unit(db, farm_id, body, current_user)
    return SuccessResponse(data=ProductionUnitResponse.model_validate(row))


@router.get("/production-units/{unit_id}", response_model=SuccessResponse[ProductionUnitResponse])
async def get_unit(
    farm_id: UUID, unit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_UNIT_VIEW)),
):
    row = await svc.get_unit(db, farm_id, unit_id)
    return SuccessResponse(data=ProductionUnitResponse.model_validate(row))


@router.patch("/production-units/{unit_id}", response_model=SuccessResponse[ProductionUnitResponse])
async def update_unit(
    farm_id: UUID, unit_id: UUID, body: ProductionUnitUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_UNIT_MANAGE)),
):
    row = await svc.update_unit(db, farm_id, unit_id, body, current_user)
    return SuccessResponse(data=ProductionUnitResponse.model_validate(row))


# ── Colonies ──────────────────────────────────────────────────────────────────

@router.get("/colonies", response_model=SuccessResponse[list[ColonyResponse]])
async def list_colonies(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_COLONY_VIEW)),
    colony_status: str | None = Query(None, alias="status"),
):
    rows = await svc.list_colonies(db, farm_id, colony_status)
    return SuccessResponse(data=[ColonyResponse.model_validate(r) for r in rows])


@router.post("/colonies", response_model=SuccessResponse[ColonyResponse], status_code=status.HTTP_201_CREATED)
async def create_colony(
    farm_id: UUID, body: ColonyCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_COLONY_MANAGE)),
):
    row = await svc.create_colony(db, farm_id, body, current_user)
    return SuccessResponse(data=ColonyResponse.model_validate(row))


@router.get("/colonies/{colony_id}", response_model=SuccessResponse[ColonyResponse])
async def get_colony(
    farm_id: UUID, colony_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_COLONY_VIEW)),
):
    row = await svc.get_colony(db, farm_id, colony_id)
    return SuccessResponse(data=ColonyResponse.model_validate(row))


@router.patch("/colonies/{colony_id}", response_model=SuccessResponse[ColonyResponse])
async def update_colony(
    farm_id: UUID, colony_id: UUID, body: ColonyUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_COLONY_MANAGE)),
):
    row = await svc.update_colony(db, farm_id, colony_id, body, current_user)
    return SuccessResponse(data=ColonyResponse.model_validate(row))


# ── Batches ───────────────────────────────────────────────────────────────────

async def _batch_detail(db, batch) -> BatchDetailResponse:
    metrics, pacing = await batch_svc.compute_metrics(db, batch)
    return BatchDetailResponse(
        **BatchResponse.model_validate(batch).model_dump(), metrics=metrics, pacing=pacing
    )


@router.post("/batches", response_model=SuccessResponse[BatchResponse], status_code=status.HTTP_201_CREATED)
async def create_batch(
    farm_id: UUID, body: BatchCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_CREATE)),
):
    farm, _ = access
    row = await batch_svc.create_batch(db, farm_id, farm.organization_id, body, current_user)
    return SuccessResponse(data=BatchResponse.model_validate(row))


@router.get("/batches", response_model=ListResponse[BatchResponse])
async def list_batches(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
    batch_status: str | None = Query(None, alias="status"),
    lifecycle_stage: str | None = Query(None),
    production_unit_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    rows, total = await batch_svc.list_batches(
        db, farm_id, status=batch_status, lifecycle_stage=lifecycle_stage,
        production_unit_id=production_unit_id, page=page, limit=limit,
    )
    return ListResponse(
        data=[BatchResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 0),
    )


@router.get("/batches/{batch_id}", response_model=SuccessResponse[BatchDetailResponse])
async def get_batch(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
):
    row = await batch_svc.get_batch(db, farm_id, batch_id)
    return SuccessResponse(data=await _batch_detail(db, row))


@router.patch("/batches/{batch_id}", response_model=SuccessResponse[BatchResponse])
async def update_batch(
    farm_id: UUID, batch_id: UUID, body: BatchUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    farm, _ = access
    row = await batch_svc.update_batch(db, farm_id, farm.organization_id, batch_id, body, current_user)
    return SuccessResponse(data=BatchResponse.model_validate(row))


@router.post("/batches/{batch_id}/advance", response_model=SuccessResponse[BatchDetailResponse])
async def advance_batch(
    farm_id: UUID, batch_id: UUID, body: BatchAdvanceInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    row = await batch_svc.advance_stage(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=await _batch_detail(db, row))


@router.post("/batches/{batch_id}/move", response_model=SuccessResponse[BatchResponse])
async def move_batch(
    farm_id: UUID, batch_id: UUID, body: BatchMoveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    row = await batch_svc.move_batch(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=BatchResponse.model_validate(row))


@router.post("/batches/{batch_id}/split", response_model=SuccessResponse[list[BatchResponse]],
             status_code=status.HTTP_201_CREATED)
async def split_batch(
    farm_id: UUID, batch_id: UUID, body: BatchSplitInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    rows = await batch_svc.split_batch(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=[BatchResponse.model_validate(r) for r in rows])


@router.post("/batches/merge", response_model=SuccessResponse[BatchResponse],
             status_code=status.HTTP_201_CREATED)
async def merge_batches(
    farm_id: UUID, body: BatchMergeInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_EDIT)),
):
    row = await batch_svc.merge_batches(db, farm_id, body, current_user)
    return SuccessResponse(data=BatchResponse.model_validate(row))


@router.post("/batches/{batch_id}/terminate", response_model=SuccessResponse[BatchResponse])
async def terminate_batch(
    farm_id: UUID, batch_id: UUID, body: BatchTerminateInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.BSF_BATCH_DELETE)),
):
    row = await batch_svc.terminate_batch(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=BatchResponse.model_validate(row))


@router.get("/batches/{batch_id}/lifecycle", response_model=SuccessResponse[list[LifecycleEventResponse]])
async def batch_lifecycle(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
):
    rows = await batch_svc.list_lifecycle_events(db, farm_id, batch_id)
    return SuccessResponse(data=[LifecycleEventResponse.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/timeline", response_model=SuccessResponse[list[BatchEventResponse]])
async def batch_timeline(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_BATCH_VIEW)),
):
    rows = await batch_svc.list_batch_events(db, farm_id, batch_id)
    return SuccessResponse(data=[BatchEventResponse.model_validate(r) for r in rows])
