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


# ── Growth & feed (Milestone 4) — weights in kilograms ─────────────────────────

class WeightCreate(AGRIOSSchema):
    recorded_on: date
    weight_kg: Decimal = Field(..., gt=0)
    method: str = Field("scale")
    body_condition_score: Decimal | None = Field(None, ge=1, le=5)
    heart_girth_cm: Decimal | None = Field(None, ge=0)
    height_cm: Decimal | None = Field(None, ge=0)
    body_length_cm: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", srm.WEIGHT_METHOD_VALUES))


class WeightResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    recorded_on: date
    weight_kg: Decimal
    method: str
    body_condition_score: Decimal | None
    heart_girth_cm: Decimal | None
    height_cm: Decimal | None
    body_length_cm: Decimal | None
    age_days: int | None
    notes: str | None


class FeedRecordCreate(AGRIOSSchema):
    animal_id: UUID | None = None
    group_id: UUID | None = None
    inventory_item_id: UUID | None = None
    feed_type: str | None = Field(None, max_length=150)
    quantity_kg: Decimal = Field(..., gt=0)
    fed_on: date
    is_mineral: bool = False
    cost: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = None


class FeedRecordResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID | None
    group_id: UUID | None
    inventory_item_id: UUID | None
    inventory_movement_id: UUID | None
    feed_type: str | None
    quantity_kg: Decimal
    fed_on: date
    is_mineral: bool
    cost: Decimal | None
    currency: str | None
    supplier: str | None
    notes: str | None


# ── Health, vaccination, deworming, hoof care & mortality (Milestone 5) ────────

