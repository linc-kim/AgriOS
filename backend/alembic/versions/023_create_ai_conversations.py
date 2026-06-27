"""create ai_conversations

AGRIOS — Migration 023
Tier 6 — AI Module

Table: ai_conversations
  One conversation thread per farmer session with ARIA.
  Farm-scoped, user-scoped, optional flock context.
  Tracks message count and active state.

DB-04: farm_id on every operational table ✓
DB-01: soft deletes via deleted_at ✓
DB-05: metadata JSONB ✓
AD-01: UUID PK ✓
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        # ── Identity ─────────────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
        # ── Farm + user scoping ───────────────────────────────────────────────
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
        # Optional flock context — narrows Farm Context Package scope
        sa.Column(
            "flock_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ── Content ───────────────────────────────────────────────────────────
        # Auto-generated title from first user message (first 60 chars)
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column(
            "message_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        # ── Timestamps + soft delete + metadata ───────────────────────────────
        sa.Column(
            "created_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMPTZ, nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )

    # Primary query: list conversations for a farm user, newest first
    op.create_index(
        "ix_ai_conversations_farm_user",
        "ai_conversations",
        ["farm_id", "user_id"],
    )
    op.create_index(
        "ix_ai_conversations_farm_id",
        "ai_conversations",
        ["farm_id"],
    )
    op.create_index(
        "ix_ai_conversations_deleted_at",
        "ai_conversations",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_conversations_deleted_at", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_farm_id", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_farm_user", table_name="ai_conversations")
    op.drop_table("ai_conversations")
