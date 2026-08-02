"""Migration 080 — Swine Breeding, AI & Pregnancy (Module 20, Milestone 3)

The reproduction backbone (Swine Doc 2 §7, Doc 3 §7-9). Natural mating and
artificial insemination share ONE cycle table (``swine_breeding``), distinguished
by ``method`` — the AI workspace is the ``method='artificial'`` slice, and pregnancy
confirmation is tracked inline (the Pregnancy workspace is the ``pregnant`` slice),
mirroring the Small Ruminant single-cycle design rather than proliferating three
near-duplicate service tables. Gestation (~114d) comes from ``swine_config`` with a
breed override, so no breeding logic is forked. Wright's genetics is REUSED from the
platform ``pedigree_engine`` (not reimplemented).

Table:
  swine_breeding — a breeding cycle (service → pregnancy-check → farrowing),
                   repeat_of self-FK, AI semen fields, inline pregnancy tracking.
The farrowing link (actual_farrowing_date is created here; the farrowing record and
piglets arrive in Migration 081, Milestone 4).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "080"
down_revision = "079"
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
        "swine_breeding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="On-farm boar; NULL for AI with external semen (semen_source recorded instead)."),
        sa.Column("repeat_of_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("method", sa.String(20), nullable=False, server_default="natural",
                  comment="natural | artificial | embryo_transfer"),
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("planned_farrowing_date", sa.Date, nullable=True,
                  comment="FORECAST = service_date + gestation (~114d, breed-overridable). Never a fact."),
        # Artificial insemination detail (used when method='artificial'; traceable).
        sa.Column("semen_source", sa.String(200), nullable=True),
        sa.Column("semen_batch", sa.String(100), nullable=True),
        sa.Column("technician", sa.String(150), nullable=True),
        # Pregnancy confirmation (inline; Pregnancy workspace reads this).
        sa.Column("pregnancy_checked_on", sa.Date, nullable=True),
        sa.Column("pregnancy_check_method", sa.String(20), nullable=True,
                  comment="palpation | ultrasound | blood_test | non_return | visual | other"),
        sa.Column("pregnancy_result", sa.String(20), nullable=False, server_default="unknown",
                  comment="unknown | pregnant | not_pregnant"),
        sa.Column("confirmed_on", sa.Date, nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="unknown",
                  comment="low | moderate | high | unknown"),
        sa.Column("actual_farrowing_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned",
                  comment="planned | serviced | pregnant | not_pregnant | farrowed | failed | closed | cancelled"),
        sa.Column("outcome", sa.String(20), nullable=True,
                  comment="successful | failed | aborted | reabsorbed | unknown"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_breeding_method", "swine_breeding", ["method"])
    op.create_index("ix_swine_breeding_status", "swine_breeding", ["status"])


def downgrade() -> None:
    op.drop_table("swine_breeding")
