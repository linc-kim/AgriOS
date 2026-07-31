"""
Greena — Black Soldier Fly Schemas (Module 16)

Request/response contracts for the BSF module. Enumerated fields are validated
against the value tuples defined on the models, so the API and the database
agree on one source of truth (matching the Aviculture convention).

Part 1 (Foundation) + Part 2 (Batch backbone) surface:
  * species catalog (data-driven biological reference)
  * production units (bins/trays/racks/incubators/dryers)
  * breeding colonies
  * production batches: create / edit / advance lifecycle / split / merge / move
  * lifecycle history, batch timeline, deterministic production metrics
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import bsf
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Validators ────────────────────────────────────────────────────────────────

def _one_of(field_name: str, allowed: tuple[str, ...]):
    def _check(value):
        if value is None:
            return value
        if value not in allowed:
            raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")
        return value

    return _check


# ── Species catalog ───────────────────────────────────────────────────────────

class SpeciesCreate(AGRIOSSchema):
    common_name: str = Field(..., min_length=1, max_length=150)
    scientific_name: str | None = Field(None, max_length=200)
    strain: str | None = Field(None, max_length=150)
    production_type: str = Field("larvae")
    profile: dict = Field(default_factory=dict)

    _pt = field_validator("production_type")(_one_of("production_type", bsf.BSF_PRODUCTION_TYPE_VALUES))


class SpeciesResponse(TimestampedSchema):
    organization_id: UUID | None
    common_name: str
    scientific_name: str | None
    strain: str | None
    production_type: str
    profile: dict
    is_system: bool


# ── Production unit ───────────────────────────────────────────────────────────

class ProductionUnitCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    unit_type: str = Field("bin")
    facility: str | None = Field(None, max_length=200)
    production_area: str | None = Field(None, max_length=200)
    capacity_grams: Decimal | None = Field(None, ge=0)
    environment_profile: dict = Field(default_factory=dict)
    notes: str | None = None

    _ut = field_validator("unit_type")(_one_of("unit_type", bsf.UNIT_TYPE_VALUES))


class ProductionUnitUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    unit_type: str | None = None
    facility: str | None = Field(None, max_length=200)
    production_area: str | None = Field(None, max_length=200)
    capacity_grams: Decimal | None = Field(None, ge=0)
    status: str | None = None
    environment_profile: dict | None = None
    maintenance_status: str | None = Field(None, max_length=50)
    notes: str | None = None

    _ut = field_validator("unit_type")(_one_of("unit_type", bsf.UNIT_TYPE_VALUES))
    _st = field_validator("status")(_one_of("status", bsf.UNIT_STATUS_VALUES))


class ProductionUnitResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    unit_type: str
    facility: str | None
    production_area: str | None
    capacity_grams: Decimal | None
    status: str
    environment_profile: dict
    maintenance_status: str | None
    notes: str | None


# ── Colony ────────────────────────────────────────────────────────────────────

class ColonyCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    species_id: UUID | None = None
    production_unit_id: UUID | None = None
    source: str = Field("unknown")
    established_on: date | None = None
    population_estimate: int | None = Field(None, ge=0)
    notes: str | None = None

    _src = field_validator("source")(_one_of("source", bsf.COLONY_SOURCE_VALUES))


class ColonyUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    species_id: UUID | None = None
    production_unit_id: UUID | None = None
    source: str | None = None
    established_on: date | None = None
    population_estimate: int | None = Field(None, ge=0)
    status: str | None = None
    retired_on: date | None = None
    notes: str | None = None

    _src = field_validator("source")(_one_of("source", bsf.COLONY_SOURCE_VALUES))
    _st = field_validator("status")(_one_of("status", bsf.COLONY_STATUS_VALUES))


class ColonyResponse(TimestampedSchema):
    farm_id: UUID
    species_id: UUID | None
    production_unit_id: UUID | None
    name: str
    code: str | None
    source: str
    established_on: date | None
    population_estimate: int | None
    status: str
    retired_on: date | None
    notes: str | None


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchCreate(AGRIOSSchema):
    batch_number: str | None = Field(None, max_length=50,
                                     description="Optional; auto-generated per farm when omitted.")
    name: str | None = Field(None, max_length=200)
    batch_type: str = Field("production")
    species_id: UUID | None = None
    source_colony_id: UUID | None = None
    production_unit_id: UUID | None = None
    lifecycle_stage: str = Field("egg")
    started_on: date | None = None
    population_estimate: int | None = Field(None, ge=0)
    biomass_estimate_g: Decimal | None = Field(None, ge=0)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None

    _bt = field_validator("batch_type")(_one_of("batch_type", bsf.BATCH_TYPE_VALUES))
    _ls = field_validator("lifecycle_stage")(_one_of("lifecycle_stage", bsf.LIFECYCLE_STAGE_VALUES))


class BatchUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=200)
    batch_type: str | None = None
    species_id: UUID | None = None
    production_unit_id: UUID | None = None
    population_estimate: int | None = Field(None, ge=0)
    biomass_estimate_g: Decimal | None = Field(None, ge=0)
    tags: list[str] | None = None
    notes: str | None = None

    _bt = field_validator("batch_type")(_one_of("batch_type", bsf.BATCH_TYPE_VALUES))


class BatchAdvanceInput(AGRIOSSchema):
    to_stage: str = Field(..., description="Target lifecycle stage (must be forward).")
    occurred_on: date | None = None
    population_estimate: int | None = Field(None, ge=0)
    biomass_estimate_g: Decimal | None = Field(None, ge=0)
    survival_rate_pct: Decimal | None = Field(None, ge=0, le=100)
    observations: str | None = None
    allow_premature: bool = Field(False,
                                  description="Acknowledge advancing before the expected stage duration.")

    _ts = field_validator("to_stage")(_one_of("to_stage", bsf.LIFECYCLE_STAGE_VALUES))


class BatchMoveInput(AGRIOSSchema):
    production_unit_id: UUID | None = Field(..., description="Target unit, or null to unassign.")
    occurred_on: date | None = None
    note: str | None = None


class BatchSplitPart(AGRIOSSchema):
    name: str | None = Field(None, max_length=200)
    population_estimate: int = Field(..., ge=0)
    production_unit_id: UUID | None = None


class BatchSplitInput(AGRIOSSchema):
    parts: list[BatchSplitPart] = Field(..., min_length=2)
    occurred_on: date | None = None
    reason: str | None = None


class BatchMergeInput(AGRIOSSchema):
    source_batch_ids: list[UUID] = Field(..., min_length=2)
    name: str | None = Field(None, max_length=200)
    production_unit_id: UUID | None = None
    occurred_on: date | None = None
    reason: str | None = None


class BatchTerminateInput(AGRIOSSchema):
    occurred_on: date | None = None
    reason: str | None = None


class BatchResponse(TimestampedSchema):
    farm_id: UUID
    species_id: UUID | None
    source_colony_id: UUID | None
    parent_batch_id: UUID | None
    production_unit_id: UUID | None
    batch_number: str
    name: str | None
    batch_type: str
    lifecycle_stage: str
    stage_started_on: date | None
    status: str
    started_on: date | None
    completed_on: date | None
    population_estimate: int | None
    biomass_estimate_g: Decimal | None
    tags: list
    notes: str | None


class LifecycleEventResponse(TimestampedSchema):
    batch_id: UUID
    previous_stage: str | None
    new_stage: str
    occurred_on: date
    population_estimate: int | None
    biomass_estimate_g: Decimal | None
    survival_rate_pct: Decimal | None
    source: str
    observations: str | None


class BatchEventResponse(TimestampedSchema):
    batch_id: UUID
    event_type: str
    summary: str | None
    details: dict
    related_batch_id: UUID | None


class BatchDetailResponse(BatchResponse):
    """Batch plus its deterministic production metrics (honesty-labelled)."""

    metrics: dict
    pacing: dict


# ── Feedstock lots (Spec Part 3 §11) ──────────────────────────────────────────

class FeedstockLotCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    category: str = Field("organic_waste")
    source: str | None = Field(None, max_length=200)
    supplier: str | None = Field(None, max_length=200)
    collection_date: date | None = None
    delivery_date: date | None = None
    weight_kg: Decimal = Field(..., ge=0)
    remaining_kg: Decimal | None = Field(None, ge=0)
    moisture_pct: Decimal | None = Field(None, ge=0, le=100)
    quality: str = Field("unknown")
    storage_location: str | None = Field(None, max_length=200)
    cost: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    notes: str | None = None

    _cat = field_validator("category")(_one_of("category", bsf.FEEDSTOCK_CATEGORY_VALUES))
    _q = field_validator("quality")(_one_of("quality", bsf.FEEDSTOCK_QUALITY_VALUES))


class FeedstockLotUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    category: str | None = None
    source: str | None = Field(None, max_length=200)
    supplier: str | None = Field(None, max_length=200)
    moisture_pct: Decimal | None = Field(None, ge=0, le=100)
    quality: str | None = None
    storage_location: str | None = Field(None, max_length=200)
    remaining_kg: Decimal | None = Field(None, ge=0)
    cost: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=10)
    status: str | None = None
    notes: str | None = None

    _cat = field_validator("category")(_one_of("category", bsf.FEEDSTOCK_CATEGORY_VALUES))
    _q = field_validator("quality")(_one_of("quality", bsf.FEEDSTOCK_QUALITY_VALUES))
    _st = field_validator("status")(_one_of("status", bsf.FEEDSTOCK_STATUS_VALUES))


class FeedstockLotResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    category: str
    source: str | None
    supplier: str | None
    collection_date: date | None
    delivery_date: date | None
    weight_kg: Decimal
    remaining_kg: Decimal
    moisture_pct: Decimal | None
    quality: str
    storage_location: str | None
    cost: Decimal | None
    currency: str | None
    status: str
    notes: str | None


# ── Feeding events (Spec Part 3 §12) ──────────────────────────────────────────

class FeedingEventCreate(AGRIOSSchema):
    feedstock_lot_id: UUID | None = None
    quantity_kg: Decimal = Field(..., gt=0)
    feeding_method: str = Field("manual")
    fed_on: date | None = None
    observations: str | None = None

    _fm = field_validator("feeding_method")(_one_of("feeding_method", bsf.FEEDING_METHOD_VALUES))


class FeedingEventResponse(TimestampedSchema):
    batch_id: UUID
    feedstock_lot_id: UUID | None
    quantity_kg: Decimal
    feeding_method: str
    fed_on: date
    observations: str | None


# ── Environmental readings (Spec Part 3 §13) ──────────────────────────────────

class EnvironmentalReadingCreate(AGRIOSSchema):
    production_unit_id: UUID | None = None
    batch_id: UUID | None = None
    recorded_at: datetime | None = None
    temperature_c: Decimal | None = None
    humidity_pct: Decimal | None = Field(None, ge=0, le=100)
    moisture_pct: Decimal | None = Field(None, ge=0, le=100)
    airflow_mps: Decimal | None = Field(None, ge=0)
    source: str = Field("manual")
    notes: str | None = None

    _src = field_validator("source")(_one_of("source", bsf.ENV_READING_SOURCE_VALUES))


class EnvironmentalReadingResponse(TimestampedSchema):
    farm_id: UUID
    production_unit_id: UUID | None
    batch_id: UUID | None
    recorded_at: datetime
    temperature_c: Decimal | None
    humidity_pct: Decimal | None
    moisture_pct: Decimal | None
    airflow_mps: Decimal | None
    source: str
    notes: str | None


class EnvironmentalReadingResult(AGRIOSSchema):
    """A recorded reading plus its deterministic threshold assessment."""

    reading: EnvironmentalReadingResponse
    assessment: dict
