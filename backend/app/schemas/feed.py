"""
Greena — Feed Management Module Pydantic Schemas (Phase 3, Module 4).

Inputs:
  FeedSupplierCreate / FeedSupplierUpdate
  FeedInventoryItemCreate / FeedInventoryItemUpdate
  FeedPurchaseInput      — buy feed into a store (creates/updates an item)
  FeedConsumptionInput   — feed a flock (draws stock down)
  FeedTransferInput      — move stock between locations
  FeedWastageInput       — write off spoiled/lost stock

Outputs:
  FeedSupplierResponse
  FeedInventoryItemResponse  (with derived stock_value + low-stock flag)
  FeedTransactionResponse
  FeedDashboardResponse
  FeedReorderAlert
  FeedAnalyticsResponse (+ nested point/row schemas)
  FeedAIContext         — structured payload for ARIA / Gemini
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

# Common Kenyan poultry feed types (free text is also accepted).
KNOWN_FEED_TYPES = [
    "chick_mash",
    "broiler_starter",
    "broiler_finisher",
    "grower_mash",
    "layer_mash",
    "kienyeji_mash",
    "supplement",
]

WASTAGE_REASONS = [
    "spoilage",
    "spillage",
    "contamination",
    "pest_damage",
    "moisture_mould",
    "theft",
    "expired",
    "other",
]


# ── Suppliers ─────────────────────────────────────────────────────────────────

class FeedSupplierCreate(AGRIOSSchema):
    name: str = Field(..., min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=255)
    feed_types: list[str] = Field(default_factory=list)
    rating: Decimal | None = Field(default=None, ge=0, le=5, decimal_places=2)
    notes: str | None = Field(default=None, max_length=2000)


class FeedSupplierUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=255)
    feed_types: list[str] | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5, decimal_places=2)
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one(self) -> "FeedSupplierUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class FeedSupplierResponse(TimestampedSchema):
    farm_id: UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    location: str | None
    feed_types: list[str]
    rating: Decimal | None
    is_active: bool
    notes: str | None
    created_by: UUID | None
    # Enriched by the service (spend history) — optional so the plain ORM
    # object still validates.
    total_spend_kes: Decimal | None = None
    purchase_count: int | None = None
    total_kg_purchased: Decimal | None = None


# ── Inventory items ───────────────────────────────────────────────────────────

class FeedInventoryItemCreate(AGRIOSSchema):
    feed_type: str = Field(..., min_length=2, max_length=100)
    name: str | None = Field(default=None, max_length=200)
    brand: str | None = Field(default=None, max_length=150)
    batch_number: str | None = Field(default=None, max_length=100)
    expiry_date: date | None = None
    location: str = Field(default="main_store", min_length=1, max_length=150)
    unit: str = Field(default="kg", max_length=20)
    reorder_level_kg: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    supplier_id: UUID | None = None
    opening_quantity_kg: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    opening_cost_per_kg: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=4)
    notes: str | None = Field(default=None, max_length=2000)


class FeedInventoryItemUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, max_length=200)
    brand: str | None = Field(default=None, max_length=150)
    batch_number: str | None = Field(default=None, max_length=100)
    expiry_date: date | None = None
    location: str | None = Field(default=None, min_length=1, max_length=150)
    reorder_level_kg: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    supplier_id: UUID | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one(self) -> "FeedInventoryItemUpdate":
        if all(getattr(self, f) is None for f in self.model_fields):
            raise ValueError("Provide at least one field to update.")
        return self


class FeedInventoryItemResponse(TimestampedSchema):
    farm_id: UUID
    feed_type: str
    name: str | None
    brand: str | None
    batch_number: str | None
    expiry_date: date | None
    location: str
    unit: str
    quantity_kg: Decimal
    avg_cost_per_kg: Decimal
    reorder_level_kg: Decimal | None
    supplier_id: UUID | None
    supplier_name: str | None = None
    is_active: bool
    notes: str | None
    stock_value_kes: Decimal
    is_low_stock: bool
    days_to_expiry: int | None
    is_expired: bool
    is_expiring_soon: bool
    created_by: UUID | None


# ── Stock movements ───────────────────────────────────────────────────────────

class FeedPurchaseInput(AGRIOSSchema):
    """Buy feed into a store. Targets an existing item, or is created by feed_type+location."""
    item_id: UUID | None = Field(
        default=None, description="Existing inventory item; omit to auto-create by type+location."
    )
    feed_type: str | None = Field(default=None, max_length=100)
    location: str = Field(default="main_store", max_length=150)
    quantity_kg: Decimal = Field(..., gt=0, decimal_places=3)
    price_per_kg: Decimal = Field(..., ge=0, decimal_places=4)
    purchase_date: date
    supplier_id: UUID | None = None
    supplier_name: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=150, description="Invoice / delivery reference.")
    delivery_date: date | None = None
    brand: str | None = Field(default=None, max_length=150)
    batch_number: str | None = Field(default=None, max_length=100)
    expiry_date: date | None = None
    flock_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("purchase_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Purchase date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def item_or_type(self) -> "FeedPurchaseInput":
        if self.item_id is None and not self.feed_type:
            raise ValueError("Provide item_id or feed_type.")
        return self


class FeedConsumptionInput(AGRIOSSchema):
    """Feed a flock. Draws stock down at the item's weighted-average cost."""
    item_id: UUID
    flock_id: UUID
    quantity_kg: Decimal = Field(..., gt=0, decimal_places=3)
    consumption_date: date
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("consumption_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Consumption date cannot be in the future.")
        return v


