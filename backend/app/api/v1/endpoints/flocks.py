"""
Greena — Flock & Operations API Endpoints

Route map:
  POST   /farms/{farm_id}/flocks                               → create flock
  GET    /farms/{farm_id}/flocks                               → list flocks
  GET    /farms/{farm_id}/flocks/{flock_id}                    → flock detail + metrics
  POST   /farms/{farm_id}/flocks/{flock_id}/close              → close flock

  POST   /farms/{farm_id}/flocks/{flock_id}/logs               → submit / upsert daily log
  GET    /farms/{farm_id}/flocks/{flock_id}/logs               → log history
  GET    /farms/{farm_id}/flocks/{flock_id}/logs/{log_date}    → single day log
  PATCH  /farms/{farm_id}/flocks/{flock_id}/logs/{log_date}    → correct log

  POST   /farms/{farm_id}/flocks/{flock_id}/production         → log egg production
  GET    /farms/{farm_id}/flocks/{flock_id}/production         → production history

  POST   /farms/{farm_id}/flocks/{flock_id}/weighins           → record weigh-in
  GET    /farms/{farm_id}/flocks/{flock_id}/weighins           → weigh-in history

  POST   /farms/{farm_id}/feed-purchases                       → record feed purchase
  GET    /farms/{farm_id}/feed-purchases                       → list feed purchases

RBAC:
  FLOCK_CREATE        → farm_owner, farm_manager
  FLOCK_CLOSE         → farm_owner, farm_manager
  FLOCK_VIEW          → all roles
  OPS_LOG_SUBMIT      → farm_owner, farm_manager, farm_worker
  OPS_LOG_CORRECT     → farm_owner, farm_manager
  OPS_PRODUCTION_LOG  → farm_owner, farm_manager, farm_worker
  OPS_WEIGHIN_LOG     → farm_owner, farm_manager, farm_worker
  OPS_FEED_LOG        → farm_owner, farm_manager, farm_worker
  OPS_LOG_VIEW        → all roles
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.flock import (
    DailyLogCorrect,
    DailyLogResponse,
    DailyLogSubmit,
    FeedPurchaseCreate,
    FeedPurchaseResponse,
    FarmProductionDashboard,
    FlockClose,
    FlockCreate,
    FlockUpdate,
    FlockDetailResponse,
    FlockResponse,
    ProductionRecordResponse,
    ProductionRecordSubmit,
    WeighinResponse,
    WeighinSubmit,
)
from app.services import flock_service

router = APIRouter()


# ── Flocks ────────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks",
    response_model=SuccessResponse[FlockResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new flock",
    tags=["Flocks"],
)
async def create_flock(
    farm_id: str,
    body: FlockCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FLOCK_CREATE)),
) -> SuccessResponse[FlockResponse]:
    farm, member = access
    flock = await flock_service.create_flock(db, farm, body, current_user)
    return SuccessResponse(data=FlockResponse.model_validate(flock))


@router.get(
    "/farms/{farm_id}/flocks",
    response_model=SuccessResponse[list[FlockResponse]],
    summary="List flocks for a farm",
    tags=["Flocks"],
)
async def list_flocks(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FLOCK_VIEW)),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status: active | sold | closed | culled",
    ),
    include_archived: bool = Query(
        default=False, description="Include archived flocks in the list."
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[FlockResponse]]:
    farm, member = access
    flocks = await flock_service.list_flocks(
        db,
        farm.id,
        status=status_filter,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=[FlockResponse.model_validate(f) for f in flocks])


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}",
    response_model=SuccessResponse[FlockDetailResponse],
    summary="Get flock detail with operational metrics",
    tags=["Flocks"],
)
async def get_flock(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FLOCK_VIEW)),
) -> SuccessResponse[FlockDetailResponse]:
    import uuid as _uuid
    farm, member = access
    flock, metrics = await flock_service.get_flock_detail(
        db, farm.id, _uuid.UUID(flock_id)
    )
    response_data = FlockDetailResponse.model_validate(
        {**flock.__dict__, "metrics": metrics.model_dump()}
    )
    return SuccessResponse(data=response_data)


@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/close",
    response_model=SuccessResponse[FlockResponse],
    summary="Close a flock (sold / closed / culled)",
    tags=["Flocks"],
)
async def close_flock(
    farm_id: str,
    flock_id: str,
    body: FlockClose,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FLOCK_CLOSE)),
) -> SuccessResponse[FlockResponse]:
    import uuid as _uuid
    farm, member = access
    flock = await flock_service.close_flock(
        db, farm.id, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=FlockResponse.model_validate(flock))


@router.patch(
    "/farms/{farm_id}/flocks/{flock_id}",
    response_model=SuccessResponse[FlockResponse],
    summary="Edit a flock's details",
    tags=["Flocks"],
)
async def update_flock(
    farm_id: str,
    flock_id: str,
    body: FlockUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FLOCK_UPDATE)),
) -> SuccessResponse[FlockResponse]:
    import uuid as _uuid
    farm, member = access
    flock = await flock_service.update_flock(
        db, farm.id, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=FlockResponse.model_validate(flock))


@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/archive",
    response_model=SuccessResponse[FlockResponse],
    summary="Archive a closed flock (hide from active lists)",
    tags=["Flocks"],
)
async def archive_flock(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.FLOCK_ARCHIVE)),
) -> SuccessResponse[FlockResponse]:
    import uuid as _uuid
    farm, member = access
    flock = await flock_service.archive_flock(db, farm.id, _uuid.UUID(flock_id))
    return SuccessResponse(data=FlockResponse.model_validate(flock))


@router.get(
    "/farms/{farm_id}/production-dashboard",
    response_model=SuccessResponse[FarmProductionDashboard],
    summary="Farm-wide production dashboard metrics (real data)",
    tags=["Flocks"],
)
async def production_dashboard(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FLOCK_VIEW)),
) -> SuccessResponse[FarmProductionDashboard]:
    farm, member = access
    data = await flock_service.get_farm_production_dashboard(db, farm.id)
    return SuccessResponse(data=data)


# ── Daily Logs ────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/logs",
    response_model=SuccessResponse[DailyLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Submit or update today's daily log (upsert)",
    tags=["Daily Logs"],
)
async def submit_daily_log(
    farm_id: str,
    flock_id: str,
    body: DailyLogSubmit,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "farm_worker"})
    ),
    _perm=Depends(require_permission(Permission.OPS_LOG_SUBMIT)),
) -> SuccessResponse[DailyLogResponse]:
    import uuid as _uuid
    farm, member = access
    log = await flock_service.submit_daily_log(
        db, farm.id, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=DailyLogResponse.model_validate(log))


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/logs",
    response_model=SuccessResponse[list[DailyLogResponse]],
    summary="List daily log history for a flock",
    tags=["Daily Logs"],
)
async def list_daily_logs(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.OPS_LOG_VIEW)),
    limit: int = Query(default=30, ge=1, le=90),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[DailyLogResponse]]:
    import uuid as _uuid
    farm, member = access
    logs = await flock_service.list_daily_logs(
        db, farm.id, _uuid.UUID(flock_id), limit=limit, offset=offset
    )
    return SuccessResponse(data=[DailyLogResponse.model_validate(l) for l in logs])


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/logs/{log_date}",
    response_model=SuccessResponse[DailyLogResponse],
    summary="Get a specific daily log by date",
    tags=["Daily Logs"],
)
async def get_daily_log(
    farm_id: str,
    flock_id: str,
    log_date: date,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.OPS_LOG_VIEW)),
) -> SuccessResponse[DailyLogResponse]:
    import uuid as _uuid
    farm, member = access
    log = await flock_service.get_daily_log_by_date(
        db, farm.id, _uuid.UUID(flock_id), log_date
    )
    return SuccessResponse(data=DailyLogResponse.model_validate(log))


@router.patch(
    "/farms/{farm_id}/flocks/{flock_id}/logs/{log_date}",
    response_model=SuccessResponse[DailyLogResponse],
    summary="Correct a previously submitted daily log",
    tags=["Daily Logs"],
)
async def correct_daily_log(
    farm_id: str,
    flock_id: str,
    log_date: date,
    body: DailyLogCorrect,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.OPS_LOG_CORRECT)),
) -> SuccessResponse[DailyLogResponse]:
    import uuid as _uuid
    farm, member = access
    log = await flock_service.correct_daily_log(
        db, farm.id, _uuid.UUID(flock_id), log_date, body, current_user
    )
    return SuccessResponse(data=DailyLogResponse.model_validate(log))


# ── Production Records ────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/production",
    response_model=SuccessResponse[ProductionRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Log daily egg production (upsert)",
    tags=["Production"],
)
async def submit_production(
    farm_id: str,
    flock_id: str,
    body: ProductionRecordSubmit,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "farm_worker"})
    ),
    _perm=Depends(require_permission(Permission.OPS_PRODUCTION_LOG)),
) -> SuccessResponse[ProductionRecordResponse]:
    import uuid as _uuid
    farm, member = access
    record = await flock_service.submit_production_record(
        db, farm.id, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=ProductionRecordResponse.model_validate(record))


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/production",
    response_model=SuccessResponse[list[ProductionRecordResponse]],
    summary="List production records for a flock",
    tags=["Production"],
)
async def list_production(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.OPS_LOG_VIEW)),
    limit: int = Query(default=30, ge=1, le=90),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[ProductionRecordResponse]]:
    import uuid as _uuid
    farm, member = access
    records = await flock_service.list_production_records(
        db, farm.id, _uuid.UUID(flock_id), limit=limit, offset=offset
    )
    return SuccessResponse(
        data=[ProductionRecordResponse.model_validate(r) for r in records]
    )


# ── Weigh-In Records ──────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/weighins",
    response_model=SuccessResponse[WeighinResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a weigh-in",
    tags=["Weigh-Ins"],
)
async def submit_weighin(
    farm_id: str,
    flock_id: str,
    body: WeighinSubmit,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "farm_worker"})
    ),
    _perm=Depends(require_permission(Permission.OPS_WEIGHIN_LOG)),
) -> SuccessResponse[WeighinResponse]:
    import uuid as _uuid
    farm, member = access
    record = await flock_service.submit_weighin(
        db, farm.id, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=WeighinResponse.model_validate(record))


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/weighins",
    response_model=SuccessResponse[list[WeighinResponse]],
    summary="List weigh-in records for a flock",
    tags=["Weigh-Ins"],
)
async def list_weighins(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.OPS_LOG_VIEW)),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[WeighinResponse]]:
    import uuid as _uuid
    farm, member = access
    records = await flock_service.list_weighins(
        db, farm.id, _uuid.UUID(flock_id), limit=limit, offset=offset
    )
    return SuccessResponse(data=[WeighinResponse.model_validate(r) for r in records])


# ── Feed Purchases ────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/feed-purchases",
    response_model=SuccessResponse[FeedPurchaseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a feed purchase",
    tags=["Feed Purchases"],
)
async def create_feed_purchase(
    farm_id: str,
    body: FeedPurchaseCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "farm_worker"})
    ),
    _perm=Depends(require_permission(Permission.OPS_FEED_LOG)),
) -> SuccessResponse[FeedPurchaseResponse]:
    farm, member = access
    purchase = await flock_service.create_feed_purchase(db, farm.id, body, current_user)
    return SuccessResponse(data=FeedPurchaseResponse.model_validate(purchase))


@router.get(
    "/farms/{farm_id}/feed-purchases",
    response_model=SuccessResponse[list[FeedPurchaseResponse]],
    summary="List feed purchases for a farm",
    tags=["Feed Purchases"],
)
async def list_feed_purchases(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.OPS_FEED_LOG)),
    flock_id: str | None = Query(
        default=None,
        description="Filter by flock ID",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[FeedPurchaseResponse]]:
    import uuid as _uuid
    farm, member = access
    flock_uuid = _uuid.UUID(flock_id) if flock_id else None
    purchases = await flock_service.list_feed_purchases(
        db, farm.id, flock_id=flock_uuid, limit=limit, offset=offset
    )
    return SuccessResponse(
        data=[FeedPurchaseResponse.model_validate(p) for p in purchases]
    )
