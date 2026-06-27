"""Migration 017 — Create vaccination_records table

Revision ID: 017
Revises: 016
Create Date: 2025-01-01 00:16:00.000000

Vaccination records track every vaccination event administered to a flock.

Key design decisions:
- `next_due_date` is computed at insert time based on vaccine interval
  (e.g., ND+IB booster 21 days after first dose). The app pre-populates
  this from known vaccine protocols, user can override.
- `next_due_date` drives the ARIA insight triggers:
    - "Vaccination due soon" (within 3 days)
    - "Vaccination overdue" (past due_date)
- `administered_by` links to users table — can be a farm worker or vet.
- `route` is the administration route: drinking_water, spray, eye_drop,
  injection, wing_stab. Stored as free text to allow extensibility.
- No UNIQUE constraint — multiple vaccines can be given on the same date.
  Same vaccine given twice on same date is a valid correction scenario.
- `species_key` FK enforces this is a poultry record in V1.
- `flock_id` nullable=False — vaccinations are always flock-scoped.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vaccination_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            comment="DB-04 Frozen: all operational records are farm-scoped.",
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
            comment="Vaccinations are always flock-scoped.",
        ),
        sa.Column(
            "species_key",
            sa.String(50),
            sa.ForeignKey("species_profiles.species_key", ondelete="RESTRICT"),
            nullable=False,
            server_default="poultry",
            comment="DB-03 Frozen: species extensibility anchor.",
        ),
        # ── Vaccine details ────────────────────────────────────────────────────
        sa.Column(
            "vaccine_name",
            sa.String(200),
            nullable=False,
            comment="e.g. Newcastle Disease (ND), Infectious Bronchitis (IB), Gumboro, Marek's",
        ),
        sa.Column(
            "vaccine_brand",
            sa.String(200),
            nullable=True,
            comment="Commercial brand name, e.g. HIPRAVIAR B1+H120",
        ),
        sa.Column(
            "dose_number",
            sa.Integer,
            nullable=False,
            server_default="1",
            comment="1 = first dose, 2 = booster, 3 = second booster, etc.",
        ),
        # ── Administration details ─────────────────────────────────────────────
        sa.Column(
            "administered_date",
            sa.Date,
            nullable=False,
            comment="Date the vaccine was given.",
        ),
        sa.Column(
            "administered_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who administered or recorded the vaccination.",
        ),
        sa.Column(
            "route",
            sa.String(50),
            nullable=True,
            comment="Administration route: drinking_water, spray, eye_drop, injection, wing_stab",
        ),
        sa.Column(
            "flock_age_days",
            sa.Integer,
            nullable=True,
            comment="Age of flock in days at time of vaccination (computed from placement_date).",
        ),
        sa.Column(
            "batch_number",
            sa.String(100),
            nullable=True,
            comment="Vaccine lot/batch number for traceability.",
        ),
        # ── Next dose planning ─────────────────────────────────────────────────
        sa.Column(
            "next_due_date",
            sa.Date,
            nullable=True,
            comment=(
                "Date the next dose is due. Drives ARIA vaccination alerts. "
                "Null when this is the final dose in the schedule."
            ),
        ),
        sa.Column(
            "next_vaccine_name",
            sa.String(200),
            nullable=True,
            comment="Name of the next vaccine due (may differ from current, e.g. ND booster after ND+IB).",
        ),
        # ── Notes ─────────────────────────────────────────────────────────────
        sa.Column("notes", sa.Text, nullable=True),
        # ── Audit ─────────────────────────────────────────────────────────────
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

    # ── Indexes ────────────────────────────────────────────────────────────────
    op.create_index("ix_vaccination_records_id", "vaccination_records", ["id"])
    op.create_index(
        "ix_vaccination_records_farm_id", "vaccination_records", ["farm_id"]
    )
    op.create_index(
        "ix_vaccination_records_flock_id", "vaccination_records", ["flock_id"]
    )
    op.create_index(
        "ix_vaccination_records_administered_date",
        "vaccination_records",
        ["administered_date"],
    )
    # Critical: this index powers the ARIA "upcoming vaccinations" and
    # "overdue vaccinations" query (WHERE next_due_date IS NOT NULL AND deleted_at IS NULL)
    op.create_index(
        "ix_vaccination_records_next_due_date",
        "vaccination_records",
        ["next_due_date"],
    )
    op.create_index(
        "ix_vaccination_records_farm_due",
        "vaccination_records",
        ["farm_id", "next_due_date"],
    )
    op.create_index(
        "ix_vaccination_records_deleted_at",
        "vaccination_records",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_table("vaccination_records")
