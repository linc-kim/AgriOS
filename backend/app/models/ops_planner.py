"""
Greena — Operations Planner (Routine Engine) Models — Platform Module 5.
Migration 071.

The **canonical, cross-module** store for recurring farm operations. NOT
enterprise-prefixed — a ``module`` discriminator ('poultry' | 'rabbit' | 'bsf' |
'aviculture' | 'goat' | …) lets every Greena agricultural module share ONE
Operations Planner, mirroring the Growth Planner (Module 16).

Design rules (spec Doc 3):
  * Routine **definitions** are separate from execution **history**.
  * Every routine mutation appends an immutable :class:`OpsRoutineVersion`; every
    manual mutation appends an immutable :class:`OpsManualRevision` — full version
    history, mirroring ``GrowthPlanRevision`` / ``MissionRevision``.
  * :class:`OpsCompletion` execution records are immutable.
  * Farm-scoped; organisation isolation flows through ``farms.organization_id``.
  * Recurring **task instances** reuse ``reminders``; automation reuses
    ``automation_rules``; the calendar & metrics are computed live — not stored.
  * Enumerated fields are validated at the schema/service layer against the value
    tuples defined here.
"""

import uuid
from datetime import date, time

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

# ── Enumerated value tuples (validated at schema/service layer) ───────────────
OPS_MANUAL_STATUS_VALUES = ("draft", "active", "under_review", "archived")
OPS_APPROVAL_STATUS_VALUES = ("pending", "approved", "rejected")
OPS_MANUAL_TRIGGER_VALUES = ("manual", "routine_change", "sop_change", "milestone", "adaptive")
OPS_ROUTINE_CATEGORY_VALUES = (
    "feeding", "health", "breeding", "cleaning", "maintenance", "biosecurity",
    "production", "harvesting", "financial", "administration", "training",
    "compliance", "safety", "environmental", "equipment",
)
OPS_FREQUENCY_VALUES = (
    "hourly", "daily", "weekly", "monthly", "quarterly", "semiannual", "annual",
    "seasonal", "custom",
)
OPS_PRIORITY_VALUES = ("low", "normal", "high", "critical")
OPS_ROUTINE_STATUS_VALUES = ("draft", "active", "paused", "archived")
OPS_SHIFT_TYPE_VALUES = ("morning", "afternoon", "night", "split", "weekend", "holiday")
OPS_ASSIGNMENT_TARGET_VALUES = ("worker", "team", "department", "supervisor", "contractor")
OPS_ASSIGNMENT_STATUS_VALUES = ("active", "completed", "ended")
OPS_COMPLETION_STATUS_VALUES = ("completed", "partial", "skipped", "failed")
OPS_EXCEPTION_CAUSE_VALUES = (
    "weather", "disease", "equipment_failure", "staff_shortage", "power_outage",
    "water_shortage", "supply_shortage", "emergency",
)
OPS_EXCEPTION_STATUS_VALUES = ("open", "resolved")
OPS_MEDIA_REQUIREMENT_VALUES = ("photo", "video", "measurement", "signature", "observation", "none")
OPS_CONFIDENCE_VALUES = ("low", "medium", "high")
OPS_RECOMMENDATION_STATUS_VALUES = ("pending", "approved", "rejected", "implemented")
OPS_IMPLEMENTATION_STATUS_VALUES = ("not_started", "in_progress", "done")


class OpsManual(AGRIOSBase):
    """A farm's living Operations Manual — parent container for all routines."""

    __tablename__ = "ops_manual"
    __table_args__ = (UniqueConstraint("farm_id", name="uq_ops_manual_farm"),)

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sections: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    revisions: Mapped[list["OpsManualRevision"]] = relationship(
        back_populates="manual", cascade="all, delete-orphan", lazy="noload")

    def __repr__(self) -> str:
        return f"<OpsManual farm={self.farm_id} v{self.version} status={self.status}>"


class OpsManualRevision(AGRIOSBase):
    """Immutable snapshot of an Operations Manual's full state (version history)."""

    __tablename__ = "ops_manual_revision"
    __table_args__ = (
        UniqueConstraint("manual_id", "revision_number", name="uq_ops_manual_revision_number"),
    )

    manual_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_manual.id", ondelete="CASCADE"), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    manual: Mapped["OpsManual"] = relationship(back_populates="revisions", lazy="noload")


