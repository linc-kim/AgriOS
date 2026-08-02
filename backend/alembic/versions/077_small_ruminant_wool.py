"""Migration 077 — Small Ruminant Wool (Modules 18/19, Milestone 7)

Shearing sessions and per-animal fleece records for wool sheep (Sheep Doc §8).
Sheep-specific — availability is gated by the species ``produces_wool`` capability
(goats are rejected from this workspace). Clean weight and wool value are computed
by the deterministic engine from the recorded greasy weight, clean yield % and
price/kg — never stored. Wool sale revenue is handled by the Sales/Finance
milestone (M8).

Tables:
  sr_shearing — a shearing session (one animal or a group)
  sr_fleece   — a per-animal fleece record from a shearing
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "077"
down_revision = "076"
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
        "sr_shearing",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("shearing_date", sa.Date, nullable=False),
        sa.Column("method", sa.String(15), nullable=False, server_default="machine",
                  comment="machine | blade | hand | other"),
        sa.Column("shearer", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_fleece",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("shearing_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_shearing.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("shorn_on", sa.Date, nullable=False),
        sa.Column("greasy_weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("clean_yield_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("staple_length_cm", sa.Numeric(6, 2), nullable=True),
        sa.Column("micron", sa.Numeric(5, 2), nullable=True),
        sa.Column("grade", sa.String(15), nullable=False, server_default="unknown",
                  comment="superfine | fine | medium | strong | carpet | unclassed | unknown"),
        sa.Column("condition", sa.String(15), nullable=False, server_default="unknown",
                  comment="excellent | good | fair | poor | unknown"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("sr_fleece")
    op.drop_table("sr_shearing")
