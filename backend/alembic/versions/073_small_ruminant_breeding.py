"""Migration 073 — Small Ruminant Breeding & Birth (Modules 18/19, Milestone 3)

The reproduction backbone shared by goats and sheep (Goat Doc 2 §8-9, Doc 3 §7).
One mating cycle (service → pregnancy check → birth) and one birth event
(kidding / lambing) — the same tables for both species, distinguished by
``species``. Gestation and the birth verb come from the species config, so no
breeding logic is forked. Wright's genetics is REUSED from the platform
``pedigree_engine`` (not reimplemented).

Tables:
  sr_breeding — a mating cycle (service→pregnancy-check→birth), repeat_of self-FK
  sr_birth    — a parturition event (kidding/lambing) + birth statistics
Adds:
  sr_animal.birth_id — the offspring's birth event (SET NULL)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "073"
down_revision = "072"
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
    # ── Mating cycle: sr_breeding ──────────────────────────────────────────────
    op.create_table(
        "sr_breeding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True, comment="goat | sheep"),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("repeat_of_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("method", sa.String(20), nullable=False, server_default="natural",
                  comment="natural | artificial | embryo_transfer"),
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("planned_birth_date", sa.Date, nullable=True,
                  comment="FORECAST = service_date + species/breed gestation. Never a recorded fact."),
        sa.Column("pregnancy_checked_on", sa.Date, nullable=True),
        sa.Column("pregnancy_result", sa.String(20), nullable=False, server_default="unknown",
                  comment="unknown | pregnant | not_pregnant"),
        sa.Column("prep_started_on", sa.Date, nullable=True),
        sa.Column("actual_birth_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned",
                  comment="planned | serviced | pregnant | not_pregnant | birthed | failed | closed | cancelled"),
        sa.Column("outcome", sa.String(20), nullable=True,
                  comment="successful | failed | aborted | reabsorbed | unknown"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_sr_breeding_status", "sr_breeding", ["status"])

    # ── Birth event: sr_birth (kidding / lambing) ──────────────────────────────
    op.create_table(
        "sr_birth",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True, comment="goat | sheep"),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breeding_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("birth_code", sa.String(50), nullable=False),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("birth_type", sa.String(15), nullable=False, server_default="unknown",
                  comment="single | twin | triplet | quadruplet | quintuplet | unknown"),
        sa.Column("total_born", sa.Integer, nullable=False, server_default="0"),
        sa.Column("live_born", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stillborn", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weaned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mortality", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_birth_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("weaning_date", sa.Date, nullable=True),
        sa.Column("assistance_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("complications", sa.Text, nullable=True),
        sa.Column("colostrum_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="received | partial | not_received | unknown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | weaned | closed"),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "birth_code", name="uq_sr_birth_farm_code"),
    )

    # ── Offspring → birth event link ───────────────────────────────────────────
    op.add_column("sr_animal", sa.Column(
        "birth_id", UUID(as_uuid=True),
        sa.ForeignKey("sr_birth.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_sr_animal_birth_id", "sr_animal", ["birth_id"])


def downgrade() -> None:
    op.drop_index("ix_sr_animal_birth_id", table_name="sr_animal")
    op.drop_column("sr_animal", "birth_id")
    op.drop_table("sr_birth")
    op.drop_table("sr_breeding")
