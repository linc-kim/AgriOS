"""Migration 032 — Phase 2 auth: email/password on users, phone optional

Revision ID: 032
Revises: 031
Create Date: 2026-07-06 00:00:00.000000

Additive / non-destructive:
- add password_hash, email_verified, email_verified_at, password_changed_at
- make phone nullable (email becomes the primary identifier; legacy phone rows
  keep working, and OTP/PIN flows are untouched)
"""

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Email is now primary; phone is an optional secondary identifier.
    op.alter_column("users", "phone", existing_type=sa.String(20), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "phone", existing_type=sa.String(20), nullable=False)
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
