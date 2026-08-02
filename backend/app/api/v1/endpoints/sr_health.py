"""
Greena — Small Ruminant Health API (Modules 18/19, Milestone 5).

Health records, vaccination, deworming, hoof care and mortality for goats and
sheep. Vaccination/deworming/hoof/health follow-ups reuse the platform Reminder
engine. Clinical writes require SR_HEALTH_LOG (owner/manager/worker/vet); reads
SR_HEALTH_VIEW. The health summary emits patterns with a §4.4 disclaimer — never a
diagnosis.

Route map (prefix /farms/{farm_id}/sr/{species}/health):
    GET/POST  /animals/{animal_id}/records       health history / record
    GET/POST  /animals/{animal_id}/vaccinations  vaccination history / record
    GET/POST  /animals/{animal_id}/deworming     deworming history / record
    GET/POST  /animals/{animal_id}/hoof-care     hoof-care history / record
    POST      /animals/{animal_id}/mortality     record mortality
    GET       /mortality                         farm mortality log
    GET       /summary                           deterministic health patterns
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    DewormingCreate,
    DewormingResponse,
    HealthRecordCreate,
    HealthRecordResponse,
    HoofCareCreate,
    HoofCareResponse,
    MortalityCreate,
    MortalityResponse,
    VaccinationCreate,
    VaccinationResponse,
)
from app.services import small_ruminant_health_service as hsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/health", tags=["Small Ruminant Health"])

_LOG = Depends(require_permission(Permission.SR_HEALTH_LOG))
_VIEW = Depends(require_permission(Permission.SR_HEALTH_VIEW))


@router.get("/animals/{animal_id}/records", response_model=SuccessResponse[list[HealthRecordResponse]])
async def list_health(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await hsvc.list_health(db, farm.id, species, animal_id)
    return SuccessResponse(data=[HealthRecordResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/records", response_model=SuccessResponse[HealthRecordResponse],
             status_code=status.HTTP_201_CREATED)
async def record_health(
    farm_id: str, animal_id: UUID, body: HealthRecordCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    r = await hsvc.record_health(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=HealthRecordResponse.model_validate(r))


@router.get("/animals/{animal_id}/vaccinations", response_model=SuccessResponse[list[VaccinationResponse]])
async def list_vaccinations(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await hsvc.list_vaccinations(db, farm.id, species, animal_id)
    return SuccessResponse(data=[VaccinationResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/vaccinations", response_model=SuccessResponse[VaccinationResponse],
             status_code=status.HTTP_201_CREATED)
async def record_vaccination(
    farm_id: str, animal_id: UUID, body: VaccinationCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    r = await hsvc.record_vaccination(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=VaccinationResponse.model_validate(r))


@router.get("/animals/{animal_id}/deworming", response_model=SuccessResponse[list[DewormingResponse]])
async def list_deworming(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await hsvc.list_deworming(db, farm.id, species, animal_id)
    return SuccessResponse(data=[DewormingResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/deworming", response_model=SuccessResponse[DewormingResponse],
             status_code=status.HTTP_201_CREATED)
async def record_deworming(
    farm_id: str, animal_id: UUID, body: DewormingCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    r = await hsvc.record_deworming(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=DewormingResponse.model_validate(r))


@router.get("/animals/{animal_id}/hoof-care", response_model=SuccessResponse[list[HoofCareResponse]])
async def list_hoof_care(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await hsvc.list_hoof_care(db, farm.id, species, animal_id)
    return SuccessResponse(data=[HoofCareResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/hoof-care", response_model=SuccessResponse[HoofCareResponse],
             status_code=status.HTTP_201_CREATED)
async def record_hoof_care(
    farm_id: str, animal_id: UUID, body: HoofCareCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    r = await hsvc.record_hoof_care(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=HoofCareResponse.model_validate(r))


@router.post("/animals/{animal_id}/mortality", response_model=SuccessResponse[MortalityResponse],
             status_code=status.HTTP_201_CREATED)
async def record_mortality(
    farm_id: str, animal_id: UUID, body: MortalityCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    r = await hsvc.record_mortality(db, farm, species, animal_id, body, current_user)
    return SuccessResponse(data=MortalityResponse.model_validate(r))


@router.get("/mortality", response_model=SuccessResponse[list[MortalityResponse]])
async def list_mortality(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await hsvc.list_mortality(db, farm.id, species)
    return SuccessResponse(data=[MortalityResponse.model_validate(r) for r in rows])


@router.get("/summary", response_model=SuccessResponse[dict])
async def health_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await hsvc.health_summary(db, farm.id, species))
