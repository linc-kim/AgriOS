"""Migration 075 — Small Ruminant Health (Modules 18/19, Milestone 5)

Health, vaccination, deworming, hoof care and mortality — shared by goats and
sheep (Goat Doc 2 §12/§15/§16). Deworming and hoof care are first-class for small
ruminants (parasite control, foot health). Vaccination/deworming/hoof/health
follow-ups REUSE the platform Reminder engine via SOFT ``reminder_id`` refs (no
FK); no small-ruminant reminder table. The deterministic health engine emits
patterns, never a diagnosis (frozen §4.4).

Tables:
  sr_health_record — chronological clinical events (recorded diagnosis input only)
  sr_vaccination   — vaccination records (+ soft reminder_id)
  sr_deworming     — anthelmintic treatments (+ FAMACHA, withdrawal, reminder_id)
  sr_hoof_care     — hoof inspection/trimming/treatment (+ lameness, reminder_id)
  sr_mortality     — immutable death record, one per animal
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def _animal_scoped() -> list[sa.Column]:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
    ]


def upgrade() -> None:
    op.create_table(
        "sr_health_record",
        *_animal_scoped(),
        sa.Column("event_type", sa.String(30), nullable=False, server_default="observation"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="recorded"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("symptoms", sa.Text, nullable=True),
        sa.Column("diagnosis", sa.String(255), nullable=True,
                  comment="Recorded veterinary input only — never inferred (frozen §4.4)."),
        sa.Column("treatment", sa.Text, nullable=True),
        sa.Column("medication", sa.String(255), nullable=True),
        sa.Column("withdrawal_until", sa.Date, nullable=True),
        sa.Column("veterinarian", sa.String(200), nullable=True),
        sa.Column("recovery_status", sa.String(30), nullable=True),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_vaccination",
        *_animal_scoped(),
        sa.Column("vaccine", sa.String(150), nullable=False),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("administered_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("administrator", sa.String(200), nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_deworming",
        *_animal_scoped(),
        sa.Column("product", sa.String(150), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="oral_drench",
                  comment="oral_drench | injectable | pour_on | bolus | feed_additive | other"),
        sa.Column("dose", sa.String(100), nullable=True),
        sa.Column("famacha_score", sa.Integer, nullable=True, comment="Recorded anaemia score 1–5 (never inferred)."),
        sa.Column("administered_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("withdrawal_until", sa.Date, nullable=True),
        sa.Column("administrator", sa.String(200), nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_hoof_care",
        *_animal_scoped(),
        sa.Column("action", sa.String(20), nullable=False, server_default="inspection",
                  comment="inspection | trimming | treatment | foot_bath | other"),
        sa.Column("condition", sa.String(20), nullable=False, server_default="unknown",
                  comment="healthy | overgrown | foot_rot | foot_scald | abscess | injury | other | unknown"),
        sa.Column("lameness_score", sa.Integer, nullable=True, comment="Recorded lameness score 0–5 (never inferred)."),
        sa.Column("treatment", sa.Text, nullable=True),
        sa.Column("performed_on", sa.Date, nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=True),
        sa.Column("reminder_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_mortality",
        *_animal_scoped(),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("age_days", sa.Integer, nullable=True),
        sa.Column("cause", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("suspected_cause", sa.String(255), nullable=True),
        sa.Column("postmortem_notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("animal_id", name="uq_sr_mortality_animal"),
    )


def downgrade() -> None:
    op.drop_table("sr_mortality")
    op.drop_table("sr_hoof_care")
    op.drop_table("sr_deworming")
    op.drop_table("sr_vaccination")
    op.drop_table("sr_health_record")
