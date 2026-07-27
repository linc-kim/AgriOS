"""
Greena — Aviculture Schemas (Module 15)

Request/response contracts for the Aviculture module. Enumerated fields are
validated against the value tuples defined on the models, so the API and the
database agree on one source of truth (Doc 14 §5).

Part 1 (Foundation) + Part 2 (Collection Management) surface:
  * catalog: species / breed / mutation (data-driven, Doc 02 §6-8)
  * birds: create / edit / archive / transfer / sale / purchase / death
  * ownership history, timeline, tags, media & document attachments
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Validators ────────────────────────────────────────────────────────────────

def _one_of(field_name: str, allowed: tuple[str, ...]):
    """Build a reusable membership validator for an enumerated string field."""

    def _check(value):
        if value is None:
            return value
        if value not in allowed:
            raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")
        return value

    return _check


# ── Catalog ───────────────────────────────────────────────────────────────────

class SpeciesCreate(AGRIOSSchema):
    common_name: str = Field(..., min_length=1, max_length=150)
    scientific_name: str | None = Field(None, max_length=200)
    species_group: str = Field("other")
    conservation_status: str | None = Field(None, max_length=50)
    profile: dict = Field(default_factory=dict)

    _grp = field_validator("species_group")(_one_of("species_group", avi.SPECIES_GROUP_VALUES))


class SpeciesResponse(TimestampedSchema):
    organization_id: UUID | None
    common_name: str
    scientific_name: str | None
    species_group: str
    conservation_status: str | None
    profile: dict
    is_system: bool


class BreedCreate(AGRIOSSchema):
    species_id: UUID
    name: str = Field(..., min_length=1, max_length=150)
    profile: dict = Field(default_factory=dict)


class BreedResponse(TimestampedSchema):
    organization_id: UUID | None
    species_id: UUID
    name: str
    profile: dict
    is_system: bool


class MutationCreate(AGRIOSSchema):
    species_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=150)
    inheritance: str = Field("unknown")
    profile: dict = Field(default_factory=dict)

    _inh = field_validator("inheritance")(_one_of("inheritance", avi.MUTATION_INHERITANCE_VALUES))


class MutationResponse(TimestampedSchema):
    organization_id: UUID | None
    species_id: UUID | None
    name: str
    inheritance: str
    profile: dict
    is_system: bool


# ── Bird ──────────────────────────────────────────────────────────────────────

class BirdMutationInput(AGRIOSSchema):
    mutation_id: UUID
    zygosity: str = Field("unknown")

    _zyg = field_validator("zygosity")(_one_of("zygosity", avi.MUTATION_ZYGOSITY_VALUES))


class BirdCreate(AGRIOSSchema):
    species_id: UUID
    breed_id: UUID | None = None
    aviary_id: UUID | None = None
    internal_ref: str | None = Field(None, max_length=50,
                                     description="Optional; auto-generated per farm when omitted.")
    name: str | None = Field(None, max_length=150)
    ring_number: str | None = Field(None, max_length=100)
    band_number: str | None = Field(None, max_length=100)
    microchip: str | None = Field(None, max_length=100)
    colour_description: str | None = Field(None, max_length=200)
    sex: str = Field("unknown")
    sex_method: str = Field("unknown")
    dna_status: str = Field("unknown")
    hatch_date: date | None = None
    hatch_date_estimated: bool = False
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    lifecycle_stage: str = Field("unknown")
    acquisition_type: str = Field("unknown")
    acquired_on: date | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    mutations: list[BirdMutationInput] = Field(default_factory=list)
    # Initial owner (defaults to the farm when omitted).
    owner_name: str | None = Field(None, max_length=200)
    owner_type: str = Field("internal")

    _sex = field_validator("sex")(_one_of("sex", avi.BIRD_SEX_VALUES))
    _sexm = field_validator("sex_method")(_one_of("sex_method", avi.BIRD_SEX_METHOD_VALUES))
    _dna = field_validator("dna_status")(_one_of("dna_status", avi.BIRD_DNA_STATUS_VALUES))
    _stage = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", avi.BIRD_LIFECYCLE_STAGE_VALUES))
    _acq = field_validator("acquisition_type")(_one_of("acquisition_type", avi.BIRD_ACQUISITION_TYPE_VALUES))
    _ot = field_validator("owner_type")(_one_of("owner_type", avi.OWNER_TYPE_VALUES))


class BirdUpdate(AGRIOSSchema):
    """All fields optional — only provided fields are changed (Doc 03 §13 audit)."""

    breed_id: UUID | None = None
    aviary_id: UUID | None = None
    name: str | None = Field(None, max_length=150)
    ring_number: str | None = Field(None, max_length=100)
    band_number: str | None = Field(None, max_length=100)
    microchip: str | None = Field(None, max_length=100)
    colour_description: str | None = Field(None, max_length=200)
    sex: str | None = None
    sex_method: str | None = None
    dna_status: str | None = None
    hatch_date: date | None = None
    hatch_date_estimated: bool | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    lifecycle_stage: str | None = None
    tags: list[str] | None = None
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", avi.BIRD_SEX_VALUES))
    _sexm = field_validator("sex_method")(_one_of("sex_method", avi.BIRD_SEX_METHOD_VALUES))
    _dna = field_validator("dna_status")(_one_of("dna_status", avi.BIRD_DNA_STATUS_VALUES))
    _stage = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", avi.BIRD_LIFECYCLE_STAGE_VALUES))


class BirdMutationResponse(TimestampedSchema):
    mutation_id: UUID
    zygosity: str
    mutation_name: str | None = None
    inheritance: str | None = None


class BirdResponse(TimestampedSchema):
    farm_id: UUID
    species_id: UUID
    breed_id: UUID | None
    aviary_id: UUID | None
    internal_ref: str
    name: str | None
    ring_number: str | None
    band_number: str | None
    microchip: str | None
    colour_description: str | None
    sex: str
    sex_method: str
    dna_status: str
    hatch_date: date | None
    hatch_date_estimated: bool
    sire_id: UUID | None
    dam_id: UUID | None
    lifecycle_stage: str
    status: str
    acquisition_type: str
    acquired_on: date | None
    tags: list[str]
    notes: str | None
    # Denormalised display helpers (recorded facts, resolved by the service).
    species_name: str | None = None
    breed_name: str | None = None
    aviary_name: str | None = None


class BirdDetailResponse(BirdResponse):
    mutations: list[BirdMutationResponse] = Field(default_factory=list)
    current_owner: "OwnershipResponse | None" = None


# ── Ownership transitions ─────────────────────────────────────────────────────

class OwnershipResponse(TimestampedSchema):
    bird_id: UUID
    owner_type: str
    owner_name: str
    owner_contact: dict
    acquisition: str
    from_date: date | None
    to_date: date | None
    is_current: bool
    notes: str | None


class TransferInput(AGRIOSSchema):
    """Move a bird to a new keeper/location without a sale (Doc 11 §8)."""

    to_owner_name: str = Field(..., min_length=1, max_length=200)
    to_owner_type: str = Field("internal")
    to_owner_contact: dict = Field(default_factory=dict)
    occurred_on: date | None = None
    destination: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ot = field_validator("to_owner_type")(_one_of("to_owner_type", avi.OWNER_TYPE_VALUES))


class SaleInput(AGRIOSSchema):
    """Record a sale as a collection fact. Price is recorded, not posted to
    finance here — Part 7 reuses the Greena Finance engine (Doc 13 Part 7)."""

    buyer_name: str = Field(..., min_length=1, max_length=200)
    buyer_contact: dict = Field(default_factory=dict)
    occurred_on: date | None = None
    price: Decimal | None = Field(None, ge=0)
    currency: str = Field("KES", max_length=8)
    notes: str | None = None


class PurchaseInput(AGRIOSSchema):
    """Record how a bird entered the collection by purchase."""

    seller_name: str = Field(..., min_length=1, max_length=200)
    seller_contact: dict = Field(default_factory=dict)
    occurred_on: date | None = None
    price: Decimal | None = Field(None, ge=0)
    currency: str = Field("KES", max_length=8)
    notes: str | None = None


class DeathInput(AGRIOSSchema):
    """Record a bird's death (Doc 02 §4). Necropsy/lab detail is a health record."""

    occurred_on: date | None = None
    cause: str | None = Field(None, max_length=200)
    notes: str | None = None


