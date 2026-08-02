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
    litter_id: UUID | None
    nurse_dam_id: UUID | None
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
    birth_sex: str
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


class MovementResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID
    movement_type: str
    from_pen_id: UUID | None
    to_pen_id: UUID | None
    from_group_id: UUID | None
    to_group_id: UUID | None
    moved_on: date
    reason: str | None
    notes: str | None
    moved_by: UUID | None


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
    status: str
    outcome: str
    notes: str | None


# ── Pregnancy (Milestone 3) — a lifecycle stage, separate from the breeding ─────

class PregnancyCheckInput(AGRIOSSchema):
    """Record a pregnancy check on a breeding. A positive result confirms a
    pregnancy; a negative result resolves the breeding as not-pregnant."""

    checked_on: date
    result: str = Field("unknown")
    method: str | None = Field(None, max_length=20)
    risk_level: str | None = Field(None, max_length=20)

    _r = field_validator("result")(_one_of("result", swm.PREGNANCY_RESULT_VALUES))
    _cm = field_validator("method")(_one_of("method", swm.PREGNANCY_CHECK_METHOD_VALUES))
    _rl = field_validator("risk_level")(_one_of("risk_level", swm.PREGNANCY_RISK_VALUES))


class PregnancyRecheckInput(AGRIOSSchema):
    risk_level: str | None = Field(None, max_length=20)
    expected_farrowing_date: date | None = None
    notes: str | None = None

    _rl = field_validator("risk_level")(_one_of("risk_level", swm.PREGNANCY_RISK_VALUES))


class PregnancyLossInput(AGRIOSSchema):
    loss_reason: str | None = Field(None, max_length=20)
    loss_date: date | None = None
    false_pregnancy: bool = False
    notes: str | None = None

    _lr = field_validator("loss_reason")(_one_of("loss_reason", swm.PREGNANCY_LOSS_REASON_VALUES))


class PregnancyResponse(TimestampedSchema):
    farm_id: UUID
    breeding_id: UUID | None
    dam_id: UUID | None
    status: str
    confirmation_date: date | None
    confirmation_method: str | None
    expected_farrowing_date: date | None
    risk_level: str
    loss_reason: str | None
    loss_date: date | None
    actual_farrowing_date: date | None
    notes: str | None


# ── Farrowing, litters & fostering (Milestone 4) ───────────────────────────────

class PigletAddInput(AGRIOSSchema):
    """One individual piglet to register against a litter (optional individualisation)."""

    internal_ref: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=150)
    ear_notch: str | None = Field(None, max_length=100)
    birth_sex: str = Field("unknown")
    birth_weight_kg: Decimal | None = Field(None, ge=0)

    _bs = field_validator("birth_sex")(_one_of("birth_sex", swm.BIRTH_SEX_VALUES))


class FarrowingRecordInput(AGRIOSSchema):
    """Record a farrowing + its litter. Provide the pregnancy or breeding it resolves
    (or an explicit dam). ``total_born`` is derived as born_alive+stillborn+mummified."""

    breeding_id: UUID | None = None
    pregnancy_id: UUID | None = None
    dam_id: UUID | None = None
    sire_id: UUID | None = None
    farrowing_date: date
    born_alive: int = Field(0, ge=0)
    stillborn: int = Field(0, ge=0)
    mummified: int = Field(0, ge=0)
    avg_birth_weight_kg: Decimal | None = Field(None, ge=0)
    litter_birth_weight_kg: Decimal | None = Field(None, ge=0)
    parity: int | None = Field(None, ge=0)
    assistance_required: bool = False
    complications: str | None = None
    colostrum_status: str = Field("unknown")
    location: str | None = Field(None, max_length=200)
    notes: str | None = None
    create_individuals: list[PigletAddInput] = Field(default_factory=list)

    _cs = field_validator("colostrum_status")(_one_of("colostrum_status", swm.COLOSTRUM_STATUS_VALUES))


class FarrowingResponse(TimestampedSchema):
    farm_id: UUID
    breeding_id: UUID | None
    pregnancy_id: UUID | None
    dam_id: UUID | None
    sire_id: UUID | None
    farrowing_code: str
    farrowing_date: date
    parity: int | None
    assistance_required: bool
    complications: str | None
    colostrum_status: str
    status: str
    location: str | None
    notes: str | None


