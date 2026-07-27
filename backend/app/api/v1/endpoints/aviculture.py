"""
Greena — Aviculture API (Module 15)

Collection management for individual birds. Every route is farm-scoped and
permission-guarded, reusing the platform's ``require_farm_access`` +
``require_permission`` dependencies (Doc 05 §4, Doc 10). Catalog routes are
organisation-level and derive the org from the farm.

Route map (prefix /farms/{farm_id}/aviculture):
  Catalog
    GET/POST  /species                       list / create species
    GET/POST  /breeds                         list / create breeds
    GET/POST  /mutations                      list / create mutations
  Birds
    POST      /birds                          create
    GET       /birds                          list (filters + pagination)
    GET       /birds/{bird_id}                detail
    PATCH     /birds/{bird_id}                edit
    POST      /birds/{bird_id}/archive        archive
    POST      /birds/{bird_id}/restore        restore
    POST      /birds/{bird_id}/transfer       transfer ownership
    POST      /birds/{bird_id}/sell           record sale
    POST      /birds/{bird_id}/purchase       record purchase provenance
    POST      /birds/{bird_id}/death          record death
    GET       /birds/{bird_id}/ownership      ownership history
    GET       /birds/{bird_id}/timeline       life-history events
    GET/POST  /birds/{bird_id}/media          attachments (photo/video/audio)
    GET/POST  /birds/{bird_id}/documents      attachments (certs / permits / …)
"""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import ListResponse, PaginationMeta, SuccessResponse
from app.schemas.aviculture import (
    ArchiveInput,
    BirdCreate,
    BirdDetailResponse,
    BirdEventResponse,
    BirdMutationResponse,
    BirdResponse,
    BirdUpdate,
    BreedCreate,
    BreedResponse,
    DeathInput,
    DocumentCreate,
    DocumentResponse,
    MediaCreate,
    MediaResponse,
    MutationCreate,
    MutationResponse,
    OwnershipResponse,
    PurchaseInput,
    SaleInput,
    SpeciesCreate,
    SpeciesResponse,
    TransferInput,
)
from app.services import aviculture_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture"])


# ── Response builders ─────────────────────────────────────────────────────────

def _bird_response(bird, names) -> BirdResponse:
    species_names, breed_names, aviary_names = names
    return BirdResponse(
        **{k: getattr(bird, k) for k in (
            "id", "created_at", "updated_at", "farm_id", "species_id", "breed_id",
            "aviary_id", "internal_ref", "name", "ring_number", "band_number",
            "microchip", "colour_description", "sex", "sex_method", "dna_status",
            "hatch_date", "hatch_date_estimated", "sire_id", "dam_id",
            "lifecycle_stage", "status", "acquisition_type", "acquired_on", "tags", "notes",
        )},
        species_name=species_names.get(bird.species_id),
        breed_name=breed_names.get(bird.breed_id),
        aviary_name=aviary_names.get(bird.aviary_id),
    )


# ── Catalog ───────────────────────────────────────────────────────────────────

@router.get("/species", response_model=SuccessResponse[list[SpeciesResponse]])
async def list_species(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_VIEW)),
):
    farm, _ = access
    rows = await svc.list_species(db, farm.organization_id)
    return SuccessResponse(data=[SpeciesResponse.model_validate(r) for r in rows])


@router.post("/species", response_model=SuccessResponse[SpeciesResponse], status_code=status.HTTP_201_CREATED)
async def create_species(
    farm_id: str, body: SpeciesCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_species(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=SpeciesResponse.model_validate(row))


@router.get("/breeds", response_model=SuccessResponse[list[BreedResponse]])
async def list_breeds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_VIEW)),
    species_id: UUID | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_breeds(db, farm.organization_id, species_id)
    return SuccessResponse(data=[BreedResponse.model_validate(r) for r in rows])


@router.post("/breeds", response_model=SuccessResponse[BreedResponse], status_code=status.HTTP_201_CREATED)
async def create_breed(
    farm_id: str, body: BreedCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_breed(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=BreedResponse.model_validate(row))


@router.get("/mutations", response_model=SuccessResponse[list[MutationResponse]])
async def list_mutations(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_VIEW)),
    species_id: UUID | None = Query(None),
):
    farm, _ = access
    rows = await svc.list_mutations(db, farm.organization_id, species_id)
    return SuccessResponse(data=[MutationResponse.model_validate(r) for r in rows])


@router.post("/mutations", response_model=SuccessResponse[MutationResponse], status_code=status.HTTP_201_CREATED)
async def create_mutation(
    farm_id: str, body: MutationCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_CATALOG_MANAGE)),
):
    farm, _ = access
    row = await svc.create_mutation(db, farm.organization_id, body, current_user)
    return SuccessResponse(data=MutationResponse.model_validate(row))


# ── Birds ─────────────────────────────────────────────────────────────────────

