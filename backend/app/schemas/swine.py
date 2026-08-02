"""
Greena — Swine Schemas (Module 20, Pig Framework)

Request/response contracts for the Swine Framework. Enumerated fields are validated
against the value tuples on the models, so the API and the database agree on one
source of truth. Swine is a single species, so there is no ``species`` path segment
(unlike Small Ruminant), and pigs are a housed species, so there is no pasture.

Milestone 1 (Foundation) + Milestone 2 (Registry & Housing) surface:
  * catalog: breed / bloodline (data-driven)
  * management: herd, group (dynamic membership)
  * physical housing: pen (crate/stall/pen/shed; biosecurity; occupancy derived)
  * pigs: register / edit / archive / restore / move / transfer / sell / death / cull
  * timeline, tags, media & document attachments
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import swine as swm
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


# ── Catalog: Breed ─────────────────────────────────────────────────────────────

class BreedCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field("other")
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict = Field(default_factory=dict)

    _cat = field_validator("category")(_one_of("category", swm.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", swm.BREED_PURPOSE_VALUES))


class BreedUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    category: str | None = None
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict | None = None

    _cat = field_validator("category")(_one_of("category", swm.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", swm.BREED_PURPOSE_VALUES))


class BreedResponse(TimestampedSchema):
    organization_id: UUID | None
    name: str
    category: str
    origin: str | None
    production_purpose: str | None
    profile: dict
    is_system: bool


# ── Catalog: Bloodline (farm-scoped) ───────────────────────────────────────────

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
    farm_id: UUID
    breed_id: UUID | None
    name: str
    code: str | None
    origin: str | None
    notes: str | None


# ── Management: Herd ────────────────────────────────────────────────────────────

class HerdCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_type: str = Field("mixed")
    status: str = Field("active")
    location: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ht = field_validator("herd_type")(_one_of("herd_type", swm.HERD_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.HERD_STATUS_VALUES))


class HerdUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_type: str | None = None
    status: str | None = None
    location: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ht = field_validator("herd_type")(_one_of("herd_type", swm.HERD_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.HERD_STATUS_VALUES))


class HerdResponse(TimestampedSchema):
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

    _gt = field_validator("group_type")(_one_of("group_type", swm.GROUP_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.GROUP_STATUS_VALUES))


class GroupUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    herd_id: UUID | None = None
    group_type: str | None = None
    status: str | None = None
    notes: str | None = None

    _gt = field_validator("group_type")(_one_of("group_type", swm.GROUP_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.GROUP_STATUS_VALUES))


class GroupResponse(TimestampedSchema):
    farm_id: UUID
    herd_id: UUID | None
    name: str
    code: str | None
    group_type: str
    status: str
    notes: str | None


# ── Physical housing: Pen ───────────────────────────────────────────────────────

class PenCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    building: str | None = Field(None, max_length=200)
    pen_type: str = Field("pen")
    capacity: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=200)
    dimensions: dict = Field(default_factory=dict)
    status: str = Field("available")
    biosecurity_status: str = Field("unknown")
    notes: str | None = None

    _pt = field_validator("pen_type")(_one_of("pen_type", swm.PEN_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.PEN_STATUS_VALUES))
    _bio = field_validator("biosecurity_status")(_one_of("biosecurity_status", swm.BIOSECURITY_STATUS_VALUES))


class PenUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    building: str | None = Field(None, max_length=200)
    pen_type: str | None = None
    capacity: int | None = Field(None, ge=0)
    location: str | None = Field(None, max_length=200)
    dimensions: dict | None = None
    status: str | None = None
    biosecurity_status: str | None = None
    notes: str | None = None

    _pt = field_validator("pen_type")(_one_of("pen_type", swm.PEN_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.PEN_STATUS_VALUES))
    _bio = field_validator("biosecurity_status")(_one_of("biosecurity_status", swm.BIOSECURITY_STATUS_VALUES))


class PenResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    building: str | None
    pen_type: str
    capacity: int | None
    location: str | None
    dimensions: dict
    status: str
    biosecurity_status: str
    notes: str | None


class PenDetailResponse(PenResponse):
    occupancy: dict


# ── Pig — register / edit ───────────────────────────────────────────────────────

class PigCreate(AGRIOSSchema):
    internal_ref: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=150)
    ear_tag: str | None = Field(None, max_length=100)
    ear_notch: str | None = Field(None, max_length=100)
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
    line: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str = Field("unknown")
    purpose: str = Field("unknown")
    purposes: list[str] = Field(default_factory=list)
    registration_status: str = Field("unknown")
    date_of_birth: date | None = None
    dob_estimated: bool = False
    birth_weight_kg: Decimal | None = Field(None, ge=0)
    current_weight_kg: Decimal | None = Field(None, ge=0)
    production_stage: str = Field("unknown")
    reproductive_status: str = Field("unknown")
    fertility_status: str = Field("unknown")
    market_status: str = Field("unknown")
    parity: int | None = Field(None, ge=0)
    acquisition_type: str = Field("unknown")
    acquired_on: date | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", swm.SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", swm.PURPOSE_VALUES))
    _reg = field_validator("registration_status")(_one_of("registration_status", swm.REGISTRATION_STATUS_VALUES))
    _ps = field_validator("production_stage")(_one_of("production_stage", swm.PRODUCTION_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", swm.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", swm.FERTILITY_STATUS_VALUES))
    _ms = field_validator("market_status")(_one_of("market_status", swm.MARKET_STATUS_VALUES))
    _at = field_validator("acquisition_type")(_one_of("acquisition_type", swm.ACQUISITION_TYPE_VALUES))


class PigUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=150)
    ear_tag: str | None = Field(None, max_length=100)
    ear_notch: str | None = Field(None, max_length=100)
    tattoo: str | None = Field(None, max_length=100)
    qr_code: str | None = Field(None, max_length=200)
    rfid: str | None = Field(None, max_length=100)
    visual_id: str | None = Field(None, max_length=150)
    registration_number: str | None = Field(None, max_length=100)
    breed_id: UUID | None = None
    bloodline_id: UUID | None = None
    herd_id: UUID | None = None
    group_id: UUID | None = None
    line: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str | None = None
    purpose: str | None = None
    purposes: list[str] | None = None
    registration_status: str | None = None
    date_of_birth: date | None = None
    dob_estimated: bool | None = None
    birth_weight_kg: Decimal | None = Field(None, ge=0)
    current_weight_kg: Decimal | None = Field(None, ge=0)
    production_stage: str | None = None
    reproductive_status: str | None = None
    fertility_status: str | None = None
    market_status: str | None = None
    parity: int | None = Field(None, ge=0)
    acquisition_type: str | None = None
    acquired_on: date | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    tags: list[str] | None = None
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", swm.SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", swm.PURPOSE_VALUES))
    _reg = field_validator("registration_status")(_one_of("registration_status", swm.REGISTRATION_STATUS_VALUES))
    _ps = field_validator("production_stage")(_one_of("production_stage", swm.PRODUCTION_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", swm.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", swm.FERTILITY_STATUS_VALUES))
    _ms = field_validator("market_status")(_one_of("market_status", swm.MARKET_STATUS_VALUES))
    _at = field_validator("acquisition_type")(_one_of("acquisition_type", swm.ACQUISITION_TYPE_VALUES))


class PigResponse(TimestampedSchema):
    farm_id: UUID
    breed_id: UUID | None
    bloodline_id: UUID | None
    herd_id: UUID | None
    group_id: UUID | None
    pen_id: UUID | None
    internal_ref: str
    name: str | None
    ear_tag: str | None
    ear_notch: str | None
    tattoo: str | None
    qr_code: str | None
    rfid: str | None
    visual_id: str | None
    registration_number: str | None
    line: str | None
    color: str | None
    sex: str
    purpose: str
    purposes: list
    registration_status: str
    date_of_birth: date | None
    dob_estimated: bool
    birth_weight_kg: Decimal | None
    current_weight_kg: Decimal | None
    production_stage: str
    status: str
    reproductive_status: str
    fertility_status: str
    market_status: str
    parity: int | None
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


class PigDetailResponse(PigResponse):
    sire_ref: str | None = None
    dam_ref: str | None = None


# ── Lifecycle inputs ───────────────────────────────────────────────────────────

class MoveInput(AGRIOSSchema):
    """Move a pig between management group and/or physical pen.

    Any field left unset is unchanged; ``clear`` lists location fields to null out
    (group/pen)."""

    group_id: UUID | None = None
    pen_id: UUID | None = None
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

class PigEventResponse(TimestampedSchema):
    pig_id: UUID
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

    _mt = field_validator("media_type")(_one_of("media_type", swm.MEDIA_TYPE_VALUES))


class MediaResponse(TimestampedSchema):
    pig_id: UUID
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

    _dt = field_validator("document_type")(_one_of("document_type", swm.DOCUMENT_TYPE_VALUES))


class DocumentResponse(TimestampedSchema):
    pig_id: UUID
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
    sire_id: UUID | None = None
    method: str = Field("natural")
    service_date: date | None = None
    # Artificial insemination detail (required when method='artificial' with no sire).
    semen_source: str | None = Field(None, max_length=200)
    semen_batch: str | None = Field(None, max_length=100)
    technician: str | None = Field(None, max_length=150)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", swm.BREEDING_METHOD_VALUES))


class ServiceInput(AGRIOSSchema):
    service_date: date


class PregnancyCheckInput(AGRIOSSchema):
    checked_on: date
    result: str = Field("unknown")
    method: str | None = Field(None, max_length=20)
    risk_level: str | None = Field(None, max_length=20)

    _r = field_validator("result")(_one_of("result", swm.PREGNANCY_RESULT_VALUES))
    _cm = field_validator("method")(_one_of("method", swm.PREGNANCY_CHECK_METHOD_VALUES))
    _rl = field_validator("risk_level")(_one_of("risk_level", swm.PREGNANCY_RISK_VALUES))


class BreedingResponse(TimestampedSchema):
    farm_id: UUID
    dam_id: UUID | None
    sire_id: UUID | None
    repeat_of_id: UUID | None
    method: str
    service_date: date | None
    planned_farrowing_date: date | None
    semen_source: str | None
    semen_batch: str | None
    technician: str | None
    pregnancy_checked_on: date | None
    pregnancy_check_method: str | None
    pregnancy_result: str
    confirmed_on: date | None
    risk_level: str
    actual_farrowing_date: date | None
    status: str
    outcome: str | None
    notes: str | None