class LitterResponse(TimestampedSchema):
    farm_id: UUID
    farrowing_id: UUID | None
    dam_id: UUID | None
    sire_id: UUID | None
    nurse_dam_id: UUID | None
    litter_code: str
    total_born: int
    born_alive: int
    stillborn: int
    mummified: int
    weaned: int
    mortality: int
    fostered_in: int
    fostered_out: int
    avg_birth_weight_kg: Decimal | None
    litter_birth_weight_kg: Decimal | None
    weaning_date: date | None
    avg_weaning_weight_kg: Decimal | None
    status: str
    notes: str | None


class LitterMortalityInput(AGRIOSSchema):
    count: int = Field(1, ge=1)
    cause: str | None = Field(None, max_length=20)
    pig_id: UUID | None = None
    occurred_on: date | None = None

    _c = field_validator("cause")(_one_of("cause", swm.PIGLET_DEATH_CAUSE_VALUES))


class FosterTransferInput(AGRIOSSchema):
    source_litter_id: UUID
    dest_litter_id: UUID
    piglet_count: int = Field(0, ge=0)
    pig_ids: list[UUID] = Field(default_factory=list)
    transfer_date: date
    reason: str | None = Field(None, max_length=255)
    notes: str | None = None


class FosterTransferResponse(TimestampedSchema):
    farm_id: UUID
    source_litter_id: UUID | None
    dest_litter_id: UUID | None
    source_dam_id: UUID | None
    dest_dam_id: UUID | None
    piglet_count: int
    pig_ids: list
    transfer_date: date
    reason: str | None
    notes: str | None


class WeaningInput(AGRIOSSchema):
    weaned: int = Field(..., ge=0)
    weaning_date: date
    avg_weaning_weight_kg: Decimal | None = Field(None, ge=0)
    nursery_group_id: UUID | None = None


# ── Feed & nutrition (Milestone 5) ─────────────────────────────────────────────

class FeedCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field("other")
    form: str = Field("pellet")
    profile: dict = Field(default_factory=dict)
    is_medicated: bool = False
    withdrawal_days: int | None = Field(None, ge=0)

    _cat = field_validator("category")(_one_of("category", swm.FEED_CATEGORY_VALUES))
    _form = field_validator("form")(_one_of("form", swm.FEED_FORM_VALUES))


class FeedUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    category: str | None = None
    form: str | None = None
    profile: dict | None = None
    is_medicated: bool | None = None
    withdrawal_days: int | None = Field(None, ge=0)

    _cat = field_validator("category")(_one_of("category", swm.FEED_CATEGORY_VALUES))
    _form = field_validator("form")(_one_of("form", swm.FEED_FORM_VALUES))


class FeedResponse(TimestampedSchema):
    organization_id: UUID | None
    name: str
    category: str
    form: str
    profile: dict
    is_medicated: bool
    withdrawal_days: int | None
    is_system: bool


class FeedPlanCreate(AGRIOSSchema):
    plan_name: str = Field(..., min_length=1, max_length=150)
    production_stage: str = Field("unknown")
    phase_label: str | None = Field(None, max_length=100)
    feed_id: UUID | None = None
    daily_amount_kg: Decimal | None = Field(None, ge=0)
    age_start_days: int | None = Field(None, ge=0)
    age_end_days: int | None = Field(None, ge=0)
    target_weight_start_kg: Decimal | None = Field(None, ge=0)
    target_weight_end_kg: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    _ps = field_validator("production_stage")(_one_of("production_stage", swm.PRODUCTION_STAGE_VALUES))


class FeedPlanUpdate(AGRIOSSchema):
    plan_name: str | None = Field(None, min_length=1, max_length=150)
    production_stage: str | None = None
    phase_label: str | None = Field(None, max_length=100)
    feed_id: UUID | None = None
    daily_amount_kg: Decimal | None = Field(None, ge=0)
    age_start_days: int | None = Field(None, ge=0)
    age_end_days: int | None = Field(None, ge=0)
    target_weight_start_kg: Decimal | None = Field(None, ge=0)
    target_weight_end_kg: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    _ps = field_validator("production_stage")(_one_of("production_stage", swm.PRODUCTION_STAGE_VALUES))


