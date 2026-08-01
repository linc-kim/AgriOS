"""
Greena — Operations Planner Schemas (Platform Module 5).

Request/response contracts for the canonical, cross-module Operations Planner.
Routines, SOPs, checklists, schedules and shifts are structured domain objects
(never free-form AI text). Enumerated fields validate against the value tuples on
the models. Deterministic-engine outputs (schedules, conflicts, workload,
recommendations) are returned as honesty-labelled dicts (recorded_fact |
calculated | forecast | strategic_recommendation | ai_suggestion | unknown |
unavailable) — see ``app.services.ops_common``.
"""

from datetime import date, time
from uuid import UUID

from pydantic import Field, field_validator

from app.models import ops_planner as m
from app.schemas.base import AGRIOSSchema, TimestampedSchema


def _one_of(field_name: str, allowed: tuple[str, ...]):
    def _check(value):
        if value is None:
            return value
        if value not in allowed:
            raise ValueError(f"{field_name} must be one of {allowed}, got {value!r}")
        return value
    return _check


# ── Operations Manual ─────────────────────────────────────────────────────────

class ManualUpdate(AGRIOSSchema):
    title: str | None = Field(None, min_length=1, max_length=200)
    status: str | None = None
    review_interval_days: int | None = Field(None, ge=1)
    effective_date: date | None = None
    reason: str | None = Field(None, description="Recorded on the immutable revision.")

    _st = field_validator("status")(_one_of("status", m.OPS_MANUAL_STATUS_VALUES))


class ManualResponse(TimestampedSchema):
    farm_id: UUID
    title: str
    version: int
    status: str
    approval_status: str
    effective_date: date | None
    review_interval_days: int | None
    sections: dict
    current_revision: int


class ManualRevisionResponse(TimestampedSchema):
    manual_id: UUID
    revision_number: int
    reason: str | None
    trigger: str
    snapshot: dict


# ── SOPs ──────────────────────────────────────────────────────────────────────

