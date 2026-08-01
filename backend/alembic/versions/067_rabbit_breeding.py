"""Migration 067 — Rabbit Breeding & Litters (Module 17, Milestone 3)

Breeding, pregnancy, kindling, litters and weaning (Spec Part 2 §5-6, Part 3
§7-8). The breeding cycle is modelled as one ``rabbit_breeding`` row per mating
attempt (service → pregnancy check → kindling) with repeat services linked via
``repeat_of_id``; a ``rabbit_litter`` is created at kindling and updated through
foster and weaning. Kits are ``rabbit`` rows linked to their birth litter via the
new ``rabbit.litter_id`` column (Spec Part 3 §8 — "each kit permanently linked to
its litter"), with sire/dam links flowing from the breeding's buck/doe.

Genetics is computed, never stored: Wright's inbreeding/relatedness are derived on
read from the pedigree links by reusing the platform ``pedigree_engine`` (built
for Aviculture) — no genetics columns and no duplicate math (ledger CON-M3-1).

Tables:
  rabbit_breeding — a mating attempt / breeding cycle
  rabbit_litter   — a litter produced at kindling
Alter:
  rabbit          — add ``litter_id`` (birth litter, SET NULL)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "067"
down_revision = "066"
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
    # ── Breeding cycle (Spec Part 3 §7) ────────────────────────────────────────
    op.create_table(
        "rabbit_breeding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("doe_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("buck_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("repeat_of_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column(
            "method",
            sa.String(20),
            nullable=False,
            server_default="natural",
            comment="natural | artificial",
        ),
        sa.Column("service_date", sa.Date, nullable=True),
        sa.Column("planned_kindling_date", sa.Date, nullable=True,
                  comment="FORECAST: service_date + gestation (breed-driven, default 31 days)."),
        sa.Column("pregnancy_checked_on", sa.Date, nullable=True),
        sa.Column(
            "pregnancy_result",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="unknown | pregnant | not_pregnant",
        ),
        sa.Column("nest_box_prepared_on", sa.Date, nullable=True),
        sa.Column("actual_kindling_date", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="planned",
            comment="planned | serviced | pregnant | not_pregnant | kindled | failed | closed | cancelled",
        ),
        sa.Column(
            "outcome",
            sa.String(20),
            nullable=True,
            comment="successful | failed | aborted | reabsorbed | unknown",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_breeding_status", "rabbit_breeding", ["status"])
    op.create_index("ix_rabbit_breeding_farm_status", "rabbit_breeding", ["farm_id", "status"])

    # ── Litter (Spec Part 3 §8) ────────────────────────────────────────────────
    op.create_table(
        "rabbit_litter",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breeding_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_breeding.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("doe_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("buck_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("litter_code", sa.String(50), nullable=False),
        sa.Column("kindling_date", sa.Date, nullable=False),
        sa.Column("total_kits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("live_kits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stillbirths", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fostered_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fostered_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weaned_kits", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mortality", sa.Integer, nullable=False, server_default="0",
                  comment="Pre-weaning kit deaths (recorded)."),
        sa.Column("avg_birth_weight_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("weaning_date", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | weaned | closed",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "litter_code", name="uq_rabbit_litter_farm_code"),
    )
    op.create_index("ix_rabbit_litter_status", "rabbit_litter", ["status"])

    # ── Kit → birth litter link (Spec Part 3 §8) ───────────────────────────────
    op.add_column(
        "rabbit",
        sa.Column("litter_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_litter.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_rabbit_litter_id", "rabbit", ["litter_id"])


def downgrade() -> None:
    op.drop_index("ix_rabbit_litter_id", table_name="rabbit")
    op.drop_column("rabbit", "litter_id")
    op.drop_table("rabbit_litter")
    op.drop_table("rabbit_breeding")
