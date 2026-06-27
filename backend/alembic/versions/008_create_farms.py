"""Migration 008 — Create farms table + add FK to user_roles.farm_id

Revision ID: 008
Revises: 007
Create Date: 2025-01-01 00:07:00.000000

This migration:
1. Creates the farms table.
2. Adds the FK constraint on user_roles.farm_id → farms.id.
   (The column was added in migration 003 without FK — deferred until farms existed.)

DB-04 (Frozen): farm_id is on every operational table. All queries are farm-scoped.
AD-02 (Frozen): PostgreSQL 16 via Supabase.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Create farms table ─────────────────────────────────────────────────
    op.create_table(
        "farms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Farm display name. Shown in top bar and all references.",
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "location",
            sa.String(255),
            nullable=True,
            comment="Kenya county or sub-county. Used for disease alert targeting.",
        ),
        sa.Column(
            "county",
            sa.String(100),
            nullable=True,
            comment="Kenya county (47 counties). Normalised for SMS alert matching.",
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            comment="The farm_owner user. Cannot delete a user who owns a farm.",
        ),
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Active subscription plan. Defaults to free plan.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'Africa/Nairobi'"),
            comment="Farm timezone. All scheduled notifications use this.",
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
    )

    op.create_index("ix_farms_id", "farms", ["id"])
    op.create_index("ix_farms_owner_id", "farms", ["owner_id"])
    op.create_index("ix_farms_plan_id", "farms", ["plan_id"])
    op.create_index("ix_farms_deleted_at", "farms", ["deleted_at"])
    op.create_index("ix_farms_county", "farms", ["county"])

    # ── 2. Add FK constraint on user_roles.farm_id → farms.id ────────────────
    # This was deferred from Migration 003. The farms table now exists.
    op.create_foreign_key(
        constraint_name="fk_user_roles_farm_id",
        source_table="user_roles",
        referent_table="farms",
        local_cols=["farm_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Remove FK first, then drop table
    op.drop_constraint(
        "fk_user_roles_farm_id",
        "user_roles",
        type_="foreignkey",
    )
    op.drop_table("farms")
