"""Migration 004 — Create otp_requests table

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 00:03:00.000000

Engineering Constitution OTP Rules:
- Max 3 wrong attempts before lock (checked against attempts column)
- Max 3 requests per phone per 10 minutes (checked at application layer)
- OTP expires after 10 minutes (expires_at column)
- Code is stored as bcrypt hash — never plaintext
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "otp_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="NULL if user does not yet exist (first registration)",
        ),
        sa.Column(
            "code_hash",
            sa.String(255),
            nullable=False,
            comment="bcrypt hash of the 6-digit OTP code",
        ),
        sa.Column(
            "attempts",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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

    op.create_index("ix_otp_requests_id", "otp_requests", ["id"])
    op.create_index("ix_otp_requests_phone", "otp_requests", ["phone"])
    op.create_index("ix_otp_requests_deleted_at", "otp_requests", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("otp_requests")
