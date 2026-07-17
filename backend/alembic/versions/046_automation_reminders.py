"""Migration 046 — automation rules, reminders + notification priority/archive

Module 8 (Automation & Notifications).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend notifications for the Activity Center.
    op.add_column("notifications", sa.Column("priority", sa.String(20), nullable=False, server_default="normal"))
    op.add_column("notifications", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("notifications", sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True))

    op.create_table(
        "automation_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(40), nullable=False, index=True),
        sa.Column("conditions", JSONB, nullable=False, server_default="{}"),
        sa.Column("actions", JSONB, nullable=False, server_default="[]"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    op.create_table(
        "reminders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("due_at", sa.TIMESTAMP(timezone=True), nullable=False, index=True),
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="none"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("done_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_fired_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("next_fire_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("automation_rules")
    op.drop_column("notifications", "archived_at")
    op.drop_column("notifications", "is_archived")
    op.drop_column("notifications", "priority")
