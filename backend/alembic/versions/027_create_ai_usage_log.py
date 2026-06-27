"""create ai_usage_log

AGRIOS — Migration 027
Tier 6 — AI Module

Table: ai_usage_log
  Immutable, append-only cost and usage record per AI call.
  Engineering Constitution DB-08: no UPDATE or DELETE endpoint exists.
  Used for: quota enforcement, cost reporting in admin dashboard, provider analytics.

  cost_usd: precise to 8 decimal places (Gemini Flash is sub-cent per call)

DB-04: farm_id ✓  AD-01: UUID PK ✓
NOTE: No soft delete (deleted_at) — log is immutable by constitution (DB-08).
NOTE: No metadata column — cost records are fixed-schema financial records.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        # ── Identity ─────────────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
        # ── Scoping ───────────────────────────────────────────────────────────
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The conversation this call belongs to (nullable — insights have no conversation)
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ── Provider ──────────────────────────────────────────────────────────
        # ai_provider ENUM created in migration 024
        sa.Column(
            "provider",
            sa.Enum("gemini", "claude", name="ai_provider"),
            nullable=False,
        ),
        sa.Column(
            "model",
            sa.String(100),
            nullable=False,
        ),
        # ── Usage ─────────────────────────────────────────────────────────────
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "cost_usd",
            sa.Numeric(14, 8),
            nullable=False,
            server_default="0",
        ),
        # AI call duration in milliseconds
        sa.Column("duration_ms", sa.Integer, nullable=True),
        # ── Outcome ───────────────────────────────────────────────────────────
        sa.Column(
            "success",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column("error_message", sa.String(500), nullable=True),
        # Call type: "conversation" | "insight_generation" | "recommendation"
        sa.Column("call_type", sa.String(30), nullable=False, server_default="conversation"),
        # ── Timestamp (immutable — created_at only, no updated_at) ────────────
        sa.Column(
            "created_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    # Monthly quota check: count calls for a farm in the current month
    op.create_index(
        "ix_ai_usage_log_farm_created",
        "ai_usage_log",
        ["farm_id", "created_at"],
    )
    # Admin cost reporting: all calls by provider in a date range
    op.create_index(
        "ix_ai_usage_log_provider_created",
        "ai_usage_log",
        ["provider", "created_at"],
    )
    op.create_index(
        "ix_ai_usage_log_user_id",
        "ai_usage_log",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_user_id", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_provider_created", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_farm_created", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
    # NOTE: ai_provider ENUM is NOT dropped here — it belongs to migration 024
    # and will be dropped when migration 024 is downgraded.
