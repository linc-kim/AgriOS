"""
Greena — Aviculture Incubation Schemas (Module 15, Part 5)

Contracts for eggs, clutches, incubation batches, candling and hatching. Derived
figures (schedule, progress, hatch statistics) are honesty-labelled by the pure
incubation engine and carried through as dicts.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Clutch ────────────────────────────────────────────────────────────────────

class ClutchCreate(AGRIOSSchema):
    pair_id: UUID | None = None
    name: str | None = Field(None, max_length=200)
    laid_start: date | None = None
    expected_eggs: int | None = Field(None, ge=0)
    notes: str | None = None


class ClutchResponse(TimestampedSchema):
    farm_id: UUID
    pair_id: UUID | None
    name: str | None
    laid_start: date | None
    expected_eggs: int | None
    notes: str | None
    egg_count: int = 0


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    method: str = Field("artificial")
    species_id: UUID | None = None
    incubator_label: str | None = Field(None, max_length=150)
    set_on: date | None = None
    incubation_days: int | None = Field(None, ge=1, le=400)
    target_temperature_c: Decimal | None = None
    target_humidity_pct: Decimal | None = Field(None, ge=0, le=100)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", avi.INCUBATION_METHOD_VALUES))


class BatchResponse(TimestampedSchema):
    farm_id: UUID
    species_id: UUID | None
    name: str
    method: str
    incubator_label: str | None
    set_on: date | None
    incubation_days: int | None
    target_temperature_c: Decimal | None
    target_humidity_pct: Decimal | None
    expected_lockdown_on: date | None
    expected_hatch_on: date | None
    turning_schedule: dict
    status: str
    notes: str | None
    egg_count: int = 0
    progress: dict | None = None


class BatchDetailResponse(BatchResponse):
    schedule: dict | None = None
    statistics: dict | None = None


# ── Egg ───────────────────────────────────────────────────────────────────────

class EggCreate(AGRIOSSchema):
    clutch_id: UUID | None = None
    pair_id: UUID | None = None
    species_id: UUID | None = None
    identifier: str | None = Field(None, max_length=50)
    laid_on: date | None = None
    weight_grams: Decimal | None = None
    length_mm: Decimal | None = None
    width_mm: Decimal | None = None
    quality: str = Field("good")
    source: str = Field("natural")
    storage_location: str | None = Field(None, max_length=150)
    notes: str | None = None

    _q = field_validator("quality")(_one_of("quality", avi.EGG_QUALITY_VALUES))
    _s = field_validator("source")(_one_of("source", avi.EGG_SOURCE_VALUES))


class EggUpdate(AGRIOSSchema):
    fertility_status: str | None = None
    quality: str | None = None
    weight_grams: Decimal | None = None
    storage_location: str | None = Field(None, max_length=150)
    notes: str | None = None

    _f = field_validator("fertility_status")(_one_of("fertility_status", avi.EGG_FERTILITY_VALUES))
    _q = field_validator("quality")(_one_of("quality", avi.EGG_QUALITY_VALUES))


class EggResponse(TimestampedSchema):
    farm_id: UUID
    clutch_id: UUID | None
    batch_id: UUID | None
    pair_id: UUID | None
    species_id: UUID | None
    identifier: str
    laid_on: date | None
    fertility_status: str
    weight_grams: Decimal | None
    length_mm: Decimal | None
    width_mm: Decimal | None
    quality: str
    storage_location: str | None
    source: str
    set_on: date | None
    status: str
    hatched_bird_id: UUID | None
    notes: str | None


class SetEggsRequest(AGRIOSSchema):
    egg_ids: list[UUID] = Field(..., min_length=1)
    set_on: date | None = None


# ── Logs / candling / hatch ───────────────────────────────────────────────────

class IncubationLogCreate(AGRIOSSchema):
    log_date: date | None = None
    temperature_c: Decimal | None = None
    humidity_pct: Decimal | None = Field(None, ge=0, le=100)
    turns_count: int | None = Field(None, ge=0)
    notes: str | None = None


class IncubationLogResponse(TimestampedSchema):
    batch_id: UUID
    log_date: date
    temperature_c: Decimal | None
    humidity_pct: Decimal | None
    turns_count: int | None
    notes: str | None


class CandlingCreate(AGRIOSSchema):
    result: str = Field("unclear")
    candled_on: date | None = None
    notes: str | None = None

    _r = field_validator("result")(_one_of("result", avi.CANDLING_RESULT_VALUES))


class CandlingResponse(TimestampedSchema):
    egg_id: UUID
    candled_on: date
    day_number: int | None
    result: str
    notes: str | None


class HatchCreate(AGRIOSSchema):
    outcome: str
    hatched_on: date | None = None
    assisted: bool = False
    hatch_weight_grams: Decimal | None = None
    failure_reason: str | None = Field(None, max_length=150)
    notes: str | None = None
    # When the outcome is a hatch, optionally create the chick as a real bird.
    create_chick: bool = True
    chick_name: str | None = Field(None, max_length=150)

    _o = field_validator("outcome")(_one_of("outcome", avi.HATCH_OUTCOME_VALUES))


class HatchResponse(TimestampedSchema):
    egg_id: UUID
    batch_id: UUID | None
    hatched_on: date | None
    outcome: str
    assisted: bool
    chick_bird_id: UUID | None
    hatch_weight_grams: Decimal | None
    failure_reason: str | None
    notes: str | None