class FeedPlanResponse(TimestampedSchema):
    farm_id: UUID
    plan_name: str
    production_stage: str
    phase_label: str | None
    feed_id: UUID | None
    daily_amount_kg: Decimal | None
    age_start_days: int | None
    age_end_days: int | None
    target_weight_start_kg: Decimal | None
    target_weight_end_kg: Decimal | None
    notes: str | None


class FeedRecordCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    feed_id: UUID | None = None
    feed_name: str | None = Field(None, max_length=150)
    quantity_kg: Decimal = Field(..., gt=0)
    fed_on: date
    inventory_item_id: UUID | None = None
    cost: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = None


class FeedRecordResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    feed_id: UUID | None
    inventory_item_id: UUID | None
    inventory_movement_id: UUID | None
    feed_name: str | None
    quantity_kg: Decimal
    fed_on: date
    cost: Decimal | None
    currency: str | None
    supplier: str | None
    notes: str | None


# ── Health & biosecurity (Milestone 6) ─────────────────────────────────────────

class DiseaseCaseCreate(AGRIOSSchema):
    scope: str = Field("individual")
    pig_id: UUID | None = None
    group_id: UUID | None = None
    pen_id: UUID | None = None
    litter_id: UUID | None = None
    disease_name: str = Field(..., min_length=1, max_length=200)
    pathogen: str | None = Field(None, max_length=200)
    status: str = Field("suspected")
    severity: str = Field("mild")
    onset_date: date | None = None
    resolved_date: date | None = None
    affected_count: int = Field(1, ge=0)
    mortality_count: int = Field(0, ge=0)
    diagnosis: str | None = None
    reported_by: str | None = Field(None, max_length=200)
    notes: str | None = None

    _sc = field_validator("scope")(_one_of("scope", swm.DISEASE_SCOPE_VALUES))
    _st = field_validator("status")(_one_of("status", swm.DISEASE_STATUS_VALUES))
    _sev = field_validator("severity")(_one_of("severity", swm.HEALTH_SEVERITY_VALUES))


class DiseaseCaseUpdate(AGRIOSSchema):
    status: str | None = None
    severity: str | None = None
    pathogen: str | None = Field(None, max_length=200)
    resolved_date: date | None = None
    affected_count: int | None = Field(None, ge=0)
    mortality_count: int | None = Field(None, ge=0)
    diagnosis: str | None = None
    reported_by: str | None = Field(None, max_length=200)
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", swm.DISEASE_STATUS_VALUES))
    _sev = field_validator("severity")(_one_of("severity", swm.HEALTH_SEVERITY_VALUES))


class DiseaseCaseResponse(TimestampedSchema):
    farm_id: UUID
    scope: str
    pig_id: UUID | None
    group_id: UUID | None
    pen_id: UUID | None
    litter_id: UUID | None
    disease_name: str
    pathogen: str | None
    status: str
    severity: str
    onset_date: date | None
    resolved_date: date | None
    affected_count: int
    mortality_count: int
    diagnosis: str | None
    reported_by: str | None
    notes: str | None


class VaccinationCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    vaccine_name: str = Field(..., min_length=1, max_length=200)
    disease_targeted: str | None = Field(None, max_length=200)
    dose: Decimal | None = Field(None, ge=0)
    dose_unit: str | None = Field(None, max_length=20)
    route: str | None = None
    batch_number: str | None = Field(None, max_length=100)
    administered_on: date
    next_due_date: date | None = None
    administered_by: str | None = Field(None, max_length=200)
    animal_count: int = Field(1, ge=1)
    inventory_item_id: UUID | None = None
    notes: str | None = None

    _rt = field_validator("route")(_one_of("route", swm.ADMIN_ROUTE_VALUES))


class VaccinationResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    vaccine_name: str
    disease_targeted: str | None
    dose: Decimal | None
    dose_unit: str | None
    route: str | None
    batch_number: str | None
    administered_on: date
    next_due_date: date | None
    administered_by: str | None
    animal_count: int
    inventory_item_id: UUID | None
    inventory_movement_id: UUID | None
    notes: str | None


class TreatmentCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    disease_case_id: UUID | None = None
    intent: str = Field("therapeutic")
    product_name: str = Field(..., min_length=1, max_length=200)
    drug: str | None = Field(None, max_length=200)
    dose: Decimal | None = Field(None, ge=0)
    dose_unit: str | None = Field(None, max_length=20)
    route: str | None = None
    started_on: date
    ended_on: date | None = None
    duration_days: int | None = Field(None, ge=0)
    withdrawal_until: date | None = None
    administered_by: str | None = Field(None, max_length=200)
    outcome: str = Field("ongoing")
    animal_count: int = Field(1, ge=1)
    inventory_item_id: UUID | None = None
    notes: str | None = None

    _in = field_validator("intent")(_one_of("intent", swm.TREATMENT_INTENT_VALUES))
    _rt = field_validator("route")(_one_of("route", swm.ADMIN_ROUTE_VALUES))
    _oc = field_validator("outcome")(_one_of("outcome", swm.TREATMENT_OUTCOME_VALUES))


class TreatmentResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    disease_case_id: UUID | None
    intent: str
    product_name: str
    drug: str | None
    dose: Decimal | None
    dose_unit: str | None
    route: str | None
    started_on: date
    ended_on: date | None
    duration_days: int | None
    withdrawal_until: date | None
    administered_by: str | None
    outcome: str
    animal_count: int
    inventory_item_id: UUID | None
    inventory_movement_id: UUID | None
    notes: str | None


class ProcedureCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    procedure_type: str = Field("other")
    performed_on: date
    performed_by: str | None = Field(None, max_length=200)
    anesthesia: bool = False
    analgesia: bool = False
    outcome: str | None = Field(None, max_length=100)
    animal_count: int = Field(1, ge=1)
    notes: str | None = None

    _pt = field_validator("procedure_type")(_one_of("procedure_type", swm.PROCEDURE_TYPE_VALUES))


class ProcedureResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    procedure_type: str
    performed_on: date
    performed_by: str | None
    anesthesia: bool
    analgesia: bool
    outcome: str | None
    animal_count: int
    notes: str | None


class ObservationCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    observation_type: str = Field("routine_check")
    observed_on: date
    temperature_c: Decimal | None = Field(None, ge=0)
    body_condition_score: Decimal | None = Field(None, ge=0)
    severity: str = Field("info")
    findings: str | None = None
    observed_by: str | None = Field(None, max_length=200)
    notes: str | None = None

    _ot = field_validator("observation_type")(_one_of("observation_type", swm.OBSERVATION_TYPE_VALUES))
    _sev = field_validator("severity")(_one_of("severity", swm.HEALTH_SEVERITY_VALUES))


class ObservationResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    observation_type: str
    observed_on: date
    temperature_c: Decimal | None
    body_condition_score: Decimal | None
    severity: str
    findings: str | None
    observed_by: str | None
    notes: str | None


class LabTestCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    disease_case_id: UUID | None = None
    sample_type: str | None = Field(None, max_length=100)
    test_name: str = Field(..., min_length=1, max_length=200)
    laboratory: str | None = Field(None, max_length=200)
    collected_on: date | None = None
    result_on: date | None = None
    status: str = Field("pending")
    result: str = Field("pending")
    result_detail: str | None = None
    reference: str | None = Field(None, max_length=150)
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", swm.LAB_STATUS_VALUES))
    _rs = field_validator("result")(_one_of("result", swm.LAB_RESULT_VALUES))


class LabTestUpdate(AGRIOSSchema):
    status: str | None = None
    result: str | None = None
    result_on: date | None = None
    result_detail: str | None = None
    reference: str | None = Field(None, max_length=150)
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", swm.LAB_STATUS_VALUES))
    _rs = field_validator("result")(_one_of("result", swm.LAB_RESULT_VALUES))


class LabTestResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    disease_case_id: UUID | None
    sample_type: str | None
    test_name: str
    laboratory: str | None
    collected_on: date | None
    result_on: date | None
    status: str
    result: str
    result_detail: str | None
    reference: str | None
    notes: str | None


class MortalityCreate(AGRIOSSchema):
    pig_id: UUID | None = None
    litter_id: UUID | None = None
    group_id: UUID | None = None
    pen_id: UUID | None = None
    disease_case_id: UUID | None = None
    treatment_id: UUID | None = None
    died_on: date
    count: int = Field(1, ge=1)
    cause_category: str = Field("unknown")
    suspected_cause: str | None = Field(None, max_length=255)
    confirmed_cause: str | None = Field(None, max_length=255)
    vet_name: str | None = Field(None, max_length=200)
    disposal_method: str = Field("unknown")
    weight_kg: Decimal | None = Field(None, ge=0)
    notes: str | None = None

    _cc = field_validator("cause_category")(_one_of("cause_category", swm.MORTALITY_CAUSE_CATEGORY_VALUES))
    _dm = field_validator("disposal_method")(_one_of("disposal_method", swm.DISPOSAL_METHOD_VALUES))


class MortalityResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    litter_id: UUID | None
    group_id: UUID | None
    pen_id: UUID | None
    disease_case_id: UUID | None
    treatment_id: UUID | None
    died_on: date
    count: int
    cause_category: str
    suspected_cause: str | None
    confirmed_cause: str | None
    vet_name: str | None
    disposal_method: str
    weight_kg: Decimal | None
    notes: str | None


class IsolationStartInput(AGRIOSSchema):
    pig_id: UUID | None = None
    group_id: UUID | None = None
    pen_id: UUID | None = None
    disease_case_id: UUID | None = None
    reason: str = Field("observation")
    started_on: date
    notes: str | None = None

    _rn = field_validator("reason")(_one_of("reason", swm.ISOLATION_REASON_VALUES))


class IsolationEndInput(AGRIOSSchema):
    ended_on: date | None = None
    cleared: bool = True
    cleared_by: str | None = Field(None, max_length=200)
    clearance_notes: str | None = None


class IsolationResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID | None
    group_id: UUID | None
    pen_id: UUID | None
    disease_case_id: UUID | None
    reason: str
    status: str
    started_on: date
    ended_on: date | None
    cleared_by: str | None
    clearance_notes: str | None
    notes: str | None


class BiosecurityRecordCreate(AGRIOSSchema):
    record_type: str = Field("inspection")
    occurred_on: date
    pen_id: UUID | None = None
    location: str | None = Field(None, max_length=200)
    party_name: str | None = Field(None, max_length=200)
    performed_by: str | None = Field(None, max_length=200)
    product_used: str | None = Field(None, max_length=200)
    compliant: bool | None = None
    detail: str | None = None
    reminder_id: UUID | None = None
    notes: str | None = None

    _rt = field_validator("record_type")(_one_of("record_type", swm.BIOSECURITY_RECORD_TYPE_VALUES))


class BiosecurityRecordUpdate(AGRIOSSchema):
    compliant: bool | None = None
    detail: str | None = None
    product_used: str | None = Field(None, max_length=200)
    notes: str | None = None


class BiosecurityRecordResponse(TimestampedSchema):
    farm_id: UUID
    record_type: str
    occurred_on: date
    pen_id: UUID | None
    location: str | None
    party_name: str | None
    performed_by: str | None
    product_used: str | None
    compliant: bool | None
    detail: str | None
    reminder_id: UUID | None
    notes: str | None


# ── Growth & production (Milestone 7) ──────────────────────────────────────────

class WeightCreate(AGRIOSSchema):
    recorded_on: date
    weight_kg: Decimal = Field(..., gt=0)
    method: str = Field("scale")
    age_days: int | None = Field(None, ge=0)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", swm.WEIGHT_METHOD_VALUES))


class WeightResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID
    recorded_on: date
    weight_kg: Decimal
    method: str
    age_days: int | None
    notes: str | None


class BodyConditionCreate(AGRIOSSchema):
    assessed_on: date
    score: Decimal = Field(..., ge=1, le=5)
    assessor: str | None = Field(None, max_length=200)
    notes: str | None = None


class BodyConditionResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID
    assessed_on: date
    score: Decimal
    assessor: str | None
    notes: str | None


class StageTransitionInput(AGRIOSSchema):
    new_stage: str
    transition_date: date
    reason: str | None = Field(None, max_length=255)
    source: str = Field("manual")

    _ns = field_validator("new_stage")(_one_of("new_stage", swm.PRODUCTION_STAGE_VALUES))
    _sr = field_validator("source")(_one_of("source", swm.STAGE_TRANSITION_SOURCE_VALUES))


class StageTransitionResponse(TimestampedSchema):
    farm_id: UUID
    pig_id: UUID
    previous_stage: str | None
    new_stage: str
    transition_date: date
    reason: str | None
    source: str
