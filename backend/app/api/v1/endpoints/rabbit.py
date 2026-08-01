"""
Greena — Rabbit API (Module 17): registry, catalog, timeline & attachments.

Every route is farm-scoped and permission-guarded, reusing the platform's
``require_farm_access`` + ``require_permission`` dependencies (Spec Part 8 §16).
Catalog (breeds) is organisation-level and derives the org from the farm;
bloodlines are farm-scoped.

Route map (prefix /farms/{farm_id}/rabbit):
  Catalog
    GET/POST   /breeds                         list / create breeds
    PATCH      /breeds/{breed_id}              edit a custom breed
    GET/POST   /bloodlines                     list / create bloodlines
    PATCH      /bloodlines/{line_id}           edit a bloodline
  Rabbits
    POST       /rabbits                        register
    GET        /rabbits                        list (filters + pagination)
    GET        /rabbits/{rabbit_id}            detail
    PATCH      /rabbits/{rabbit_id}            edit
    POST       /rabbits/{rabbit_id}/move       move between cages
    POST       /rabbits/{rabbit_id}/archive    archive
    POST       /rabbits/{rabbit_id}/restore    restore
    POST       /rabbits/{rabbit_id}/transfer   transfer ownership
    POST       /rabbits/{rabbit_id}/sell       record sale (herd fact)
    POST       /rabbits/{rabbit_id}/death      record death
    GET        /rabbits/{rabbit_id}/timeline   life-history events
    GET/POST   /rabbits/{rabbit_id}/media      attachments (photo/video/audio)
    GET/POST   /rabbits/{rabbit_id}/documents  attachments (certs / reports / …)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.rabbit import (
    ArchiveInput,
    BloodlineCreate,
    BloodlineResponse,
    BloodlineUpdate,
    BreedCreate,
    BreedResponse,
    BreedUpdate,
    DeathInput,
    DocumentCreate,
    DocumentResponse,
    MediaCreate,
    MediaResponse,
    MoveInput,
    RabbitCreate,
    RabbitDetailResponse,
    RabbitEventResponse,
    RabbitResponse,
    RabbitUpdate,
    SaleInput,
    TransferInput,
)
from app.services import rabbit_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit", tags=["Rabbit"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}


# ── Response builders ─────────────────────────────────────────────────────────

def _rabbit_response(r, names) -> RabbitResponse:
    breed_names, line_names, cage_names = names
    payload = {k: getattr(r, k) for k in (
        "id", "created_at", "updated_at", "farm_id", "breed_id", "bloodline_id", "cage_id",
        "litter_id", "internal_ref", "name", "ear_tag", "tattoo", "qr_code", "rfid", "variety", "color",
        "sex", "purpose", "purposes", "date_of_birth", "dob_estimated", "birth_weight_g",
        "current_weight_g", "lifecycle_stage", "status", "reproductive_status",
        "fertility_status", "acquisition_type", "acquired_on", "sire_id", "dam_id", "tags", "notes",
    )}
    return RabbitResponse(
        **payload,
        breed_name=breed_names.get(r.breed_id),
        bloodline_name=line_names.get(r.bloodline_id),
        cage_name=cage_names.get(r.cage_id),
    )


# ── Catalog: Breeds ─────────────────────────────────────────────────────────────

@router.get("/breeds", response_model=SuccessResponse[list[BreedResponse]])
async def list_breeds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_breeds(db, farm.organization_id)
    return SuccessResponse(data=[BreedResponse.model_validate(r) for r in rows])


@router.post("/breeds", response_model=SuccessResponse[BreedResponse], status_code=status.HTTP_201_CREATED)
async def create_breed(
    farm_id: str, body: BreedCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_breed(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


@router.patch("/breeds/{breed_id}", response_model=SuccessResponse[BreedResponse])
async def update_breed(
    farm_id: str, breed_id: UUID, body: BreedUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_breed(db, farm.organization_id, breed_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


# ── Catalog: Bloodlines ─────────────────────────────────────────────────────────

@router.get("/bloodlines", response_model=SuccessResponse[list[BloodlineResponse]])
async def list_bloodlines(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_bloodlines(db, farm.id)
    return SuccessResponse(data=[BloodlineResponse.model_validate(r) for r in rows])


@router.post("/bloodlines", response_model=SuccessResponse[BloodlineResponse], status_code=status.HTTP_201_CREATED)
async def create_bloodline(
    farm_id: str, body: BloodlineCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_bloodline(db, farm, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


@router.patch("/bloodlines/{line_id}", response_model=SuccessResponse[BloodlineResponse])
async def update_bloodline(
    farm_id: str, line_id: UUID, body: BloodlineUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_bloodline(db, farm.id, line_id, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


# ── Rabbits ─────────────────────────────────────────────────────────────────────

@router.post("/rabbits", response_model=SuccessResponse[RabbitResponse], status_code=status.HTTP_201_CREATED)
async def register_rabbit(
    farm_id: str, body: RabbitCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_CREATE)),
):
    farm, _ = access
    r = await svc.create_rabbit(db, farm, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.get("/rabbits", response_model=ListResponse[RabbitResponse])
async def list_rabbits(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
    status_: str | None = Query(None, alias="status"),
    breed_id: UUID | None = Query(None),
    bloodline_id: UUID | None = Query(None),
    cage_id: UUID | None = Query(None),
    sex: str | None = Query(None),
    purpose: str | None = Query(None),
    lifecycle_stage: str | None = Query(None),
    search: str | None = Query(None),
    tag: str | None = Query(None),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    farm, _ = access
    offset = (page - 1) * limit
    rows, total, names = await svc.list_rabbits(
        db, farm.id, status=status_, breed_id=breed_id, bloodline_id=bloodline_id,
        cage_id=cage_id, sex=sex, purpose=purpose, lifecycle_stage=lifecycle_stage,
        search=search, tag=tag, include_archived=include_archived, limit=limit, offset=offset,
    )
    data = [_rabbit_response(r, names) for r in rows]
    return ListResponse(
        data=data,
        meta=PaginationMeta(total=total, page=page, limit=limit, pages=ceil(total / limit) if total else 1),
    )


@router.get("/rabbits/{rabbit_id}", response_model=SuccessResponse[RabbitDetailResponse])
async def get_rabbit(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
):
    farm, _ = access
    r, names, parent_refs = await svc.get_rabbit_detail(db, farm.id, rabbit_id)
    base = _rabbit_response(r, names)
    detail = RabbitDetailResponse(
        **base.model_dump(),
        sire_ref=parent_refs.get(r.sire_id),
        dam_ref=parent_refs.get(r.dam_id),
        location_path=base.cage_name,
    )
    return SuccessResponse(data=detail)


@router.patch("/rabbits/{rabbit_id}", response_model=SuccessResponse[RabbitResponse])
async def update_rabbit(
    farm_id: str, rabbit_id: UUID, body: RabbitUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_EDIT)),
):
    farm, _ = access
    r = await svc.update_rabbit(db, farm.id, rabbit_id, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/move", response_model=SuccessResponse[RabbitResponse])
async def move_rabbit(
    farm_id: str, rabbit_id: UUID, body: MoveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_EDIT)),
):
    farm, _ = access
    r = await svc.move_rabbit(db, farm.id, rabbit_id, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/archive", response_model=SuccessResponse[RabbitResponse])
async def archive_rabbit(
    farm_id: str, rabbit_id: UUID, body: ArchiveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_ARCHIVE)),
):
    farm, _ = access
    r = await svc.archive_rabbit(db, farm.id, rabbit_id, body.reason, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/restore", response_model=SuccessResponse[RabbitResponse])
async def restore_rabbit(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_ARCHIVE)),
):
    farm, _ = access
    r = await svc.restore_rabbit(db, farm.id, rabbit_id, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/transfer", response_model=SuccessResponse[RabbitResponse])
async def transfer_rabbit(
    farm_id: str, rabbit_id: UUID, body: TransferInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_TRANSACT)),
):
    farm, _ = access
    r = await svc.transfer_rabbit(db, farm.id, rabbit_id, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/sell", response_model=SuccessResponse[RabbitResponse])
async def sell_rabbit(
    farm_id: str, rabbit_id: UUID, body: SaleInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_TRANSACT)),
):
    farm, _ = access
    r = await svc.sell_rabbit(db, farm.id, rabbit_id, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.post("/rabbits/{rabbit_id}/death", response_model=SuccessResponse[RabbitResponse])
async def record_death(
    farm_id: str, rabbit_id: UUID, body: DeathInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_TRANSACT)),
):
    farm, _ = access
    r = await svc.record_death(db, farm.id, rabbit_id, body, current_user)
    names = await svc._resolve_names(db, [r])
    return SuccessResponse(data=_rabbit_response(r, names))


@router.get("/rabbits/{rabbit_id}/timeline", response_model=SuccessResponse[list[RabbitEventResponse]])
async def rabbit_timeline(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    farm, _ = access
    rows = await svc.list_events(db, farm.id, rabbit_id, limit=limit, offset=offset)
    return SuccessResponse(data=[RabbitEventResponse.model_validate(r) for r in rows])


# ── Attachments ─────────────────────────────────────────────────────────────────

@router.get("/rabbits/{rabbit_id}/media", response_model=SuccessResponse[list[MediaResponse]])
async def list_media(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
):
    farm, _ = access
    rows = await svc.list_media(db, farm.id, rabbit_id)
    return SuccessResponse(data=[MediaResponse.model_validate(r) for r in rows])


@router.post("/rabbits/{rabbit_id}/media", response_model=SuccessResponse[MediaResponse], status_code=status.HTTP_201_CREATED)
async def add_media(
    farm_id: str, rabbit_id: UUID, body: MediaCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_EDIT)),
):
    farm, _ = access
    row = await svc.add_media(db, farm.id, rabbit_id, body, current_user)
    return SuccessResponse(data=MediaResponse.model_validate(row))


@router.get("/rabbits/{rabbit_id}/documents", response_model=SuccessResponse[list[DocumentResponse]])
async def list_documents(
    farm_id: str, rabbit_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_VIEW)),
):
    farm, _ = access
    rows = await svc.list_documents(db, farm.id, rabbit_id)
    return SuccessResponse(data=[DocumentResponse.model_validate(r) for r in rows])


@router.post("/rabbits/{rabbit_id}/documents", response_model=SuccessResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def add_document(
    farm_id: str, rabbit_id: UUID, body: DocumentCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_EDIT)),
):
    farm, _ = access
    row = await svc.add_document(db, farm.id, rabbit_id, body, current_user)
    return SuccessResponse(data=DocumentResponse.model_validate(row))
