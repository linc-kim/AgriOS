"""
Greena — Aviculture Breeding Schemas (Module 15, Part 4)

Contracts for pairs, breeding programmes, pedigrees, compatibility and
relatedness. Genetic figures returned here are always honesty-labelled by the
pure pedigree engine — the schemas simply carry them.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Pairs ─────────────────────────────────────────────────────────────────────

class PairCreate(AGRIOSSchema):
    male_bird_id: UUID | None = None
    female_bird_id: UUID | None = None
    name: str | None = Field(None, max_length=200)
    purpose: str | None = None
    formation_type: str = Field("natural")
    formed_on: date | None = None
    program_id: UUID | None = None
    notes: str | None = None

    _ft = field_validator("formation_type")(_one_of("formation_type", avi.PAIR_FORMATION_TYPE_VALUES))


class PairDissolve(AGRIOSSchema):
    dissolved_on: date | None = None
    reason: str | None = None


class PairResponse(TimestampedSchema):
    farm_id: UUID
    male_bird_id: UUID | None
    female_bird_id: UUID | None
    name: str | None
    purpose: str | None
    formation_type: str
    formed_on: date | None
    status: str
    dissolved_on: date | None
    dissolution_reason: str | None
    program_id: UUID | None
    notes: str | None
    # Denormalised display + live compatibility (labelled).
    male_name: str | None = None
    female_name: str | None = None
    compatibility: dict | None = None


# ── Breeding programmes ───────────────────────────────────────────────────────

class ProgramCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    species_id: UUID | None = None
    objective: str | None = None
    strategy: str = Field("outcross")
    target_traits: list[str] = Field(default_factory=list)
    notes: str | None = None

    _st = field_validator("strategy")(_one_of("strategy", avi.BREEDING_STRATEGY_VALUES))


class ProgramUpdate(AGRIOSSchema):
    name: str | None = Field(None, max_length=200)
    objective: str | None = None
    strategy: str | None = None
    target_traits: list[str] | None = None
    status: str | None = None
    notes: str | None = None

    _st = field_validator("strategy")(_one_of("strategy", avi.BREEDING_STRATEGY_VALUES))
    _ss = field_validator("status")(_one_of("status", avi.BREEDING_PROGRAM_STATUS_VALUES))


class ProgramResponse(TimestampedSchema):
    farm_id: UUID
    species_id: UUID | None
    name: str
    objective: str | None
    strategy: str
    target_traits: list
    status: str
    notes: str | None
    pair_count: int = 0


class GoalCreate(AGRIOSSchema):
    description: str = Field(..., min_length=1, max_length=500)
    target_metric: str | None = Field(None, max_length=100)
    target_value: Decimal | None = None


class GoalResponse(TimestampedSchema):
    program_id: UUID
    description: str
    target_metric: str | None
    target_value: Decimal | None
    status: str


# ── Compatibility / pedigree / relatedness ────────────────────────────────────

class CompatibilityRequest(AGRIOSSchema):
    male_bird_id: UUID
    female_bird_id: UUID


class CompatibilityResponse(AGRIOSSchema):
    compatible: bool
    blocking: bool
    risk_level: str
    relationship_coefficient: dict
    offspring_inbreeding: dict
    warnings: list[dict]
    confidence: str
    limitations: list[str]


class PedigreeResponse(AGRIOSSchema):
    bird_id: UUID
    ancestry: dict
    inbreeding_coefficient: dict
    founders: list[str]
    generations: int


class RelatednessResponse(AGRIOSSchema):
    bird_a: UUID
    bird_b: UUID
    relationship_coefficient: dict


class OffspringResponse(AGRIOSSchema):
    bird_id: UUID
    offspring: list[dict]
    performance: dict


class PairEventResponse(TimestampedSchema):
    pair_id: UUID
    event_type: str
    occurred_on: date
    title: str
    description: str | None
    data: dict
