"""Migration 048 — admin platform: org suspend, feature flags, system config, jobs

Module 10 (Admin Platform).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def _base():
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.add_column("organizations", sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default="false"))

    op.create_table(
        "feature_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("flag_key", sa.String(60), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("flag_key", "organization_id", name="uq_feature_flag_key_org"),
    )

    op.create_table(
        "system_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_only_mode", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("banner_message", sa.Text(), nullable=True),
        sa.Column("maintenance_scheduled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ai_provider_priority", JSONB, nullable=False, server_default='["gemini", "claude", "offline"]'),
        sa.Column("email_sender", sa.String(200), nullable=False, server_default="noreply@greena.app"),
        sa.Column("sms_sender", sa.String(50), nullable=False, server_default="GREENA"),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("default_timezone", sa.String(50), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("data_retention_days", sa.Integer(), nullable=False, server_default="3650"),
        sa.Column("limits", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "background_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("queue", sa.String(60), nullable=False, server_default="default"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", JSONB, nullable=False, server_default="{}"),
        sa.Column("triggered_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("background_jobs")
    op.drop_table("system_config")
    op.drop_table("feature_flags")
    op.drop_column("organizations", "is_suspended")
