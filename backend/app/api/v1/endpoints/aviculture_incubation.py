"""
Greena — Aviculture Incubation API (Module 15, Part 5)

Eggs, clutches, incubation batches, candling and hatching. Schedule, progress and
hatch statistics are computed by the pure incubation engine and returned
honesty-labelled. A hatched egg produces a real chick bird. Farm-scoped and
permission-guarded.

Prefix: /farms/{farm_id}/aviculture
"""

from datetime import date
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.aviculture_incubation import (
    BatchCreate, BatchDetailResponse, BatchResponse, CandlingCreate, CandlingResponse,
    ClutchCreate, ClutchResponse, EggCreate, EggResponse, EggUpdate, HatchCreate, HatchResponse,
    IncubationLogCreate, IncubationLogResponse, SetEggsRequest,
)
from app.services import incubation_service as svc
from app.services import incubation_engine

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture — Incubation"])

_MANAGE = {"farm_owner", "farm_manager", "farm_worker"}


def _batch_response(batch, egg_count: int) -> BatchResponse:
    r = BatchResponse.model_validate(batch)
    r.egg_count = egg_count
    r.progress = incubation_engine.incubation_progress(batch.set_on, batch.incubation_days, date.today(), batch.status)
    return r


# ── Clutches ──────────────────────────────────────────────────────────────────

@router.post("/clutches", response_model=SuccessResponse[ClutchResponse], status_code=status.HTTP_201_CREATED)
async def create_clutch(farm_id: str, body: ClutchCreate, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access(_MANAGE)),
                        _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=ClutchResponse.model_validate(await svc.create_clutch(db, farm, body, current_user)))


@router.get("/clutches", response_model=SuccessResponse[list[ClutchResponse]])
async def list_clutches(farm_id: str, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW))):
    farm, _ = access
    rows, counts = await svc.list_clutches(db, farm.id)
    out = []
    for c in rows:
        r = ClutchResponse.model_validate(c)
        r.egg_count = counts.get(c.id, 0)
        out.append(r)
    return SuccessResponse(data=out)


# ── Eggs ──────────────────────────────────────────────────────────────────────

@router.post("/eggs", response_model=SuccessResponse[EggResponse], status_code=status.HTTP_201_CREATED)
async def create_egg(farm_id: str, body: EggCreate, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access(_MANAGE)),
                     _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=EggResponse.model_validate(await svc.create_egg(db, farm, body, current_user)))


@router.get("/eggs", response_model=ListResponse[EggResponse])
async def list_eggs(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW)),
                    batch_id: UUID | None = Query(None), clutch_id: UUID | None = Query(None),
                    status_filter: str | None = Query(None, alias="status"),
                    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    farm, _ = access
    rows, total = await svc.list_eggs(db, farm.id, batch_id=batch_id, clutch_id=clutch_id,
                                      status=status_filter, limit=limit, offset=offset)
    return ListResponse(data=[EggResponse.model_validate(e) for e in rows],
                        meta=PaginationMeta(total=total, page=(offset // limit) + 1, limit=limit,
                                            pages=max(1, ceil(total / limit)) if total else 1))


@router.patch("/eggs/{egg_id}", response_model=SuccessResponse[EggResponse])
async def update_egg(farm_id: str, egg_id: UUID, body: EggUpdate, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access(_MANAGE)),
                     _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=EggResponse.model_validate(await svc.update_egg(db, farm.id, egg_id, body, current_user)))


@router.post("/eggs/{egg_id}/candling", response_model=SuccessResponse[CandlingResponse], status_code=status.HTTP_201_CREATED)
async def add_candling(farm_id: str, egg_id: UUID, body: CandlingCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_MANAGE)),
                       _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=CandlingResponse.model_validate(await svc.add_candling(db, farm.id, egg_id, body, current_user)))


@router.get("/eggs/{egg_id}/candling", response_model=SuccessResponse[list[CandlingResponse]])
async def list_candling(farm_id: str, egg_id: UUID, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW))):
    farm, _ = access
    return SuccessResponse(data=[CandlingResponse.model_validate(c) for c in await svc.list_candling(db, farm.id, egg_id)])


@router.post("/eggs/{egg_id}/hatch", response_model=SuccessResponse[HatchResponse], status_code=status.HTTP_201_CREATED)
async def record_hatch(farm_id: str, egg_id: UUID, body: HatchCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_MANAGE)),
                       _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=HatchResponse.model_validate(await svc.record_hatch(db, farm.id, egg_id, body, current_user)))


# ── Batches ───────────────────────────────────────────────────────────────────

@router.post("/incubation-batches", response_model=SuccessResponse[BatchResponse], status_code=status.HTTP_201_CREATED)
async def create_batch(farm_id: str, body: BatchCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_MANAGE)),
                       _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=_batch_response(await svc.create_batch(db, farm, body, current_user), 0))


@router.get("/incubation-batches", response_model=SuccessResponse[list[BatchResponse]])
async def list_batches(farm_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW)),
                       status_filter: str | None = Query(None, alias="status")):
    farm, _ = access
    rows, counts = await svc.list_batches(db, farm.id, status_filter)
    return SuccessResponse(data=[_batch_response(b, counts.get(b.id, 0)) for b in rows])


@router.get("/incubation-batches/{batch_id}", response_model=SuccessResponse[BatchDetailResponse])
async def get_batch(farm_id: str, batch_id: UUID, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW))):
    farm, _ = access
    batch, schedule, progress, stats, egg_count = await svc.get_batch_detail(db, farm.id, batch_id)
    r = BatchDetailResponse.model_validate(batch)
    r.egg_count = egg_count
    r.schedule = schedule
    r.progress = progress
    r.statistics = stats
    return SuccessResponse(data=r)


@router.post("/incubation-batches/{batch_id}/set-eggs", response_model=SuccessResponse[dict])
async def set_eggs(farm_id: str, batch_id: UUID, body: SetEggsRequest, db: DBSession, current_user: CurrentUser,
                   access: tuple = Depends(require_farm_access(_MANAGE)),
                   _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    count = await svc.set_eggs(db, farm.id, batch_id, body, current_user)
    return SuccessResponse(data={"eggs_set": count})


@router.post("/incubation-batches/{batch_id}/logs", response_model=SuccessResponse[IncubationLogResponse], status_code=status.HTTP_201_CREATED)
async def add_log(farm_id: str, batch_id: UUID, body: IncubationLogCreate, db: DBSession, current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access(_MANAGE)),
                  _perm=Depends(require_permission(Permission.AVI_INCUBATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=IncubationLogResponse.model_validate(await svc.add_log(db, farm.id, batch_id, body, current_user)))


@router.get("/incubation-batches/{batch_id}/logs", response_model=SuccessResponse[list[IncubationLogResponse]])
async def list_logs(farm_id: str, batch_id: UUID, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW))):
    farm, _ = access
    return SuccessResponse(data=[IncubationLogResponse.model_validate(x) for x in await svc.list_logs(db, farm.id, batch_id)])


@router.get("/incubation-batches/{batch_id}/hatch-events", response_model=SuccessResponse[list[HatchResponse]])
async def list_hatch_events(farm_id: str, batch_id: UUID, db: DBSession, current_user: CurrentUser,
                            access: tuple = Depends(require_farm_access()),
                            _perm=Depends(require_permission(Permission.AVI_INCUBATION_VIEW))):
    farm, _ = access
    return SuccessResponse(data=[HatchResponse.model_validate(h) for h in await svc.list_hatch_events(db, farm.id, batch_id)])
