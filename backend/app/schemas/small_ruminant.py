"""
Greena — Small Ruminant Schemas (Modules 18 Goat + 19 Sheep)

Request/response contracts for the shared Small Ruminant subsystem. Enumerated
fields are validated against the value tuples on the models, so the API and the
database agree on one source of truth. ``species`` is supplied by the route path
(two workspaces over one schema), so create bodies never carry it.

Milestone 1 (Foundation) + Milestone 2 (Registry & Housing) surface:
  * catalog: breed / bloodline (data-driven, species-scoped)
  * management: herd/flock, group (dynamic membership)
  * physical housing: pen, pasture (species-neutral; occupancy derived)
  * animals: register / edit / archive / restore / move / transfer / sell / death
  * timeline, tags, media & document attachments
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import small_ruminant as srm
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


# ── Catalog: Breed (species-scoped) ────────────────────────────────────────────

class BreedCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field("other")
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict = Field(default_factory=dict)

    _cat = field_validator("category")(_one_of("category", srm.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", srm.BREED_PURPOSE_VALUES))


class BreedUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    category: str | None = None
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict | None = None

    _cat = field_validator("category")(_one_of("category", srm.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", srm.BREED_PURPOSE_VALUES))


class BreedResponse(TimestampedSchema):
    species: str
    organization_id: UUID | None
    name: str
    category: str
    origin: str | None
    production_purpose: str | None
    profile: dict
    is_system: bool


# ── Catalog: Bloodline (farm-scoped, species-scoped) ───────────────────────────

class BloodlineCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    code: str | None = Field(None, max_length=50)
    breed_id: UUID | None = None
    origin: str | None = Field(None, max_length=200)
    notes: str | None = None


class BloodlineUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    code: str | None = Field(None, max_length=50)
    breed_id: UUID | None = None
    origin: str | None = Field(None, max_length=200)
    notes: str | None = None


class BloodlineResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    breed_id: UUID | None
    name: str
    code: str | None
    origin: str | None
    notes: str | None


# ── Management: Herd / Flock (species-scoped) ──────────────────────────────────

class HerdCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_type: str = Field("mixed")
    status: str = Field("active")
    location: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ht = field_validator("herd_type")(_one_of("herd_type", srm.HERD_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.HERD_STATUS_VALUES))


class HerdUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_type: str | None = None
    status: str | None = None
    location: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ht = field_validator("herd_type")(_one_of("herd_type", srm.HERD_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.HERD_STATUS_VALUES))


class HerdResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    name: str
    code: str | None
    herd_type: str
    status: str
    location: str | None
    notes: str | None


# ── Management: Group (dynamic membership) ─────────────────────────────────────

class GroupCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_id: UUID | None = None
    group_type: str = Field("general")
    status: str = Field("active")
    notes: str | None = None

    _gt = field_validator("group_type")(_one_of("group_type", srm.GROUP_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.GROUP_STATUS_VALUES))


class GroupUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_id: UUID | None = None
    group_type: str | None = None
    status: str | None = None
    notes: str | None = None

    _gt = field_validator("group_type")(_one_of("group_type", srm.GROUP_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.GROUP_STATUS_VALUES))


class GroupResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    herd_id: UUID | None
    name: str
    code: str | None
    group_type: str
    status: str
    notes: str | None


# ── Physical housing: Pen (species-neutral) ────────────────────────────────────

class PenCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    pen_type: str = Field("pen")
    capacity: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=200)
    dimensions: dict = Field(default_factory=dict)
    status: str = Field("available")
    notes: str | None = None

    _pt = field_validator("pen_type")(_one_of("pen_type", srm.PEN_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.PEN_STATUS_VALUES))


class PenUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    pen_type: str | None = None
    capacity: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=200)
    dimensions: dict | None = None
    status: str | None = None
    notes: str | None = None

    _pt = field_validator("pen_type")(_one_of("pen_type", srm.PEN_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.PEN_STATUS_VALUES))


class PenResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    pen_type: str
    capacity: int | None
    location: str | None
    dimensions: dict
    status: str
    notes: str | None


class PenDetailResponse(PenResponse):
    occupancy: dict


# ── Physical housing: Pasture (species-neutral) ────────────────────────────────

class PastureCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    area_hectares: Decimal | None = Field(None, ge=0)
    carrying_capacity: int | None = Field(None, ge=0)
    grass_species: str | None = Field(None, max_length=255)
    browse_species: str | None = Field(None, max_length=255)
    status: str = Field("available")
    profile: dict = Field(default_factory=dict)
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", srm.PASTURE_STATUS_VALUES))


class PastureUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    area_hectares: Decimal | None = Field(None, ge=0)
    carrying_capacity: int | None = Field(None, ge=0)
    grass_species: str | None = Field(None, max_length=255)
    browse_species: str | None = Field(None, max_length=255)
    status: str | None = None
    profile: dict | None = None
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", srm.PASTURE_STATUS_VALUES))


class PastureResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    area_hectares: Decimal | None
    carrying_capacity: int | None
    grass_species: str | None
    browse_species: str | None
    status: str
    profile: dict
    notes: str | None


class PastureDetailResponse(PastureResponse):
    occupancy: dict


# ── Animal — register / edit ───────────────────────────────────────────────────

class AnimalCreate(AGRIOSSchema):
    internal_ref: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=150)
    ear_tag: str | None = Field(None, max_length=100)
    tattoo: str | None = Field(None, max_length=100)
    qr_code: str | None = Field(None, max_length=200)
    rfid: str | None = Field(None, max_length=100)
    visual_id: str | None = Field(None, max_length=150)
    registration_number: str | None = Field(None, max_length=100)
    breed_id: UUID | None = None
    bloodline_id: UUID | None = None
    herd_id: UUID | None = None
    group_id: UUID | None = None
    pen_id: UUID | None = None
    pasture_id: UUID | None = None
    variety: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str = Field("unknown")
    purpose: str = Field("unknown")
    purposes: list[str] = Field(default_factory=list)
    horn_status: str = Field("unknown")
    registration_status: str = Field("unknown")
    date_of_birth: date | None = None
    dob_estimated: bool = False
    birth_type: str = Field("unknown")
    birth_weight_kg: Decimal | None = Field(None, ge=0)
    current_weight_kg: Decimal | None = Field(None, ge=0)
    lifecycle_stage: str = Field("unknown")
    reproductive_status: str = Field("unknown")
    fertility_status: str = Field("unknown")
    acquisition_type: str = Field("unknown")
    acquired_on: date | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", srm.SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", srm.PURPOSE_VALUES))
    _horn = field_validator("horn_status")(_one_of("horn_status", srm.HORN_STATUS_VALUES))
    _reg = field_validator("registration_status")(_one_of("registration_status", srm.REGISTRATION_STATUS_VALUES))
    _bt = field_validator("birth_type")(_one_of("birth_type", srm.BIRTH_TYPE_VALUES))
    _ls = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", srm.LIFECYCLE_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", srm.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", srm.FERTILITY_STATUS_VALUES))
    _at = field_validator("acquisition_type")(_one_of("acquisition_type", srm.ACQUISITION_TYPE_VALUES))


class AnimalUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=150)
    ear_tag: str | None = Field(None, max_length=100)
    tattoo: str | None = Field(None, max_length=100)
    qr_code: str | None = Field(None, max_length=200)
    rfid: str | None = Field(None, max_length=100)
    visual_id: str | None = Field(None, max_length=150)
    registration_number: str | None = Field(None, max_length=100)
    breed_id: UUID | None = None
    bloodline_id: UUID | None = None
    herd_id: UUID | None = None
    group_id: UUID | None = None
    variety: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str | None = None
    purpose: str | None = None
    purposes: list[str] | None = None
    horn_status: str | None = None
    registration_status: str | None = None
    date_of_birth: date | None = None
    dob_estimated: bool | None = None
    birth_type: str | None = None
    birth_weight_kg: Decimal | None = Field(None, ge=0)
    current_weight_kg: Decimal | None = Field(None, ge=0)
    lifecycle_stage: str | None = None
    reproductive_status: str | None = None
    fertility_status: str | None = None
    acquisition_type: str | None = None
    acquired_on: date | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    tags: list[str] | None = None
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", srm.SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", srm.PURPOSE_VALUES))
    _horn = field_validator("horn_status")(_one_of("horn_status", srm.HORN_STATUS_VALUES))
    _reg = field_validator("registration_status")(_one_of("registration_status", srm.REGISTRATION_STATUS_VALUES))
    _bt = field_validator("birth_type")(_one_of("birth_type", srm.BIRTH_TYPE_VALUES))
    _ls = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", srm.LIFECYCLE_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", srm.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", srm.FERTILITY_STATUS_VALUES))
    _at = field_validator("acquisition_type")(_one_of("acquisition_type", srm.ACQUISITION_TYPE_VALUES))


class AnimalResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    breed_id: UUID | None
    bloodline_id: UUID | None
    herd_id: UUID | None
    group_id: UUID | None
    pen_id: UUID | None
    pasture_id: UUID | None
    internal_ref: str
    name: str | None
    ear_tag: str | None
    tattoo: str | None
    qr_code: str | None
    rfid: str | None
    visual_id: str | None
    registration_number: str | None
    variety: str | None
    color: str | None
    sex: str
    purpose: str
    purposes: list
    horn_status: str
    registration_status: str
    date_of_birth: date | None
    dob_estimated: bool
    birth_type: str
    birth_weight_kg: Decimal | None
    current_weight_kg: Decimal | None
    lifecycle_stage: str
    status: str
    reproductive_status: str
    fertility_status: str
    acquisition_type: str
    acquired_on: date | None
    sire_id: UUID | None
    dam_id: UUID | None
    tags: list
    notes: str | None
    # Resolved display names (recorded references only)
    breed_name: str | None = None
    bloodline_name: str | None = None
    herd_name: str | None = None
    group_name: str | None = None
    pen_name: str | None = None
    pasture_name: str | None = None


class AnimalDetailResponse(AnimalResponse):
    sire_ref: str | None = None
    dam_ref: str | None = None


# ── Lifecycle inputs ───────────────────────────────────────────────────────────

class MoveInput(AGRIOSSchema):
    """Move an animal between management group and/or physical pen/pasture.

    Any field left unset is unchanged; pass ``null`` explicitly to clear a link.
    ``clear`` lists location fields to null out (group/pen/pasture)."""

    group_id: UUID | None = None
    pen_id: UUID | None = None
    pasture_id: UUID | None = None
    clear: list[str] = Field(default_factory=list)
    reason: str | None = None
    occurred_on: date | None = None
    notes: str | None = None


class ArchiveInput(AGRIOSSchema):
    reason: str | None = None


class TransferInput(AGRIOSSchema):
    to_owner_name: str = Field(..., min_length=1, max_length=200)
    destination: str | None = Field(None, max_length=200)
    occurred_on: date | None = None
    notes: str | None = None


class SaleInput(AGRIOSSchema):
    buyer_name: str = Field(..., min_length=1, max_length=200)
    price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    occurred_on: date | None = None
    notes: str | None = None


class DeathInput(AGRIOSSchema):
    cause: str | None = Field(None, max_length=255)
    occurred_on: date | None = None
    notes: str | None = None


class CullInput(AGRIOSSchema):
    reason: str | None = Field(None, max_length=255)
    occurred_on: date | None = None
    notes: str | None = None


# ── Timeline & attachments ─────────────────────────────────────────────────────

class AnimalEventResponse(TimestampedSchema):
    animal_id: UUID
    event_type: str
    occurred_at: datetime | None = None
    summary: str | None
    details: dict
    operator_id: UUID | None


class MediaCreate(AGRIOSSchema):
    media_type: str = Field("photo")
    title: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=1000)
    storage_path: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=255)
    content_type: str | None = Field(None, max_length=120)
    size_bytes: int | None = Field(None, ge=0)
    captured_on: date | None = None

    _mt = field_validator("media_type")(_one_of("media_type", srm.MEDIA_TYPE_VALUES))


class MediaResponse(TimestampedSchema):
    animal_id: UUID
    media_type: str
    title: str | None
    url: str | None
    storage_path: str | None
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    captured_on: date | None


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

    _dt = field_validator("document_type")(_one_of("document_type", srm.DOCUMENT_TYPE_VALUES))


class DocumentResponse(TimestampedSchema):
    animal_id: UUID
    document_type: str
    title: str | None
    url: str | None
    storage_path: str | None
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    issued_on: date | None
    expires_on: date | None


# ── Breeding cycle (Milestone 3) ───────────────────────────────────────────────

class BreedingCreate(AGRIOSSchema):
    dam_id: UUID
    sire_id: UUID
    method: str = Field("natural")
    service_date: date | None = None
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", srm.BREEDING_METHOD_VALUES))


class ServiceInput(AGRIOSSchema):
    service_date: date


class PregnancyCheckInput(AGRIOSSchema):
    checked_on: date
    result: str = Field("unknown")

    _r = field_validator("result")(_one_of("result", srm.PREGNANCY_RESULT_VALUES))


class BirthRecordInput(AGRIOSSchema):
    birth_date: date
    birth_type: str = Field("unknown")
    total_born: int = Field(0, ge=0)
    live_born: int = Field(0, ge=0)
    stillborn: int = Field(0, ge=0)
    avg_birth_weight_kg: Decimal | None = Field(None, ge=0)
    assistance_required: bool = False
    complications: str | None = None
    colostrum_status: str = Field("unknown")
    location: str | None = Field(None, max_length=200)
    notes: str | None = None
    # Offspring auto-creation (Goat Doc 6 §6): create minimal animal rows with
    # sire/dam/birth pedigree links.
    create_offspring: bool = False
    offspring_herd_id: UUID | None = None
    offspring_group_id: UUID | None = None

    _bt = field_validator("birth_type")(_one_of("birth_type", srm.BIRTH_TYPE_VALUES))
    _cs = field_validator("colostrum_status")(_one_of("colostrum_status", srm.COLOSTRUM_STATUS_VALUES))


class WeaningInput(AGRIOSSchema):
    weaned: int = Field(..., ge=0)
    weaning_date: date


class BreedingResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    dam_id: UUID | None
    sire_id: UUID | None
    repeat_of_id: UUID | None
    method: str
    service_date: date | None
    planned_birth_date: date | None
    pregnancy_checked_on: date | None
    pregnancy_result: str
    prep_started_on: date | None
    actual_birth_date: date | None
    status: str
    outcome: str | None
    notes: str | None


class BirthResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    breeding_id: UUID | None
    dam_id: UUID | None
    sire_id: UUID | None
    birth_code: str
    birth_date: date
    birth_type: str
    total_born: int
    live_born: int
    stillborn: int
    weaned: int
    mortality: int
    avg_birth_weight_kg: Decimal | None
    weaning_date: date | None
    assistance_required: bool
    complications: str | None
    colostrum_status: str
    status: str
    location: str | None
    notes: str | None
