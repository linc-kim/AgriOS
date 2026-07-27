"""Migration 058 — Aviculture Health Engine (Module 15, Part 6)

Extends the Part 1 foundation ``avi_health_record`` into the full individual-bird
health system (Doc 02 §17, Doc 13 Part 6). Nothing is duplicated: the existing
table gains the columns the engine needs, and two new lifecycle tables are added.

The platform already has a *flock-scoped* health module (Module 1: HealthEvent,
VaccinationRecord, DiseaseAlert). Those are batch/flock records and cannot
represent an individual bird's medical history, so the aviculture health engine
extends the individual ``avi_health_record`` rather than forking that system.

Changes:
  avi_health_record  +title, +status, +severity, +next_due_on, +body_condition
  avi_quarantine     — quarantine / isolation episodes per bird
  avi_disease_event  — farm-level outbreak / biosecurity tracking
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Extend the foundation health record ───────────────────────────────────
    op.add_column("avi_health_record", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("avi_health_record", sa.Column("status", sa.String(20), nullable=False, server_default="recorded",
                  comment="recorded | open | ongoing | resolved (chronic/recovery tracking)."))
    op.add_column("avi_health_record", sa.Column("severity", sa.String(20), nullable=True,
                  comment="info | mild | moderate | severe | critical."))
    op.add_column("avi_health_record", sa.Column("next_due_on", sa.Date(), nullable=True,
                  comment="Next due date for preventive care (drives reminders, Doc 11 §5)."))
    op.add_column("avi_health_record", sa.Column("body_condition", sa.String(30), nullable=True))
    op.create_index("ix_avi_health_next_due", "avi_health_record", ["next_due_on"])

    # ── Quarantine / isolation ────────────────────────────────────────────────
    op.create_table(
        "avi_quarantine",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("bird_id", UUID(as_uuid=True), sa.ForeignKey("avi_bird.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("aviary_id", UUID(as_uuid=True), sa.ForeignKey("avi_aviary.id", ondelete="SET NULL"),
                  nullable=True, index=True, comment="Isolation location."),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("expected_end_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | released"),
        sa.Column("outcome", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_quarantine_status", "avi_quarantine", ["bird_id", "status"])

    # ── Disease / outbreak / biosecurity events ───────────────────────────────
    op.create_table(
        "avi_disease_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("aviary_id", UUID(as_uuid=True), sa.ForeignKey("avi_aviary.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("disease_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="suspected",
                  comment="suspected | confirmed | contained | resolved"),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("resolved_on", sa.Date(), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_notifiable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_disease_status", "avi_disease_event", ["farm_id", "status"])


def downgrade() -> None:
    op.drop_table("avi_disease_event")
    op.drop_table("avi_quarantine")
    op.drop_index("ix_avi_health_next_due", table_name="avi_health_record")
    op.drop_column("avi_health_record", "body_condition")
    op.drop_column("avi_health_record", "next_due_on")
    op.drop_column("avi_health_record", "severity")
    op.drop_column("avi_health_record", "status")
    op.drop_column("avi_health_record", "title")
