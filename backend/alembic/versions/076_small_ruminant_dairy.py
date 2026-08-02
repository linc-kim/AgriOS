"""Migration 076 — Small Ruminant Dairy (Modules 18/19, Milestone 6)

Lactation cycles and milk-yield records for dairy females (Goat Doc 2 §10). Goats
are the primary dairy species; dairy sheep are supported too — availability is
gated by the species ``produces_milk`` capability, not hard-coded to goats. Yields
(total, peak, 305-day projection) are computed by the deterministic engine from the
milk records — never stored. Quantities in litres.

Tables:
  sr_lactation   — a lactation cycle (freshening → dry-off)
  sr_milk_record — a milking-session / daily yield measurement
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "076"
down_revision = "075"
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
        "sr_lactation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("birth_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_birth.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("lactation_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("freshening_date", sa.Date, nullable=False),
        sa.Column("expected_dry_off_date", sa.Date, nullable=True, comment="FORECAST, never a recorded fact."),
        sa.Column("dry_off_date", sa.Date, nullable=True),
        sa.Column("milking_frequency", sa.Integer, nullable=False, server_default="2"),
        sa.Column("status", sa.String(15), nullable=False, server_default="active",
                  comment="active | dry | completed"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_milk_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("lactation_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_lactation.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("session", sa.String(10), nullable=False, server_default="total",
                  comment="am | pm | midday | total | once"),
        sa.Column("quantity_liters", sa.Numeric(8, 3), nullable=False),
        sa.Column("fat_pct", sa.Numeric(4, 2), nullable=True),
        sa.Column("protein_pct", sa.Numeric(4, 2), nullable=True),
        sa.Column("somatic_cell_count", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("sr_milk_record")
    op.drop_table("sr_lactation")
