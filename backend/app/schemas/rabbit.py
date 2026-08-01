"""
Greena — Rabbit Management Schemas (Module 17)

Request/response contracts for the Rabbit module. Enumerated fields are validated
against the value tuples defined on the models, so the API and the database agree
on one source of truth (GMIS §5).

Milestone 1 (Foundation) + Milestone 2 (Registry & Housing) surface:
  * catalog: breed / bloodline (data-driven, Spec Part 3 §5-6)
  * housing hierarchy: rabbitry / building / room / row / cage (Spec Part 1 §6)
  * rabbits: register / edit / archive / restore / move / transfer / sell / death
  * timeline, tags, media & document attachments (Spec Part 8 §14-15)
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import rabbit as rb
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


# ── Catalog: Breed (Spec Part 3 §5) ───────────────────────────────────────────

class BreedCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    category: str = Field("other")
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict = Field(default_factory=dict)

    _cat = field_validator("category")(_one_of("category", rb.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", rb.BREED_PURPOSE_VALUES))


class BreedUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=150)
    category: str | None = None
    origin: str | None = Field(None, max_length=150)
    production_purpose: str | None = Field(None, max_length=30)
    profile: dict | None = None

    _cat = field_validator("category")(_one_of("category", rb.BREED_CATEGORY_VALUES))
    _pur = field_validator("production_purpose")(_one_of("production_purpose", rb.BREED_PURPOSE_VALUES))


class BreedResponse(TimestampedSchema):
    organization_id: UUID | None
    name: str
    category: str
    origin: str | None
    production_purpose: str | None
    profile: dict
    is_system: bool


# ── Catalog: Bloodline (Spec Part 3 §6) ────────────────────────────────────────

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


# ── Housing hierarchy (Spec Part 1 §6) ─────────────────────────────────────────

class _HousingBase(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    status: str = Field("active")
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", rb.HOUSING_STATUS_VALUES))


class RabbitryCreate(_HousingBase):
    location: str | None = Field(None, max_length=200)


class RabbitryUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    location: str | None = Field(None, max_length=200)
    status: str | None = None
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", rb.HOUSING_STATUS_VALUES))


class RabbitryResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    location: str | None
    status: str
    notes: str | None


class BuildingCreate(_HousingBase):
    rabbitry_id: UUID


class BuildingUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    rabbitry_id: UUID | None = None
    status: str | None = None
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", rb.HOUSING_STATUS_VALUES))


class BuildingResponse(TimestampedSchema):
    farm_id: UUID
    rabbitry_id: UUID
    name: str
    code: str | None
    status: str
    notes: str | None


class RoomCreate(_HousingBase):
    building_id: UUID


class RoomUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    building_id: UUID | None = None
    status: str | None = None
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", rb.HOUSING_STATUS_VALUES))


class RoomResponse(TimestampedSchema):
    farm_id: UUID
    building_id: UUID
    name: str
    code: str | None
    status: str
    notes: str | None


class RowCreate(_HousingBase):
    room_id: UUID


class RowUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    room_id: UUID | None = None
    status: str | None = None
    notes: str | None = None

    _st = field_validator("status")(_one_of("status", rb.HOUSING_STATUS_VALUES))


class RowResponse(TimestampedSchema):
    farm_id: UUID
    room_id: UUID
    name: str
    code: str | None
    status: str
    notes: str | None


class CageCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    row_id: UUID | None = None
    cage_type: str = Field("cage")
    capacity: int | None = Field(None, ge=0)
    dimensions: dict = Field(default_factory=dict)
    status: str = Field("available")
    maintenance_status: str | None = Field(None, max_length=50)
    notes: str | None = None

    _ct = field_validator("cage_type")(_one_of("cage_type", rb.CAGE_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", rb.CAGE_STATUS_VALUES))


class CageUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    row_id: UUID | None = None
    cage_type: str | None = None
    capacity: int | None = Field(None, ge=0)
    dimensions: dict | None = None
    status: str | None = None
    maintenance_status: str | None = Field(None, max_length=50)
    notes: str | None = None

    _ct = field_validator("cage_type")(_one_of("cage_type", rb.CAGE_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", rb.CAGE_STATUS_VALUES))


class CageResponse(TimestampedSchema):
    farm_id: UUID
    row_id: UUID | None
    name: str
    code: str | None
    cage_type: str
    capacity: int | None
    dimensions: dict
    status: str
    maintenance_status: str | None
    notes: str | None


class CageDetailResponse(CageResponse):
    """A cage plus its deterministic occupancy (Housing Capacity engine)."""

    occupancy: dict


# ── Rabbit (Spec Part 3 §4) ────────────────────────────────────────────────────

class RabbitCreate(AGRIOSSchema):
    internal_ref: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=150)
    breed_id: UUID | None = None
    bloodline_id: UUID | None = None
    cage_id: UUID | None = None

    ear_tag: str | None = Field(None, max_length=100)
    tattoo: str | None = Field(None, max_length=100)
    qr_code: str | None = Field(None, max_length=200)
    rfid: str | None = Field(None, max_length=100)

    variety: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str = Field("unknown")
    purpose: str = Field("unknown")
    purposes: list[str] = Field(default_factory=list)

    date_of_birth: date | None = None
    dob_estimated: bool = False
    birth_weight_g: Decimal | None = Field(None, ge=0)
    current_weight_g: Decimal | None = Field(None, ge=0)

    lifecycle_stage: str = Field("unknown")
    reproductive_status: str = Field("unknown")
    fertility_status: str = Field("unknown")
    acquisition_type: str = Field("unknown")
    acquired_on: date | None = None

    sire_id: UUID | None = None
    dam_id: UUID | None = None

    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", rb.RABBIT_SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", rb.RABBIT_PURPOSE_VALUES))
    _ls = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", rb.RABBIT_LIFECYCLE_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", rb.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", rb.FERTILITY_STATUS_VALUES))
    _acq = field_validator("acquisition_type")(_one_of("acquisition_type", rb.RABBIT_ACQUISITION_TYPE_VALUES))

    @field_validator("purposes")
    @classmethod
    def _check_purposes(cls, v):
        for p in v or []:
            if p not in rb.RABBIT_PURPOSE_VALUES:
                raise ValueError(f"purpose {p!r} must be one of {rb.RABBIT_PURPOSE_VALUES}")
        return v


class RabbitUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=150)
    breed_id: UUID | None = None
    bloodline_id: UUID | None = None
    ear_tag: str | None = Field(None, max_length=100)
    tattoo: str | None = Field(None, max_length=100)
    qr_code: str | None = Field(None, max_length=200)
    rfid: str | None = Field(None, max_length=100)
    variety: str | None = Field(None, max_length=100)
    color: str | None = Field(None, max_length=100)
    sex: str | None = None
    purpose: str | None = None
    purposes: list[str] | None = None
    date_of_birth: date | None = None
    dob_estimated: bool | None = None
    birth_weight_g: Decimal | None = Field(None, ge=0)
    current_weight_g: Decimal | None = Field(None, ge=0)
    lifecycle_stage: str | None = None
    reproductive_status: str | None = None
    fertility_status: str | None = None
    acquisition_type: str | None = None
    acquired_on: date | None = None
    sire_id: UUID | None = None
    dam_id: UUID | None = None
    tags: list[str] | None = None
    notes: str | None = None

    _sex = field_validator("sex")(_one_of("sex", rb.RABBIT_SEX_VALUES))
    _pur = field_validator("purpose")(_one_of("purpose", rb.RABBIT_PURPOSE_VALUES))
    _ls = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", rb.RABBIT_LIFECYCLE_STAGE_VALUES))
    _rs = field_validator("reproductive_status")(_one_of("reproductive_status", rb.REPRODUCTIVE_STATUS_VALUES))
    _fs = field_validator("fertility_status")(_one_of("fertility_status", rb.FERTILITY_STATUS_VALUES))
    _acq = field_validator("acquisition_type")(_one_of("acquisition_type", rb.RABBIT_ACQUISITION_TYPE_VALUES))


class RabbitResponse(TimestampedSchema):
    farm_id: UUID
    breed_id: UUID | None
    bloodline_id: UUID | None
    cage_id: UUID | None
    litter_id: UUID | None
    internal_ref: str
    name: str | None
    ear_tag: str | None
    tattoo: str | None
    qr_code: str | None
    rfid: str | None
    variety: str | None
    color: str | None
    sex: str
    purpose: str
    purposes: list
    date_of_birth: date | None
    dob_estimated: bool
    birth_weight_g: Decimal | None
    current_weight_g: Decimal | None
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
    # Denormalised display names (resolved by the service; avoids N+1).
    breed_name: str | None = None
    bloodline_name: str | None = None
    cage_name: str | None = None


class RabbitDetailResponse(RabbitResponse):
    sire_ref: str | None = None
    dam_ref: str | None = None
    location_path: str | None = None


# ── Lifecycle / movement inputs ────────────────────────────────────────────────

class MoveInput(AGRIOSSchema):
    cage_id: UUID | None = None
    reason: str | None = Field(None, max_length=200)
    occurred_on: date | None = None
    notes: str | None = None


class TransferInput(AGRIOSSchema):
    to_owner_name: str = Field(..., min_length=1, max_length=200)
    to_owner_contact: str | None = Field(None, max_length=200)
    destination: str | None = Field(None, max_length=200)
    occurred_on: date | None = None
    notes: str | None = None


class SaleInput(AGRIOSSchema):
    buyer_name: str = Field(..., min_length=1, max_length=200)
    buyer_contact: str | None = Field(None, max_length=200)
    price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    occurred_on: date | None = None
    notes: str | None = None


class DeathInput(AGRIOSSchema):
    cause: str | None = Field(None, max_length=200)
    occurred_on: date | None = None
    notes: str | None = None


class ArchiveInput(AGRIOSSchema):
    reason: str | None = Field(None, max_length=300)


class RabbitEventResponse(TimestampedSchema):
    rabbit_id: UUID
    event_type: str
    occurred_at: object
    summary: str | None
    details: dict
    operator_id: UUID | None


# ── Attachments ────────────────────────────────────────────────────────────────

class MediaCreate(AGRIOSSchema):
    media_type: str = Field("photo")
    title: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=1000)
    storage_path: str | None = Field(None, max_length=500)
    filename: str | None = Field(None, max_length=255)
    content_type: str | None = Field(None, max_length=120)
    size_bytes: int | None = Field(None, ge=0)
    captured_on: date | None = None

    _mt = field_validator("media_type")(_one_of("media_type", rb.MEDIA_TYPE_VALUES))


class MediaResponse(TimestampedSchema):
    rabbit_id: UUID
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

    _dt = field_validator("document_type")(_one_of("document_type", rb.DOCUMENT_TYPE_VALUES))


class DocumentResponse(TimestampedSchema):
    rabbit_id: UUID
    document_type: str
    title: str | None
    url: str | None
    storage_path: str | None
    filename: str | None
    content_type: str | None
    size_bytes: int | None
    issued_on: date | None
    expires_on: date | None


# ── Breeding cycle (Spec Part 3 §7, Part 4 §6) ─────────────────────────────────

class BreedingCreate(AGRIOSSchema):
    doe_id: UUID
    buck_id: UUID
    method: str = Field("natural")
    service_date: date | None = None
    repeat_of_id: UUID | None = None
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", rb.BREEDING_METHOD_VALUES))


class ServiceInput(AGRIOSSchema):
    service_date: date
    method: str | None = None

    _m = field_validator("method")(_one_of("method", rb.BREEDING_METHOD_VALUES))


class PregnancyCheckInput(AGRIOSSchema):
    result: str
    checked_on: date | None = None
    notes: str | None = None

    @field_validator("result")
    @classmethod
    def _check_result(cls, v):
        if v not in ("pregnant", "not_pregnant"):
            raise ValueError("result must be 'pregnant' or 'not_pregnant'")
        return v


class PrepareKindlingInput(AGRIOSSchema):
    prepared_on: date | None = None


class KindlingInput(AGRIOSSchema):
    kindling_date: date
    total_kits: int = Field(..., ge=0)
    live_kits: int | None = Field(None, ge=0)
    stillbirths: int | None = Field(None, ge=0)
    avg_birth_weight_g: Decimal | None = Field(None, ge=0)
    create_kits: bool = False
    notes: str | None = None


class FosterInput(AGRIOSSchema):
    fostered_in: int | None = Field(None, ge=0)
    fostered_out: int | None = Field(None, ge=0)
    notes: str | None = None


class WeaningInput(AGRIOSSchema):
    weaned_kits: int = Field(..., ge=0)
    weaning_date: date | None = None
    notes: str | None = None


class CompatibilityInput(AGRIOSSchema):
    buck_id: UUID
    doe_id: UUID


class BreedingResponse(TimestampedSchema):
    farm_id: UUID
    doe_id: UUID | None
    buck_id: UUID | None
    repeat_of_id: UUID | None
    method: str
    service_date: date | None
    planned_kindling_date: date | None
    pregnancy_checked_on: date | None
    pregnancy_result: str
    nest_box_prepared_on: date | None
    actual_kindling_date: date | None
    status: str
    outcome: str | None
    notes: str | None


class LitterResponse(TimestampedSchema):
    farm_id: UUID
    breeding_id: UUID | None
    doe_id: UUID | None
    buck_id: UUID | None
    litter_code: str
    kindling_date: date
    total_kits: int
    live_kits: int
    stillbirths: int
    fostered_in: int
    fostered_out: int
    weaned_kits: int
    mortality: int
    avg_birth_weight_g: Decimal | None
    weaning_date: date | None
    status: str
    notes: str | None


class LitterDetailResponse(LitterResponse):
    performance: dict
