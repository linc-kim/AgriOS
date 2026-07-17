"""Migration 040 — create health_events

Phase 3 Health module. A single flock-scoped health record covering
observations, symptoms, diagnoses, treatments, medication, mortality
investigations, quarantine/isolation, vet visits, recovery, and follow-ups.

Structured JSONB fields (symptoms, observations, attachments) are stored so
future AI (ARIA) disease analysis can consume them without a schema change.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "health_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "flock_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_date", sa.Date(), nullable=False, index=True),
        # observation | symptom | diagnosis | treatment | medication |
        # mortality_investigation | quarantine | vet_visit | recovery | followup
        sa.Column("event_type", sa.String(length=40), nullable=False, index=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        # AI-ready structured detail
        sa.Column("symptoms", JSONB, nullable=False, server_default="[]"),
        sa.Column("observations", JSONB, nullable=False, server_default="{}"),
        sa.Column("attachments", JSONB, nullable=False, server_default="[]"),
        sa.Column("diagnosis", sa.String(length=500), nullable=True),
        sa.Column("treatment", sa.String(length=500), nullable=True),
        sa.Column("medication_name", sa.String(length=200), nullable=True),
        sa.Column("dosage", sa.String(length=200), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
        sa.Column("affected_count", sa.Integer(), nullable=True),
        # open | monitoring | resolved
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolved_date", sa.Date(), nullable=True),
        sa.Column("vet_name", sa.String(length=200), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True, index=True),
        sa.Column("cost_kes", sa.Numeric(14, 2), nullable=True),
        sa.Column("expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_health_events_flock_status", "health_events", ["flock_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_health_events_flock_status", table_name="health_events")
    op.drop_table("health_events")
