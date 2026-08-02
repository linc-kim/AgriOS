"""
Greena — Swine Breeding API (Module 20, Milestone 3).

The reproduction workspace: service (natural or AI) → pregnancy check, plus
pedigree, compatibility and performance. Natural mating, artificial insemination
and pregnancy are three views over one cycle table (filter by ``method`` /
``status``). Breeding writes require SWINE_BREEDING_MANAGE; reads SWINE_BREEDING_VIEW;
pedigree/genetics reads SWINE_PEDIGREE_VIEW.

Route map (prefix /farms/{farm_id}/swine/breeding):
    GET/POST   /                                list / register breedings (natural or AI)
    POST       /{breeding_id}/service           record service date
    POST       /{breeding_id}/pregnancy-check   record pregnancy result
    GET        /pregnancies                     confirmed pregnancies (Pregnancy workspace)
    GET        /summary                         reproduction dashboard
    GET        /dam/{pig_id}/performance        per-sow service history
    GET        /sire/{pig_id}/performance       per-boar fertility
    GET        /pedigree/{pig_id}               ancestry + inbreeding F
    GET        /compatibility                   boar × dam pairing assessment
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    BreedingCreate,
    BreedingResponse,
    PregnancyCheckInput,
    ServiceInput,
)
from app.services import swine_breeding_service as bsvc

router = APIRouter(prefix="/farms/{farm_id}/swine/breeding", tags=["Swine Breeding"])


@router.get("", response_model=SuccessResponse[list[BreedingResponse]])
async def list_breedings(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    dam_id: UUID | None = None, sire_id: UUID | None = None,
    method: str | None = None, status_: str | None = Query(None, alias="status"),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await bsvc.list_breedings(db, farm.id, dam_id=dam_id, sire_id=sire_id, method=method, status=status_)
    return SuccessResponse(data=[BreedingResponse.model_validate(r) for r in rows])


@router.post("", response_model=SuccessResponse[BreedingResponse], status_code=status.HTTP_201_CREATED)
async def create_breeding(
    farm_id: str, body: BreedingCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.create_breeding(db, farm, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.post("/{breeding_id}/service", response_model=SuccessResponse[BreedingResponse])
async def record_service(
    farm_id: str, breeding_id: UUID, body: ServiceInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.record_service(db, farm.id, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.post("/{breeding_id}/pregnancy-check", response_model=SuccessResponse[BreedingResponse])
async def record_pregnancy_check(
    farm_id: str, breeding_id: UUID, body: PregnancyCheckInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.record_pregnancy_check(db, farm.id, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.get("/pregnancies", response_model=SuccessResponse[list[BreedingResponse]])
async def list_pregnancies(
    farm_id: str, db: DBSession, current_user: CurrentUser, risk_level: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await bsvc.list_pregnancies(db, farm.id, risk_level=risk_level)
    return SuccessResponse(data=[BreedingResponse.model_validate(r) for r in rows])


@router.get("/summary", response_model=SuccessResponse[dict])
async def reproduction_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.reproduction_summary(db, farm.id))


@router.get("/dam/{pig_id}/performance", response_model=SuccessResponse[dict])
async def dam_performance(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.dam_performance(db, farm.id, pig_id))


@router.get("/sire/{pig_id}/performance", response_model=SuccessResponse[dict])
async def sire_performance(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.sire_performance(db, farm.id, pig_id))


@router.get("/pedigree/{pig_id}", response_model=SuccessResponse[dict])
async def pedigree(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    max_generations: int = Query(5, ge=1, le=8),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_PEDIGREE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.pedigree(db, farm.id, pig_id, max_generations))


@router.get("/compatibility", response_model=SuccessResponse[dict])
async def compatibility(
    farm_id: str, sire_id: UUID, dam_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_PEDIGREE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.compatibility(db, farm.id, sire_id, dam_id))
