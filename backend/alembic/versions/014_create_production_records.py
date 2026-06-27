"""Migration 014 — Create production_records table

Revision ID: 014
Revises: 013
Create Date: 2025-01-01 00:13:00.000000

Production records capture egg output for layer flocks.
One record per flock per day (enforced via UNIQUE constraint).

Metrics captured:
  - eggs_collected   : total eggs gathered that day
  - broken_eggs      : damaged/cracked eggs (excluded from saleable count)
  - saleable_eggs    : computed at insert time (eggs_collected - broken_eggs)
  - hen_day_prod     : eggs_collected / current_flock_count (calculated at app layer)

Note: broiler flocks do not generate production records — the API enforces this
via the species_profile lookup on the parent flock.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            comment="DB-04: farm_id on every operational table",
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column(
            "eggs_collected",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "broken_eggs",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "saleable_eggs",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
            comment="eggs_collected - broken_eggs. Computed at insert time.",
        ),
        sa.Column(
            "hen_day_production",
            sa.Numeric(6, 4),
            nullable=True,
            comment="eggs_collected / current flock count. Computed at app layer.",
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

    # One production record per flock per day
    op.create_unique_constraint(
        "uq_production_records_flock_date",
        "production_records",
        ["flock_id", "record_date"],
    )

    op.create_index("ix_production_records_id", "production_records", ["id"])
    op.create_index("ix_production_records_farm_id", "production_records", ["farm_id"])
    op.create_index("ix_production_records_flock_id", "production_records", ["flock_id"])
    op.create_index(
        "ix_production_records_flock_date",
        "production_records",
        ["flock_id", "record_date"],
    )
    op.create_index(
        "ix_production_records_deleted_at",
        "production_records",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_table("production_records")
