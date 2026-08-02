"""Migration 085 — Swine Growth & Production (Module 20, Milestone 7)

Immutable weight events, production-stage transition history, and independent body-
condition scoring (Swine Doc 2 §4, Doc 3 §16). Growth metrics (ADG, gain, FCR,
curves) are CALCULATED by the deterministic engine from these records and never
stored, avoiding stale/duplicate figures. The pig's ``current_weight_kg`` remains a
fast-display mirror of the latest weight (derived, not the source of truth), and its
``production_stage`` is the latest transition's ``new_stage``.

Tables:
  swine_weight            — immutable weighing events (kg; method; age_days)
  swine_stage_transition  — append-only production-stage change history
  swine_body_condition    — body-condition scores (independent of weight)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "085"
down_revision = "084"
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
    op.create_table(
        "swine_weight",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("method", sa.String(15), nullable=False, server_default="scale",
                  comment="scale | tape | estimate | visual | unknown"),
        sa.Column("age_days", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_weight_recorded_on", "swine_weight", ["recorded_on"])

    op.create_table(
        "swine_stage_transition",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("previous_stage", sa.String(20), nullable=True),
        sa.Column("new_stage", sa.String(20), nullable=False),
        sa.Column("transition_date", sa.Date, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual",
                  comment="manual | weaning | market | breeding_assignment | cull | system"),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "swine_body_condition",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("assessed_on", sa.Date, nullable=False),
        sa.Column("score", sa.Numeric(3, 1), nullable=False, comment="BCS 1 (emaciated) … 5 (obese)."),
        sa.Column("assessor", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("swine_body_condition")
    op.drop_table("swine_stage_transition")
    op.drop_table("swine_weight")
