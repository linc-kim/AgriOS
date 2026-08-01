"""
Greena — Rabbit Health API (Module 17, Milestone 5).

Health records, vaccinations (reusing the platform Reminder engine) and mortality.
Every route is farm-scoped and permission-guarded. Writes → RABBIT_HEALTH_LOG;
reads → RABBIT_HEALTH_VIEW.

Route map (prefix /farms/{farm_id}/rabbit):
  Health
    POST   /rabbits/{id}/health          record a clinical event
    GET    /rabbits/{id}/health          medical history (chronological)
  Vaccination
    POST   /rabbits/{id}/vaccinations    record a vaccination (+ Reminder)
    GET    /rabbits/{id}/vaccinations    rabbit vaccination history
    GET    /vaccinations                 farm vaccination list
  Mortality
    POST   /rabbits/{id}/mortality       record death (→ deceased)
    GET    /mortality                    farm mortality list
  Analytics
    GET    /health/summary               deterministic health/mortality summary
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.rabbit import (
    HealthRecordCreate,
    HealthRecordResponse,
    MortalityCreate,
    MortalityResponse,
    VaccinationCreate,
    VaccinationResponse,
)
from app.services import rabbit_health_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit", tags=["Rabbit Health"])

_LOG = Permission.RABBIT_HEALTH_LOG
_VIEW = Permission.RABBIT_HEALTH_VIEW


# ── Health records ───────────────────────────────────────────────────────────────

@router.post("/rabbits/{rabbit_id}/health", response_model=SuccessResponse[HealthRecordResponse], status_code=status.HTTP_201_CREATED)
async def record_health(
    farm_id: str, rabbit_id: UUID, body: HealthRecordCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_LOG)),
):
    farm, _ = access
    row = await svc.record_health(db, farm, rabbit_id, body, current_user)
    return SuccessResponse(data=HealthRecordResponse.model_validate(row))


@router.get("/rabbits/{rabbit_id}/health", response_model=SuccessResponse[list[HealthRecordResponse]])
async def list_health(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    rows = await svc.list_health(db, farm.id, rabbit_id)
    return SuccessResponse(data=[HealthRecordResponse.model_validate(r) for r in rows])


# ── Vaccinations ─────────────────────────────────────────────────────────────────

@router.post("/rabbits/{rabbit_id}/vaccinations", response_model=SuccessResponse[VaccinationResponse], status_code=status.HTTP_201_CREATED)
async def record_vaccination(
    farm_id: str, rabbit_id: UUID, body: VaccinationCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_LOG)),
):
    farm, _ = access
    row = await svc.record_vaccination(db, farm, rabbit_id, body, current_user)
    return SuccessResponse(data=VaccinationResponse.model_validate(row))


@router.get("/rabbits/{rabbit_id}/vaccinations", response_model=SuccessResponse[list[VaccinationResponse]])
async def list_rabbit_vaccinations(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    rows = await svc.list_vaccinations(db, farm.id, rabbit_id)
    return SuccessResponse(data=[VaccinationResponse.model_validate(r) for r in rows])


@router.get("/vaccinations", response_model=SuccessResponse[list[VaccinationResponse]])
async def list_vaccinations(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    rows = await svc.list_vaccinations(db, farm.id, None)
    return SuccessResponse(data=[VaccinationResponse.model_validate(r) for r in rows])


# ── Mortality ────────────────────────────────────────────────────────────────────

@router.post("/rabbits/{rabbit_id}/mortality", response_model=SuccessResponse[MortalityResponse], status_code=status.HTTP_201_CREATED)
async def record_mortality(
    farm_id: str, rabbit_id: UUID, body: MortalityCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_LOG)),
):
    farm, _ = access
    row = await svc.record_mortality(db, farm, rabbit_id, body, current_user)
    return SuccessResponse(data=MortalityResponse.model_validate(row))


@router.get("/mortality", response_model=SuccessResponse[list[MortalityResponse]])
async def list_mortality(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    rows = await svc.list_mortality(db, farm.id)
    return SuccessResponse(data=[MortalityResponse.model_validate(r) for r in rows])


# ── Analytics ────────────────────────────────────────────────────────────────────

@router.get("/health/summary", response_model=SuccessResponse[dict])
async def health_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.health_summary(db, farm.id))