class OpsRoutineTemplate(AGRIOSBase):
    """A reusable, enterprise-specific routine template. farm_id NULL = global platform template."""

    __tablename__ = "ops_routine_template"

    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enterprise_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="administration")
    default_schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    default_sops: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    default_checklists: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    default_task_templates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    estimated_labor: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    estimated_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<OpsRoutineTemplate '{self.name}' module={self.module} builtin={self.is_builtin}>"


class OpsShift(AGRIOSBase):
    """A shift definition (morning/afternoon/night/…). Integrates with workforce (farm_members)."""

    __tablename__ = "ops_shift"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    shift_type: Mapped[str] = mapped_column(String(20), nullable=False, default="morning")
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    breaks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    days_of_week: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OpsSOP(AGRIOSBase):
    """A Standard Operating Procedure, reusable across routines."""

    __tablename__ = "ops_sop"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    module: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="administration")
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_equipment: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    verification_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    revision_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<OpsSOP '{self.name}' v{self.version} status={self.approval_status}>"


class OpsRoutine(AGRIOSBase):
    """A recurring operational routine (definition). Aggregate root for a routine."""

    __tablename__ = "ops_routine"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    manual_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_manual.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="administration")
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_equipment: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assigned_shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_shift.id", ondelete="SET NULL"), nullable=True)
    assigned_team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine_template.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    versions: Mapped[list["OpsRoutineVersion"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", lazy="noload")
    schedules: Mapped[list["OpsSchedule"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", lazy="noload")
    task_templates: Mapped[list["OpsTaskTemplate"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", lazy="noload")

    def __repr__(self) -> str:
        return f"<OpsRoutine '{self.name}' module={self.module} freq={self.frequency} status={self.status}>"


class OpsRoutineVersion(AGRIOSBase):
    """Immutable snapshot of a routine's full state (version history)."""

    __tablename__ = "ops_routine_version"
    __table_args__ = (
        UniqueConstraint("routine_id", "version_number", name="uq_ops_routine_version_number"),
    )

    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    routine: Mapped["OpsRoutine"] = relationship(back_populates="versions", lazy="noload")


class OpsSchedule(AGRIOSBase):
    """A recurrence rule bound to a routine. The Recurrence/Scheduling engines read this."""

    __tablename__ = "ops_schedule"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="daily")
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    byday: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    bymonthday: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    time_windows: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exceptions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rrule: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    routine: Mapped["OpsRoutine"] = relationship(back_populates="schedules", lazy="noload")


class OpsTaskTemplate(AGRIOSBase):
    """A task a routine materialises into a reminder (task instance). Definition only."""

    __tablename__ = "ops_task_template"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    required_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    required_skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_equipment: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    depends_on: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    routine: Mapped["OpsRoutine"] = relationship(back_populates="task_templates", lazy="noload")


class OpsChecklist(AGRIOSBase):
    """A checklist attached to a routine and/or an SOP."""

    __tablename__ = "ops_checklist"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True)
    sop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_sop.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    items: Mapped[list["OpsChecklistItem"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan", lazy="noload")


class OpsChecklistItem(AGRIOSBase):
    """A single checklist item, optionally requiring media/verification."""

    __tablename__ = "ops_checklist_item"

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_checklist.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    completion_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    media_requirement: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verification_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    checklist: Mapped["OpsChecklist"] = relationship(back_populates="items", lazy="noload")


class OpsAssignment(AGRIOSBase):
    """A routine ↔ worker/team/shift assignment. History preserved in ``history`` JSONB."""

    __tablename__ = "ops_assignment"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False, default="worker")
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_shift.id", ondelete="SET NULL"), nullable=True)
    schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rotation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OpsCompletion(AGRIOSBase):
    """Immutable routine execution record. Links to the materialised reminder if any."""

    __tablename__ = "ops_completion"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True)
    occurrence_date: Mapped[date] = mapped_column(Date, nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deviations: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    checklist_results: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    verification: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    supervisor_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OpsException(AGRIOSBase):
    """A temporary deviation from a routine — never mutates the routine definition."""

    __tablename__ = "ops_exception"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True)
    cause: Mapped[str] = mapped_column(String(40), nullable=False)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporary_adjustments: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class OpsRecommendation(AGRIOSBase):
    """An improvement recommendation (advisory). Carries evidence per the Honesty Framework."""

    __tablename__ = "ops_recommendation"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    module: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    routine_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    supporting_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_benefit: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    implementation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<OpsRecommendation '{self.title}' confidence={self.confidence} status={self.approval_status}>"
