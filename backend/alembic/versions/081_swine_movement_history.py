"""Migration 081 — Swine Movement History (Module 20, refinement)

A dedicated, append-only movement-history table (Swine Doc 2 §16, Doc 3 §19). The
pig's *current* pen/group lives on ``swine_pig``; this table is the permanent record
of every move a pig makes, so disease tracing, biosecurity investigations, welfare
monitoring and audit history have a first-class source of truth that a current-
assignment field can never replace. Occupancy remains DERIVED from ``swine_pig`` —
this table records transitions, not state.

Table:
  swine_movement — pig, movement_type, from/to pen, from/to group, moved_on, reason.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "081"
down_revision = "080"
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
        "swine_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("movement_type", sa.String(20), nullable=False, server_default="pen_transfer",
                  comment="arrival | pen_transfer | group_change | stage_transition | isolation | "
                  "farrowing_move | weaning_move | hospital | loading | farm_transfer | departure | other"),
        sa.Column("from_pen_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("to_pen_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("from_group_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("to_group_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("moved_on", sa.Date, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("moved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_movement_type", "swine_movement", ["movement_type"])


def downgrade() -> None:
    op.drop_table("swine_movement")
