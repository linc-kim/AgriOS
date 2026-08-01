"""Migration 069 — Rabbit Health, Vaccination & Mortality (Module 17, Milestone 5)

Health records, vaccinations and mortality (Spec Part 2 §10/§15, Part 3 §11-12/§16,
Part 4 §9). Health records are chronological (Spec Part 3 §11); mortality records
are immutable after recording (Spec Part 3 §16). Genetics-style calculation
(mortality/recovery rates, frequencies) is computed by the deterministic engine —
never stored, never a diagnosis (frozen §4.4).

Reuse, not duplication (ledger CON-M5):
  * Vaccination follow-ups reuse the platform Reminder engine — the created
    reminder id is a SOFT ref (``reminder_id``, no FK) on ``rabbit_vaccination``.
  * Attachments reuse the existing ``rabbit_document`` / ``rabbit_media`` tables.
  * Timeline/audit reuse ``rabbit_event`` + the platform audit log.

Tables:
  rabbit_health_record — chronological clinical events (illness/injury/treatment…)
  rabbit_vaccination   — vaccination records (+ Reminder soft ref)
  rabbit_mortality     — immutable death record (one per rabbit)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "069"
down_revision = "068"
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
    # ── Health records (Spec Part 3 §11) ───────────────────────────────────────
    op.create_table(
        "rabbit_health_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
            server_default="observation",
            comment="observation | exam | illness | injury | treatment | medication | "
            "deworming | surgery | vet_visit | recovery | quarantine | note",
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="recorded",
            comment="recorded | open | ongoing | resolved",
        ),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            server_default="info",
            comment="info | mild | moderate | severe | critical",
        ),
        sa.Column("symptoms", sa.Text, nullable=True),
        sa.Column("diagnosis", sa.String(255), nullable=True,
                  comment="Recorded veterinary input only (a fact) — never inferred (frozen §4.4)."),
        sa.Column("treatment", sa.Text, nullable=True),
        sa.Column("medication", sa.String(255), nullable=True),
        sa.Column("veterinarian", sa.String(200), nullable=True),
        sa.Column("recovery_status", sa.String(30), nullable=True),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True,
                  comment="Follow-up date; may seed a platform Reminder."),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_health_rabbit_date", "rabbit_health_record", ["rabbit_id", "occurred_on"])
    op.create_index("ix_rabbit_health_event_type", "rabbit_health_record", ["event_type"])

    # ── Vaccinations (Spec Part 3 §12) ─────────────────────────────────────────
    op.create_table(
        "rabbit_vaccination",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("vaccine", sa.String(150), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("administered_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("administrator", sa.String(200), nullable=True),
        # Soft reference to the platform Reminder created for the next dose (no FK).
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_vaccination_rabbit", "rabbit_vaccination", ["rabbit_id", "administered_on"])
    op.create_index("ix_rabbit_vaccination_due", "rabbit_vaccination", ["next_due_on"])

    # ── Mortality (Spec Part 3 §16; immutable) ─────────────────────────────────
    op.create_table(
        "rabbit_mortality",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("age_days", sa.Integer, nullable=True),
        sa.Column(
            "cause",
            sa.String(30),
            nullable=False,
            server_default="unknown",
            comment="disease | injury | predation | environmental | congenital | digestive | "
            "respiratory | heat_stress | starvation | unknown | other",
        ),
        sa.Column("suspected_cause", sa.String(255), nullable=True),
        sa.Column("postmortem_notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("rabbit_id", name="uq_rabbit_mortality_rabbit"),
    )


def downgrade() -> None:
    op.drop_table("rabbit_mortality")
    op.drop_table("rabbit_vaccination")
    op.drop_table("rabbit_health_record")
