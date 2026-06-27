"""Migration 011 — Create production_houses table

Revision ID: 011
Revises: 010
Create Date: 2025-01-01 00:10:00.000000

Production houses are individual physical structures within a farm unit.
e.g., "House 1", "Broiler Pen A", "Layer House 3".

One active flock per house at a time (enforced at application layer).
current_flock_id references flocks.id — FK added in Sprint 3 Migration 012
when the flocks table exists.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

HOUSE_TYPES = ("broiler", "layer", "breeder", "pullet", "multi")


def upgrade() -> None:
    house_type_enum = postgresql.ENUM(
        *HOUSE_TYPES,
        name="house_type",
        create_type=True,
    )
    house_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "production_houses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farm_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Display name, e.g. 'House 1', 'Broiler Pen A'.",
        ),
        sa.Column(
            "capacity",
            sa.Integer,
            nullable=False,
            comment="Maximum bird capacity. Used for stocking density calculations.",
        ),
        sa.Column(
            "house_type",
            house_type_enum,
            nullable=False,
            server_default=sa.text("'broiler'"),
            comment="Primary use type: broiler | layer | breeder | pullet | multi",
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        # current_flock_id: stored as UUID without FK constraint here.
        # FK to flocks.id is added in Sprint 3 Migration 012.
        sa.Column(
            "current_flock_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Active flock occupying this house. NULL when empty. "
                    "FK to flocks.id added in Migration 012.",
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

    op.create_index("ix_production_houses_id", "production_houses", ["id"])
    op.create_index("ix_production_houses_farm_id", "production_houses", ["farm_id"])
    op.create_index("ix_production_houses_unit_id", "production_houses", ["unit_id"])
    op.create_index(
        "ix_production_houses_current_flock_id",
        "production_houses",
        ["current_flock_id"],
    )
    op.create_index(
        "ix_production_houses_deleted_at",
        "production_houses",
        ["deleted_at"],
    )
    op.create_index(
        "ix_production_houses_unit_sort",
        "production_houses",
        ["unit_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_table("production_houses")
    postgresql.ENUM(
        *HOUSE_TYPES,
        name="house_type",
    ).drop(op.get_bind(), checkfirst=True)
