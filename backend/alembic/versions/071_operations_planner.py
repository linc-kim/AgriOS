"""Migration 071 — Operations Planner (Routine Engine) — Platform Module 5

The canonical, cross-module store for **recurring** farm operations: the living
Operations Manual, routines and their immutable version history, SOPs, checklists,
schedules (recurrence rules), task templates, shifts, assignments, execution
history, exceptions and improvement recommendations.

NOT enterprise-prefixed — a ``module`` discriminator ('poultry' | 'rabbit' | 'bsf'
| 'aviculture' | 'goat' | …) lets every Greena agricultural module share ONE
Operations Planner, exactly as the Growth Planner (Migration 065) shares one
planner. Farm-scoped; organisation isolation flows through ``farms.organization_id``.

Reuse-first (spec Doc 3 §24): generated recurring **task instances** are the
existing ``reminders`` rows (not a new table); automation reuses ``automation_rules``;
the operational calendar and operational metrics are **computed live** (like Mission
Control), never stored. Routine DEFINITIONS are kept separate from execution HISTORY
(spec Doc 3 §2); historical versions and completions are immutable.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def _pk() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _created_by() -> sa.Column:
    return sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def upgrade() -> None:
    # ── Operations Manual (aggregate root — one per farm) ─────────────────────
    op.create_table(
        "ops_manual",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft",
                  comment="draft | active | under_review | archived"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | approved | rejected"),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("review_interval_days", sa.Integer, nullable=True),
        sa.Column("sections", JSONB, nullable=False, server_default="{}",
                  comment="Living manual content by section (daily/weekly/…/emergency/SOPs/responsibilities)"),
        sa.Column("current_revision", sa.Integer, nullable=False, server_default="1"),
        _created_by(),
        *_base(),
        sa.UniqueConstraint("farm_id", name="uq_ops_manual_farm"),
    )

    op.create_table(
        "ops_manual_revision",
        _pk(),
        sa.Column("manual_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_manual.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("trigger", sa.String(40), nullable=False, server_default="manual",
                  comment="manual | routine_change | sop_change | milestone | adaptive"),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        _created_by(),
        *_base(),
        sa.UniqueConstraint("manual_id", "revision_number", name="uq_ops_manual_revision_number"),
    )

    # ── Routine templates (platform-provided; farm_id NULL = global) ──────────
    op.create_table(
        "ops_routine_template",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True,
                  comment="NULL = global platform template; non-NULL = farm-cloned template"),
        sa.Column("module", sa.String(40), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("enterprise_type", sa.String(80), nullable=True),
        sa.Column("category", sa.String(40), nullable=False, server_default="administration"),
        sa.Column("default_schedule", JSONB, nullable=False, server_default="{}"),
        sa.Column("default_sops", JSONB, nullable=False, server_default="[]"),
        sa.Column("default_checklists", JSONB, nullable=False, server_default="[]"),
        sa.Column("default_task_templates", JSONB, nullable=False, server_default="[]"),
        sa.Column("estimated_labor", JSONB, nullable=False, server_default="{}"),
        sa.Column("estimated_time_minutes", sa.Integer, nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="false"),
        _created_by(),
        *_base(),
    )

    # ── Shift definitions (genuinely new; no shift table exists) ──────────────
    op.create_table(
        "ops_shift",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("shift_type", sa.String(20), nullable=False, server_default="morning",
                  comment="morning | afternoon | night | split | weekend | holiday"),
        sa.Column("start_time", sa.Time, nullable=True),
        sa.Column("end_time", sa.Time, nullable=True),
        sa.Column("breaks", JSONB, nullable=False, server_default="[]"),
        sa.Column("days_of_week", JSONB, nullable=False, server_default="[]"),
        sa.Column("supervisor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=True),
        _created_by(),
        *_base(),
    )

    # ── SOPs (reusable across routines) ───────────────────────────────────────
    op.create_table(
        "ops_sop",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module", sa.String(40), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(40), nullable=False, server_default="administration"),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("required_equipment", JSONB, nullable=False, server_default="[]"),
        sa.Column("safety_notes", sa.Text, nullable=True),
        sa.Column("steps", JSONB, nullable=False, server_default="[]"),
        sa.Column("verification_steps", JSONB, nullable=False, server_default="[]"),
        sa.Column("expected_outcome", sa.Text, nullable=True),
        sa.Column("completion_criteria", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | approved | rejected"),
        sa.Column("revision_history", JSONB, nullable=False, server_default="[]"),
        _created_by(),
        *_base(),
    )

    # ── Routine (definition) ──────────────────────────────────────────────────
    op.create_table(
        "ops_routine",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module", sa.String(40), nullable=False, index=True,
                  comment="Owning enterprise/module: poultry | rabbit | bsf | aviculture | goat | …"),
        sa.Column("manual_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_manual.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(40), nullable=False, server_default="administration",
                  comment="feeding | health | breeding | cleaning | maintenance | biosecurity | production | "
                          "harvesting | financial | administration | training | compliance | safety | "
                          "environmental | equipment"),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="daily",
                  comment="hourly | daily | weekly | monthly | quarterly | semiannual | annual | seasonal | custom"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal",
                  comment="low | normal | high | critical"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft",
                  comment="draft | active | paused | archived"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=True),
        sa.Column("required_skills", JSONB, nullable=False, server_default="[]"),
        sa.Column("required_equipment", JSONB, nullable=False, server_default="[]"),
        sa.Column("assigned_shift_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_shift.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_team", sa.String(120), nullable=True),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("current_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("source_template_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine_template.id", ondelete="SET NULL"), nullable=True),
        _created_by(),
        *_base(),
    )
    op.create_index("ix_ops_routine_farm_module", "ops_routine", ["farm_id", "module"])

    op.create_table(
        "ops_routine_version",
        _pk(),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | approved | rejected"),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("previous_version", sa.Integer, nullable=True),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        _created_by(),
        *_base(),
        sa.UniqueConstraint("routine_id", "version_number", name="uq_ops_routine_version_number"),
    )

    # ── Schedule (recurrence rule bound to a routine) ─────────────────────────
    op.create_table(
        "ops_schedule",
        _pk(),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="daily"),
        sa.Column("interval", sa.Integer, nullable=False, server_default="1",
                  comment="Repeat every N frequency units (e.g. every 3 days → interval=3)"),
        sa.Column("byday", JSONB, nullable=False, server_default="[]",
                  comment='Weekday codes, e.g. ["MO","WE","FR"]'),
        sa.Column("bymonthday", JSONB, nullable=False, server_default="[]"),
        sa.Column("time_windows", JSONB, nullable=False, server_default="[]",
                  comment='Time-of-day windows, e.g. [{"start":"06:00","end":"08:00"}]'),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("exceptions", JSONB, nullable=False, server_default="[]",
                  comment="Excluded dates / suspensions"),
        sa.Column("dependencies", JSONB, nullable=False, server_default="[]",
                  comment="Routine/task ids this schedule depends on"),
        sa.Column("rrule", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        _created_by(),
        *_base(),
    )

    # ── Task templates (the tasks a routine materialises into reminders) ──────
    op.create_table(
        "ops_task_template",
        _pk(),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_duration_minutes", sa.Integer, nullable=True),
        sa.Column("required_role", sa.String(40), nullable=True),
        sa.Column("required_skills", JSONB, nullable=False, server_default="[]"),
        sa.Column("required_equipment", JSONB, nullable=False, server_default="[]"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("completion_criteria", sa.Text, nullable=True),
        sa.Column("depends_on", JSONB, nullable=False, server_default="[]"),
        _created_by(),
        *_base(),
    )

    # ── Checklists + items ────────────────────────────────────────────────────
    op.create_table(
        "ops_checklist",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sop_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_sop.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=True),
        sa.Column("completion_requirements", JSONB, nullable=False, server_default="{}"),
        _created_by(),
        *_base(),
    )

    op.create_table(
        "ops_checklist_item",
        _pk(),
        sa.Column("checklist_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_checklist.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("completion_method", sa.String(40), nullable=True),
        sa.Column("media_requirement", sa.String(40), nullable=True,
                  comment="photo | video | measurement | signature | observation | none"),
        sa.Column("verification_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text, nullable=True),
        _created_by(),
        *_base(),
    )

    # ── Assignment (routine ↔ worker/team/shift; history preserved) ───────────
    op.create_table(
        "ops_assignment",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_type", sa.String(20), nullable=False, server_default="worker",
                  comment="worker | team | department | supervisor | contractor"),
        sa.Column("worker_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("team", sa.String(120), nullable=True),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("ops_shift.id", ondelete="SET NULL"), nullable=True),
        sa.Column("schedule", JSONB, nullable=False, server_default="{}"),
        sa.Column("rotation", JSONB, nullable=False, server_default="{}"),
        sa.Column("supervisor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | completed | ended"),
        sa.Column("history", JSONB, nullable=False, server_default="[]"),
        _created_by(),
        *_base(),
    )

    # ── Completion (immutable execution history) ──────────────────────────────
    op.create_table(
        "ops_completion",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("occurrence_date", sa.Date, nullable=False),
        sa.Column("worker_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed",
                  comment="completed | partial | skipped | failed"),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("deviations", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("attachments", JSONB, nullable=False, server_default="[]"),
        sa.Column("checklist_results", JSONB, nullable=False, server_default="{}"),
        sa.Column("verification", JSONB, nullable=True),
        sa.Column("supervisor_approved", sa.Boolean, nullable=True),
        sa.Column("supervisor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), sa.ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True,
                  comment="The materialised task instance (reused reminders row), if any"),
        _created_by(),
        *_base(),
    )
    op.create_index("ix_ops_completion_routine_date", "ops_completion", ["routine_id", "occurrence_date"])

    # ── Exception (temporary deviation — never mutates the routine) ────────────
    op.create_table(
        "ops_exception",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("cause", sa.String(40), nullable=False,
                  comment="weather | disease | equipment_failure | staff_shortage | power_outage | "
                          "water_shortage | supply_shortage | emergency"),
        sa.Column("impact", sa.Text, nullable=True),
        sa.Column("temporary_adjustments", JSONB, nullable=False, server_default="{}"),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open",
                  comment="open | resolved"),
        _created_by(),
        *_base(),
    )

    # ── Improvement recommendation (Honesty Framework) ────────────────────────
    op.create_table(
        "ops_recommendation",
        _pk(),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module", sa.String(40), nullable=True, index=True),
        sa.Column("routine_id", UUID(as_uuid=True),
                  sa.ForeignKey("ops_routine.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("evidence", JSONB, nullable=False, server_default="{}"),
        sa.Column("supporting_metrics", JSONB, nullable=False, server_default="{}"),
        sa.Column("expected_benefit", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(20), nullable=False, server_default="medium",
                  comment="low | medium | high"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | approved | rejected | implemented"),
        sa.Column("implementation_status", sa.String(20), nullable=False, server_default="not_started",
                  comment="not_started | in_progress | done"),
        _created_by(),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("ops_recommendation")
    op.drop_table("ops_exception")
    op.drop_index("ix_ops_completion_routine_date", table_name="ops_completion")
    op.drop_table("ops_completion")
    op.drop_table("ops_assignment")
    op.drop_table("ops_checklist_item")
    op.drop_table("ops_checklist")
    op.drop_table("ops_task_template")
    op.drop_table("ops_schedule")
    op.drop_table("ops_routine_version")
    op.drop_index("ix_ops_routine_farm_module", table_name="ops_routine")
    op.drop_table("ops_routine")
    op.drop_table("ops_sop")
    op.drop_table("ops_shift")
    op.drop_table("ops_routine_template")
    op.drop_table("ops_manual_revision")
    op.drop_table("ops_manual")
