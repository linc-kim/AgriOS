"""
Greena — Rabbit Growth & Feed API (Module 17, Milestone 4).

Weight recording + growth analysis, and feeding (which reuses the platform
Inventory module). Every route is farm-scoped and permission-guarded.

Route map (prefix /farms/{farm_id}/rabbit):
  Growth / weight
    POST   /rabbits/{id}/weights          record a weight (RABBIT_WEIGHT_LOG)
    GET    /rabbits/{id}/weights          list weights (RABBIT_VIEW)
    GET    /rabbits/{id}/growth           growth analysis (RABBIT_VIEW)
  Feed (Inventory reuse)
    POST   /feed                          record a feeding (RABBIT_FEED_RECORD)
    GET    /feed                          list feeding (RABBIT_FEED_VIEW)
    GET    /feed/summary                  feed summary + FCR (RABBIT_FEED_VIEW)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.rabbit import (
    FeedRecordCreate,
    FeedRecordResponse,
    WeightCreate,
    WeightResponse,
)
from app.services import rabbit_feed_service as feed_svc
from app.services import rabbit_growth_service as growth_svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit", tags=["Rabbit Growth & Feed"])


# ── Weight & growth ──────────────────────────────────────────────────────────────

@router.post("/rabbits/{rabbit_id}/weights", response_model=SuccessResponse[WeightResponse], status_code=status.HTTP_201_CREATED)
async def record_weight(
    farm_id: str, rabbit_id: UUID, body: WeightCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_WEIGHT_LOG)),
):
    farm, _ = access
    row = await growth_svc.record_weight(db, farm, rabbit_id, body, current_user)
    return SuccessResponse(data=WeightResponse.model_validate(row))


@router.get("/rabbits/{rabbit_id}/weights", response_model=SuccessResponse[list[WeightResponse]])
async def list_weights(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
):
    farm, _ = access
    rows = await growth_svc.list_weights(db, farm.id, rabbit_id)
    return SuccessResponse(data=[WeightResponse.model_validate(r) for r in rows])


@router.get("/rabbits/{rabbit_id}/growth", response_model=SuccessResponse[dict])
async def growth_analysis(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await growth_svc.growth_analysis(db, farm.id, rabbit_id))


# ── Feed (reuses platform Inventory) ─────────────────────────────────────────────

@router.post("/feed", response_model=SuccessResponse[FeedRecordResponse], status_code=status.HTTP_201_CREATED)
async def record_feeding(
    farm_id: str, body: FeedRecordCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_FEED_RECORD)),
):
    farm, _ = access
    row = await feed_svc.record_feeding(db, farm, body, current_user)
    return SuccessResponse(data=FeedRecordResponse.model_validate(row))


@router.get("/feed", response_model=ListResponse[FeedRecordResponse])
async def list_feeding(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_FEED_VIEW)),
    rabbit_id: UUID | None = Query(None),
    cage_id: UUID | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    farm, _ = access
    rows, total = await feed_svc.list_feeding(
        db, farm.id, rabbit_id=rabbit_id, cage_id=cage_id, limit=limit, offset=(page - 1) * limit
    )
    return ListResponse(
        data=[FeedRecordResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 1),
    )


@router.get("/feed/summary", response_model=SuccessResponse[dict])
async def feed_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_FEED_VIEW)),
    rabbit_id: UUID | None = Query(None),
):
    farm, _ = access
    return SuccessResponse(data=await feed_svc.feed_summary(db, farm.id, rabbit_id))
