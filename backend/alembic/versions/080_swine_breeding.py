"""Migration 080 — Swine Breeding, AI & Pregnancy (Module 20, Milestone 3)

The reproduction backbone (Swine Doc 2 §7, Doc 3 §7-9). Natural mating and
artificial insemination share ONE service table (``swine_breeding``), distinguished
by ``method`` — the AI workspace is the ``method='artificial'`` slice. Pregnancy is
a distinct LIFECYCLE STAGE, not a breeding event, so it lives in its own
``swine_pregnancy`` table linked to the breeding — cleanly supporting confirmation,
rechecks, pregnancy loss, false pregnancy and farrowing linkage. Gestation (~114d)
comes from ``swine_config`` with a breed override, so no breeding logic is forked.
Wright's genetics is REUSED from the platform ``pedigree_engine`` (not reimplemented).

Tables:
  swine_breeding  — a breeding service (natural or AI), repeat_of self-FK, AI semen
                    fields; service-cycle status + resolved outcome.
  swine_pregnancy — a pregnancy confirmed from a breeding: status lifecycle,
                    confirmation, expected/actual farrowing, risk, loss reason.
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
    # ── swine_breeding — the service (natural or AI) ───────────────────────────
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
        sa.Column("semen_source", sa.String(200), nullable=True),
        sa.Column("semen_batch", sa.String(100), nullable=True),
        sa.Column("technician", sa.String(150), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned",
                  comment="planned | serviced | closed | cancelled (service cycle only)"),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | pregnant | not_pregnant | failed | unknown (resolved result)"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_breeding_method", "swine_breeding", ["method"])
    op.create_index("ix_swine_breeding_status", "swine_breeding", ["status"])

    # ── swine_pregnancy — the lifecycle stage confirmed from a breeding ────────
    op.create_table(
        "swine_pregnancy",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breeding_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="Denormalised from the breeding for fast per-sow querying."),
        sa.Column("status", sa.String(20), nullable=False, server_default="unconfirmed",
                  comment="unconfirmed | confirmed | lost | farrowed | false_pregnancy"),
        sa.Column("confirmation_date", sa.Date, nullable=True),
        sa.Column("confirmation_method", sa.String(20), nullable=True,
                  comment="palpation | ultrasound | blood_test | non_return | visual | other"),
        sa.Column("expected_farrowing_date", sa.Date, nullable=True,
                  comment="FORECAST = service_date + gestation. Refined at confirmation."),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="unknown",
                  comment="low | moderate | high | unknown"),
        sa.Column("loss_reason", sa.String(20), nullable=True,
                  comment="abortion | resorption | mummification | stillbirth | disease | injury | unknown | other"),
        sa.Column("loss_date", sa.Date, nullable=True),
        sa.Column("actual_farrowing_date", sa.Date, nullable=True,
                  comment="Set when the farrowing is recorded (Milestone 4)."),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_pregnancy_status", "swine_pregnancy", ["status"])


def downgrade() -> None:
    op.drop_table("swine_pregnancy")
    op.drop_table("swine_breeding")
