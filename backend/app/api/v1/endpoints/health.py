"""
Greena — Health Module API Endpoints

Route map:
  POST   /farms/{farm_id}/flocks/{flock_id}/vaccinations            → log vaccination
  GET    /farms/{farm_id}/flocks/{flock_id}/vaccinations            → vaccination history for flock
  GET    /farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id} → single record
  PATCH  /farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id} → correct record
  DELETE /farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id} → soft-delete

  GET    /farms/{farm_id}/health/schedule        → upcoming + overdue vaccinations (all flocks)
  GET    /farms/{farm_id}/health/alerts          → disease alerts relevant to this farm

  --- Admin-only (super_admin) ---
  POST   /health/alerts                          → create alert (draft)
  GET    /health/alerts                          → list all alerts (admin view)
  GET    /health/alerts/{alert_id}               → single alert
  PATCH  /health/alerts/{alert_id}               → update draft alert
  POST   /health/alerts/{alert_id}/publish       → publish draft → active
  POST   /health/alerts/{alert_id}/deactivate    → deactivate active alert

RBAC:
  HEALTH_VACCINATION_LOG    → farm_owner, farm_manager, vet_consultant
  HEALTH_VACCINATION_VIEW   → all roles (farm_owner, farm_manager, vet_consultant, farm_worker, viewer)
  HEALTH_ALERT_VIEW         → all roles
  ADMIN_ALERT_PUBLISH       → super_admin only
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.health import (
    ActiveAlertSummary,
    DiseaseAlertCreate,
    DiseaseAlertResponse,
    DiseaseAlertUpdate,
    FlockHealthSummary,
    HealthEventCreate,
    HealthEventResponse,
    HealthEventUpdate,
    UpcomingVaccinationsResponse,
    VaccinationRecordCreate,
    VaccinationRecordResponse,
    VaccinationRecordUpdate,
)
from app.services import health_service

router = APIRouter()

_HEALTH_WRITE_ROLES = {"farm_owner", "farm_manager", "vet_consultant"}


# ── Health Events — Flock-scoped ──────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/health-events",
    response_model=SuccessResponse[HealthEventResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Log a health event (observation, symptom, treatment, medication, ...)",
    tags=["Health"],
)
async def create_health_event(
    farm_id: str,
    flock_id: str,
    body: HealthEventCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_HEALTH_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_LOG)),
) -> SuccessResponse[HealthEventResponse]:
    import uuid as _uuid
    farm, _ = access
    event = await health_service.create_health_event(
        db, farm, _uuid.UUID(flock_id), body, current_user
    )
    return SuccessResponse(data=HealthEventResponse.model_validate(event))


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/health-events",
    response_model=SuccessResponse[list[HealthEventResponse]],
    summary="List a flock's health events",
    tags=["Health"],
)
async def list_health_events(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_VIEW)),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[HealthEventResponse]]:
    import uuid as _uuid
    farm, _ = access
    events = await health_service.list_health_events(
        db, farm.id, _uuid.UUID(flock_id), status=status_filter, limit=limit, offset=offset
    )
    return SuccessResponse(data=[HealthEventResponse.model_validate(e) for e in events])


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/health-events/{event_id}",
    response_model=SuccessResponse[HealthEventResponse],
    summary="Get a health event",
    tags=["Health"],
)
async def get_health_event(
    farm_id: str,
    flock_id: str,
    event_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_VIEW)),
) -> SuccessResponse[HealthEventResponse]:
    import uuid as _uuid
    farm, _ = access
    event = await health_service.get_health_event(db, farm.id, _uuid.UUID(event_id))
    return SuccessResponse(data=HealthEventResponse.model_validate(event))


@router.patch(
    "/farms/{farm_id}/flocks/{flock_id}/health-events/{event_id}",
    response_model=SuccessResponse[HealthEventResponse],
    summary="Update / progress a health event (e.g. mark resolved)",
    tags=["Health"],
)
async def update_health_event(
    farm_id: str,
    flock_id: str,
    event_id: str,
    body: HealthEventUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_HEALTH_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_LOG)),
) -> SuccessResponse[HealthEventResponse]:
    import uuid as _uuid
    farm, _ = access
    event = await health_service.update_health_event(db, farm.id, _uuid.UUID(event_id), body)
    return SuccessResponse(data=HealthEventResponse.model_validate(event))


@router.delete(
    "/farms/{farm_id}/flocks/{flock_id}/health-events/{event_id}",
    response_model=SuccessResponse[dict],
    summary="Soft-delete a health event",
    tags=["Health"],
)
async def delete_health_event(
    farm_id: str,
    flock_id: str,
    event_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_HEALTH_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_LOG)),
) -> SuccessResponse[dict]:
    import uuid as _uuid
    farm, _ = access
    await health_service.delete_health_event(db, farm.id, _uuid.UUID(event_id))
    return SuccessResponse(data={"message": "Health event deleted."})


@router.get(
    "/farms/{farm_id}/health/summary",
    response_model=SuccessResponse[FlockHealthSummary],
    summary="Farm-wide health dashboard summary",
    tags=["Health"],
)
async def health_summary(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_EVENT_VIEW)),
) -> SuccessResponse[FlockHealthSummary]:
    farm, _ = access
    summary = await health_service.get_farm_health_summary(db, farm)
    return SuccessResponse(data=summary)


# ── Vaccination Records — Flock-scoped ────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/flocks/{flock_id}/vaccinations",
    response_model=SuccessResponse[VaccinationRecordResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Log a vaccination event for a flock",
    tags=["Health"],
)
async def log_vaccination(
    farm_id: str,
    flock_id: str,
    body: VaccinationRecordCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "vet_consultant"})
    ),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_LOG)),
) -> SuccessResponse[VaccinationRecordResponse]:
    farm, member = access
    record = await health_service.log_vaccination(
        db, farm, UUID(flock_id), body, current_user
    )
    await db.commit()
    return SuccessResponse(data=VaccinationRecordResponse.model_validate(record))


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/vaccinations",
    response_model=SuccessResponse[list[VaccinationRecordResponse]],
    summary="List vaccination records for a flock",
    tags=["Health"],
)
async def list_vaccinations(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_VIEW)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[VaccinationRecordResponse]]:
    farm, member = access
    records = await health_service.list_vaccination_records(
        db, farm.id, UUID(flock_id), limit=limit, offset=offset
    )
    return SuccessResponse(
        data=[VaccinationRecordResponse.model_validate(r) for r in records]
    )


@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id}",
    response_model=SuccessResponse[VaccinationRecordResponse],
    summary="Get a single vaccination record",
    tags=["Health"],
)
async def get_vaccination(
    farm_id: str,
    flock_id: str,
    record_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_VIEW)),
) -> SuccessResponse[VaccinationRecordResponse]:
    farm, member = access
    record = await health_service.get_vaccination_record(db, farm.id, UUID(record_id))
    return SuccessResponse(data=VaccinationRecordResponse.model_validate(record))


@router.patch(
    "/farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id}",
    response_model=SuccessResponse[VaccinationRecordResponse],
    summary="Correct a vaccination record",
    tags=["Health"],
)
async def update_vaccination(
    farm_id: str,
    flock_id: str,
    record_id: str,
    body: VaccinationRecordUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(
        require_farm_access({"farm_owner", "farm_manager", "vet_consultant"})
    ),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_LOG)),
) -> SuccessResponse[VaccinationRecordResponse]:
    farm, member = access
    record = await health_service.update_vaccination_record(
        db, farm.id, UUID(record_id), body, current_user
    )
    await db.commit()
    return SuccessResponse(data=VaccinationRecordResponse.model_validate(record))


@router.delete(
    "/farms/{farm_id}/flocks/{flock_id}/vaccinations/{record_id}",
    response_model=SuccessResponse[dict],
    summary="Soft-delete a vaccination record",
    tags=["Health"],
)
async def delete_vaccination(
    farm_id: str,
    flock_id: str,
    record_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_LOG)),
) -> SuccessResponse[dict]:
    farm, member = access
    await health_service.delete_vaccination_record(db, farm.id, UUID(record_id))
    await db.commit()
    return SuccessResponse(data={"deleted": True})


# ── Farm-level Health Queries ─────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/health/schedule",
    response_model=SuccessResponse[UpcomingVaccinationsResponse],
    summary="Get upcoming and overdue vaccinations for all active flocks on the farm",
    tags=["Health"],
)
async def get_vaccination_schedule(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_VACCINATION_VIEW)),
) -> SuccessResponse[UpcomingVaccinationsResponse]:
    farm, member = access
    schedule = await health_service.get_upcoming_vaccinations(db, farm.id)
    return SuccessResponse(data=schedule)


@router.get(
    "/farms/{farm_id}/health/alerts",
    response_model=SuccessResponse[list[DiseaseAlertResponse]],
    summary="Get disease alerts relevant to this farm (county + species matched)",
    tags=["Health"],
)
async def get_farm_alerts(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_ALERT_VIEW)),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[DiseaseAlertResponse]]:
    farm, member = access
    alerts = await health_service.list_disease_alerts(
        db, farm, limit=limit, offset=offset
    )
    return SuccessResponse(
        data=[DiseaseAlertResponse.model_validate(a) for a in alerts]
    )


@router.get(
    "/farms/{farm_id}/health/alerts/active",
    response_model=SuccessResponse[list[ActiveAlertSummary]],
    summary="Get active disease alerts for the Home Dashboard banner (Zone 1)",
    tags=["Health"],
)
async def get_active_alert_banner(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.HEALTH_ALERT_VIEW)),
) -> SuccessResponse[list[ActiveAlertSummary]]:
    farm, member = access
    alerts = await health_service.get_active_alerts_for_farm(db, farm)
    return SuccessResponse(
        data=[ActiveAlertSummary.model_validate(a) for a in alerts]
    )


# ── Admin — Disease Alert Management (super_admin only) ───────────────────────

@router.post(
    "/health/alerts",
    response_model=SuccessResponse[DiseaseAlertResponse],
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Create a new disease alert (draft)",
    tags=["Admin: Health"],
)
async def admin_create_alert(
    body: DiseaseAlertCreate,
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
) -> SuccessResponse[DiseaseAlertResponse]:
    alert = await health_service.admin_create_alert(db, body, current_user)
    await db.commit()
    return SuccessResponse(data=DiseaseAlertResponse.model_validate(alert))


@router.get(
    "/health/alerts",
    response_model=SuccessResponse[list[DiseaseAlertResponse]],
    summary="[Admin] List all disease alerts",
    tags=["Admin: Health"],
)
async def admin_list_alerts(
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
    status_filter: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[DiseaseAlertResponse]]:
    alerts = await health_service.admin_list_all_alerts(
        db, status_filter=status_filter, limit=limit, offset=offset
    )
    return SuccessResponse(
        data=[DiseaseAlertResponse.model_validate(a) for a in alerts]
    )


@router.get(
    "/health/alerts/{alert_id}",
    response_model=SuccessResponse[DiseaseAlertResponse],
    summary="[Admin] Get a single disease alert",
    tags=["Admin: Health"],
)
async def admin_get_alert(
    alert_id: str,
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
) -> SuccessResponse[DiseaseAlertResponse]:
    alert = await health_service.get_disease_alert(db, UUID(alert_id))
    return SuccessResponse(data=DiseaseAlertResponse.model_validate(alert))


@router.patch(
    "/health/alerts/{alert_id}",
    response_model=SuccessResponse[DiseaseAlertResponse],
    summary="[Admin] Update a draft disease alert",
    tags=["Admin: Health"],
)
async def admin_update_alert(
    alert_id: str,
    body: DiseaseAlertUpdate,
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
) -> SuccessResponse[DiseaseAlertResponse]:
    alert = await health_service.admin_update_alert(db, UUID(alert_id), body)
    await db.commit()
    return SuccessResponse(data=DiseaseAlertResponse.model_validate(alert))


@router.post(
    "/health/alerts/{alert_id}/publish",
    response_model=SuccessResponse[DiseaseAlertResponse],
    summary="[Admin] Publish a draft alert (draft → active)",
    tags=["Admin: Health"],
)
async def admin_publish_alert(
    alert_id: str,
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
) -> SuccessResponse[DiseaseAlertResponse]:
    alert = await health_service.admin_publish_alert(db, UUID(alert_id), current_user)
    await db.commit()
    return SuccessResponse(data=DiseaseAlertResponse.model_validate(alert))


@router.post(
    "/health/alerts/{alert_id}/deactivate",
    response_model=SuccessResponse[DiseaseAlertResponse],
    summary="[Admin] Deactivate an active alert",
    tags=["Admin: Health"],
)
async def admin_deactivate_alert(
    alert_id: str,
    db: DBSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_ALERT_PUBLISH)),
) -> SuccessResponse[DiseaseAlertResponse]:
    alert = await health_service.admin_deactivate_alert(db, UUID(alert_id))
    await db.commit()
    return SuccessResponse(data=DiseaseAlertResponse.model_validate(alert))
