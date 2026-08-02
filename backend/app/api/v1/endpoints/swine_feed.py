"""
Greena — Swine Feed API (Module 20, Milestone 5).

Feed catalog, feed plans by production stage, and the Inventory-integrated feeding
log. Feeding consumption draws down platform Inventory stock (no re-expense). Feed
catalog writes require SWINE_CATALOG_MANAGE; plan + feeding writes SWINE_FEED_RECORD;
reads SWINE_FEED_VIEW.

Route map (prefix /farms/{farm_id}/swine/feed):
    GET/POST /feeds                list / create feed catalog
    PATCH    /feeds/{feed_id}      edit a custom feed
    GET/POST /plans                list / create feed-plan entries
    PATCH    /plans/{entry_id}     edit a feed-plan entry
    GET/POST /records              list / record feedings
    GET      /summary              deterministic feed summary (+ FCR when available)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.swine import (
    FeedCreate,
    FeedPlanCreate,
    FeedPlanResponse,
    FeedPlanUpdate,
    FeedRecordCreate,
    FeedRecordResponse,
    FeedResponse,
    FeedUpdate,
)
from app.services import swine_feed_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/feed", tags=["Swine Feed"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}


# ── Feed catalog ────────────────────────────────────────────────────────────────

@router.get("/feeds", response_model=SuccessResponse[list[FeedResponse]])
async def list_feeds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_VIEW)),
):
    farm, _ = access
    rows = await svc.list_feeds(db, farm.organization_id)
    return SuccessResponse(data=[FeedResponse.model_validate(r) for r in rows])


@router.post("/feeds", response_model=SuccessResponse[FeedResponse], status_code=status.HTTP_201_CREATED)
async def create_feed(
    farm_id: str, body: FeedCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_feed(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=FeedResponse.model_validate(row))


@router.patch("/feeds/{feed_id}", response_model=SuccessResponse[FeedResponse])
async def update_feed(
    farm_id: str, feed_id: UUID, body: FeedUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_feed(db, farm.organization_id, feed_id, body, current_user)
    return SuccessResponse(data=FeedResponse.model_validate(row))


# ── Feed plans ──────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=SuccessResponse[list[FeedPlanResponse]])
async def list_plans(
    farm_id: str, db: DBSession, current_user: CurrentUser, plan_name: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_VIEW)),
):
    farm, _ = access
    rows = await svc.list_plans(db, farm.id, plan_name=plan_name)
    return SuccessResponse(data=[FeedPlanResponse.model_validate(r) for r in rows])


@router.post("/plans", response_model=SuccessResponse[FeedPlanResponse], status_code=status.HTTP_201_CREATED)
async def create_plan(
    farm_id: str, body: FeedPlanCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_RECORD)),
):
    farm, _ = access
    row = await svc.create_plan_entry(db, farm, body, current_user)
    return SuccessResponse(data=FeedPlanResponse.model_validate(row))


@router.patch("/plans/{entry_id}", response_model=SuccessResponse[FeedPlanResponse])
async def update_plan(
    farm_id: str, entry_id: UUID, body: FeedPlanUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_RECORD)),
):
    farm, _ = access
    row = await svc.update_plan_entry(db, farm.id, entry_id, body, current_user)
    return SuccessResponse(data=FeedPlanResponse.model_validate(row))


# ── Feeding log ─────────────────────────────────────────────────────────────────

@router.get("/records", response_model=ListResponse[FeedRecordResponse])
async def list_records(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    pig_id: UUID | None = None, group_id: UUID | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_VIEW)),
):
    farm, _ = access
    rows, total = await svc.list_feeding(db, farm.id, pig_id=pig_id, group_id=group_id,
                                         limit=page_size, offset=(page - 1) * page_size)
    meta = PaginationMeta(total=total, page=page, limit=page_size,
                          pages=ceil(total / page_size) if page_size else 0)
    return ListResponse(data=[FeedRecordResponse.model_validate(r) for r in rows], meta=meta)


@router.post("/records", response_model=SuccessResponse[FeedRecordResponse], status_code=status.HTTP_201_CREATED)
async def record_feeding(
    farm_id: str, body: FeedRecordCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_RECORD)),
):
    farm, _ = access
    row = await svc.record_feeding(db, farm, body, current_user)
    return SuccessResponse(data=FeedRecordResponse.model_validate(row))


@router.get("/summary", response_model=SuccessResponse[dict])
async def feed_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    pig_id: UUID | None = None, group_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_FEED_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.feed_summary(db, farm.id, pig_id=pig_id, group_id=group_id))
