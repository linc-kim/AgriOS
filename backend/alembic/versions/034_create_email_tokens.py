"""Migration 034 — create email_tokens (verify / reset / change-email)

Revision ID: 034
Revises: 033
Create Date: 2026-07-06 00:02:00.000000

Single-use expiring tokens. Only the SHA-256 (token_lookup) is stored.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_type", sa.String(32), nullable=False),
        sa.Column("token_lookup", sa.String(64), nullable=False),
        sa.Column("new_email", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index("ix_email_tokens_id", "email_tokens", ["id"])
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
    op.create_index("ix_email_tokens_token_type", "email_tokens", ["token_type"])
    op.create_index(
        "ix_email_tokens_token_lookup", "email_tokens", ["token_lookup"], unique=True
    )
    op.create_index("ix_email_tokens_deleted_at", "email_tokens", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("email_tokens")
