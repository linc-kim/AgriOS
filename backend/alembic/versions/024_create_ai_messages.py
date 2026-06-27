"""create ai_messages

AGRIOS — Migration 024
Tier 6 — AI Module

Table: ai_messages
  Individual messages within a conversation thread.
  role: "user" | "assistant"
  language: "en" | "sw"   — detected/set from user question
  provider: "gemini" | "claude" | null (user messages have no provider)

DB-04: farm_id on every operational table ✓  (denormalized from conversation for direct queries)
DB-01: soft deletes via deleted_at ✓
AD-01: UUID PK ✓

Note: ai_messages has NO metadata column — messages are immutable content records;
      metadata extensibility lives on ai_conversations.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None

# ── Message role ENUM ─────────────────────────────────────────────────────────
MESSAGE_ROLE_ENUM = sa.Enum("user", "assistant", name="message_role")

# ── AI provider ENUM ──────────────────────────────────────────────────────────
AI_PROVIDER_ENUM = sa.Enum("gemini", "claude", name="ai_provider")


def upgrade() -> None:
    # Create ENUMs first
    MESSAGE_ROLE_ENUM.create(op.get_bind(), checkfirst=True)
    AI_PROVIDER_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_messages",
        # ── Identity ─────────────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
        # ── Foreign keys ─────────────────────────────────────────────────────
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized for direct per-farm message queries
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ── Content ───────────────────────────────────────────────────────────
        sa.Column(
            "role",
            MESSAGE_ROLE_ENUM,
            nullable=False,
        ),
        sa.Column(
            "content",
            sa.Text,
            nullable=False,
        ),
        # Language detected from the user message (propagated to assistant response)
        sa.Column(
            "language",
            sa.String(5),
            nullable=False,
            server_default="en",
        ),
        # ── AI provider metadata (null for user messages) ─────────────────────
        sa.Column(
            "provider",
            AI_PROVIDER_ENUM,
            nullable=True,
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "total_tokens",
            sa.Integer,
            nullable=True,
        ),
        # Latency of this specific AI call in ms (null for user messages)
        sa.Column(
            "latency_ms",
            sa.Integer,
            nullable=True,
        ),
        # ── Timestamps + soft delete ──────────────────────────────────────────
        # Messages use created_at only — they are immutable after creation
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
    )

    # Primary query: list messages for a conversation, chronological
    op.create_index(
        "ix_ai_messages_conversation_id",
        "ai_messages",
        ["conversation_id"],
    )
    op.create_index(
        "ix_ai_messages_farm_id",
        "ai_messages",
        ["farm_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_messages_farm_id", table_name="ai_messages")
    op.drop_index("ix_ai_messages_conversation_id", table_name="ai_messages")
    op.drop_table("ai_messages")
    sa.Enum(name="ai_provider").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="message_role").drop(op.get_bind(), checkfirst=True)
