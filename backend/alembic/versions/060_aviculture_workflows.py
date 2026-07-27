"""Migration 060 — Aviculture Workflows (Module 15, Part 9)

Part 9 (Automation) is REUSE-first (Doc 11, Doc 13 Part 9, Doc 14 §1):
  * Reminders/tasks materialise into the existing platform ``reminders`` table
    (tagged ``metadata.module='aviculture'``); the scheduler's ``run_reminders``
    already fires them into the platform Notification engine. No aviculture
    reminder or notification table.
  * The deterministic "what is due" logic lives in a pure engine.

The one concept the platform has no engine for is a **staged workflow** with
history (Doc 11 §8 — New Bird Intake, Quarantine, Incubation Cycle, Sale
Process…). That gets two small tables; stage templates and transitions are
deterministic (in the pure engine), never stored as a source of truth.

Tables:
  avi_workflow        — a staged process on a bird / entity
  avi_workflow_event  — append-only stage-transition history
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.create_table(
        "avi_workflow",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("bird_id", UUID(as_uuid=True), sa.ForeignKey("avi_bird.id", ondelete="CASCADE"),
                  nullable=True, index=True),
        sa.Column("workflow_type", sa.String(30), nullable=False,
                  comment="intake | quarantine | treatment | incubation | sale | purchase | transfer | exhibition"),
        sa.Column("current_stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | completed | cancelled"),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("responsible_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_workflow_status", "avi_workflow", ["farm_id", "status"])

    op.create_table(
        "avi_workflow_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("avi_workflow.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("from_stage", sa.String(50), nullable=True),
        sa.Column("to_stage", sa.String(50), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("avi_workflow_event")
    op.drop_table("avi_workflow")
