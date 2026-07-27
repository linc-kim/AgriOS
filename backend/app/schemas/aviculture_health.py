"""
Greena — Aviculture Health Schemas (Module 15, Part 6)

Contracts for individual-bird health records, quarantine, disease events and
analytics. Differential diagnoses are carried inside ``details`` and always
returned with a disclaimer stamped by the service — veterinary guidance, never a
definitive diagnosis (Doc 04 §7, Doc 06/Part 6 spec).
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Health records ────────────────────────────────────────────────────────────

class HealthRecordCreate(AGRIOSSchema):
    record_type: str = Field("observation")
    recorded_on: date | None = None
    title: str | None = Field(None, max_length=255)
    summary: str | None = None
    weight_grams: Decimal | None = Field(None, ge=0)
    body_condition: str | None = Field(None, max_length=30)
    status: str = Field("recorded")
    severity: str | None = None
    next_due_on: date | None = None
    details: dict = Field(default_factory=dict)

    _t = field_validator("record_type")(_one_of("record_type", avi.HEALTH_RECORD_TYPE_VALUES))
    _s = field_validator("status")(_one_of("status", avi.HEALTH_RECORD_STATUS_VALUES))
    _sev = field_validator("severity")(_one_of("severity", avi.HEALTH_SEVERITY_VALUES))


class HealthRecordUpdate(AGRIOSSchema):
    status: str | None = None
    severity: str | None = None
    next_due_on: date | None = None
    summary: str | None = None

    _s = field_validator("status")(_one_of("status", avi.HEALTH_RECORD_STATUS_VALUES))
    _sev = field_validator("severity")(_one_of("severity", avi.HEALTH_SEVERITY_VALUES))


class HealthRecordResponse(TimestampedSchema):
    bird_id: UUID
    record_type: str
    recorded_on: date
    title: str | None
    summary: str | None
    weight_grams: Decimal | None
    body_condition: str | None
    status: str
    severity: str | None
    next_due_on: date | None
    details: dict


# ── Quarantine ────────────────────────────────────────────────────────────────

class QuarantineStart(AGRIOSSchema):
    reason: str | None = Field(None, max_length=255)
    aviary_id: UUID | None = None
    started_on: date | None = None
    expected_end_on: date | None = None
    notes: str | None = None


class QuarantineEnd(AGRIOSSchema):
    ended_on: date | None = None
    outcome: str | None = Field(None, max_length=255)


class QuarantineResponse(TimestampedSchema):
    farm_id: UUID
    bird_id: UUID
    aviary_id: UUID | None
    reason: str | None
    started_on: date
    expected_end_on: date | None
    ended_on: date | None
    status: str
    outcome: str | None
    notes: str | None


# ── Disease events ────────────────────────────────────────────────────────────

class DiseaseEventCreate(AGRIOSSchema):
    disease_name: str = Field(..., min_length=1, max_length=200)
    aviary_id: UUID | None = None
    status: str = Field("suspected")
    started_on: date | None = None
    affected_count: int = Field(0, ge=0)
    is_notifiable: bool = False
    notes: str | None = None

    _s = field_validator("status")(_one_of("status", avi.DISEASE_EVENT_STATUS_VALUES))


class DiseaseEventUpdate(AGRIOSSchema):
    status: str | None = None
    resolved_on: date | None = None
    affected_count: int | None = Field(None, ge=0)
    notes: str | None = None

    _s = field_validator("status")(_one_of("status", avi.DISEASE_EVENT_STATUS_VALUES))


class DiseaseEventResponse(TimestampedSchema):
    farm_id: UUID
    aviary_id: UUID | None
    disease_name: str
    status: str
    started_on: date
    resolved_on: date | None
    affected_count: int
    is_notifiable: bool
    notes: str | None


# ── Analytics ─────────────────────────────────────────────────────────────────

class WeightTrendResponse(AGRIOSSchema):
    bird_id: UUID
    trend: dict


class HealthSummaryResponse(AGRIOSSchema):
    records_total: dict
    records_by_type: dict
    active_birds: dict
    mortality_rate_pct: dict
    vaccination_coverage_pct: dict
    active_quarantines: dict
    active_disease_events: dict
    preventive_due: dict
