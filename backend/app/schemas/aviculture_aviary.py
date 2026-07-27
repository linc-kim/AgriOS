"""
Greena — Aviculture Aviary Schemas (Module 15, Part 3)

Request/response contracts for aviary management. Enumerated fields validate
against the model value tuples so API and DB share one source of truth.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Aviary ────────────────────────────────────────────────────────────────────

class AviaryCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(None, max_length=50)
    aviary_type: str = Field("mixed")
    building: str | None = Field(None, max_length=150)
    purpose: str = Field("general")
    biosecurity_level: str = Field("standard")
    capacity: int | None = Field(None, ge=0)
    dimensions: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)
    status: str = Field("active")
    notes: str | None = None

    _t = field_validator("aviary_type")(_one_of("aviary_type", avi.AVIARY_TYPE_VALUES))
    _p = field_validator("purpose")(_one_of("purpose", avi.AVIARY_PURPOSE_VALUES))
    _b = field_validator("biosecurity_level")(_one_of("biosecurity_level", avi.AVIARY_BIOSECURITY_VALUES))
    _s = field_validator("status")(_one_of("status", avi.AVIARY_STATUS_VALUES))


class AviaryUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=200)
    code: str | None = Field(None, max_length=50)
    aviary_type: str | None = None
    building: str | None = Field(None, max_length=150)
    purpose: str | None = None
    biosecurity_level: str | None = None
    capacity: int | None = Field(None, ge=0)
    dimensions: dict | None = None
    environment: dict | None = None
    status: str | None = None
    notes: str | None = None

    _t = field_validator("aviary_type")(_one_of("aviary_type", avi.AVIARY_TYPE_VALUES))
    _p = field_validator("purpose")(_one_of("purpose", avi.AVIARY_PURPOSE_VALUES))
    _b = field_validator("biosecurity_level")(_one_of("biosecurity_level", avi.AVIARY_BIOSECURITY_VALUES))
    _s = field_validator("status")(_one_of("status", avi.AVIARY_STATUS_VALUES))


class AviaryResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    code: str | None
    aviary_type: str
    building: str | None
    purpose: str
    biosecurity_level: str
    capacity: int | None
    dimensions: dict
    environment: dict
    status: str
    notes: str | None
    # Computed by the pure engine (labelled).
    occupancy: dict | None = None


class AviaryDetailResponse(AviaryResponse):
    environment_summary: dict | None = None
    cleaning: dict | None = None
    housing_assessment: dict | None = None
    zone_count: int = 0
    fixture_count: int = 0


# ── Zones ─────────────────────────────────────────────────────────────────────

class ZoneCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=150)
    zone_type: str = Field("zone")
    capacity: int | None = Field(None, ge=0)
    notes: str | None = None

    _zt = field_validator("zone_type")(_one_of("zone_type", avi.AVIARY_ZONE_TYPE_VALUES))


class ZoneResponse(TimestampedSchema):
    aviary_id: UUID
    name: str
    zone_type: str
    capacity: int | None
    notes: str | None


# ── Fixtures ──────────────────────────────────────────────────────────────────

class FixtureCreate(AGRIOSSchema):
    fixture_type: str
    zone_id: UUID | None = None
    label: str | None = Field(None, max_length=150)
    quantity: int = Field(1, ge=1)
    status: str = Field("active")
    details: dict = Field(default_factory=dict)

    _ft = field_validator("fixture_type")(_one_of("fixture_type", avi.FIXTURE_TYPE_VALUES))
    _fs = field_validator("status")(_one_of("status", avi.FIXTURE_STATUS_VALUES))


class FixtureResponse(TimestampedSchema):
    aviary_id: UUID
    zone_id: UUID | None
    fixture_type: str
    label: str | None
    quantity: int
    status: str
    details: dict


# ── Environmental readings ────────────────────────────────────────────────────

class EnvironmentalReadingCreate(AGRIOSSchema):
    temperature_c: Decimal | None = None
    humidity_pct: Decimal | None = Field(None, ge=0, le=100)
    light_hours: Decimal | None = Field(None, ge=0, le=24)
    air_quality: str | None = Field(None, max_length=50)
    noise_level: str | None = Field(None, max_length=50)
    recorded_at: datetime | None = None
    notes: str | None = None


class EnvironmentalReadingResponse(TimestampedSchema):
    aviary_id: UUID
    recorded_at: datetime
    temperature_c: Decimal | None
    humidity_pct: Decimal | None
    light_hours: Decimal | None
    air_quality: str | None
    noise_level: str | None
    notes: str | None


# ── Tasks (cleaning / maintenance) ────────────────────────────────────────────

class TaskCreate(AGRIOSSchema):
    task_type: str
    title: str = Field(..., min_length=1, max_length=255)
    scheduled_for: date | None = None
    recurrence: str = Field("none")
    notes: str | None = None

    _tt = field_validator("task_type")(_one_of("task_type", avi.AVIARY_TASK_TYPE_VALUES))
    _rc = field_validator("recurrence")(_one_of("recurrence", avi.AVIARY_TASK_RECURRENCE_VALUES))


class TaskComplete(AGRIOSSchema):
    completed_on: date | None = None
    notes: str | None = None


class TaskResponse(TimestampedSchema):
    aviary_id: UUID
    task_type: str
    title: str
    status: str
    scheduled_for: date | None
    completed_on: date | None
    recurrence: str
    notes: str | None


# ── Timeline & media ──────────────────────────────────────────────────────────

class AviaryEventResponse(TimestampedSchema):
    aviary_id: UUID
    event_type: str
    occurred_on: date
    title: str
    description: str | None
    data: dict


class AviaryMediaCreate(AGRIOSSchema):
    media_type: str = Field("photo")
    url: str = Field(..., max_length=1000)
    caption: str | None = None
    is_primary: bool = False

    _mt = field_validator("media_type")(_one_of("media_type", avi.MEDIA_TYPE_VALUES))


class AviaryMediaResponse(TimestampedSchema):
    aviary_id: UUID
    media_type: str
    url: str | None
    caption: str | None
    is_primary: bool


# ── Infrastructure summary (for Mission Control / ARIA to read) ───────────────

class InfrastructureSummary(AGRIOSSchema):
    aviary_count: int
    total_capacity: dict
    total_occupied: dict
    available: dict
    by_purpose: dict
    quarantine_aviaries: int
