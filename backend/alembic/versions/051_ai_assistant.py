"""Migration 051 — AI assistant settings + uploaded documents

Module 13 Part 8 (ARIA as the AI Farm Assistant).

Two tables:
  * ai_settings   — per-farm AI configuration (enable/disable, model, temperature,
                    token limit, modality switches, monthly budget). One row per farm.
  * ai_documents  — uploaded documents whose text was extracted deterministically,
                    kept so ARIA can retrieve and cite them.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "051"
down_revision = "050"
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
    op.create_table(
        "ai_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default="true"),
        # gemini-flash | gemini-pro | offline
        sa.Column("model", sa.String(40), nullable=False, server_default="gemini-flash"),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False, server_default="0.30"),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("allow_vision", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("allow_documents", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("monthly_budget_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("updated_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", name="uq_ai_settings_farm"),
    )

    op.create_table(
        "ai_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(120), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False, server_default="generic"),
        sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("table_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("ai_documents")
    op.drop_table("ai_settings")