class HealthRecordCreate(AGRIOSSchema):
    event_type: str = Field("observation")
    title: str | None = Field(None, max_length=255)
    status: str = Field("recorded")
    severity: str = Field("info")
    symptoms: str | None = None
    diagnosis: str | None = Field(None, max_length=255)
    treatment: str | None = None
    medication: str | None = Field(None, max_length=255)
    withdrawal_until: date | None = None
    veterinarian: str | None = Field(None, max_length=200)
    recovery_status: str | None = Field(None, max_length=30)
    occurred_on: date
    next_due_on: date | None = None
    notes: str | None = None

    _et = field_validator("event_type")(_one_of("event_type", srm.HEALTH_EVENT_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", srm.HEALTH_STATUS_VALUES))
    _sv = field_validator("severity")(_one_of("severity", srm.HEALTH_SEVERITY_VALUES))


class HealthRecordResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    event_type: str
    title: str | None
    status: str
    severity: str
    symptoms: str | None
    diagnosis: str | None
    treatment: str | None
    medication: str | None
    withdrawal_until: date | None
    veterinarian: str | None
    recovery_status: str | None
    occurred_on: date
    next_due_on: date | None
    reminder_id: UUID | None
    notes: str | None


class VaccinationCreate(AGRIOSSchema):
    vaccine: str = Field(..., min_length=1, max_length=150)
    batch_number: str | None = Field(None, max_length=100)
    administered_on: date
    next_due_on: date | None = None
    administrator: str | None = Field(None, max_length=200)
    notes: str | None = None


class VaccinationResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    vaccine: str
    batch_number: str | None
    administered_on: date
    next_due_on: date | None
    administrator: str | None
    reminder_id: UUID | None
    notes: str | None


class DewormingCreate(AGRIOSSchema):
    product: str = Field(..., min_length=1, max_length=150)
    method: str = Field("oral_drench")
    dose: str | None = Field(None, max_length=100)
    famacha_score: int | None = Field(None, ge=1, le=5)
    administered_on: date
    next_due_on: date | None = None
    withdrawal_until: date | None = None
    administrator: str | None = Field(None, max_length=200)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", srm.DEWORMING_METHOD_VALUES))


class DewormingResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    product: str
    method: str
    dose: str | None
    famacha_score: int | None
    administered_on: date
    next_due_on: date | None
    withdrawal_until: date | None
    administrator: str | None
    reminder_id: UUID | None
    notes: str | None


class HoofCareCreate(AGRIOSSchema):
    action: str = Field("inspection")
    condition: str = Field("unknown")
    lameness_score: int | None = Field(None, ge=0, le=5)
    treatment: str | None = None
    performed_on: date
    next_due_on: date | None = None
    notes: str | None = None

    _a = field_validator("action")(_one_of("action", srm.HOOF_ACTION_VALUES))
    _c = field_validator("condition")(_one_of("condition", srm.HOOF_CONDITION_VALUES))


class HoofCareResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    action: str
    condition: str
    lameness_score: int | None
    treatment: str | None
    performed_on: date
    next_due_on: date | None
    reminder_id: UUID | None
    notes: str | None


class MortalityCreate(AGRIOSSchema):
    occurred_on: date
    cause: str = Field("unknown")
    suspected_cause: str | None = Field(None, max_length=255)
    postmortem_notes: str | None = None

    _c = field_validator("cause")(_one_of("cause", srm.MORTALITY_CAUSE_VALUES))


class MortalityResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    occurred_on: date
    age_days: int | None
    cause: str
    suspected_cause: str | None
    postmortem_notes: str | None


# ── Dairy — lactation & milk (Milestone 6) ─────────────────────────────────────

class LactationStartInput(AGRIOSSchema):
    freshening_date: date
    lactation_number: int | None = Field(None, ge=1)
    birth_id: UUID | None = None
    milking_frequency: int = Field(2, ge=1, le=4)
    notes: str | None = None


class LactationDryOffInput(AGRIOSSchema):
    dry_off_date: date


class LactationResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    birth_id: UUID | None
    lactation_number: int
    freshening_date: date
    expected_dry_off_date: date | None
    dry_off_date: date | None
    milking_frequency: int
    status: str
    notes: str | None


class MilkRecordCreate(AGRIOSSchema):
    recorded_on: date
    session: str = Field("total")
    quantity_liters: Decimal = Field(..., ge=0)
    lactation_id: UUID | None = None
    fat_pct: Decimal | None = Field(None, ge=0, le=100)
    protein_pct: Decimal | None = Field(None, ge=0, le=100)
    somatic_cell_count: int | None = Field(None, ge=0)
    notes: str | None = None

    _s = field_validator("session")(_one_of("session", srm.MILK_SESSION_VALUES))


class MilkRecordResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID
    lactation_id: UUID | None
    recorded_on: date
    session: str
    quantity_liters: Decimal
    fat_pct: Decimal | None
    protein_pct: Decimal | None
    somatic_cell_count: int | None
    notes: str | None


# ── Wool — shearing & fleece (Milestone 7) ─────────────────────────────────────

class FleeceCreate(AGRIOSSchema):
    animal_id: UUID
    greasy_weight_kg: Decimal = Field(..., gt=0)
    clean_yield_pct: Decimal | None = Field(None, ge=0, le=100)
    staple_length_cm: Decimal | None = Field(None, ge=0)
    micron: Decimal | None = Field(None, gt=0)
    grade: str = Field("unknown")
    condition: str = Field("unknown")
    notes: str | None = None

    _g = field_validator("grade")(_one_of("grade", srm.WOOL_GRADE_VALUES))
    _c = field_validator("condition")(_one_of("condition", srm.FLEECE_CONDITION_VALUES))


class ShearingCreate(AGRIOSSchema):
    shearing_date: date
    method: str = Field("machine")
    shearer: str | None = Field(None, max_length=200)
    group_id: UUID | None = None
    fleeces: list[FleeceCreate] = Field(default_factory=list)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", srm.SHEARING_METHOD_VALUES))


class ShearingResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    group_id: UUID | None
    shearing_date: date
    method: str
    shearer: str | None
    notes: str | None


class FleeceResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    shearing_id: UUID | None
    animal_id: UUID
    shorn_on: date
    greasy_weight_kg: Decimal
    clean_yield_pct: Decimal | None
    staple_length_cm: Decimal | None
    micron: Decimal | None
    grade: str
    condition: str
    notes: str | None


# ── Sales & Finance (Milestone 8) ──────────────────────────────────────────────

class SaleCreate(AGRIOSSchema):
    sale_type: str = Field("live")
    animal_id: UUID | None = None
    buyer_name: str | None = Field(None, max_length=200)
    buyer_contact: str | None = Field(None, max_length=200)
    sale_date: date
    quantity: Decimal = Field(Decimal("1"), gt=0)
    unit: str | None = Field(None, max_length=15)
    weight_kg: Decimal | None = Field(None, ge=0)
    unit_price: Decimal | None = Field(None, ge=0)
    total_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    invoice_reference: str | None = Field(None, max_length=150)
    notes: str | None = None

    _st = field_validator("sale_type")(_one_of("sale_type", srm.SALE_TYPE_VALUES))


class SaleResponse(TimestampedSchema):
    species: str
    farm_id: UUID
    animal_id: UUID | None
    sale_type: str
    buyer_name: str | None
    buyer_contact: str | None
    sale_date: date
    quantity: Decimal
    unit: str | None
    weight_kg: Decimal | None
    unit_price: Decimal | None
    total_price: Decimal
    currency: str | None
    invoice_reference: str | None
    notes: str | None


class OperationalExpenseCreate(AGRIOSSchema):
    category_slug: str = Field(..., min_length=1, max_length=50)
    amount: Decimal = Field(..., gt=0)
    description: str | None = Field(None, max_length=500)
    expense_date: date


# ── ARIA (Milestone 10) ────────────────────────────────────────────────────────

class AriaAsk(AGRIOSSchema):
    question: str = Field(..., min_length=1, max_length=1000)


class AriaAnswer(AGRIOSSchema):
    provider: str
    engine: str
    fact_type: str
    answer: str
    sources: list[str]
    confidence: str
    ai_enabled: bool
