"""Migration 056 — Aviculture Breeding Engine (Module 15, Part 4)

Part 1 stored the deterministic pedigree links (``avi_bird.sire_id/dam_id``) and
the ``avi_pair`` entity. Part 4 adds the strategic breeding layer on top —
programs, goals and pair history — while pedigrees, relatedness and inbreeding
remain **computed live** by the pure ``pedigree_engine`` and are never stored
(storing a derived genetic value would duplicate a calculation, Doc 14 §5).

New tables:
  avi_breeding_program — an objective-driven breeding programme (Doc 02 §11)
  avi_breeding_goal    — measurable goals within a programme
  avi_pair_event       — pair timeline / history (Doc 03 §5 PairHistory)

Alter:
  avi_pair.program_id  — optional link from a pair to its breeding programme
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "056"
down_revision = "055"
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
        "avi_breeding_program",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_species.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(30), nullable=False, server_default="outcross",
                  comment="outcross | line_breeding | inbreeding | conservation | exhibition | mixed"),
        sa.Column("target_traits", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | paused | completed | archived"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "avi_breeding_goal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("program_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_breeding_program.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("target_metric", sa.String(100), nullable=True),
        sa.Column("target_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open",
                  comment="open | achieved | abandoned"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_base(),
    )

    op.create_table(
        "avi_pair_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pair_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_pair.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(40), nullable=False,
                  comment="formed | suspended | resumed | dissolved | clutch | note"),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_pair_event_time", "avi_pair_event", ["pair_id", "occurred_on"])

    op.add_column("avi_pair", sa.Column(
        "program_id", UUID(as_uuid=True),
        sa.ForeignKey("avi_breeding_program.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_avi_pair_program", "avi_pair", ["program_id"])


def downgrade() -> None:
    op.drop_index("ix_avi_pair_program", table_name="avi_pair")
    op.drop_column("avi_pair", "program_id")
    op.drop_table("avi_pair_event")
    op.drop_table("avi_breeding_goal")
    op.drop_table("avi_breeding_program")
