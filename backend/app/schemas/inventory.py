"""
Greena — Inventory & Asset Management Schemas (Module 6).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

InventoryCategory = Literal[
    "feed", "medication", "vaccines", "equipment", "consumables",
    "cleaning_supplies", "ppe", "packaging", "fuel", "office_supplies",
    "spare_parts", "miscellaneous",
]
MovementType = Literal[
    "stock_in", "stock_out", "transfer_in", "transfer_out",
    "adjustment", "loss", "damage", "return", "consumption",
]
AssetType = Literal[
    "building", "vehicle", "machinery", "generator", "incubator",
    "feeder", "drinker", "solar_system", "computer", "phone", "tool",
]
AssetCondition = Literal["excellent", "good", "fair", "poor", "needs_repair", "decommissioned"]
MaintenanceStatus = Literal["scheduled", "in_progress", "completed", "overdue", "cancelled"]


# ── Suppliers ─────────────────────────────────────────────────────────────────

class SupplierCreate(AGRIOSSchema):
    name: str = Field(..., min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)
    products_supplied: list[str] = Field(default_factory=list)
    rating: Decimal | None = Field(default=None, ge=0, le=5, decimal_places=2)
    outstanding_balance: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class SupplierUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=400)
    products_supplied: list[str] | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5, decimal_places=2)
    outstanding_balance: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one(self) -> "SupplierUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class SupplierResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    products_supplied: list[str]
    rating: Decimal | None
    outstanding_balance: Decimal
    is_active: bool
    notes: str | None
    created_by: UUID | None
    total_spend: Decimal | None = None
    order_count: int | None = None


# ── Items ─────────────────────────────────────────────────────────────────────

class ItemCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    category: InventoryCategory
    description: str | None = Field(default=None, max_length=2000)
    sku: str | None = Field(default=None, max_length=80)
    barcode: str | None = Field(default=None, max_length=120)
    qr_code: str | None = Field(default=None, max_length=255)
    unit: str = Field(default="unit", max_length=20)
    location: str = Field(default="main_store", max_length=150)
    min_stock: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    reorder_level: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    supplier_id: UUID | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    opening_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    opening_cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=4)
    batch_number: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=120)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    warranty_expiry: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ItemUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: InventoryCategory | None = None
    sku: str | None = Field(default=None, max_length=80)
    barcode: str | None = Field(default=None, max_length=120)
    qr_code: str | None = Field(default=None, max_length=255)
    unit: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=150)
    min_stock: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    reorder_level: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    supplier_id: UUID | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    batch_number: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=120)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    warranty_expiry: date | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one(self) -> "ItemUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class ItemResponse(TimestampedSchema):
    farm_id: UUID
    sku: str | None
    barcode: str | None
    qr_code: str | None
    name: str
    description: str | None
    category: str
    unit: str
    quantity: Decimal
    min_stock: Decimal | None
    reorder_level: Decimal | None
    location: str
    supplier_id: UUID | None
    supplier_name: str | None = None
    purchase_price: Decimal | None
    avg_cost: Decimal
    current_value: Decimal
    batch_number: str | None
    serial_number: str | None
    manufacture_date: date | None
    expiry_date: date | None
    warranty_expiry: date | None
    is_active: bool
    notes: str | None
    is_low_stock: bool
    is_out_of_stock: bool
    is_expired: bool
    is_expiring_soon: bool
    days_to_expiry: int | None
    created_by: UUID | None


# ── Movements ─────────────────────────────────────────────────────────────────

class MovementCreate(AGRIOSSchema):
    item_id: UUID
    movement_type: MovementType
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_cost: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    movement_date: date | None = None
    reason: str | None = Field(default=None, max_length=255)
    reference: str | None = Field(default=None, max_length=150)
    location_to: str | None = Field(default=None, max_length=150)
    supplier_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class MovementResponse(TimestampedSchema):
    farm_id: UUID
    item_id: UUID
    item_name: str | None = None
    category: str | None = None
    movement_type: str
    direction: int
    quantity: Decimal
    qty_before: Decimal
    qty_after: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    reason: str | None
    reference: str | None
    location_from: str | None
    location_to: str | None
    expense_id: UUID | None
    notes: str | None
    created_by: UUID | None


# ── Assets ────────────────────────────────────────────────────────────────────

class AssetCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    asset_type: AssetType
    description: str | None = Field(default=None, max_length=2000)
    serial_number: str | None = Field(default=None, max_length=120)
    purchase_date: date
    purchase_price: Decimal = Field(..., ge=0, decimal_places=2)
    depreciation_method: Literal["straight_line", "none"] = "straight_line"
    useful_life_years: int | None = Field(default=None, ge=1, le=100)
    salvage_value: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    warranty_expiry: date | None = None
    location: str | None = Field(default=None, max_length=150)
    assigned_user_id: UUID | None = None
    condition: AssetCondition = "good"
    service_interval_days: int | None = Field(default=None, ge=1, le=3650)
    last_service_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("purchase_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Purchase date cannot be in the future.")
        return v


class AssetUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    serial_number: str | None = Field(default=None, max_length=120)
    depreciation_method: Literal["straight_line", "none"] | None = None
    useful_life_years: int | None = Field(default=None, ge=1, le=100)
    salvage_value: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    warranty_expiry: date | None = None
    location: str | None = Field(default=None, max_length=150)
    assigned_user_id: UUID | None = None
    condition: AssetCondition | None = None
    service_interval_days: int | None = Field(default=None, ge=1, le=3650)
    last_service_date: date | None = None
    next_service_date: date | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one(self) -> "AssetUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class AssetResponse(TimestampedSchema):
    farm_id: UUID
    asset_type: str
    name: str
    description: str | None
    serial_number: str | None
    purchase_date: date
    purchase_price: Decimal
    depreciation_method: str
    useful_life_years: int | None
    salvage_value: Decimal
    warranty_expiry: date | None
    location: str | None
    assigned_user_id: UUID | None
    condition: str
    service_interval_days: int | None
    last_service_date: date | None
    next_service_date: date | None
    is_active: bool
    notes: str | None
    age_days: int
    current_value: Decimal
    accumulated_depreciation: Decimal
    is_maintenance_due: bool
    is_warranty_expiring: bool
    created_by: UUID | None


# ── Maintenance ───────────────────────────────────────────────────────────────

class MaintenanceCreate(AGRIOSSchema):
    asset_id: UUID
    title: str = Field(..., min_length=2, max_length=200)
    status: MaintenanceStatus = "scheduled"
    scheduled_date: date | None = None
    completed_date: date | None = None
    cost: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    parts_used: list[str] = Field(default_factory=list)
    technician: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    attachments: list[str] = Field(default_factory=list)


class MaintenanceUpdate(AGRIOSSchema):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    status: MaintenanceStatus | None = None
    scheduled_date: date | None = None
    completed_date: date | None = None
    cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    parts_used: list[str] | None = None
    technician: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    attachments: list[str] | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "MaintenanceUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class MaintenanceResponse(TimestampedSchema):
    farm_id: UUID
    asset_id: UUID
    asset_name: str | None = None
    title: str
    status: str
    scheduled_date: date | None
    completed_date: date | None
    cost: Decimal
    parts_used: list[str]
    technician: str | None
    notes: str | None
    attachments: list[str]
    expense_id: UUID | None
    created_by: UUID | None


# ── Dashboard / alerts / analytics ────────────────────────────────────────────

class CategoryValuation(AGRIOSSchema):
    category: str
    item_count: int
    total_quantity: Decimal
    total_value: Decimal


class InventoryAlert(AGRIOSSchema):
    kind: str            # low_stock | out_of_stock | expiring_soon | expired | warranty_expiry | maintenance_due
    severity: str        # info | warning | critical
    ref_id: UUID
    ref_type: str        # item | asset | maintenance
    title: str
    detail: str


class ReorderRecommendation(AGRIOSSchema):
    item_id: UUID
    name: str
    category: str
    quantity: Decimal
    reorder_level: Decimal | None
    avg_daily_consumption: Decimal
    suggested_order_qty: Decimal
    supplier_name: str | None


class MovementTrendPoint(AGRIOSSchema):
    period: str
    stock_in: Decimal
    stock_out: Decimal


class ItemVelocity(AGRIOSSchema):
    item_id: UUID
    name: str
    category: str
    consumed_qty: Decimal
    consumed_value: Decimal


class SupplierPerformance(AGRIOSSchema):
    supplier_id: UUID
    name: str
    total_spend: Decimal
    order_count: int
    rating: Decimal | None
    outstanding_balance: Decimal


class InventoryDashboard(AGRIOSSchema):
    item_count: int
    total_inventory_value: Decimal
    low_stock_count: int
    out_of_stock_count: int
    expiring_count: int
    expired_count: int
    asset_count: int
    total_asset_value: Decimal
    maintenance_due_count: int
    window_days: int
    stock_in_value: Decimal
    stock_out_value: Decimal
    category_valuation: list[CategoryValuation]
    alerts: list[InventoryAlert]
    recent_movements: list[MovementResponse]


class InventoryAnalytics(AGRIOSSchema):
    window_days: int
    inventory_valuation: Decimal
    asset_valuation: Decimal
    total_depreciation: Decimal
    maintenance_cost: Decimal
    category_valuation: list[CategoryValuation]
    movement_trend: list[MovementTrendPoint]       # monthly
    most_consumed: list[ItemVelocity]
    fast_moving: list[ItemVelocity]
    slow_moving: list[ItemVelocity]
    dead_stock: list[ItemResponse]
    reorder_recommendations: list[ReorderRecommendation]
    supplier_performance: list[SupplierPerformance]


class InventoryAIContext(AGRIOSSchema):
    farm_id: UUID
    generated_at: datetime
    inventory_value: Decimal
    asset_value: Decimal
    items: list[dict]
    recent_movements: list[dict]
    alerts: list[dict]
    supplier_performance: list[dict]
    reorder_recommendations: list[dict]
