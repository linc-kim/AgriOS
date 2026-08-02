"""
Greena — Swine API (Module 20): registry, catalog, timeline & attachments.

Single-species pig workspace (no ``species`` path segment). Farm isolation +
permission checks reuse the platform's ``require_farm_access`` + ``require_permission``
dependencies (Swine Doc 3 §22, Doc 5 §15).

Route map (prefix /farms/{farm_id}/swine):
  Catalog
    GET/POST   /breeds                       list / create breeds
    PATCH      /breeds/{breed_id}            edit a custom breed
    GET/POST   /bloodlines                   list / create bloodlines
    PATCH      /bloodlines/{line_id}         edit a bloodline
  Pigs
    POST       /pigs                         register
    GET        /pigs                         list (filters + pagination)
    GET        /pigs/{pig_id}                detail
    PATCH      /pigs/{pig_id}                edit
    POST       /pigs/{pig_id}/move           move (group / pen)
    POST       /pigs/{pig_id}/archive        archive
    POST       /pigs/{pig_id}/restore        restore
    POST       /pigs/{pig_id}/transfer       transfer ownership
    POST       /pigs/{pig_id}/sell           record sale (herd fact)
    POST       /pigs/{pig_id}/death          record death
    POST       /pigs/{pig_id}/cull           record culling
    GET        /pigs/{pig_id}/timeline       life-history events
    GET/POST   /pigs/{pig_id}/media          attachments (photo/video/audio)
    GET/POST   /pigs/{pig_id}/documents      attachments (certs / reports / …)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.swine import (
    ArchiveInput,
    BloodlineCreate,
    BloodlineResponse,
    BloodlineUpdate,
    BreedCreate,
    BreedResponse,
    BreedUpdate,
    CullInput,
    DeathInput,
    DocumentCreate,
    DocumentResponse,
    MediaCreate,
    MediaResponse,
    MovementResponse,
    MoveInput,
    PigCreate,
    PigDetailResponse,
    PigEventResponse,
    PigResponse,
    PigUpdate,
    SaleInput,
    TransferInput,
)
from app.services import swine_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine", tags=["Swine"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}


# ── Response builders ─────────────────────────────────────────────────────────

def _pig_response(p, names) -> PigResponse:
    payload = {k: getattr(p, k) for k in (
        "id", "created_at", "updated_at", "farm_id", "breed_id", "bloodline_id",
        "herd_id", "group_id", "pen_id", "internal_ref", "name", "ear_tag", "ear_notch",
        "tattoo", "qr_code", "rfid", "visual_id", "registration_number", "line", "color",
        "sex", "purpose", "purposes", "registration_status", "date_of_birth", "dob_estimated",
        "birth_weight_kg", "current_weight_kg", "production_stage", "status", "reproductive_status",
        "fertility_status", "market_status", "parity", "acquisition_type", "acquired_on",
        "sire_id", "dam_id", "tags", "notes",
    )}
    return PigResponse(
        **payload,
        breed_name=names["breed"].get(p.breed_id),
        bloodline_name=names["bloodline"].get(p.bloodline_id),
        herd_name=names["herd"].get(p.herd_id),
        group_name=names["group"].get(p.group_id),
        pen_name=names["pen"].get(p.pen_id),
    )


# ── Catalog: Breeds ─────────────────────────────────────────────────────────────

@router.get("/breeds", response_model=SuccessResponse[list[BreedResponse]])
async def list_breeds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_breeds(db, farm.organization_id)
    return SuccessResponse(data=[BreedResponse.model_validate(r) for r in rows])


@router.post("/breeds", response_model=SuccessResponse[BreedResponse], status_code=status.HTTP_201_CREATED)
async def create_breed(
    farm_id: str, body: BreedCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_breed(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


@router.patch("/breeds/{breed_id}", response_model=SuccessResponse[BreedResponse])
async def update_breed(
    farm_id: str, breed_id: UUID, body: BreedUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_breed(db, farm.organization_id, breed_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


# ── Catalog: Bloodlines ─────────────────────────────────────────────────────────

@router.get("/bloodlines", response_model=SuccessResponse[list[BloodlineResponse]])
async def list_bloodlines(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_bloodlines(db, farm.id)
    return SuccessResponse(data=[BloodlineResponse.model_validate(r) for r in rows])


@router.post("/bloodlines", response_model=SuccessResponse[BloodlineResponse],
             status_code=status.HTTP_201_CREATED)
async def create_bloodline(
    farm_id: str, body: BloodlineCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_bloodline(db, farm, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


@router.patch("/bloodlines/{line_id}", response_model=SuccessResponse[BloodlineResponse])
async def update_bloodline(
    farm_id: str, line_id: UUID, body: BloodlineUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_bloodline(db, farm.id, line_id, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


# ── Pigs ────────────────────────────────────────────────────────────────────────

@router.post("/pigs", response_model=SuccessResponse[PigResponse], status_code=status.HTTP_201_CREATED)
async def create_pig(
    farm_id: str, body: PigCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_CREATE)),
):
    farm, _ = access
    p = await svc.create_pig(db, farm, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.get("/pigs", response_model=ListResponse[PigResponse])
async def list_pigs(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    status_: str | None = Query(None, alias="status"),
    breed_id: UUID | None = None, herd_id: UUID | None = None, group_id: UUID | None = None,
    pen_id: UUID | None = None, sex: str | None = None, purpose: str | None = None,
    production_stage: str | None = None, reproductive_status: str | None = None,
    market_status: str | None = None, search: str | None = None, tag: str | None = None,
    include_archived: bool = False, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    pigs, total, names = await svc.list_pigs(
        db, farm.id, status=status_, breed_id=breed_id, herd_id=herd_id, group_id=group_id,
        pen_id=pen_id, sex=sex, purpose=purpose, production_stage=production_stage,
        reproductive_status=reproductive_status, market_status=market_status, search=search, tag=tag,
        include_archived=include_archived, limit=page_size, offset=(page - 1) * page_size,
    )
    meta = PaginationMeta(total=total, page=page, limit=page_size,
                          pages=ceil(total / page_size) if page_size else 0)
    return ListResponse(data=[_pig_response(p, names) for p in pigs], meta=meta)


@router.get("/pigs/{pig_id}", response_model=SuccessResponse[PigDetailResponse])
async def get_pig(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    p, names, refs = await svc.get_pig_detail(db, farm.id, pig_id)
    base = _pig_response(p, names)
    detail = PigDetailResponse(**base.model_dump(), sire_ref=refs.get(p.sire_id), dam_ref=refs.get(p.dam_id))
    return SuccessResponse(data=detail)


@router.patch("/pigs/{pig_id}", response_model=SuccessResponse[PigResponse])
async def update_pig(
    farm_id: str, pig_id: UUID, body: PigUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_EDIT)),
):
    farm, _ = access
    p = await svc.update_pig(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/move", response_model=SuccessResponse[PigResponse])
async def move_pig(
    farm_id: str, pig_id: UUID, body: MoveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_EDIT)),
):
    farm, _ = access
    p = await svc.move_pig(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/archive", response_model=SuccessResponse[PigResponse])
async def archive_pig(
    farm_id: str, pig_id: UUID, body: ArchiveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_ARCHIVE)),
):
    farm, _ = access
    p = await svc.archive_pig(db, farm.id, pig_id, body.reason, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/restore", response_model=SuccessResponse[PigResponse])
async def restore_pig(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_ARCHIVE)),
):
    farm, _ = access
    p = await svc.restore_pig(db, farm.id, pig_id, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/transfer", response_model=SuccessResponse[PigResponse])
async def transfer_pig(
    farm_id: str, pig_id: UUID, body: TransferInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_TRANSACT)),
):
    farm, _ = access
    p = await svc.transfer_pig(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/sell", response_model=SuccessResponse[PigResponse])
async def sell_pig(
    farm_id: str, pig_id: UUID, body: SaleInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_TRANSACT)),
):
    farm, _ = access
    p = await svc.sell_pig(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/death", response_model=SuccessResponse[PigResponse])
async def record_death(
    farm_id: str, pig_id: UUID, body: DeathInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_TRANSACT)),
):
    farm, _ = access
    p = await svc.record_death(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


@router.post("/pigs/{pig_id}/cull", response_model=SuccessResponse[PigResponse])
async def cull_pig(
    farm_id: str, pig_id: UUID, body: CullInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SWINE_TRANSACT)),
):
    farm, _ = access
    p = await svc.cull_pig(db, farm.id, pig_id, body, current_user)
    _, names, _refs = await svc.get_pig_detail(db, farm.id, p.id)
    return SuccessResponse(data=_pig_response(p, names))


# ── Timeline & attachments ──────────────────────────────────────────────────────

@router.get("/pigs/{pig_id}/timeline", response_model=SuccessResponse[list[PigEventResponse]])
async def list_timeline(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    events = await svc.list_events(db, farm.id, pig_id, limit=limit, offset=offset)
    return SuccessResponse(data=[PigEventResponse.model_validate(e) for e in events])


@router.get("/pigs/{pig_id}/movements", response_model=SuccessResponse[list[MovementResponse]])
async def list_movements(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    rows = await svc.list_movements(db, farm.id, pig_id, limit=limit, offset=offset)
    return SuccessResponse(data=[MovementResponse.model_validate(r) for r in rows])


@router.get("/pigs/{pig_id}/media", response_model=SuccessResponse[list[MediaResponse]])
async def list_media(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    rows = await svc.list_media(db, farm.id, pig_id)
    return SuccessResponse(data=[MediaResponse.model_validate(r) for r in rows])


@router.post("/pigs/{pig_id}/media", response_model=SuccessResponse[MediaResponse],
             status_code=status.HTTP_201_CREATED)
async def add_media(
    farm_id: str, pig_id: UUID, body: MediaCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_EDIT)),
):
    farm, _ = access
    row = await svc.add_media(db, farm.id, pig_id, body, current_user)
    return SuccessResponse(data=MediaResponse.model_validate(row))


@router.get("/pigs/{pig_id}/documents", response_model=SuccessResponse[list[DocumentResponse]])
async def list_documents(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_VIEW)),
):
    farm, _ = access
    rows = await svc.list_documents(db, farm.id, pig_id)
    return SuccessResponse(data=[DocumentResponse.model_validate(r) for r in rows])


@router.post("/pigs/{pig_id}/documents", response_model=SuccessResponse[DocumentResponse],
             status_code=status.HTTP_201_CREATED)
async def add_document(
    farm_id: str, pig_id: UUID, body: DocumentCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_EDIT)),
):
    farm, _ = access
    row = await svc.add_document(db, farm.id, pig_id, body, current_user)
    return SuccessResponse(data=DocumentResponse.model_validate(row))
