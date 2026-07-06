"""Migration 035 — Phase 2 session columns (device mgmt + O(1) refresh lookup)

Revision ID: 035
Revises: 034
Create Date: 2026-07-06 00:03:00.000000

Additive. token_lookup (SHA-256) lets Phase 2 email sessions be refreshed with a
single indexed query instead of scanning + bcrypt-comparing every live session.
Legacy OTP/PIN sessions leave it NULL and keep working.
"""

import sqlalchemy as sa
from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("token_lookup", sa.String(64), nullable=True))
    op.add_column("sessions", sa.Column("device_name", sa.String(120), nullable=True))
    op.add_column(
        "sessions",
        sa.Column(
            "remember_me",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sessions", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Partial-unique via a plain unique index; Postgres permits many NULLs.
    op.create_index(
        "ix_sessions_token_lookup", "sessions", ["token_lookup"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_token_lookup", table_name="sessions")
    op.drop_column("sessions", "last_used_at")
    op.drop_column("sessions", "remember_me")
    op.drop_column("sessions", "device_name")
    op.drop_column("sessions", "token_lookup")
