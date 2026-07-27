"""
Greena — Aviculture Breeding API (Module 15, Part 4)

Pairs, breeding programmes, pedigrees, relatedness and compatibility. Every
genetic figure is computed by the pure ``pedigree_engine`` and returned
honesty-labelled (calculated / forecast / recorded / unknown). Circular ancestry
is rejected at the write boundary. Routes are farm-scoped and permission-guarded.

Prefix: /farms/{farm_id}/aviculture
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.aviculture_breeding import (
    CompatibilityRequest,
    CompatibilityResponse,
    GoalCreate,
    GoalResponse,
    OffspringResponse,
    PairCreate,
    PairDissolve,
    PairEventResponse,
    PairResponse,
    PedigreeResponse,
    ProgramCreate,
    ProgramResponse,
    ProgramUpdate,
    RelatednessResponse,
)
from app.services import breeding_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture — Breeding"])

_MANAGE = {"farm_owner", "farm_manager"}


def _pair_response(pair, names: dict, compatibility: dict | None = None) -> PairResponse:
    data = PairResponse.model_validate(pair)
    data.male_name = names.get(pair.male_bird_id)
    data.female_name = names.get(pair.female_bird_id)
    data.compatibility = compatibility
    return data


# ── Pairs ─────────────────────────────────────────────────────────────────────

@router.post("/pairs", response_model=SuccessResponse[PairResponse], status_code=status.HTTP_201_CREATED)
async def create_pair(
    farm_id: str, body: PairCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
):
    farm, _ = access
    pair = await svc.create_pair(db, farm, body, current_user)
    return SuccessResponse(data=_pair_response(pair, await _names_for(db, farm.id, pair)))


async def _names_for(db, farm_id, pair) -> dict:
    from sqlalchemy import select
    from app.models.aviculture import AviBird
    ids = [b for b in (pair.male_bird_id, pair.female_bird_id) if b]
    if not ids:
        return {}
    rows = await db.execute(select(AviBird.id, AviBird.name, AviBird.internal_ref).where(AviBird.id.in_(ids)))
    return {r[0]: (r[1] or r[2]) for r in rows}


@router.get("/pairs", response_model=ListResponse[PairResponse])
async def list_pairs(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
    status_filter: str | None = Query(None, alias="status"),
    program_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    farm, _ = access
    rows, total, names = await svc.list_pairs(db, farm.id, status=status_filter, program_id=program_id,
                                              limit=limit, offset=offset)
    return ListResponse(
        data=[_pair_response(p, names) for p in rows],
        meta=PaginationMeta(total=total, page=(offset // limit) + 1, limit=limit,
                            pages=max(1, ceil(total / limit)) if total else 1),
    )


@router.get("/pairs/{pair_id}", response_model=SuccessResponse[PairResponse])
async def get_pair(
    farm_id: str, pair_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    pair = await svc.get_pair(db, farm.id, pair_id)
    compatibility = await svc.pair_compatibility(db, farm.id, pair)
    return SuccessResponse(data=_pair_response(pair, await _names_for(db, farm.id, pair), compatibility))


@router.post("/pairs/{pair_id}/dissolve", response_model=SuccessResponse[PairResponse])
async def dissolve_pair(
    farm_id: str, pair_id: UUID, body: PairDissolve, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
):
    farm, _ = access
    pair = await svc.dissolve_pair(db, farm.id, pair_id, body, current_user)
    return SuccessResponse(data=_pair_response(pair, await _names_for(db, farm.id, pair)))


@router.get("/pairs/{pair_id}/events", response_model=SuccessResponse[list[PairEventResponse]])
async def pair_events(
    farm_id: str, pair_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await svc.list_pair_events(db, farm.id, pair_id)
    return SuccessResponse(data=[PairEventResponse.model_validate(e) for e in rows])


# ── Compatibility / pedigree / relatedness ────────────────────────────────────

@router.post("/compatibility", response_model=SuccessResponse[CompatibilityResponse])
async def check_compatibility(
    farm_id: str, body: CompatibilityRequest, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    result = await svc.assess_compatibility(db, farm.id, body.male_bird_id, body.female_bird_id)
    return SuccessResponse(data=CompatibilityResponse.model_validate(result))


@router.get("/birds/{bird_id}/pedigree", response_model=SuccessResponse[PedigreeResponse])
async def bird_pedigree(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
    generations: int = Query(5, ge=1, le=10),
):
    farm, _ = access
    return SuccessResponse(data=PedigreeResponse.model_validate(
        await svc.get_pedigree(db, farm.id, bird_id, generations)))


@router.get("/birds/{bird_id}/offspring", response_model=SuccessResponse[OffspringResponse])
async def bird_offspring(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=OffspringResponse.model_validate(await svc.get_offspring(db, farm.id, bird_id)))


@router.post("/birds/{bird_id}/parents", response_model=SuccessResponse[dict])
async def set_parents(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
    sire_id: UUID | None = Body(None), dam_id: UUID | None = Body(None),
):
    farm, _ = access
    bird = await svc.set_parents(db, farm.id, bird_id, sire_id, dam_id, current_user)
    return SuccessResponse(data={"id": str(bird.id), "sire_id": str(bird.sire_id) if bird.sire_id else None,
                                 "dam_id": str(bird.dam_id) if bird.dam_id else None})


@router.get("/relatedness", response_model=SuccessResponse[RelatednessResponse])
async def relatedness(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
    bird_a: UUID = Query(...), bird_b: UUID = Query(...),
):
    farm, _ = access
    return SuccessResponse(data=RelatednessResponse.model_validate(
        await svc.get_relatedness(db, farm.id, bird_a, bird_b)))


# ── Breeding programmes ───────────────────────────────────────────────────────

@router.post("/breeding-programs", response_model=SuccessResponse[ProgramResponse], status_code=status.HTTP_201_CREATED)
async def create_program(
    farm_id: str, body: ProgramCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=ProgramResponse.model_validate(await svc.create_program(db, farm, body, current_user)))


@router.get("/breeding-programs", response_model=SuccessResponse[list[ProgramResponse]])
async def list_programs(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
    status_filter: str | None = Query(None, alias="status"),
):
    farm, _ = access
    rows, counts = await svc.list_programs(db, farm.id, status_filter)
    out = []
    for p in rows:
        r = ProgramResponse.model_validate(p)
        r.pair_count = counts.get(p.id, 0)
        out.append(r)
    return SuccessResponse(data=out)


@router.get("/breeding-programs/{program_id}", response_model=SuccessResponse[ProgramResponse])
async def get_program(
    farm_id: str, program_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=ProgramResponse.model_validate(await svc.get_program(db, farm.id, program_id)))


@router.patch("/breeding-programs/{program_id}", response_model=SuccessResponse[ProgramResponse])
async def update_program(
    farm_id: str, program_id: UUID, body: ProgramUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=ProgramResponse.model_validate(await svc.update_program(db, farm.id, program_id, body, current_user)))


@router.post("/breeding-programs/{program_id}/goals", response_model=SuccessResponse[GoalResponse], status_code=status.HTTP_201_CREATED)
async def add_goal(
    farm_id: str, program_id: UUID, body: GoalCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGE)),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_MANAGE)),
):
    farm, _ = access
    return SuccessResponse(data=GoalResponse.model_validate(await svc.add_goal(db, farm.id, program_id, body, current_user)))


@router.get("/breeding-programs/{program_id}/goals", response_model=SuccessResponse[list[GoalResponse]])
async def list_goals(
    farm_id: str, program_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await svc.list_goals(db, farm.id, program_id)
    return SuccessResponse(data=[GoalResponse.model_validate(g) for g in rows])