class FeedTransferInput(AGRIOSSchema):
    """Move stock from one item/location to another (value moves, no new cost)."""
    from_item_id: UUID
    to_location: str = Field(..., min_length=1, max_length=150)
    quantity_kg: Decimal = Field(..., gt=0, decimal_places=3)
    transfer_date: date
    reason: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("transfer_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Transfer date cannot be in the future.")
        return v


class FeedWastageInput(AGRIOSSchema):
    """Write off spoiled/lost stock. Records the value loss."""
    item_id: UUID
    quantity_kg: Decimal = Field(..., gt=0, decimal_places=3)
    wastage_date: date
    reason: str = Field(default="other", max_length=50)
    flock_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("wastage_date")
    @classmethod
    def not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Wastage date cannot be in the future.")
        return v


class FeedTransactionResponse(TimestampedSchema):
    farm_id: UUID
    item_id: UUID
    flock_id: UUID | None
    txn_type: str
    direction: int
    txn_date: date
    quantity_kg: Decimal
    unit_cost_per_kg: Decimal
    total_cost: Decimal
    supplier_id: UUID | None
    counterparty_item_id: UUID | None
    reason: str | None
    reference: str | None
    expense_id: UUID | None
    notes: str | None
    created_by: UUID | None
    # Enriched for list rendering.
    feed_type: str | None = None
    location: str | None = None
    flock_name: str | None = None


# ── Dashboard / alerts ────────────────────────────────────────────────────────

class FeedReorderAlert(AGRIOSSchema):
    item_id: UUID
    feed_type: str
    location: str
    quantity_kg: Decimal
    reorder_level_kg: Decimal
    shortfall_kg: Decimal
    supplier_id: UUID | None
    supplier_name: str | None


class FeedExpiryAlert(AGRIOSSchema):
    item_id: UUID
    feed_type: str
    location: str
    batch_number: str | None
    quantity_kg: Decimal
    expiry_date: date
    days_to_expiry: int
    is_expired: bool


class FeedTopFlock(AGRIOSSchema):
    flock_id: UUID
    flock_name: str
    consumed_kg: Decimal
    feed_cost_kes: Decimal


class FeedForecastItem(AGRIOSSchema):
    item_id: UUID
    feed_type: str
    location: str
    quantity_kg: Decimal
    avg_daily_consumption_kg: Decimal
    days_remaining: int | None          # None = no recent consumption (can't forecast)
    depletion_date: date | None
    recommended_purchase_date: date | None
    reorder_level_kg: Decimal | None
    status: str                         # ok | reorder_soon | critical | depleting | no_data


class FeedForecastResponse(AGRIOSSchema):
    window_days: int
    lead_time_days: int
    items: list[FeedForecastItem]
    soonest_depletion_date: date | None
    next_purchase_date: date | None
    items_needing_purchase: int


class FeedDashboardResponse(AGRIOSSchema):
    total_stock_kg: Decimal
    total_stock_value_kes: Decimal
    item_count: int
    low_stock_count: int
    expiring_count: int
    # Rolling window (default 30 days).
    window_days: int
    purchased_kg: Decimal
    purchased_cost_kes: Decimal
    consumed_kg: Decimal
    consumed_cost_kes: Decimal
    consumed_today_kg: Decimal
    consumed_week_kg: Decimal
    wasted_kg: Decimal
    wasted_cost_kes: Decimal
    reorder_alerts: list[FeedReorderAlert]
    expiry_alerts: list[FeedExpiryAlert]
    top_flocks: list[FeedTopFlock]
    forecast: FeedForecastResponse
    items: list[FeedInventoryItemResponse]
    recent_transactions: list[FeedTransactionResponse]


# ── Analytics ─────────────────────────────────────────────────────────────────

class FeedUsagePoint(AGRIOSSchema):
    period: str            # e.g. "2026-07-01"
    consumed_kg: Decimal
    consumed_cost_kes: Decimal
    purchased_kg: Decimal
    wasted_kg: Decimal


class FeedTypeBreakdown(AGRIOSSchema):
    feed_type: str
    consumed_kg: Decimal
    consumed_cost_kes: Decimal
    pct_of_total: Decimal | None


class FeedSupplierSpend(AGRIOSSchema):
    supplier_id: UUID | None
    supplier_name: str
    total_kg: Decimal
    total_cost_kes: Decimal
    purchase_count: int


class FeedFlockCost(AGRIOSSchema):
    flock_id: UUID
    flock_name: str
    consumed_kg: Decimal
    feed_cost_kes: Decimal
    live_birds: int
    cost_per_bird_kes: Decimal | None
    eggs_collected: int
    cost_per_egg_kes: Decimal | None
    # Feed conversion — computed from the latest weigh-in biomass.
    weight_gain_kg: Decimal | None = None
    fcr: Decimal | None = None
    cost_per_kg_gain_kes: Decimal | None = None


class FeedAnalyticsResponse(AGRIOSSchema):
    window_days: int
    total_consumed_kg: Decimal
    total_consumed_cost_kes: Decimal
    total_wasted_kg: Decimal
    wastage_pct: Decimal | None
    avg_cost_per_kg: Decimal | None
    usage_trend: list[FeedUsagePoint]
    by_feed_type: list[FeedTypeBreakdown]
    by_supplier: list[FeedSupplierSpend]
    by_flock: list[FeedFlockCost]


# ── AI-ready context ──────────────────────────────────────────────────────────

class FeedAIContext(AGRIOSSchema):
    """Structured feed intelligence for ARIA / Gemini (no free-text prose)."""
    farm_id: UUID
    generated_at: datetime
    window_days: int
    inventory: list[dict]
    feed_history: list[dict]
    consumption: list[dict]
    costs: dict
    supplier_history: list[dict]
    feed_conversions: list[dict]
    performance: dict
