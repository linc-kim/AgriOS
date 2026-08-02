"""
Greena — Small Ruminant API (Modules 18 Goat + 19 Sheep): registry, catalog,
timeline & attachments.

Two species workspaces over one shared implementation. The ``species`` path
segment ('goat' | 'sheep') selects the workspace and is validated on every route;
farm isolation + species scoping are enforced in the service. Every route reuses
the platform's ``require_farm_access`` + ``require_permission`` dependencies
(Goat Doc 7 §16).

Route map (prefix /farms/{farm_id}/sr/{species}):
  Catalog
    GET/POST   /breeds                          list / create breeds
    PATCH      /breeds/{breed_id}               edit a custom breed
    GET/POST   /bloodlines                      list / create bloodlines
    PATCH      /bloodlines/{line_id}            edit a bloodline
  Animals
    POST       /animals                         register
    GET        /animals                         list (filters + pagination)
    GET        /animals/{animal_id}             detail
    PATCH      /animals/{animal_id}             edit
    POST       /animals/{animal_id}/move        move (group / pen / pasture)
    POST       /animals/{animal_id}/archive     archive
    POST       /animals/{animal_id}/restore     restore
    POST       /animals/{animal_id}/transfer    transfer ownership
    POST       /animals/{animal_id}/sell        record sale (herd fact)
    POST       /animals/{animal_id}/death       record death
    POST       /animals/{animal_id}/cull        record culling
    GET        /animals/{animal_id}/timeline    life-history events
    GET/POST   /animals/{animal_id}/media       attachments (photo/video/audio)
    GET/POST   /animals/{animal_id}/documents   attachments (certs / reports / …)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.exceptions import NotFoundException
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.small_ruminant import (
    AnimalCreate,
    AnimalDetailResponse,
    AnimalEventResponse,
    AnimalResponse,
    AnimalUpdate,
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
    MoveInput,
    SaleInput,
    TransferInput,
)
from app.services import small_ruminant_service as svc
from app.services import small_ruminant_species_config as cfg

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}", tags=["Small Ruminant"])

_MANAGER_ROLES = {"farm_owner", "farm_manager"}


def require_species(species: str) -> str:
    """Validate the workspace discriminator in the path (no such workspace → 404)."""
    if not cfg.is_supported(species):
        raise NotFoundException(f"No small-ruminant workspace for {species!r}.")
    return species


SpeciesParam = Depends(require_species)


# ── Response builders ─────────────────────────────────────────────────────────

def _animal_response(a, names) -> AnimalResponse:
    payload = {k: getattr(a, k) for k in (
        "id", "created_at", "updated_at", "species", "farm_id", "breed_id", "bloodline_id",
        "herd_id", "group_id", "pen_id", "pasture_id", "internal_ref", "name", "ear_tag",
        "tattoo", "qr_code", "rfid", "visual_id", "registration_number", "variety", "color",
        "sex", "purpose", "purposes", "horn_status", "registration_status", "date_of_birth",
        "dob_estimated", "birth_type", "birth_weight_kg", "current_weight_kg", "lifecycle_stage",
        "status", "reproductive_status", "fertility_status", "acquisition_type", "acquired_on",
        "sire_id", "dam_id", "tags", "notes",
    )}
    return AnimalResponse(
        **payload,
        breed_name=names["breed"].get(a.breed_id),
        bloodline_name=names["bloodline"].get(a.bloodline_id),
        herd_name=names["herd"].get(a.herd_id),
        group_name=names["group"].get(a.group_id),
        pen_name=names["pen"].get(a.pen_id),
        pasture_name=names["pasture"].get(a.pasture_id),
    )


# ── Catalog: Breeds ─────────────────────────────────────────────────────────────

@router.get("/breeds", response_model=SuccessResponse[list[BreedResponse]])
async def list_breeds(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_breeds(db, species, farm.organization_id)
    return SuccessResponse(data=[BreedResponse.model_validate(r) for r in rows])


@router.post("/breeds", response_model=SuccessResponse[BreedResponse], status_code=status.HTTP_201_CREATED)
async def create_breed(
    farm_id: str, body: BreedCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_breed(db, species, farm.organization_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


@router.patch("/breeds/{breed_id}", response_model=SuccessResponse[BreedResponse])
async def update_breed(
    farm_id: str, breed_id: UUID, body: BreedUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_breed(db, species, farm.organization_id, breed_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


# ── Catalog: Bloodlines ─────────────────────────────────────────────────────────

@router.get("/bloodlines", response_model=SuccessResponse[list[BloodlineResponse]])
async def list_bloodlines(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_bloodlines(db, farm.id, species)
    return SuccessResponse(data=[BloodlineResponse.model_validate(r) for r in rows])


@router.post("/bloodlines", response_model=SuccessResponse[BloodlineResponse],
             status_code=status.HTTP_201_CREATED)
async def create_bloodline(
    farm_id: str, body: BloodlineCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_bloodline(db, farm, species, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


@router.patch("/bloodlines/{line_id}", response_model=SuccessResponse[BloodlineResponse])
async def update_bloodline(
    farm_id: str, line_id: UUID, body: BloodlineUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.update_bloodline(db, farm.id, species, line_id, body, current_user)
    return SuccessResponse(data=BloodlineResponse.model_validate(row))


# ── Animals ─────────────────────────────────────────────────────────────────────

@router.post("/animals", response_model=SuccessResponse[AnimalResponse], status_code=status.HTTP_201_CREATED)
async def create_animal(
    farm_id: str, body: AnimalCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_CREATE)),
):
    farm, _ = access
    a = await svc.create_animal(db, farm, species, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.get("/animals", response_model=ListResponse[AnimalResponse])
async def list_animals(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    status_: str | None = Query(None, alias="status"),
    breed_id: UUID | None = None, herd_id: UUID | None = None, group_id: UUID | None = None,
    pen_id: UUID | None = None, pasture_id: UUID | None = None,
    sex: str | None = None, purpose: str | None = None, lifecycle_stage: str | None = None,
    reproductive_status: str | None = None, search: str | None = None, tag: str | None = None,
    include_archived: bool = False, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    animals, total, names = await svc.list_animals(
        db, farm.id, species, status=status_, breed_id=breed_id, herd_id=herd_id, group_id=group_id,
        pen_id=pen_id, pasture_id=pasture_id, sex=sex, purpose=purpose, lifecycle_stage=lifecycle_stage,
        reproductive_status=reproductive_status, search=search, tag=tag,
        include_archived=include_archived, limit=page_size, offset=(page - 1) * page_size,
    )
    meta = PaginationMeta(total=total, page=page, limit=page_size,
                          pages=ceil(total / page_size) if page_size else 0)
    return ListResponse(data=[_animal_response(a, names) for a in animals], meta=meta)


@router.get("/animals/{animal_id}", response_model=SuccessResponse[AnimalDetailResponse])
async def get_animal(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    a, names, refs = await svc.get_animal_detail(db, farm.id, species, animal_id)
    base = _animal_response(a, names)
    detail = AnimalDetailResponse(**base.model_dump(),
                                  sire_ref=refs.get(a.sire_id), dam_ref=refs.get(a.dam_id))
    return SuccessResponse(data=detail)


@router.patch("/animals/{animal_id}", response_model=SuccessResponse[AnimalResponse])
async def update_animal(
    farm_id: str, animal_id: UUID, body: AnimalUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_EDIT)),
):
    farm, _ = access
    a = await svc.update_animal(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/move", response_model=SuccessResponse[AnimalResponse])
async def move_animal(
    farm_id: str, animal_id: UUID, body: MoveInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_EDIT)),
):
    farm, _ = access
    a = await svc.move_animal(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/archive", response_model=SuccessResponse[AnimalResponse])
async def archive_animal(
    farm_id: str, animal_id: UUID, body: ArchiveInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_ARCHIVE)),
):
    farm, _ = access
    a = await svc.archive_animal(db, farm.id, species, animal_id, body.reason, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/restore", response_model=SuccessResponse[AnimalResponse])
async def restore_animal(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_ARCHIVE)),
):
    farm, _ = access
    a = await svc.restore_animal(db, farm.id, species, animal_id, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/transfer", response_model=SuccessResponse[AnimalResponse])
async def transfer_animal(
    farm_id: str, animal_id: UUID, body: TransferInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_TRANSACT)),
):
    farm, _ = access
    a = await svc.transfer_animal(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/sell", response_model=SuccessResponse[AnimalResponse])
async def sell_animal(
    farm_id: str, animal_id: UUID, body: SaleInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_TRANSACT)),
):
    farm, _ = access
    a = await svc.sell_animal(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/death", response_model=SuccessResponse[AnimalResponse])
async def record_death(
    farm_id: str, animal_id: UUID, body: DeathInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_TRANSACT)),
):
    farm, _ = access
    a = await svc.record_death(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


@router.post("/animals/{animal_id}/cull", response_model=SuccessResponse[AnimalResponse])
async def cull_animal(
    farm_id: str, animal_id: UUID, body: CullInput, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.SR_TRANSACT)),
):
    farm, _ = access
    a = await svc.cull_animal(db, farm.id, species, animal_id, body, current_user)
    _, names, _refs = await svc.get_animal_detail(db, farm.id, species, a.id)
    return SuccessResponse(data=_animal_response(a, names))


# ── Timeline & attachments ──────────────────────────────────────────────────────

@router.get("/animals/{animal_id}/timeline", response_model=SuccessResponse[list[AnimalEventResponse]])
async def list_timeline(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    events = await svc.list_events(db, farm.id, species, animal_id, limit=limit, offset=offset)
    return SuccessResponse(data=[AnimalEventResponse.model_validate(e) for e in events])


@router.get("/animals/{animal_id}/media", response_model=SuccessResponse[list[MediaResponse]])
async def list_media(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    rows = await svc.list_media(db, farm.id, species, animal_id)
    return SuccessResponse(data=[MediaResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/media", response_model=SuccessResponse[MediaResponse],
             status_code=status.HTTP_201_CREATED)
async def add_media(
    farm_id: str, animal_id: UUID, body: MediaCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_EDIT)),
):
    farm, _ = access
    row = await svc.add_media(db, farm.id, species, animal_id, body, current_user)
    return SuccessResponse(data=MediaResponse.model_validate(row))


@router.get("/animals/{animal_id}/documents", response_model=SuccessResponse[list[DocumentResponse]])
async def list_documents(
    farm_id: str, animal_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_VIEW)),
):
    farm, _ = access
    rows = await svc.list_documents(db, farm.id, species, animal_id)
    return SuccessResponse(data=[DocumentResponse.model_validate(r) for r in rows])


@router.post("/animals/{animal_id}/documents", response_model=SuccessResponse[DocumentResponse],
             status_code=status.HTTP_201_CREATED)
async def add_document(
    farm_id: str, animal_id: UUID, body: DocumentCreate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_EDIT)),
):
    farm, _ = access
    row = await svc.add_document(db, farm.id, species, animal_id, body, current_user)
    return SuccessResponse(data=DocumentResponse.model_validate(row))
