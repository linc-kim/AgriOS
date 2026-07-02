"""Migration 012 — Create flocks table

Revision ID: 012
Revises: 011
Create Date: 2025-01-01 00:11:00.000000

Flocks are the central operational unit of AGRIOS.
Every daily log, weighin, production record, vaccination, and expense
references a flock_id.

This migration also resolves the deferred FK:
  production_houses.current_flock_id → flocks.id
(stored as bare UUID in Migration 011, FK added here when table exists).

Flock status lifecycle: active → sold | closed | culled
One active flock per production house at a time (enforced at application layer).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

FLOCK_STATUSES = ("active", "sold", "closed", "culled")


def upgrade() -> None:
    flock_status_enum = postgresql.ENUM(
        *FLOCK_STATUSES,
        name="flock_status",
        create_type=False,
    )
    flock_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "flocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "house_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("production_houses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "species_key",
            sa.String(50),
            sa.ForeignKey("species_profiles.species_key", ondelete="RESTRICT"),
            nullable=False,
            server_default="poultry",
            comment="FK to species_profiles. Always 'poultry' in V1.",
        ),
        sa.Column("name", sa.String(255), nullable=False,
                  comment="Display name, e.g. 'Batch 3 – Broiler May 2025'"),
        sa.Column("breed", sa.String(100), nullable=True,
                  comment="Bird breed, e.g. Ross 308, Cobb 500, ISA Brown"),
        sa.Column("batch_number", sa.String(50), nullable=True,
                  comment="Optional farmer-assigned batch reference"),
        sa.Column("initial_count", sa.Integer, nullable=False,
                  comment="Number of birds placed at start of batch"),
        sa.Column("placement_date", sa.Date, nullable=False,
                  comment="Date chicks/pullets were introduced to the house"),
        sa.Column("expected_cycle_days", sa.Integer, nullable=False,
                  server_default=sa.text("42"),
                  comment="Expected days to close. 42 for broilers, 350+ for layers."),
        sa.Column("expected_close_date", sa.Date, nullable=True,
                  comment="placement_date + expected_cycle_days. Computed at creation."),
        sa.Column(
            "status",
            flock_status_enum,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("close_date", sa.Date, nullable=True,
                  comment="Date the flock was sold, closed, or culled."),
        sa.Column("close_reason", sa.Text, nullable=True),
        sa.Column("sale_price_per_kg", sa.Numeric(10, 2), nullable=True,
                  comment="KES per kg at time of sale. Populated when status=sold."),
        sa.Column("total_birds_sold", sa.Integer, nullable=True,
                  comment="Final count of birds sold. Populated when status=sold."),
        sa.Column("closing_weight_kg", sa.Numeric(10, 3), nullable=True,
                  comment="Average live weight at close (kg per bird)."),
        sa.Column(
            "created_by",
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

    # Indexes
    op.create_index("ix_flocks_id", "flocks", ["id"])
    op.create_index("ix_flocks_farm_id", "flocks", ["farm_id"])
    op.create_index("ix_flocks_house_id", "flocks", ["house_id"])
    op.create_index("ix_flocks_status", "flocks", ["status"])
    op.create_index("ix_flocks_deleted_at", "flocks", ["deleted_at"])
    op.create_index(
    "ix_flocks_farm_status",
    "flocks",
    ["farm_id", "status"],
)
    op.create_index(
        "ix_flocks_placement_date",
        "flocks",
        ["farm_id", "placement_date"],
    )

    # ── Resolve deferred FK: production_houses.current_flock_id → flocks.id ──
    # This FK was deferred in Migration 011 because flocks did not exist yet.
    op.create_foreign_key(
        constraint_name="fk_production_houses_current_flock_id",
        source_table="production_houses",
        referent_table="flocks",
        local_cols=["current_flock_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the deferred FK first
    op.drop_constraint(
        "fk_production_houses_current_flock_id",
        "production_houses",
        type_="foreignkey",
    )
    op.drop_table("flocks")
    postgresql.ENUM(*FLOCK_STATUSES, name="flock_status").drop(
        op.get_bind(), checkfirst=True
    )
