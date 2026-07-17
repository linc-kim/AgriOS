"""
Greena — Inventory & Asset Management Module Models (Module 6).
Migration 044.

A general store/inventory system (distinct from the Feed module, which manages
feed specifically) plus fixed-asset tracking and maintenance:

  inventory_suppliers   — general vendor directory
  inventory_items       — any stocked item across 12 categories
  inventory_movements   — append-only ledger of every stock movement
  assets                — fixed assets with straight-line depreciation
  asset_maintenance     — maintenance schedule + history

All carry an ``ai_context`` JSONB column for ARIA / Gemini. Everything is
farm-scoped (DB-04 Frozen) and soft-deleted (DB-02 Frozen).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.farm import Farm

# The 12 inventory categories (stored as free strings for extensibility).
INVENTORY_CATEGORIES = (
    "feed", "medication", "vaccines", "equipment", "consumables",
    "cleaning_supplies", "ppe", "packaging", "fuel", "office_supplies",
    "spare_parts", "miscellaneous",
)

# Movement verbs. direction (+1 in / -1 out) is set by the service.
INVENTORY_MOVEMENT_TYPES = (
    "stock_in", "stock_out", "transfer_in", "transfer_out",
    "adjustment", "loss", "damage", "return", "consumption",
)

ASSET_TYPES = (
    "building", "vehicle", "machinery", "generator", "incubator",
    "feeder", "drinker", "solar_system", "computer", "phone", "tool",
)


class InventorySupplier(AGRIOSBase):
    """A general vendor the farm buys inventory / assets from."""

    __tablename__ = "inventory_suppliers"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    products_supplied: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")


class InventoryItem(AGRIOSBase):
    """A stocked item in any of the 12 inventory categories."""

    __tablename__ = "inventory_items"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    barcode: Mapped[str | None] = mapped_column(String(120), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, server_default="unit")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"), server_default="0")
    min_stock: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    reorder_level: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    location: Mapped[str] = mapped_column(String(150), nullable=False, server_default="main_store")
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0")
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    warranty_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    supplier: Mapped["InventorySupplier | None"] = relationship(
        "InventorySupplier", foreign_keys=[supplier_id], lazy="noload"
    )

    @property
    def current_value(self) -> Decimal:
        return (self.quantity * self.avg_cost).quantize(Decimal("0.01"))

    @property
    def is_low_stock(self) -> bool:
        threshold = self.reorder_level if self.reorder_level is not None else self.min_stock
        if threshold is None:
            return False
        return self.quantity <= threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity <= 0

    @property
    def days_to_expiry(self) -> int | None:
        if self.expiry_date is None:
            return None
        from datetime import date as _d
        return (self.expiry_date - _d.today()).days

    @property
    def is_expired(self) -> bool:
        d = self.days_to_expiry
        return d is not None and d < 0

    @property
    def is_expiring_soon(self) -> bool:
        d = self.days_to_expiry
        return d is not None and 0 <= d <= 30


class InventoryMovement(AGRIOSBase):
    """One stock movement. Append-only ledger behind every item quantity."""

    __tablename__ = "inventory_movements"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    qty_before: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    qty_after: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0")
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location_from: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location_to: Mapped[str | None] = mapped_column(String(150), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    ai_context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    item: Mapped["InventoryItem"] = relationship("InventoryItem", foreign_keys=[item_id], lazy="noload")


class Asset(AGRIOSBase):
    """A fixed farm asset with straight-line depreciation."""

    __tablename__ = "assets"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    depreciation_method: Mapped[str] = mapped_column(String(20), nullable=False, server_default="straight_line")
    useful_life_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    warranty_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    condition: Mapped[str] = mapped_column(String(20), nullable=False, server_default="good")
    service_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")

    @property
    def age_days(self) -> int:
        from datetime import date as _d
        return max((_d.today() - self.purchase_date).days, 0)

    @property
    def current_value(self) -> Decimal:
        """Straight-line depreciated value, floored at salvage value."""
        if self.depreciation_method != "straight_line" or not self.useful_life_years:
            return self.purchase_price.quantize(Decimal("0.01"))
        life_days = Decimal(self.useful_life_years) * Decimal("365")
        if life_days <= 0:
            return self.purchase_price.quantize(Decimal("0.01"))
        depreciable = self.purchase_price - self.salvage_value
        depreciated = depreciable * (Decimal(self.age_days) / life_days)
        value = self.purchase_price - depreciated
        if value < self.salvage_value:
            value = self.salvage_value
        return value.quantize(Decimal("0.01"))

    @property
    def accumulated_depreciation(self) -> Decimal:
        return (self.purchase_price - self.current_value).quantize(Decimal("0.01"))

    @property
    def is_maintenance_due(self) -> bool:
        if self.next_service_date is None:
            return False
        from datetime import date as _d, timedelta
        return self.next_service_date <= _d.today() + timedelta(days=7)

    @property
    def is_warranty_expiring(self) -> bool:
        if self.warranty_expiry is None:
            return False
        from datetime import date as _d, timedelta
        return self.warranty_expiry <= _d.today() + timedelta(days=30)


class AssetMaintenance(AGRIOSBase):
    """A maintenance record (scheduled or completed) for an asset."""

    __tablename__ = "asset_maintenance"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="scheduled", index=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    parts_used: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    technician: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    asset: Mapped["Asset"] = relationship("Asset", foreign_keys=[asset_id], lazy="noload")
