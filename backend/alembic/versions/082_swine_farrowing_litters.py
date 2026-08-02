"""Migration 082 — Swine Farrowing, Litters & Fostering (Module 20, Milestone 4)

Farrowing and the offspring lifecycle (Swine Doc 2 §8-10, Doc 3 §10-12). The
farrowing is the birthing EVENT; the litter is the offspring COHORT (1:1). Litters
carry aggregate counts so smallholders manage at litter level, while commercial
farms additionally individualise pigs via ``swine_pig.litter_id`` — both workflows
supported, neither forced. Fostering moves piglets between nursing sows at the
individual grain while preserving birth-litter traceability.

Tables:
  swine_farrowing       — the birthing event (assistance, complications, colostrum)
  swine_litter          — the offspring cohort (born alive/stillborn/mummified, weaning)
  swine_foster_transfer — a cross-fostering event (count + optional individual pig_ids)
Adds to swine_pig:
  litter_id     — the birth litter this pig belongs to (SET NULL)
  nurse_dam_id  — a foster (nursing) sow different from the birth dam (SET NULL)
  birth_sex     — biological birth sex (male/female) recorded before class assignment
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "082"
down_revision = "081"
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
    # ── swine_farrowing — the birthing event ───────────────────────────────────
    op.create_table(
        "swine_farrowing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breeding_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pregnancy_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pregnancy.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("farrowing_code", sa.String(50), nullable=False),
        sa.Column("farrowing_date", sa.Date, nullable=False),
        sa.Column("parity", sa.Integer, nullable=True, comment="The sow's litter number."),
        sa.Column("assistance_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("complications", sa.Text, nullable=True),
        sa.Column("colostrum_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="received | partial | not_received | unknown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="recorded",
                  comment="recorded | active | closed"),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "farrowing_code", name="uq_swine_farrowing_farm_code"),
    )

    # ── swine_litter — the offspring cohort ────────────────────────────────────
    op.create_table(
        "swine_litter",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("farrowing_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_farrowing.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("nurse_dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="Current nursing sow; may differ from birth dam after fostering."),
        sa.Column("litter_code", sa.String(50), nullable=False),
        sa.Column("total_born", sa.Integer, nullable=False, server_default="0"),
        sa.Column("born_alive", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stillborn", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mummified", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weaned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mortality", sa.Integer, nullable=False, server_default="0",
                  comment="Pre-wean deaths (born alive that did not wean)."),
        sa.Column("fostered_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fostered_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_birth_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("litter_birth_weight_kg", sa.Numeric(9, 3), nullable=True),
        sa.Column("weaning_date", sa.Date, nullable=True),
        sa.Column("avg_weaning_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | weaned | closed"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "litter_code", name="uq_swine_litter_farm_code"),
    )
    op.create_index("ix_swine_litter_status", "swine_litter", ["status"])

    # ── swine_foster_transfer — cross-fostering event ──────────────────────────
    op.create_table(
        "swine_foster_transfer",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_litter_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dest_litter_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("source_dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dest_dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("piglet_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pig_ids", JSONB, nullable=False, server_default="[]",
                  comment="Individual swine_pig ids moved (when the farm tracks individuals)."),
        sa.Column("transfer_date", sa.Date, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── swine_pig additions ────────────────────────────────────────────────────
    op.add_column("swine_pig", sa.Column(
        "litter_id", UUID(as_uuid=True),
        sa.ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True,
        comment="Birth litter (individualised management); NULL for litter-level-only or purchased pigs."))
    op.add_column("swine_pig", sa.Column(
        "nurse_dam_id", UUID(as_uuid=True),
        sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True,
        comment="Foster (nursing) sow, if different from the birth dam."))
    op.add_column("swine_pig", sa.Column(
        "birth_sex", sa.String(10), nullable=False, server_default="unknown",
        comment="male | female | unknown — biological birth sex, recorded before class assignment."))
    op.create_index("ix_swine_pig_litter_id", "swine_pig", ["litter_id"])


def downgrade() -> None:
    op.drop_index("ix_swine_pig_litter_id", table_name="swine_pig")
    op.drop_column("swine_pig", "birth_sex")
    op.drop_column("swine_pig", "nurse_dam_id")
    op.drop_column("swine_pig", "litter_id")
    op.drop_table("swine_foster_transfer")
    op.drop_table("swine_litter")
    op.drop_table("swine_farrowing")
