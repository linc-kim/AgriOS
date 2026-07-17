"""Migration 041 — create feed management tables

Phase 3, Module 4 (Feed Management). A small event-sourced feed system:

  feed_suppliers        — a farm's feed vendor directory
  feed_inventory_items  — running stock per feed type + location, with a
                          weighted-average cost for valuation
  feed_transactions     — append-only ledger of every stock movement
                          (purchase / consumption / transfer / wastage /
                          adjustment)

All three carry an ``ai_context`` JSONB column so ARIA / Gemini can consume feed
history, consumption and supplier performance without a schema change.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── feed_suppliers ────────────────────────────────────────────────────────
    op.create_table(
        "feed_suppliers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("feed_types", JSONB, nullable=False, server_default="[]"),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    # ── feed_inventory_items ──────────────────────────────────────────────────
    op.create_table(
        "feed_inventory_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("feed_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=150), nullable=False, server_default="main_store"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="kg"),
        sa.Column("quantity_kg", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("avg_cost_per_kg", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("reorder_level_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feed_suppliers.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_feed_inventory_farm_type_loc",
        "feed_inventory_items",
        ["farm_id", "feed_type", "location"],
    )

    # ── feed_transactions ─────────────────────────────────────────────────────
    op.create_table(
        "feed_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feed_inventory_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "flock_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("txn_type", sa.String(length=20), nullable=False, index=True),
        sa.Column("direction", sa.SmallInteger(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False, index=True),
        sa.Column("quantity_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost_per_kg", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "supplier_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feed_suppliers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "counterparty_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feed_inventory_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("reference", sa.String(length=150), nullable=True),
        sa.Column("expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index(
        "ix_feed_txn_farm_date",
        "feed_transactions",
        ["farm_id", "txn_date"],
    )
    op.create_index(
        "ix_feed_txn_flock_type",
        "feed_transactions",
        ["flock_id", "txn_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_feed_txn_flock_type", table_name="feed_transactions")
    op.drop_index("ix_feed_txn_farm_date", table_name="feed_transactions")
    op.drop_table("feed_transactions")
    op.drop_index("ix_feed_inventory_farm_type_loc", table_name="feed_inventory_items")
    op.drop_table("feed_inventory_items")
    op.drop_table("feed_suppliers")
