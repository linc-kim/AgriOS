"""
Greena — Rabbit Breeding API (Module 17, Milestone 3).

Breeding cycle, litters, pedigree and genetics. Every route is farm-scoped and
permission-guarded. Reads use RABBIT_BREEDING_VIEW; pedigree/genetics reads use
RABBIT_PEDIGREE_VIEW; writes use RABBIT_BREEDING_MANAGE (ledger CON-M3-7).

Route map (prefix /farms/{farm_id}/rabbit):
  Breeding
    POST     /breedings                        schedule / record a mating
    GET      /breedings                        list (filters + pagination)
    GET      /breedings/{id}                   detail
    POST     /breedings/{id}/service           record a service
    POST     /breedings/{id}/pregnancy-check   confirm / negative
    POST     /breedings/{id}/prepare-kindling  nest-box preparation
    POST     /breedings/{id}/kindling          record kindling (→ litter [+kits])
    POST     /breedings/{id}/close             close the cycle
  Litters
    GET      /litters                          list
    GET      /litters/{id}                     detail (+ performance)
    POST     /litters/{id}/foster              record foster in/out
    POST     /litters/{id}/weaning             record weaning
  Pedigree & genetics
    GET      /rabbits/{id}/pedigree            ancestry tree + inbreeding F
    GET      /rabbits/{id}/breeding-performance doe/buck performance
    POST     /breeding/compatibility           assess a candidate buck × doe
    GET      /breeding/reproduction-summary    herd reproduction dashboard
    GET      /breeding/genetics                advisory genetic analytics
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.rabbit import (
    BreedingCreate,
    BreedingResponse,
    CompatibilityInput,
    FosterInput,
    KindlingInput,
    LitterDetailResponse,
    LitterResponse,
    PregnancyCheckInput,
    PrepareKindlingInput,
    ServiceInput,
    WeaningInput,
)
from app.services import rabbit_breeding_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit", tags=["Rabbit Breeding"])

_VIEW = Permission.RABBIT_BREEDING_VIEW
_MANAGE = Permission.RABBIT_BREEDING_MANAGE
_PEDIGREE = Permission.RABBIT_PEDIGREE_VIEW


# ── Breeding ─────────────────────────────────────────────────────────────────────

@router.post("/breedings", response_model=SuccessResponse[BreedingResponse], status_code=status.HTTP_201_CREATED)
async def create_breeding(
    farm_id: str, body: BreedingCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.create_breeding(db, farm, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


@router.get("/breedings", response_model=ListResponse[BreedingResponse])
async def list_breedings(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    doe_id: UUID | None = Query(None),
    buck_id: UUID | None = Query(None),
    status_: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    farm, _ = access
    rows, total = await svc.list_breedings(
        db, farm.id, doe_id=doe_id, buck_id=buck_id, status=status_, limit=limit, offset=(page - 1) * limit
    )
    return ListResponse(
        data=[BreedingResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 1),
    )


@router.get("/breedings/{breeding_id}", response_model=SuccessResponse[BreedingResponse])
async def get_breeding(
    farm_id: str, breeding_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    row = await svc.get_breeding(db, farm.id, breeding_id)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


@router.post("/breedings/{breeding_id}/service", response_model=SuccessResponse[BreedingResponse])
async def record_service(
    farm_id: str, breeding_id: UUID, body: ServiceInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.record_service(db, farm.id, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


@router.post("/breedings/{breeding_id}/pregnancy-check", response_model=SuccessResponse[BreedingResponse])
async def pregnancy_check(
    farm_id: str, breeding_id: UUID, body: PregnancyCheckInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.record_pregnancy_check(db, farm.id, breeding_id, body, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


@router.post("/breedings/{breeding_id}/prepare-kindling", response_model=SuccessResponse[BreedingResponse])
async def prepare_kindling(
    farm_id: str, breeding_id: UUID, body: PrepareKindlingInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.prepare_kindling(db, farm.id, breeding_id, body.prepared_on, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


@router.post("/breedings/{breeding_id}/kindling", response_model=SuccessResponse[LitterResponse], status_code=status.HTTP_201_CREATED)
async def record_kindling(
    farm_id: str, breeding_id: UUID, body: KindlingInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    litter = await svc.record_kindling(db, farm, breeding_id, body, current_user)
    return SuccessResponse(data=LitterResponse.model_validate(litter))


@router.post("/breedings/{breeding_id}/close", response_model=SuccessResponse[BreedingResponse])
async def close_breeding(
    farm_id: str, breeding_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.close_breeding(db, farm.id, breeding_id, current_user)
    return SuccessResponse(data=BreedingResponse.model_validate(row))


# ── Litters ──────────────────────────────────────────────────────────────────────

@router.get("/litters", response_model=ListResponse[LitterResponse])
async def list_litters(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    doe_id: UUID | None = Query(None),
    status_: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    farm, _ = access
    rows, total = await svc.list_litters(
        db, farm.id, doe_id=doe_id, status=status_, limit=limit, offset=(page - 1) * limit
    )
    return ListResponse(
        data=[LitterResponse.model_validate(r) for r in rows],
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 1),
    )


@router.get("/litters/{litter_id}", response_model=SuccessResponse[LitterDetailResponse])
async def get_litter(
    farm_id: str, litter_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    litter, performance = await svc.get_litter_detail(db, farm.id, litter_id)
    return SuccessResponse(data=LitterDetailResponse(
        **LitterResponse.model_validate(litter).model_dump(), performance=performance
    ))


@router.post("/litters/{litter_id}/foster", response_model=SuccessResponse[LitterResponse])
async def record_foster(
    farm_id: str, litter_id: UUID, body: FosterInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.record_foster(db, farm.id, litter_id, body, current_user)
    return SuccessResponse(data=LitterResponse.model_validate(row))


@router.post("/litters/{litter_id}/weaning", response_model=SuccessResponse[LitterResponse])
async def record_weaning(
    farm_id: str, litter_id: UUID, body: WeaningInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_MANAGE)),
):
    farm, _ = access
    row = await svc.record_weaning(db, farm.id, litter_id, body, current_user)
    return SuccessResponse(data=LitterResponse.model_validate(row))


# ── Pedigree & genetics ──────────────────────────────────────────────────────────

@router.get("/rabbits/{rabbit_id}/pedigree", response_model=SuccessResponse[dict])
async def get_pedigree(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_PEDIGREE)),
    generations: int = Query(4, ge=1, le=6),
):
    farm, _ = access
    return SuccessResponse(data=await svc.get_pedigree(db, farm.id, rabbit_id, generations))


@router.get("/rabbits/{rabbit_id}/breeding-performance", response_model=SuccessResponse[dict])
async def breeding_performance(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.get_breeding_performance(db, farm.id, rabbit_id))


@router.post("/breeding/compatibility", response_model=SuccessResponse[dict])
async def check_compatibility(
    farm_id: str, body: CompatibilityInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_PEDIGREE)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.check_compatibility(db, farm.id, body.buck_id, body.doe_id))


@router.get("/breeding/reproduction-summary", response_model=SuccessResponse[dict])
async def reproduction_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.reproduction_summary(db, farm.id))


@router.get("/breeding/genetics", response_model=SuccessResponse[dict])
async def genetics_overview(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_PEDIGREE)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.genetic_overview(db, farm.id))
