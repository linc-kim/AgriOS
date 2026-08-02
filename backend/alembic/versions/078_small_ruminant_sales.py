"""Migration 078 — Small Ruminant Sales (Modules 18/19, Milestone 8)

Sales of animals and products (meat/milk/wool/fiber/manure), shared by goats and
sheep (Goat Doc 2 §16). Revenue is a RECORDED FACT on ``sr_sale`` — never posted to
the flock-scoped platform revenue ledger (frozen DB-07). Operational COSTS reuse
the shared ``expenses`` ledger (tagged by species) — no small-ruminant cost table.
The P&L / unit economics are computed on demand by the deterministic finance
engine; nothing is stored as a competing snapshot.

Table:
  sr_sale — a sale (animal or product); total_price is the recorded revenue fact
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sr_sale",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("sale_type", sa.String(15), nullable=False, server_default="live",
                  comment="live | breeding | meat | milk | wool | fiber | manure | cull | other"),
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("buyer_contact", sa.String(200), nullable=True),
        sa.Column("sale_date", sa.Date, nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(15), nullable=True),
        sa.Column("weight_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("invoice_reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_sr_sale_type", "sr_sale", ["sale_type"])


def downgrade() -> None:
    op.drop_table("sr_sale")
