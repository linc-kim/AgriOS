"""
Greena — Growth Planner Schemas (Platform, introduced by Module 16)

Request/response contracts for the canonical, cross-module Growth Planner. Goals
and milestones are structured domain objects (never free-form AI text). Enumerated
fields validate against the value tuples on the models.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import growth as m
from app.schemas.base import AGRIOSSchema, TimestampedSchema


def _one_of(field_name: str, allowed: tuple[str, ...]):
    def _check(value):
        if value is None:
            return value
        if value not in allowed:
            raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")
        return value
    return _check


# ── Inputs ────────────────────────────────────────────────────────────────────

class GoalInput(AGRIOSSchema):
    metric_key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=200)
    unit: str | None = Field(None, max_length=40)
    baseline_value: Decimal | None = None
    target_value: Decimal
    target_date: date | None = None
    is_primary: bool = False


class MilestoneInput(AGRIOSSchema):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    sequence: int = Field(0, ge=0)
    target_date: date | None = None
    target_metric_key: str | None = Field(None, max_length=80)
    target_metric_value: Decimal | None = None
    expected_impact: str | None = None
    dependencies: list = Field(default_factory=list)


class PlanCreate(AGRIOSSchema):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    is_primary: bool = False
    goals: list[GoalInput] = Field(default_factory=list)
    milestones: list[MilestoneInput] = Field(default_factory=list)


class PlanUpdate(AGRIOSSchema):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None
    reason: str | None = Field(None, description="Why this revision was made (recorded on the revision).")
    goals: list[GoalInput] | None = Field(None, description="When provided, replaces all goals (prior kept in history).")
    milestones: list[MilestoneInput] | None = Field(None, description="When provided, replaces all milestones.")

    _st = field_validator("status")(_one_of("status", m.GROWTH_PLAN_STATUS_VALUES))


class MilestoneStatusUpdate(AGRIOSSchema):
    status: str
    reason: str | None = None

    _st = field_validator("status")(_one_of("status", m.GROWTH_MILESTONE_STATUS_VALUES))


# ── Responses ─────────────────────────────────────────────────────────────────

class GoalResponse(TimestampedSchema):
    plan_id: UUID
    metric_key: str
    label: str
    unit: str | None
    baseline_value: Decimal | None
    target_value: Decimal
    target_date: date | None
    status: str
    is_primary: bool


class MilestoneResponse(TimestampedSchema):
    plan_id: UUID
    title: str
    description: str | None
    sequence: int
    target_date: date | None
    status: str
    target_metric_key: str | None
    target_metric_value: Decimal | None
    expected_impact: str | None
    dependencies: list


class PlanResponse(TimestampedSchema):
    farm_id: UUID
    module: str
    title: str
    description: str | None
    status: str
    is_primary: bool
    current_revision: int


class PlanDetailResponse(PlanResponse):
    goals: list[GoalResponse]
    milestones: list[MilestoneResponse]
    progress: dict


class RevisionResponse(TimestampedSchema):
    plan_id: UUID
    revision_number: int
    reason: str | None
    trigger: str
    snapshot: dict
