"""Migration 010 — Create farm_units table

Revision ID: 010
Revises: 009
Create Date: 2025-01-01 00:09:00.000000

Farm units are named physical sections of a farm, e.g. "Section A", "Unit 1".
They group production houses for organisational clarity.
A farm can have multiple units. A unit belongs to exactly one farm.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "farm_units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
            comment="Display name, e.g. 'Section A', 'Block 1'.",
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
            comment="Display order within the farm. Lower numbers appear first.",
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

    op.create_index("ix_farm_units_id", "farm_units", ["id"])
    op.create_index("ix_farm_units_farm_id", "farm_units", ["farm_id"])
    op.create_index("ix_farm_units_deleted_at", "farm_units", ["deleted_at"])
    op.create_index(
        "ix_farm_units_farm_sort",
        "farm_units",
        ["farm_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_table("farm_units")
