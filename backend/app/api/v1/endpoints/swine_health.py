"""
Greena — Swine Health API (Module 20, Milestone 6).

Independent clinical event records — disease cases (group-capable), vaccinations,
treatments (therapeutic/preventive), procedures, observations, lab tests — plus
mortality (preserves cause history + transitions the pig) and historical isolation.
The health summary is a deterministic pattern, never a diagnosis (frozen §4.4).
Writes require SWINE_HEALTH_LOG; reads SWINE_HEALTH_VIEW.

Route map (prefix /farms/{farm_id}/swine/health):
    GET/POST /disease-cases   · PATCH /disease-cases/{id}
    GET/POST /vaccinations
    GET/POST /treatments      (filter ?intent=)
    GET/POST /procedures
    GET/POST /observations
    GET/POST /lab-tests       · PATCH /lab-tests/{id}
    GET/POST /mortality
    GET/POST /isolations      · POST /isolations/{id}/end
    GET      /summary
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    DiseaseCaseCreate,
    DiseaseCaseResponse,
    DiseaseCaseUpdate,
    IsolationEndInput,
    IsolationResponse,
    IsolationStartInput,
    LabTestCreate,
    LabTestResponse,
    LabTestUpdate,
    MortalityCreate,
    MortalityResponse,
    ObservationCreate,
    ObservationResponse,
    ProcedureCreate,
    ProcedureResponse,
    TreatmentCreate,
    TreatmentResponse,
    VaccinationCreate,
    VaccinationResponse,
)
from app.services import swine_health_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/health", tags=["Swine Health"])

_LOG = Depends(require_permission(Permission.SWINE_HEALTH_LOG))
_VIEW = Depends(require_permission(Permission.SWINE_HEALTH_VIEW))


# ── Disease cases ───────────────────────────────────────────────────────────────

@router.get("/disease-cases", response_model=SuccessResponse[list[DiseaseCaseResponse]])
async def list_disease_cases(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    status_: str | None = None, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_disease_cases(db, farm.id, status=status_, pig_id=pig_id)
    return SuccessResponse(data=[DiseaseCaseResponse.model_validate(r) for r in rows])


@router.post("/disease-cases", response_model=SuccessResponse[DiseaseCaseResponse],
             status_code=status.HTTP_201_CREATED)
async def create_disease_case(
    farm_id: str, body: DiseaseCaseCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_disease_case(db, farm, body, current_user)
    return SuccessResponse(data=DiseaseCaseResponse.model_validate(row))


@router.patch("/disease-cases/{case_id}", response_model=SuccessResponse[DiseaseCaseResponse])
async def update_disease_case(
    farm_id: str, case_id: UUID, body: DiseaseCaseUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.update_disease_case(db, farm.id, case_id, body, current_user)
    return SuccessResponse(data=DiseaseCaseResponse.model_validate(row))


# ── Vaccinations ────────────────────────────────────────────────────────────────

@router.get("/vaccinations", response_model=SuccessResponse[list[VaccinationResponse]])
async def list_vaccinations(
    farm_id: str, db: DBSession, current_user: CurrentUser, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_vaccinations(db, farm.id, pig_id=pig_id)
    return SuccessResponse(data=[VaccinationResponse.model_validate(r) for r in rows])


@router.post("/vaccinations", response_model=SuccessResponse[VaccinationResponse],
             status_code=status.HTTP_201_CREATED)
async def create_vaccination(
    farm_id: str, body: VaccinationCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_vaccination(db, farm, body, current_user)
    return SuccessResponse(data=VaccinationResponse.model_validate(row))


# ── Treatments (therapeutic / preventive) ───────────────────────────────────────

@router.get("/treatments", response_model=SuccessResponse[list[TreatmentResponse]])
async def list_treatments(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    pig_id: UUID | None = None, intent: str | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_treatments(db, farm.id, pig_id=pig_id, intent=intent)
    return SuccessResponse(data=[TreatmentResponse.model_validate(r) for r in rows])


@router.post("/treatments", response_model=SuccessResponse[TreatmentResponse],
             status_code=status.HTTP_201_CREATED)
async def create_treatment(
    farm_id: str, body: TreatmentCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_treatment(db, farm, body, current_user)
    return SuccessResponse(data=TreatmentResponse.model_validate(row))


# ── Procedures ──────────────────────────────────────────────────────────────────

@router.get("/procedures", response_model=SuccessResponse[list[ProcedureResponse]])
async def list_procedures(
    farm_id: str, db: DBSession, current_user: CurrentUser, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_procedures(db, farm.id, pig_id=pig_id)
    return SuccessResponse(data=[ProcedureResponse.model_validate(r) for r in rows])


@router.post("/procedures", response_model=SuccessResponse[ProcedureResponse],
             status_code=status.HTTP_201_CREATED)
async def create_procedure(
    farm_id: str, body: ProcedureCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_procedure(db, farm, body, current_user)
    return SuccessResponse(data=ProcedureResponse.model_validate(row))


# ── Observations ────────────────────────────────────────────────────────────────

@router.get("/observations", response_model=SuccessResponse[list[ObservationResponse]])
async def list_observations(
    farm_id: str, db: DBSession, current_user: CurrentUser, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_observations(db, farm.id, pig_id=pig_id)
    return SuccessResponse(data=[ObservationResponse.model_validate(r) for r in rows])


@router.post("/observations", response_model=SuccessResponse[ObservationResponse],
             status_code=status.HTTP_201_CREATED)
async def create_observation(
    farm_id: str, body: ObservationCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_observation(db, farm, body, current_user)
    return SuccessResponse(data=ObservationResponse.model_validate(row))


# ── Lab tests ───────────────────────────────────────────────────────────────────

@router.get("/lab-tests", response_model=SuccessResponse[list[LabTestResponse]])
async def list_lab_tests(
    farm_id: str, db: DBSession, current_user: CurrentUser, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_lab_tests(db, farm.id, pig_id=pig_id)
    return SuccessResponse(data=[LabTestResponse.model_validate(r) for r in rows])


@router.post("/lab-tests", response_model=SuccessResponse[LabTestResponse],
             status_code=status.HTTP_201_CREATED)
async def create_lab_test(
    farm_id: str, body: LabTestCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.create_lab_test(db, farm, body, current_user)
    return SuccessResponse(data=LabTestResponse.model_validate(row))


@router.patch("/lab-tests/{test_id}", response_model=SuccessResponse[LabTestResponse])
async def update_lab_test(
    farm_id: str, test_id: UUID, body: LabTestUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.update_lab_test(db, farm.id, test_id, body, current_user)
    return SuccessResponse(data=LabTestResponse.model_validate(row))


# ── Mortality ───────────────────────────────────────────────────────────────────

@router.get("/mortality", response_model=SuccessResponse[list[MortalityResponse]])
async def list_mortality(
    farm_id: str, db: DBSession, current_user: CurrentUser, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_mortality(db, farm.id, pig_id=pig_id)
    return SuccessResponse(data=[MortalityResponse.model_validate(r) for r in rows])


@router.post("/mortality", response_model=SuccessResponse[MortalityResponse],
             status_code=status.HTTP_201_CREATED)
async def record_mortality(
    farm_id: str, body: MortalityCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.record_mortality(db, farm, body, current_user)
    return SuccessResponse(data=MortalityResponse.model_validate(row))


# ── Isolation (historical) ──────────────────────────────────────────────────────

@router.get("/isolations", response_model=SuccessResponse[list[IsolationResponse]])
async def list_isolations(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    status_: str | None = None, pig_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_isolations(db, farm.id, status=status_, pig_id=pig_id)
    return SuccessResponse(data=[IsolationResponse.model_validate(r) for r in rows])


@router.post("/isolations", response_model=SuccessResponse[IsolationResponse],
             status_code=status.HTTP_201_CREATED)
async def start_isolation(
    farm_id: str, body: IsolationStartInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.start_isolation(db, farm, body, current_user)
    return SuccessResponse(data=IsolationResponse.model_validate(row))


@router.post("/isolations/{isolation_id}/end", response_model=SuccessResponse[IsolationResponse])
async def end_isolation(
    farm_id: str, isolation_id: UUID, body: IsolationEndInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.end_isolation(db, farm.id, isolation_id, body, current_user)
    return SuccessResponse(data=IsolationResponse.model_validate(row))


# ── Summary (deterministic; never a diagnosis) ──────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[dict])
async def health_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.health_summary(db, farm.id))
