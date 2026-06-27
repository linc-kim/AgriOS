"""Migration 003 — Create user_roles junction table

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:02:00.000000

Engineering Constitution:
- UNIQUE(user_id, farm_id) — one role per user per farm
- farm_id is UUID without FK here; FK to farms.id added in Sprint 2 Migration 008
- NULL farm_id = platform-level role (super_admin, platform_admin)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # farm_id stored as UUID — FK added in Migration 008 when farms table exists
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "assigned_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        # UNIQUE constraint: one role per user per farm (NULL farm = platform level)
        sa.UniqueConstraint(
            "user_id",
            "farm_id",
            name="uq_user_roles_user_farm",
        ),
    )

    op.create_index("ix_user_roles_id", "user_roles", ["id"])
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    op.create_index("ix_user_roles_farm_id", "user_roles", ["farm_id"])
    op.create_index("ix_user_roles_deleted_at", "user_roles", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("user_roles")
