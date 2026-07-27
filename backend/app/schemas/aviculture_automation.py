"""
Greena — Aviculture Automation Schemas (Module 15, Part 9)

Contracts for the deterministic automation preview, materialised tasks (which are
platform Reminders tagged aviculture), and staged workflows. The engine's items
are honesty-labelled recorded-fact derivations (Priority/Reason/Evidence/Due).
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


def _task_response(r) -> "TaskResponse":
    """Build a TaskResponse from a Reminder ORM row, reading the JSONB column
    ``metadata_`` explicitly (``reminder.metadata`` is SQLAlchemy's MetaData)."""
    return TaskResponse(
        id=r.id, created_at=r.created_at, updated_at=r.updated_at, farm_id=r.farm_id,
        title=r.title, notes=r.notes, due_at=r.due_at, priority=r.priority,
        is_done=r.is_done, metadata=r.metadata_ or {})


class OperationalItem(AGRIOSSchema):
    kind: str
    title: str
    priority: str
    reason: str
    evidence: dict
    suggested_due_on: str | None
    dedup_key: str


class GenerateResult(AGRIOSSchema):
    created: int
    skipped: int
    notified: int
    evaluated: int


class TaskResponse(TimestampedSchema):
    farm_id: UUID
    title: str
    notes: str | None
    due_at: datetime
    priority: str
    is_done: bool
    # Populated explicitly from Reminder.metadata_ (see _task_response) — never via
    # model_validate, because reminder.metadata is SQLAlchemy's MetaData object.
    metadata: dict


# ── Workflows ─────────────────────────────────────────────────────────────────

class WorkflowStart(AGRIOSSchema):
    workflow_type: str
    bird_id: UUID | None = None
    notes: str | None = None

    _t = field_validator("workflow_type")(_one_of("workflow_type", avi.WORKFLOW_TYPE_VALUES))


class WorkflowAdvance(AGRIOSSchema):
    note: str | None = None


class WorkflowResponse(TimestampedSchema):
    farm_id: UUID
    bird_id: UUID | None
    workflow_type: str
    current_stage: str
    status: str
    started_on: date
    completed_on: date | None
    notes: str | None
    stages: list[str] = Field(default_factory=list)


class WorkflowEventResponse(TimestampedSchema):
    workflow_id: UUID
    from_stage: str | None
    to_stage: str
    occurred_on: date
    note: str | None
