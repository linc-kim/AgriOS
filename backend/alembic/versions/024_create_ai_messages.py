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

Note: this migration originally omitted the metadata column on the grounds that
      messages are immutable content records. That conflicted with AGRIOSBase,
      which maps a metadata column on every model, so every AIMessage query
      errored. Migration 049 adds the column.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None

# ── Message role ENUM ─────────────────────────────────────────────────────────
# postgresql.ENUM with create_type=False so create_table does not re-emit
# CREATE TYPE; the explicit .create(checkfirst=True) below owns creation.
MESSAGE_ROLE_ENUM = ENUM("user", "assistant", name="message_role", create_type=False)

# ── AI provider ENUM (owned by this migration; referenced by 027) ─────────────
AI_PROVIDER_ENUM = ENUM("gemini", "claude", name="ai_provider", create_type=False)


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
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
    ENUM(name="ai_provider").drop(op.get_bind(), checkfirst=True)
    ENUM(name="message_role").drop(op.get_bind(), checkfirst=True)
