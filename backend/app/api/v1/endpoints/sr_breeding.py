"""
Greena — Small Ruminant Breeding API (Modules 18/19, Milestone 3).

The shared reproduction workspace for goats and sheep: service → pregnancy check →
birth (kidding/lambing) → weaning, plus pedigree, compatibility and performance.
Breeding writes require SR_BREEDING_MANAGE; reads SR_BREEDING_VIEW; pedigree/
genetics reads SR_PEDIGREE_VIEW.

Route map (prefix /farms/{farm_id}/sr/{species}/breeding):
    GET/POST   /                                  list / register breedings
    POST       /{breeding_id}/service             record service date
    POST       /{breeding_id}/pregnancy-check     record pregnancy result
    POST       /{breeding_id}/birth               record birth (+ optional offspring)
    GET        /births                            list births
    POST       /births/{birth_id}/wean           record weaning
    GET        /summary                           reproduction dashboard
    GET        /dam/{animal_id}/performance       per-dam productivity
    GET        /sire/{animal_id}/performance      per-sire fertility
    GET        /pedigree/{animal_id}              ancestry + inbreeding F
    GET        /compatibility                     sire × dam pairing assessment
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import (
    BirthRecordInput,
    BirthResponse,
    BreedingCreate,
    BreedingResponse,
    PregnancyCheckInput,
    ServiceInput,
    WeaningInput,
)
from app.services import small_ruminant_breeding_service as bsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/breeding", tags=["Small Ruminant Breeding"])


@router.get("", response_model=SuccessResponse[list[BreedingResponse]])
async def list_breedings(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    dam_id: UUID | None = None, status_: str | None = Query(None, alias="status"),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await bsvc.list_breedings(db, farm.id, species, dam_id=dam_id, status=status_)
    return SuccessResponse(data=[BreedingResponse.model_validate(r) for r in rows])


@router.post("", response_model=SuccessResponse[BreedingResponse], status_code=status.HTTP_201_CREATED)
async def create_breeding(
    farm_id: str, body: BreedingCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.create_breeding(db, farm, species, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.post("/{breeding_id}/service", response_model=SuccessResponse[BreedingResponse])
async def record_service(
    farm_id: str, breeding_id: UUID, body: ServiceInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.record_service(db, farm.id, species, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.post("/{breeding_id}/pregnancy-check", response_model=SuccessResponse[BreedingResponse])
async def record_pregnancy_check(
    farm_id: str, breeding_id: UUID, body: PregnancyCheckInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_MANAGE)),
):
    farm, _ = access
    b = await bsvc.record_pregnancy_check(db, farm.id, species, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(b))


@router.post("/{breeding_id}/birth", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def record_birth(
    farm_id: str, breeding_id: UUID, body: BirthRecordInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_MANAGE)),
):
    farm, _ = access
    birth, offspring = await bsvc.record_birth(db, farm, species, breeding_id, body, current_user)
    return SuccessResponse(data={"birth": BirthResponse.model_validate(birth).model_dump(mode="json"),
                                 "offspring_created": offspring})


@router.get("/births", response_model=SuccessResponse[list[BirthResponse]])
async def list_births(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    dam_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await bsvc.list_births(db, farm.id, species, dam_id=dam_id)
    return SuccessResponse(data=[BirthResponse.model_validate(r) for r in rows])


@router.post("/births/{birth_id}/wean", response_model=SuccessResponse[BirthResponse])
async def record_weaning(
    farm_id: str, birth_id: UUID, body: WeaningInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_MANAGE)),
):
    farm, _ = access
    birth = await bsvc.record_weaning(db, farm.id, species, birth_id, body, current_user)
    return SuccessResponse(data=BirthResponse.model_validate(birth))


@router.get("/summary", response_model=SuccessResponse[dict])
async def reproduction_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.reproduction_summary(db, farm.id, species))


@router.get("/dam/{animal_id}/performance", response_model=SuccessResponse[dict])
async def dam_performance(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.dam_performance(db, farm.id, species, animal_id))


@router.get("/sire/{animal_id}/performance", response_model=SuccessResponse[dict])
async def sire_performance(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.sire_performance(db, farm.id, species, animal_id))


@router.get("/pedigree/{animal_id}", response_model=SuccessResponse[dict])
async def pedigree(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    max_generations: int = Query(5, ge=1, le=8),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_PEDIGREE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.pedigree(db, farm.id, species, animal_id, max_generations))


@router.get("/compatibility", response_model=SuccessResponse[dict])
async def compatibility(
    farm_id: str, sire_id: UUID, dam_id: UUID, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_PEDIGREE_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await bsvc.compatibility(db, farm.id, species, sire_id, dam_id))
