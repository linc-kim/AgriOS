"""Migration 015 — Create weighin_records table

Revision ID: 015
Revises: 014
Create Date: 2025-01-01 00:14:00.000000

Weigh-in records capture live-weight samples from a random subset of the flock.
Used to compute FCR (Feed Conversion Ratio) and track growth against breed targets.

Fields:
  - sample_size      : number of birds weighed (not the whole flock)
  - average_weight_kg: mean live weight of the sample
  - min_weight_kg    : lightest bird in sample (uniformity indicator)
  - max_weight_kg    : heaviest bird in sample
  - total_biomass_kg : average_weight_kg * current_flock_count (app-computed)
  - fcr_to_date      : total_feed_consumed_kg / total_biomass_kg (app-computed)

Multiple weigh-ins per flock are allowed (no unique constraint on date).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weighin_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weighed_at", sa.Date, nullable=False),
        sa.Column(
            "sample_size",
            sa.Integer,
            nullable=False,
            comment="Number of birds weighed in this sample",
        ),
        sa.Column(
            "average_weight_kg",
            sa.Numeric(8, 3),
            nullable=False,
            comment="Mean live weight of the sample (kg)",
        ),
        sa.Column(
            "min_weight_kg",
            sa.Numeric(8, 3),
            nullable=True,
            comment="Lightest bird weighed (kg). Used for uniformity analysis.",
        ),
        sa.Column(
            "max_weight_kg",
            sa.Numeric(8, 3),
            nullable=True,
            comment="Heaviest bird weighed (kg).",
        ),
        sa.Column(
            "total_biomass_kg",
            sa.Numeric(12, 3),
            nullable=True,
            comment="average_weight_kg * flock.current_count. App-computed at insert.",
        ),
        sa.Column(
            "fcr_to_date",
            sa.Numeric(8, 3),
            nullable=True,
            comment="Feed Conversion Ratio = total_feed_kg / total_biomass_kg",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "logged_by",
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
    )

    op.create_index("ix_weighin_records_id", "weighin_records", ["id"])
    op.create_index("ix_weighin_records_farm_id", "weighin_records", ["farm_id"])
    op.create_index("ix_weighin_records_flock_id", "weighin_records", ["flock_id"])
    op.create_index(
        "ix_weighin_records_flock_date",
        "weighin_records",
        ["flock_id", "weighed_at"],
    )
    op.create_index("ix_weighin_records_deleted_at", "weighin_records", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("weighin_records")
