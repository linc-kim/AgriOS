"""
Greena — Aviculture Aviary API (Module 15, Part 3)

Facility management for aviaries: CRUD, zones, fixtures, environmental readings,
cleaning/maintenance tasks, timeline, media, and a farm-wide infrastructure
summary. Every route is farm-scoped and permission-guarded (reuse of
``require_farm_access`` + ``require_permission``). Occupancy and environment
figures come from the pure ``aviary_engine`` and are honesty-labelled.

Prefix: /farms/{farm_id}/aviculture/aviaries
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.aviculture_aviary import (
    AviaryCreate,
    AviaryDetailResponse,
    AviaryEventResponse,
    AviaryMediaCreate,
    AviaryMediaResponse,
    AviaryResponse,
    AviaryUpdate,
    EnvironmentalReadingCreate,
    EnvironmentalReadingResponse,
    FixtureCreate,
    FixtureResponse,
    InfrastructureSummary,
    TaskComplete,
    TaskCreate,
    TaskResponse,
    ZoneCreate,
    ZoneResponse,
)
from app.services import aviary_service as svc
from app.services import aviary_engine

router = APIRouter(prefix="/farms/{farm_id}/aviculture/aviaries", tags=["Aviculture — Aviaries"])

_MANAGE = {"farm_owner", "farm_manager"}
_LOG = {"farm_owner", "farm_manager", "farm_worker"}


def _aviary_response(aviary, occupied: int | None) -> AviaryResponse:
    data = AviaryResponse.model_validate(aviary)
    if occupied is not None:
        data.occupancy = aviary_engine.compute_occupancy(aviary.capacity, occupied).as_dict()
    return data


# ── Infrastructure summary ────────────────────────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[InfrastructureSummary])
async def infrastructure_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=InfrastructureSummary.model_validate(await svc.infrastructure_summary(db, farm.id)))


# ── Aviary CRUD ───────────────────────────────────────────────────────────────

@router.post("", response_model=SuccessResponse[AviaryResponse], status_code=status.HTTP_201_CREATED)
async def create_aviary(
    farm_id: str, body: AviaryCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    aviary = await svc.create_aviary(db, farm, body, current_user)
    return SuccessResponse(data=_aviary_response(aviary, 0))


@router.get("", response_model=ListResponse[AviaryResponse])
async def list_aviaries(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
    purpose: str | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    farm, _ = access
    rows, total, occ = await svc.list_aviaries(
        db, farm.id, purpose=purpose, status=status_filter, search=search, limit=limit, offset=offset)
    return ListResponse(
        data=[_aviary_response(a, occ.get(a.id, 0)) for a in rows],
        meta=PaginationMeta(total=total, page=(offset // limit) + 1, limit=limit,
                            pages=max(1, ceil(total / limit)) if total else 1),
    )


@router.get("/{aviary_id}", response_model=SuccessResponse[AviaryDetailResponse])
async def get_aviary(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    aviary, occupancy, env, cleaning, housing, zones, fixtures = await svc.get_aviary_detail(db, farm.id, aviary_id)
    base = AviaryDetailResponse.model_validate(aviary)
    base.occupancy = occupancy.as_dict()
    base.environment_summary = env.as_dict()
    base.cleaning = cleaning
    base.housing_assessment = housing
    base.zone_count = zones
    base.fixture_count = fixtures
    return SuccessResponse(data=base)


@router.patch("/{aviary_id}", response_model=SuccessResponse[AviaryResponse])
async def update_aviary(
    farm_id: str, aviary_id: UUID, body: AviaryUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    aviary = await svc.update_aviary(db, farm.id, aviary_id, body, current_user)
    return SuccessResponse(data=AviaryResponse.model_validate(aviary))


@router.post("/{aviary_id}/deactivate", response_model=SuccessResponse[AviaryResponse])
async def deactivate_aviary(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    aviary = await svc.archive_aviary(db, farm.id, aviary_id, current_user)
    return SuccessResponse(data=AviaryResponse.model_validate(aviary))


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.post("/{aviary_id}/zones", response_model=SuccessResponse[ZoneResponse], status_code=status.HTTP_201_CREATED)
async def add_zone(
    farm_id: str, aviary_id: UUID, body: ZoneCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=ZoneResponse.model_validate(await svc.add_zone(db, farm.id, aviary_id, body, current_user)))


@router.get("/{aviary_id}/zones", response_model=SuccessResponse[list[ZoneResponse]])
async def list_zones(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=[ZoneResponse.model_validate(z) for z in await svc.list_zones(db, farm.id, aviary_id)])


# ── Fixtures ──────────────────────────────────────────────────────────────────

@router.post("/{aviary_id}/fixtures", response_model=SuccessResponse[FixtureResponse], status_code=status.HTTP_201_CREATED)
async def add_fixture(
    farm_id: str, aviary_id: UUID, body: FixtureCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=FixtureResponse.model_validate(await svc.add_fixture(db, farm.id, aviary_id, body, current_user)))


@router.get("/{aviary_id}/fixtures", response_model=SuccessResponse[list[FixtureResponse]])
async def list_fixtures(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
    fixture_type: str | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_fixtures(db, farm.id, aviary_id, fixture_type)
    return SuccessResponse(data=[FixtureResponse.model_validate(f) for f in rows])


# ── Environmental readings ────────────────────────────────────────────────────

@router.post("/{aviary_id}/environment", response_model=SuccessResponse[EnvironmentalReadingResponse], status_code=status.HTTP_201_CREATED)
async def add_reading(
    farm_id: str, aviary_id: UUID, body: EnvironmentalReadingCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_LOG)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=EnvironmentalReadingResponse.model_validate(await svc.add_reading(db, farm.id, aviary_id, body, current_user)))


@router.get("/{aviary_id}/environment", response_model=SuccessResponse[list[EnvironmentalReadingResponse]])
async def list_readings(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    rows = await svc.list_readings(db, farm.id, aviary_id)
    return SuccessResponse(data=[EnvironmentalReadingResponse.model_validate(r) for r in rows])


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.post("/{aviary_id}/tasks", response_model=SuccessResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def add_task(
    farm_id: str, aviary_id: UUID, body: TaskCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_LOG)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=TaskResponse.model_validate(await svc.add_task(db, farm.id, aviary_id, body, current_user)))


@router.get("/{aviary_id}/tasks", response_model=SuccessResponse[list[TaskResponse]])
async def list_tasks(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
    status_filter: str | None = Query(None, alias="status"),
):
    farm, _ = access
    rows = await svc.list_tasks(db, farm.id, aviary_id, status_filter)
    return SuccessResponse(data=[TaskResponse.model_validate(t) for t in rows])


@router.post("/{aviary_id}/tasks/{task_id}/complete", response_model=SuccessResponse[TaskResponse])
async def complete_task(
    farm_id: str, aviary_id: UUID, task_id: UUID, body: TaskComplete, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_LOG)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=TaskResponse.model_validate(await svc.complete_task(db, farm.id, aviary_id, task_id, body, current_user)))


# ── Timeline & media ──────────────────────────────────────────────────────────

@router.get("/{aviary_id}/timeline", response_model=SuccessResponse[list[AviaryEventResponse]])
async def aviary_timeline(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    rows = await svc.list_events(db, farm.id, aviary_id)
    return SuccessResponse(data=[AviaryEventResponse.model_validate(e) for e in rows])


@router.post("/{aviary_id}/media", response_model=SuccessResponse[AviaryMediaResponse], status_code=status.HTTP_201_CREATED)
async def add_media(
    farm_id: str, aviary_id: UUID, body: AviaryMediaCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_LOG)),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=AviaryMediaResponse.model_validate(await svc.add_media(db, farm.id, aviary_id, body, current_user)))


@router.get("/{aviary_id}/media", response_model=SuccessResponse[list[AviaryMediaResponse]])
async def list_media(
    farm_id: str, aviary_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_AVIARY_VIEW)),
):
    farm, _ = access
    rows = await svc.list_media(db, farm.id, aviary_id)
    return SuccessResponse(data=[AviaryMediaResponse.model_validate(m) for m in rows])