class ArchiveInput(AGRIOSSchema):
    reason: str | None = Field(None, max_length=500)


# ── Timeline ──────────────────────────────────────────────────────────────────

class BirdEventResponse(TimestampedSchema):
    bird_id: UUID
    event_type: str
    occurred_on: date
    title: str
    description: str | None
    data: dict
    actor_id: UUID | None


# ── Attachments ───────────────────────────────────────────────────────────────

class MediaCreate(AGRIOSSchema):
    media_type: str = Field("photo")
    url: str | None = Field(None, max_length=1000)
    storage_path: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=255)
    content_type: str | None = Field(None, max_length=120)
    size_bytes: int | None = Field(None, ge=0)
    caption: str | None = None
    is_primary: bool = False
    taken_on: date | None = None

    _mt = field_validator("media_type")(_one_of("media_type", avi.MEDIA_TYPE_VALUES))


class MediaResponse(TimestampedSchema):
    bird_id: UUID
    media_type: str
    url: str | None
    storage_path: str | None
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    caption: str | None
    is_primary: bool
    taken_on: date | None


class DocumentCreate(AGRIOSSchema):
    document_type: str = Field("other")
    title: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=1000)
    storage_path: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=255)
    content_type: str | None = Field(None, max_length=120)
    size_bytes: int | None = Field(None, ge=0)
    issued_on: date | None = None
    expires_on: date | None = None
    is_restricted: bool = False

    _dt = field_validator("document_type")(_one_of("document_type", avi.DOCUMENT_TYPE_VALUES))


class DocumentResponse(TimestampedSchema):
    bird_id: UUID
    document_type: str
    title: str | None
    url: str | None
    storage_path: str | None
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    issued_on: date | None
    expires_on: date | None
    is_restricted: bool


BirdDetailResponse.model_rebuild()
