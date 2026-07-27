"""
Greena — Aviculture Health API (Module 15, Part 6)

Individual-bird health records, quarantine, disease events and analytics. Every
route is farm-scoped and permission-guarded. Analytics come from the pure health
engine, honesty-labelled. ARIA may explain these records; it never diagnoses.

Prefix: /farms/{farm_id}/aviculture
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.aviculture_health import (
    DiseaseEventCreate, DiseaseEventResponse, DiseaseEventUpdate, HealthRecordCreate,
    HealthRecordResponse, HealthRecordUpdate, HealthSummaryResponse, QuarantineEnd,
    QuarantineResponse, QuarantineStart, WeightTrendResponse,
)
from app.services import aviculture_health_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture — Health"])

# The vet consultant holds AVI_HEALTH_LOG and must be able to write clinical records.
_CLINICAL = {"farm_owner", "farm_manager", "farm_worker", "vet_consultant"}


# ── Health records ────────────────────────────────────────────────────────────

@router.post("/birds/{bird_id}/health", response_model=SuccessResponse[HealthRecordResponse], status_code=status.HTTP_201_CREATED)
async def add_record(farm_id: str, bird_id: UUID, body: HealthRecordCreate, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access(_CLINICAL)),
                     _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=HealthRecordResponse.model_validate(await svc.add_record(db, farm.id, bird_id, body, current_user)))


@router.get("/birds/{bird_id}/health", response_model=SuccessResponse[list[HealthRecordResponse]])
async def list_records(farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW)),
                       record_type: str | None = Query(None)):
    farm, _ = access
    rows = await svc.list_records(db, farm.id, bird_id, record_type)
    return SuccessResponse(data=[HealthRecordResponse.model_validate(r) for r in rows])


@router.patch("/birds/{bird_id}/health/{record_id}", response_model=SuccessResponse[HealthRecordResponse])
async def update_record(farm_id: str, bird_id: UUID, record_id: UUID, body: HealthRecordUpdate,
                        db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access(_CLINICAL)),
                        _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=HealthRecordResponse.model_validate(await svc.update_record(db, farm.id, bird_id, record_id, body, current_user)))


@router.get("/birds/{bird_id}/weight-trend", response_model=SuccessResponse[WeightTrendResponse])
async def weight_trend(farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW))):
    farm, _ = access
    return SuccessResponse(data=WeightTrendResponse.model_validate(await svc.weight_trend(db, farm.id, bird_id)))


# ── Quarantine ────────────────────────────────────────────────────────────────

@router.post("/birds/{bird_id}/quarantine", response_model=SuccessResponse[QuarantineResponse], status_code=status.HTTP_201_CREATED)
async def start_quarantine(farm_id: str, bird_id: UUID, body: QuarantineStart, db: DBSession, current_user: CurrentUser,
                           access: tuple = Depends(require_farm_access(_CLINICAL)),
                           _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=QuarantineResponse.model_validate(await svc.start_quarantine(db, farm.id, bird_id, body, current_user)))


@router.get("/birds/{bird_id}/quarantine", response_model=SuccessResponse[list[QuarantineResponse]])
async def list_bird_quarantine(farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
                               access: tuple = Depends(require_farm_access()),
                               _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW))):
    farm, _ = access
    rows = await svc.list_quarantine(db, farm.id, bird_id=bird_id)
    return SuccessResponse(data=[QuarantineResponse.model_validate(q) for q in rows])


@router.get("/quarantine", response_model=SuccessResponse[list[QuarantineResponse]])
async def list_quarantine(farm_id: str, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW)),
                          active_only: bool = Query(False)):
    farm, _ = access
    rows = await svc.list_quarantine(db, farm.id, active_only=active_only)
    return SuccessResponse(data=[QuarantineResponse.model_validate(q) for q in rows])


@router.post("/quarantine/{quarantine_id}/release", response_model=SuccessResponse[QuarantineResponse])
async def release_quarantine(farm_id: str, quarantine_id: UUID, body: QuarantineEnd, db: DBSession, current_user: CurrentUser,
                             access: tuple = Depends(require_farm_access(_CLINICAL)),
                             _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=QuarantineResponse.model_validate(await svc.end_quarantine(db, farm.id, quarantine_id, body, current_user)))


# ── Disease events ────────────────────────────────────────────────────────────

@router.post("/disease-events", response_model=SuccessResponse[DiseaseEventResponse], status_code=status.HTTP_201_CREATED)
async def create_disease_event(farm_id: str, body: DiseaseEventCreate, db: DBSession, current_user: CurrentUser,
                               access: tuple = Depends(require_farm_access(_CLINICAL)),
                               _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=DiseaseEventResponse.model_validate(await svc.create_disease_event(db, farm.id, body, current_user)))


@router.get("/disease-events", response_model=SuccessResponse[list[DiseaseEventResponse]])
async def list_disease_events(farm_id: str, db: DBSession, current_user: CurrentUser,
                              access: tuple = Depends(require_farm_access()),
                              _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW)),
                              status_filter: str | None = Query(None, alias="status")):
    farm, _ = access
    rows = await svc.list_disease_events(db, farm.id, status_filter)
    return SuccessResponse(data=[DiseaseEventResponse.model_validate(e) for e in rows])


@router.patch("/disease-events/{event_id}", response_model=SuccessResponse[DiseaseEventResponse])
async def update_disease_event(farm_id: str, event_id: UUID, body: DiseaseEventUpdate, db: DBSession, current_user: CurrentUser,
                               access: tuple = Depends(require_farm_access(_CLINICAL)),
                               _perm=Depends(require_permission(Permission.AVI_HEALTH_LOG))):
    farm, _ = access
    return SuccessResponse(data=DiseaseEventResponse.model_validate(await svc.update_disease_event(db, farm.id, event_id, body, current_user)))


# ── Farm health summary ───────────────────────────────────────────────────────

@router.get("/health/summary", response_model=SuccessResponse[HealthSummaryResponse])
async def health_summary(farm_id: str, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access()),
                         _perm=Depends(require_permission(Permission.AVI_HEALTH_VIEW))):
    farm, _ = access
    return SuccessResponse(data=HealthSummaryResponse.model_validate(await svc.health_summary(db, farm.id)))
