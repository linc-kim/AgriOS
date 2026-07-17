"""Migration 044 — create inventory & asset management tables

Module 6. A general store/inventory system plus fixed-asset tracking and
maintenance:

  inventory_suppliers   — general vendor directory
  inventory_items       — any stocked item across 12 categories
  inventory_movements   — append-only stock-movement ledger
  assets                — fixed assets with straight-line depreciation
  asset_maintenance     — maintenance schedule + history
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def _base_cols():
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.create_table(
        "inventory_suppliers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("address", sa.String(400), nullable=True),
        sa.Column("products_supplied", JSONB, nullable=False, server_default="[]"),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("outstanding_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base_cols(),
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sku", sa.String(80), nullable=True, index=True),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("qr_code", sa.String(255), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(40), nullable=False, index=True),
        sa.Column("unit", sa.String(20), nullable=False, server_default="unit"),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("min_stock", sa.Numeric(14, 3), nullable=True),
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=True),
        sa.Column("location", sa.String(150), nullable=False, server_default="main_store"),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("purchase_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("avg_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("serial_number", sa.String(120), nullable=True),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True, index=True),
        sa.Column("warranty_expiry", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base_cols(),
    )
    op.create_index("ix_inventory_items_farm_cat", "inventory_items", ["farm_id", "category"])

    op.create_table(
        "inventory_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("movement_type", sa.String(20), nullable=False, index=True),
        sa.Column("direction", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("qty_before", sa.Numeric(14, 3), nullable=False),
        sa.Column("qty_after", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("reference", sa.String(150), nullable=True),
        sa.Column("location_from", sa.String(150), nullable=True),
        sa.Column("location_to", sa.String(150), nullable=True),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base_cols(),
    )
    op.create_index("ix_inventory_moves_item_type", "inventory_movements", ["item_id", "movement_type"])

    op.create_table(
        "assets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("asset_type", sa.String(40), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("serial_number", sa.String(120), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("purchase_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("depreciation_method", sa.String(20), nullable=False, server_default="straight_line"),
        sa.Column("useful_life_years", sa.Integer(), nullable=True),
        sa.Column("salvage_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("warranty_expiry", sa.Date(), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column("assigned_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("condition", sa.String(20), nullable=False, server_default="good"),
        sa.Column("service_interval_days", sa.Integer(), nullable=True),
        sa.Column("last_service_date", sa.Date(), nullable=True),
        sa.Column("next_service_date", sa.Date(), nullable=True, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("ai_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base_cols(),
    )

    op.create_table(
        "asset_maintenance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("asset_id", UUID(as_uuid=True), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled", index=True),
        sa.Column("scheduled_date", sa.Date(), nullable=True, index=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("parts_used", JSONB, nullable=False, server_default="[]"),
        sa.Column("technician", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attachments", JSONB, nullable=False, server_default="[]"),
        sa.Column("expense_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base_cols(),
    )


def downgrade() -> None:
    op.drop_table("asset_maintenance")
    op.drop_table("assets")
    op.drop_index("ix_inventory_moves_item_type", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_index("ix_inventory_items_farm_cat", table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_table("inventory_suppliers")
