"""Migration 086 — Swine Sales & Finance (Module 20, Milestone 8)

Swine finance is an ANALYTICS layer over the shared Finance engine (Swine Doc 2 §17,
Doc 3 §12, Doc 5 §5) — not a parallel accounting system. This migration adds only the
sale record; costs and P&L reuse existing platform infrastructure:

  * ``swine_sale`` — the RECORDED revenue fact (frozen DB-07 keeps the platform
    revenue ledger flock-scoped, so animal-sale revenue lives here).
  * Operating costs post ONCE to the shared ``expenses`` ledger tagged
    ``metadata.module="swine"`` (no swine cost table).
  * Feed / medication costs come from their source records (already expensed at
    Inventory stock-in) and are never re-posted.
  * Profit / margin / ROI / per-unit costs are COMPUTED on demand — nothing stored.

Table:
  swine_sale — pig/product sale (multiple sale types), a revenue fact.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "086"
down_revision = "085"
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
        "swine_sale",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sale_type", sa.String(20), nullable=False, server_default="market",
                  comment="market | breeding_stock | cull | piglet | weaner | internal_transfer | product | other"),
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("buyer_contact", sa.String(200), nullable=True),
        sa.Column("destination", sa.String(200), nullable=True),
        sa.Column("sale_date", sa.Date, nullable=False),
        sa.Column("head_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(15), nullable=True),
        sa.Column("weight_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(14, 2), nullable=False,
                  comment="Recorded revenue fact (DB-07); never re-posted to the platform revenue ledger."),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("invoice_reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_sale_sale_date", "swine_sale", ["sale_date"])
    op.create_index("ix_swine_sale_sale_type", "swine_sale", ["sale_type"])


def downgrade() -> None:
    op.drop_table("swine_sale")
