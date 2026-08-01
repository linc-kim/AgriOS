"""Migration 070 — Rabbit Sales (Module 17, Milestone 6)

Sales records (Spec Part 2 §16, Part 3 §15). Sale **revenue is a recorded fact**
on ``rabbit_sale`` — it is never posted to ``revenue_records`` because that ledger
is flock-scoped (frozen DB-07); this mirrors the Aviculture/BSF finance pattern
(ledger CON-M6-2). Operational **costs** reuse the shared ``expenses`` ledger via
``finance_service`` tagged ``metadata.module='rabbit'`` — no rabbit finance table
for costs, no change to the Finance platform.

P&L and unit-economics are computed on demand by the deterministic
``rabbit_finance_engine`` from recorded facts; nothing is stored as a snapshot.

Table:
  rabbit_sale — a sale of a rabbit or a rabbit product (meat/fiber/manure)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "070"
down_revision = "069"
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
        "rabbit_sale",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="NULL for product sales (meat/fiber/manure) not tied to one rabbit."),
        sa.Column(
            "sale_type",
            sa.String(20),
            nullable=False,
            server_default="live",
            comment="live | breeding_stock | pet | meat | fiber | manure | other",
        ),
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("buyer_contact", sa.String(200), nullable=True),
        sa.Column("sale_date", sa.Date, nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("weight_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        # The recorded revenue fact (Spec Part 3 §15). Never posted to revenue_records.
        sa.Column("total_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("invoice_reference", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_sale_farm_date", "rabbit_sale", ["farm_id", "sale_date"])
    op.create_index("ix_rabbit_sale_type", "rabbit_sale", ["sale_type"])


def downgrade() -> None:
    op.drop_table("rabbit_sale")