@router.post("/birds", response_model=SuccessResponse[BirdResponse], status_code=status.HTTP_201_CREATED)
async def create_bird(
    farm_id: str, body: BirdCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_CREATE)),
):
    farm, _ = access
    bird = await svc.create_bird(db, farm, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.get("/birds", response_model=ListResponse[BirdResponse])
async def list_birds(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
    status_filter: str | None = Query(None, alias="status"),
    species_id: UUID | None = Query(None),
    aviary_id: UUID | None = Query(None),
    sex: str | None = Query(None),
    lifecycle_stage: str | None = Query(None),
    search: str | None = Query(None),
    tag: str | None = Query(None),
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    farm, _ = access
    birds, total, names = await svc.list_birds(
        db, farm.id, status=status_filter, species_id=species_id, aviary_id=aviary_id,
        sex=sex, lifecycle_stage=lifecycle_stage, search=search, tag=tag,
        include_archived=include_archived, limit=limit, offset=offset,
    )
    return ListResponse(
        data=[_bird_response(b, names) for b in birds],
        meta=PaginationMeta(
            total=total, page=(offset // limit) + 1, limit=limit,
            pages=max(1, ceil(total / limit)) if total else 1,
        ),
    )


@router.get("/birds/{bird_id}", response_model=SuccessResponse[BirdDetailResponse])
async def get_bird(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
):
    farm, _ = access
    bird, names, mutations, owner = await svc.get_bird_detail(db, farm.id, bird_id)
    base = _bird_response(bird, names)
    detail = BirdDetailResponse(
        **base.model_dump(),
        mutations=[
            BirdMutationResponse(
                id=m["row"].id, created_at=m["row"].created_at, updated_at=m["row"].updated_at,
                mutation_id=m["row"].mutation_id, zygosity=m["row"].zygosity,
                mutation_name=m["mutation_name"], inheritance=m["inheritance"],
            ) for m in mutations
        ],
        current_owner=OwnershipResponse.model_validate(owner) if owner else None,
    )
    return SuccessResponse(data=detail)


@router.patch("/birds/{bird_id}", response_model=SuccessResponse[BirdResponse])
async def update_bird(
    farm_id: str, bird_id: UUID, body: BirdUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_UPDATE)),
):
    farm, _ = access
    bird = await svc.update_bird(db, farm.id, bird_id, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


# ── Lifecycle transitions ─────────────────────────────────────────────────────

@router.post("/birds/{bird_id}/archive", response_model=SuccessResponse[BirdResponse])
async def archive_bird(
    farm_id: str, bird_id: UUID, body: ArchiveInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_ARCHIVE)),
):
    farm, _ = access
    bird = await svc.archive_bird(db, farm.id, bird_id, body.reason, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.post("/birds/{bird_id}/restore", response_model=SuccessResponse[BirdResponse])
async def restore_bird(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_ARCHIVE)),
):
    farm, _ = access
    bird = await svc.restore_bird(db, farm.id, bird_id, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.post("/birds/{bird_id}/transfer", response_model=SuccessResponse[BirdResponse])
async def transfer_bird(
    farm_id: str, bird_id: UUID, body: TransferInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_TRANSACT)),
):
    farm, _ = access
    bird = await svc.transfer_bird(db, farm.id, bird_id, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.post("/birds/{bird_id}/sell", response_model=SuccessResponse[BirdResponse])
async def sell_bird(
    farm_id: str, bird_id: UUID, body: SaleInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_TRANSACT)),
):
    farm, _ = access
    bird = await svc.sell_bird(db, farm.id, bird_id, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.post("/birds/{bird_id}/purchase", response_model=SuccessResponse[BirdResponse])
async def purchase_bird(
    farm_id: str, bird_id: UUID, body: PurchaseInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_TRANSACT)),
):
    farm, _ = access
    bird = await svc.record_purchase(db, farm.id, bird_id, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


@router.post("/birds/{bird_id}/death", response_model=SuccessResponse[BirdResponse])
async def death_bird(
    farm_id: str, bird_id: UUID, body: DeathInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_TRANSACT)),
):
    farm, _ = access
    bird = await svc.record_death(db, farm.id, bird_id, body, current_user)
    names = await svc._resolve_names(db, [bird])
    return SuccessResponse(data=_bird_response(bird, names))


# ── Ownership & timeline ──────────────────────────────────────────────────────

@router.get("/birds/{bird_id}/ownership", response_model=SuccessResponse[list[OwnershipResponse]])
async def bird_ownership(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
):
    farm, _ = access
    rows = await svc.list_ownership(db, farm.id, bird_id)
    return SuccessResponse(data=[OwnershipResponse.model_validate(r) for r in rows])


@router.get("/birds/{bird_id}/timeline", response_model=SuccessResponse[list[BirdEventResponse]])
async def bird_timeline(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
):
    farm, _ = access
    rows = await svc.list_events(db, farm.id, bird_id, limit=limit, offset=offset)
    return SuccessResponse(data=[BirdEventResponse.model_validate(r) for r in rows])


# ── Attachments ───────────────────────────────────────────────────────────────

@router.post("/birds/{bird_id}/media", response_model=SuccessResponse[MediaResponse], status_code=status.HTTP_201_CREATED)
async def add_media(
    farm_id: str, bird_id: UUID, body: MediaCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_UPDATE)),
):
    farm, _ = access
    row = await svc.add_media(db, farm.id, bird_id, body, current_user)
    return SuccessResponse(data=MediaResponse.model_validate(row))


@router.get("/birds/{bird_id}/media", response_model=SuccessResponse[list[MediaResponse]])
async def list_media(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
):
    farm, _ = access
    rows = await svc.list_media(db, farm.id, bird_id)
    return SuccessResponse(data=[MediaResponse.model_validate(r) for r in rows])


@router.post("/birds/{bird_id}/documents", response_model=SuccessResponse[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def add_document(
    farm_id: str, bird_id: UUID, body: DocumentCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager", "farm_worker"})),
    _perm=Depends(require_permission(Permission.AVI_BIRD_UPDATE)),
):
    farm, _ = access
    row = await svc.add_document(db, farm.id, bird_id, body, current_user)
    return SuccessResponse(data=DocumentResponse.model_validate(row))


@router.get("/birds/{bird_id}/documents", response_model=SuccessResponse[list[DocumentResponse]])
async def list_documents(
    farm_id: str, bird_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
):
    farm, _ = access
    rows = await svc.list_documents(db, farm.id, bird_id)
    return SuccessResponse(data=[DocumentResponse.model_validate(r) for r in rows])
