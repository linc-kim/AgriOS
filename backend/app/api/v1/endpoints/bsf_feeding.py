"""
Greena — BSF Feedstock & Feeding API (Module 16, Part 3)

Feedstock lots and feeding events. Farm-scoped and permission-guarded.

Route map (prefix /farms/{farm_id}/bsf):
  Feedstock
    GET/POST  /feedstock-lots                    list / create
    GET/PATCH /feedstock-lots/{lot_id}           detail / edit
  Feeding
    POST      /batches/{batch_id}/feedings       record a feeding
    GET       /batches/{batch_id}/feedings       feeding history
    GET       /batches/{batch_id}/feed-conversion  deterministic FCR summary
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import (
    FeedingEventCreate,
    FeedingEventResponse,
    FeedstockLotCreate,
    FeedstockLotResponse,
    FeedstockLotUpdate,
)
from app.services import bsf_feedstock_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf", tags=["Black Soldier Fly"])


# ── Feedstock lots ────────────────────────────────────────────────────────────

@router.get("/feedstock-lots", response_model=SuccessResponse[list[FeedstockLotResponse]])
async def list_feedstock_lots(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_VIEW)),
    lot_status: str | None = Query(None, alias="status"),
):
    rows = await svc.list_feedstock_lots(db, farm_id, lot_status)
    return SuccessResponse(data=[FeedstockLotResponse.model_validate(r) for r in rows])


@router.post("/feedstock-lots", response_model=SuccessResponse[FeedstockLotResponse],
             status_code=status.HTTP_201_CREATED)
async def create_feedstock_lot(
    farm_id: UUID, body: FeedstockLotCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_RECORD)),
):
    row = await svc.create_feedstock_lot(db, farm_id, body, current_user)
    return SuccessResponse(data=FeedstockLotResponse.model_validate(row))


@router.get("/feedstock-lots/{lot_id}", response_model=SuccessResponse[FeedstockLotResponse])
async def get_feedstock_lot(
    farm_id: UUID, lot_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_VIEW)),
):
    row = await svc.get_feedstock_lot(db, farm_id, lot_id)
    return SuccessResponse(data=FeedstockLotResponse.model_validate(row))


@router.patch("/feedstock-lots/{lot_id}", response_model=SuccessResponse[FeedstockLotResponse])
async def update_feedstock_lot(
    farm_id: UUID, lot_id: UUID, body: FeedstockLotUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_RECORD)),
):
    row = await svc.update_feedstock_lot(db, farm_id, lot_id, body, current_user)
    return SuccessResponse(data=FeedstockLotResponse.model_validate(row))


# ── Feeding ───────────────────────────────────────────────────────────────────

@router.post("/batches/{batch_id}/feedings", response_model=SuccessResponse[FeedingEventResponse],
             status_code=status.HTTP_201_CREATED)
async def record_feeding(
    farm_id: UUID, batch_id: UUID, body: FeedingEventCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_RECORD)),
):
    row = await svc.record_feeding(db, farm_id, batch_id, body, current_user)
    return SuccessResponse(data=FeedingEventResponse.model_validate(row))


@router.get("/batches/{batch_id}/feedings", response_model=SuccessResponse[list[FeedingEventResponse]])
async def list_feedings(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_VIEW)),
):
    rows = await svc.list_feeding_events(db, farm_id, batch_id)
    return SuccessResponse(data=[FeedingEventResponse.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/feed-conversion", response_model=SuccessResponse[dict])
async def feed_conversion(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_FEED_VIEW)),
):
    data = await svc.feed_conversion_summary(db, farm_id, batch_id)
    return SuccessResponse(data=data)