class SOPInput(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    module: str | None = Field(None, max_length=40)
    category: str = Field("administration", max_length=40)
    purpose: str | None = None
    scope: str | None = None
    required_equipment: list = Field(default_factory=list)
    safety_notes: str | None = None
    steps: list = Field(default_factory=list)
    verification_steps: list = Field(default_factory=list)
    expected_outcome: str | None = None
    completion_criteria: str | None = None

    _cat = field_validator("category")(_one_of("category", m.OPS_ROUTINE_CATEGORY_VALUES))


class SOPResponse(TimestampedSchema):
    farm_id: UUID
    module: str | None
    name: str
    category: str
    purpose: str | None
    scope: str | None
    required_equipment: list
    safety_notes: str | None
    steps: list
    verification_steps: list
    expected_outcome: str | None
    completion_criteria: str | None
    version: int
    approval_status: str
    revision_history: list


# ── Checklists ────────────────────────────────────────────────────────────────

class ChecklistItemInput(AGRIOSSchema):
    description: str = Field(..., min_length=1)
    sequence: int = Field(0, ge=0)
    is_required: bool = True
    completion_method: str | None = Field(None, max_length=40)
    media_requirement: str | None = None
    verification_required: bool = False
    notes: str | None = None

    _mr = field_validator("media_requirement")(_one_of("media_requirement", m.OPS_MEDIA_REQUIREMENT_VALUES))


class ChecklistInput(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    routine_id: UUID | None = None
    sop_id: UUID | None = None
    estimated_duration_minutes: int | None = Field(None, ge=0)
    completion_requirements: dict = Field(default_factory=dict)
    items: list[ChecklistItemInput] = Field(default_factory=list)


class ChecklistItemResponse(TimestampedSchema):
    checklist_id: UUID
    sequence: int
    description: str
    is_required: bool
    completion_method: str | None
    media_requirement: str | None
    verification_required: bool
    notes: str | None


class ChecklistResponse(TimestampedSchema):
    farm_id: UUID
    routine_id: UUID | None
    sop_id: UUID | None
    name: str
    description: str | None
    estimated_duration_minutes: int | None
    completion_requirements: dict
    items: list[ChecklistItemResponse] = Field(default_factory=list)


# ── Schedule / recurrence ─────────────────────────────────────────────────────

class ScheduleInput(AGRIOSSchema):
    frequency: str = "daily"
    interval: int = Field(1, ge=1)
    byday: list = Field(default_factory=list)
    bymonthday: list = Field(default_factory=list)
    time_windows: list = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    exceptions: list = Field(default_factory=list)
    dependencies: list = Field(default_factory=list)
    rrule: str | None = Field(None, max_length=255)

    _fq = field_validator("frequency")(_one_of("frequency", m.OPS_FREQUENCY_VALUES))


class ScheduleResponse(TimestampedSchema):
    routine_id: UUID
    farm_id: UUID
    frequency: str
    interval: int
    byday: list
    bymonthday: list
    time_windows: list
    start_date: date | None
    end_date: date | None
    exceptions: list
    dependencies: list
    rrule: str | None
    is_active: bool


# ── Task templates ────────────────────────────────────────────────────────────

class TaskTemplateInput(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    sequence: int = Field(0, ge=0)
    description: str | None = None
    default_duration_minutes: int | None = Field(None, ge=0)
    required_role: str | None = Field(None, max_length=40)
    required_skills: list = Field(default_factory=list)
    required_equipment: list = Field(default_factory=list)
    priority: str = "normal"
    completion_criteria: str | None = None
    depends_on: list = Field(default_factory=list)

    _pr = field_validator("priority")(_one_of("priority", m.OPS_PRIORITY_VALUES))


class TaskTemplateResponse(TimestampedSchema):
    routine_id: UUID
    sequence: int
    name: str
    description: str | None
    default_duration_minutes: int | None
    required_role: str | None
    required_skills: list
    required_equipment: list
    priority: str
    completion_criteria: str | None
    depends_on: list


# ── Routine ───────────────────────────────────────────────────────────────────

class RoutineCreate(AGRIOSSchema):
    module: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str = "administration"
    frequency: str = "daily"
    priority: str = "normal"
    estimated_duration_minutes: int | None = Field(None, ge=0)
    required_skills: list = Field(default_factory=list)
    required_equipment: list = Field(default_factory=list)
    assigned_shift_id: UUID | None = None
    assigned_team: str | None = Field(None, max_length=120)
    requires_approval: bool = False
    schedule: ScheduleInput | None = None
    task_templates: list[TaskTemplateInput] = Field(default_factory=list)

    _cat = field_validator("category")(_one_of("category", m.OPS_ROUTINE_CATEGORY_VALUES))
    _fq = field_validator("frequency")(_one_of("frequency", m.OPS_FREQUENCY_VALUES))
    _pr = field_validator("priority")(_one_of("priority", m.OPS_PRIORITY_VALUES))


class RoutineUpdate(AGRIOSSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    frequency: str | None = None
    priority: str | None = None
    status: str | None = None
    estimated_duration_minutes: int | None = Field(None, ge=0)
    required_skills: list | None = None
    required_equipment: list | None = None
    assigned_shift_id: UUID | None = None
    assigned_team: str | None = Field(None, max_length=120)
    requires_approval: bool | None = None
    schedule: ScheduleInput | None = None
    task_templates: list[TaskTemplateInput] | None = None
    change_summary: str | None = Field(None, description="Recorded on the immutable routine version.")
    reason: str | None = None

    _cat = field_validator("category")(_one_of("category", m.OPS_ROUTINE_CATEGORY_VALUES))
    _fq = field_validator("frequency")(_one_of("frequency", m.OPS_FREQUENCY_VALUES))
    _pr = field_validator("priority")(_one_of("priority", m.OPS_PRIORITY_VALUES))
    _st = field_validator("status")(_one_of("status", m.OPS_ROUTINE_STATUS_VALUES))


class RoutineResponse(TimestampedSchema):
    farm_id: UUID
    module: str
    manual_id: UUID | None
    name: str
    description: str | None
    category: str
    frequency: str
    priority: str
    status: str
    is_active: bool
    estimated_duration_minutes: int | None
    required_skills: list
    required_equipment: list
    assigned_shift_id: UUID | None
    assigned_team: str | None
    requires_approval: bool
    current_version: int
    source_template_id: UUID | None


class RoutineDetailResponse(RoutineResponse):
    schedule: ScheduleResponse | None = None
    task_templates: list[TaskTemplateResponse] = Field(default_factory=list)


class RoutineVersionResponse(TimestampedSchema):
    routine_id: UUID
    version_number: int
    author_id: UUID | None
    approval_status: str
    effective_date: date | None
    change_summary: str | None
    reason: str | None
    previous_version: int | None
    snapshot: dict


# ── Shift ─────────────────────────────────────────────────────────────────────

class ShiftInput(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=120)
    shift_type: str = "morning"
    start_time: time | None = None
    end_time: time | None = None
    breaks: list = Field(default_factory=list)
    days_of_week: list = Field(default_factory=list)
    supervisor_id: UUID | None = None
    capacity: int | None = Field(None, ge=0)

    _st = field_validator("shift_type")(_one_of("shift_type", m.OPS_SHIFT_TYPE_VALUES))


class ShiftResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    shift_type: str
    start_time: time | None
    end_time: time | None
    breaks: list
    days_of_week: list
    supervisor_id: UUID | None
    capacity: int | None


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentInput(AGRIOSSchema):
    routine_id: UUID
    target_type: str = "worker"
    worker_id: UUID | None = None
    team: str | None = Field(None, max_length=120)
    shift_id: UUID | None = None
    schedule: dict = Field(default_factory=dict)
    rotation: dict = Field(default_factory=dict)
    supervisor_id: UUID | None = None

    _tt = field_validator("target_type")(_one_of("target_type", m.OPS_ASSIGNMENT_TARGET_VALUES))


class AssignmentResponse(TimestampedSchema):
    farm_id: UUID
    routine_id: UUID
    target_type: str
    worker_id: UUID | None
    team: str | None
    shift_id: UUID | None
    schedule: dict
    rotation: dict
    supervisor_id: UUID | None
    status: str
    history: list


# ── Completion (execution record) ─────────────────────────────────────────────

class CompletionInput(AGRIOSSchema):
    routine_id: UUID
    occurrence_date: date
    worker_id: UUID | None = None
    status: str = "completed"
    duration_minutes: int | None = Field(None, ge=0)
    deviations: str | None = None
    notes: str | None = None
    attachments: list = Field(default_factory=list)
    checklist_results: dict = Field(default_factory=dict)
    verification: dict | None = None
    reminder_id: UUID | None = None

    _st = field_validator("status")(_one_of("status", m.OPS_COMPLETION_STATUS_VALUES))


class CompletionResponse(TimestampedSchema):
    farm_id: UUID
    routine_id: UUID
    occurrence_date: date
    worker_id: UUID | None
    status: str
    duration_minutes: int | None
    deviations: str | None
    notes: str | None
    attachments: list
    checklist_results: dict
    verification: dict | None
    supervisor_approved: bool | None
    supervisor_id: UUID | None
    reminder_id: UUID | None


# ── Exception ─────────────────────────────────────────────────────────────────

class ExceptionInput(AGRIOSSchema):
    routine_id: UUID | None = None
    cause: str
    impact: str | None = None
    temporary_adjustments: dict = Field(default_factory=dict)
    resolution: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    _c = field_validator("cause")(_one_of("cause", m.OPS_EXCEPTION_CAUSE_VALUES))


class ExceptionResponse(TimestampedSchema):
    farm_id: UUID
    routine_id: UUID | None
    cause: str
    impact: str | None
    temporary_adjustments: dict
    resolution: str | None
    start_date: date | None
    end_date: date | None
    status: str


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateResponse(TimestampedSchema):
    farm_id: UUID | None
    module: str
    name: str
    description: str | None
    enterprise_type: str | None
    category: str
    default_schedule: dict
    default_sops: list
    default_checklists: list
    default_task_templates: list
    estimated_labor: dict
    estimated_time_minutes: int | None
    is_builtin: bool


class ApplyTemplateInput(AGRIOSSchema):
    template_id: UUID
    module: str | None = Field(None, description="Override the template's module for this farm.")
    activate: bool = False


# ── Recommendation ────────────────────────────────────────────────────────────

class RecommendationResponse(TimestampedSchema):
    farm_id: UUID
    module: str | None
    routine_id: UUID | None
    title: str
    recommendation: str
    evidence: dict
    supporting_metrics: dict
    expected_benefit: str | None
    confidence: str
    priority: str
    approval_status: str
    implementation_status: str


class RecommendationDecision(AGRIOSSchema):
    approval_status: str

    _st = field_validator("approval_status")(_one_of("approval_status", m.OPS_RECOMMENDATION_STATUS_VALUES))
