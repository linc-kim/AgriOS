"""
Greena — Finance Module Pydantic Schemas
Covers Migrations 019-022:
  ExpenseCategory  (019)
  Expense          (020)
  RevenueRecord    (021)
  FinancialSnapshot (022)

Input schemas:
  ExpenseCategoryCreate
  ExpenseCreate / ExpenseUpdate
  RevenueRecordCreate / RevenueRecordUpdate

Output schemas:
  ExpenseCategoryResponse
  ExpenseResponse
  ExpenseSummaryItem         — condensed for list views
  RevenueRecordResponse
  RevenueSummaryItem
  FinancialSnapshotResponse  — full P&L
  FinanceDashboardResponse   — dashboard overview
  FlockPnLResponse           — per-flock P&L card

Calculator schemas (no DB):
  FCRCalculatorInput / FCRCalculatorResult
  ProfitProjectionInput / ProfitProjectionResult
  BreakEvenInput / BreakEvenResult
  FeedNeedsInput / FeedNeedsResult
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema


# ── ExpenseCategory ───────────────────────────────────────────────────────────

class ExpenseCategoryCreate(AGRIOSSchema):
    """Create a custom (non-system) expense category for a farm."""
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9_]+$")
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("slug")
    @classmethod
    def slug_no_spaces(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Slug cannot contain spaces — use underscores")
        return v.lower()


class ExpenseCategoryResponse(AGRIOSSchema):
    id: UUID
    farm_id: Optional[UUID]
    name: str
    slug: str
    icon: Optional[str]
    color: Optional[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime


# ── Expense ───────────────────────────────────────────────────────────────────

PAYMENT_METHODS = Literal["cash", "mpesa", "bank_transfer", "credit"]


class ExpenseCreate(AGRIOSSchema):
    """Record a new expense."""
    flock_id: Optional[UUID] = None
    category_id: UUID
    expense_date: date
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    description: str = Field(..., min_length=2, max_length=300)
    payment_method: Optional[PAYMENT_METHODS] = None
    receipt_url: Optional[str] = Field(None, max_length=500)
    supplier: Optional[str] = Field(None, max_length=200)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None

    @field_validator("expense_date")
    @classmethod
    def expense_date_not_future(cls, v: date) -> date:
        from datetime import date as dt_date
        if v > dt_date.today():
            raise ValueError("Expense date cannot be in the future")
        return v

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v


class ExpenseUpdate(AGRIOSSchema):
    """Update an existing expense. At least one field required."""
    category_id: Optional[UUID] = None
    flock_id: Optional[UUID] = None
    expense_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    description: Optional[str] = Field(None, min_length=2, max_length=300)
    payment_method: Optional[PAYMENT_METHODS] = None
    supplier: Optional[str] = Field(None, max_length=200)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    correction_reason: str = Field(..., min_length=5, max_length=500)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ExpenseUpdate":
        updatable = [
            "category_id", "flock_id", "expense_date", "amount",
            "description", "payment_method", "supplier", "quantity", "unit", "notes",
        ]
        if not any(getattr(self, f) is not None for f in updatable):
            raise ValueError("At least one field must be provided for update")
        return self


class ExpenseSummaryItem(AGRIOSSchema):
    """Condensed expense for list views."""
    id: UUID
    expense_date: date
    amount: Decimal
    description: str
    category_name: str
    category_icon: Optional[str]
    category_color: Optional[str]
    payment_method: Optional[str]
    flock_id: Optional[UUID]


class ExpenseResponse(AGRIOSSchema):
    """Full expense detail."""
    id: UUID
    farm_id: UUID
    flock_id: Optional[UUID]
    category_id: UUID
    category: ExpenseCategoryResponse
    expense_date: date
    amount: Decimal
    description: str
    payment_method: Optional[str]
    receipt_url: Optional[str]
    supplier: Optional[str]
    quantity: Optional[Decimal]
    unit: Optional[str]
    notes: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(AGRIOSSchema):
    """Paginated expense list."""
    items: list[ExpenseSummaryItem]
    total: int
    page: int
    page_size: int
    total_kes: Decimal


# ── RevenueRecord ─────────────────────────────────────────────────────────────

REVENUE_TYPES = Literal["eggs", "birds", "chicks", "manure", "other"]
REVENUE_UNITS = Literal["tray", "kg", "bird", "bag", "piece", "litre"]


class RevenueRecordCreate(AGRIOSSchema):
    """Record a new revenue event."""
    flock_id: UUID
    revenue_type: REVENUE_TYPES
    revenue_date: date
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[Decimal] = Field(None, gt=0)

    # Bird-sale specifics
    birds_sold: Optional[int] = Field(None, gt=0)
    avg_weight_kg: Optional[Decimal] = Field(None, gt=0)

    # Egg-sale specifics
    eggs_count: Optional[int] = Field(None, gt=0)
    trays_count: Optional[int] = Field(None, gt=0)

    # Buyer
    buyer_name: Optional[str] = Field(None, max_length=200)
    buyer_phone: Optional[str] = Field(None, max_length=20)
    payment_method: Optional[PAYMENT_METHODS] = None
    notes: Optional[str] = None

    @field_validator("revenue_date")
    @classmethod
    def revenue_date_not_future(cls, v: date) -> date:
        from datetime import date as dt_date
        if v > dt_date.today():
            raise ValueError("Revenue date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_type_fields(self) -> "RevenueRecordCreate":
        if self.revenue_type == "birds" and self.birds_sold is None:
            raise ValueError("birds_sold is required when revenue_type is 'birds'")
        if self.revenue_type == "eggs" and self.eggs_count is None and self.trays_count is None:
            raise ValueError("Either eggs_count or trays_count is required when revenue_type is 'eggs'")
        return self


class RevenueRecordUpdate(AGRIOSSchema):
    """Update a revenue record. At least one field required."""
    revenue_type: Optional[REVENUE_TYPES] = None
    revenue_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[Decimal] = Field(None, gt=0)
    birds_sold: Optional[int] = Field(None, gt=0)
    avg_weight_kg: Optional[Decimal] = Field(None, gt=0)
    eggs_count: Optional[int] = Field(None, gt=0)
    trays_count: Optional[int] = Field(None, gt=0)
    buyer_name: Optional[str] = Field(None, max_length=200)
    payment_method: Optional[PAYMENT_METHODS] = None
    notes: Optional[str] = None
    correction_reason: str = Field(..., min_length=5, max_length=500)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RevenueRecordUpdate":
        updatable = [
            "revenue_type", "revenue_date", "amount", "quantity", "unit",
            "unit_price", "birds_sold", "avg_weight_kg", "eggs_count",
            "trays_count", "buyer_name", "payment_method", "notes",
        ]
        if not any(getattr(self, f) is not None for f in updatable):
            raise ValueError("At least one field must be provided for update")
        return self


class RevenueSummaryItem(AGRIOSSchema):
    """Condensed revenue record for list views."""
    id: UUID
    revenue_date: date
    revenue_type: str
    amount: Decimal
    quantity: Optional[Decimal]
    unit: Optional[str]
    buyer_name: Optional[str]
    payment_method: Optional[str]
    flock_id: UUID


class RevenueRecordResponse(AGRIOSSchema):
    """Full revenue record detail."""
    id: UUID
    farm_id: UUID
    flock_id: UUID
    revenue_type: str
    revenue_date: date
    amount: Decimal
    quantity: Optional[Decimal]
    unit: Optional[str]
    unit_price: Optional[Decimal]
    birds_sold: Optional[int]
    avg_weight_kg: Optional[Decimal]
    eggs_count: Optional[int]
    trays_count: Optional[int]
    buyer_name: Optional[str]
    buyer_phone: Optional[str]
    payment_method: Optional[str]
    notes: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class RevenueListResponse(AGRIOSSchema):
    """Paginated revenue list."""
    items: list[RevenueSummaryItem]
    total: int
    page: int
    page_size: int
    total_kes: Decimal


# ── FinancialSnapshot ─────────────────────────────────────────────────────────

class FinancialSnapshotResponse(AGRIOSSchema):
    """Full P&L snapshot for a flock (DB-07: pre-computed, never real-time)."""
    id: UUID
    farm_id: UUID
    flock_id: UUID
    snapshot_at: datetime

    # Revenue
    total_revenue_kes: Decimal
    revenue_eggs_kes: Decimal
    revenue_birds_kes: Decimal
    revenue_manure_kes: Decimal
    revenue_other_kes: Decimal

    # Expenses
    total_expenses_kes: Decimal
    feed_cost_kes: Decimal
    doc_cost_kes: Decimal
    vet_health_cost_kes: Decimal
    labour_cost_kes: Decimal
    other_cost_kes: Decimal

    # P&L
    gross_profit_kes: Decimal
    gross_margin_pct: Optional[Decimal]
    is_profitable: bool

    # Per-bird
    cost_per_bird_kes: Optional[Decimal]
    revenue_per_bird_kes: Optional[Decimal]
    break_even_price_kes: Optional[Decimal]

    # FCR
    total_feed_kg: Decimal
    fcr_computed: Optional[Decimal]

    # Flock state
    bird_count_snapshot: Optional[int]
    birds_sold_snapshot: Optional[int]
    feed_cost_pct: Optional[Decimal]

    updated_at: datetime


class FlockPnLCard(AGRIOSSchema):
    """Condensed P&L card for a flock — for the finance dashboard list."""
    flock_id: UUID
    flock_name: str
    flock_status: str
    snapshot_at: Optional[datetime]
    total_revenue_kes: Decimal
    total_expenses_kes: Decimal
    gross_profit_kes: Decimal
    gross_margin_pct: Optional[Decimal]
    is_profitable: bool
    days_alive: Optional[int]


class FinanceDashboardResponse(AGRIOSSchema):
    """Farm-level finance dashboard summary."""
    # Farm totals (all active flocks, current cycle or rolling 30 days)
    period_label: str  # e.g. "Current cycle" or "Last 30 days"
    total_revenue_kes: Decimal
    total_expenses_kes: Decimal
    gross_profit_kes: Decimal
    gross_margin_pct: Optional[Decimal]
    is_profitable: bool

    # Category breakdown for current period
    feed_cost_kes: Decimal
    feed_cost_pct: Optional[Decimal]
    doc_cost_kes: Decimal
    vet_health_cost_kes: Decimal
    labour_cost_kes: Decimal
    other_cost_kes: Decimal

    # Flock P&L cards
    flock_cards: list[FlockPnLCard]

    # Most recent expense + revenue
    recent_expenses: list[ExpenseSummaryItem]
    recent_revenue: list[RevenueSummaryItem]


class ExpenseCategoryBreakdown(AGRIOSSchema):
    """Category spend breakdown for the period."""
    category_id: UUID
    category_name: str
    category_icon: Optional[str]
    category_color: Optional[str]
    total_kes: Decimal
    pct_of_total: Optional[Decimal]
    transaction_count: int


# ── Financial Calculators ─────────────────────────────────────────────────────

class FCRCalculatorInput(AGRIOSSchema):
    """FCR = total_feed_consumed_kg / total_live_weight_gained_kg."""
    total_feed_kg: Decimal = Field(..., gt=0)
    total_live_weight_kg: Decimal = Field(..., gt=0)


class FCRCalculatorResult(AGRIOSSchema):
    fcr: Decimal
    interpretation: str  # e.g. "Excellent (< 1.8)", "Good (1.8-2.0)", "Poor (> 2.5)"
    feed_kg: Decimal
    live_weight_kg: Decimal


class ProfitProjectionInput(AGRIOSSchema):
    """Project total profit at sale given current flock metrics."""
    current_bird_count: int = Field(..., gt=0)
    expected_close_weight_kg: Decimal = Field(..., gt=0)
    expected_sale_price_per_kg: Decimal = Field(..., gt=0)
    total_expenses_so_far_kes: Decimal = Field(..., ge=0)
    expected_additional_expenses_kes: Decimal = Field(default=Decimal("0"), ge=0)
    expected_mortality_pct: Decimal = Field(
        default=Decimal("3"), ge=0, le=100,
        description="Expected additional mortality % before sale"
    )


class ProfitProjectionResult(AGRIOSSchema):
    birds_at_sale: int
    total_live_weight_kg: Decimal
    projected_revenue_kes: Decimal
    projected_total_expenses_kes: Decimal
    projected_profit_kes: Decimal
    projected_margin_pct: Decimal
    revenue_per_bird_kes: Decimal
    cost_per_bird_kes: Decimal
    is_profitable: bool


class BreakEvenInput(AGRIOSSchema):
    """Compute the minimum sale price per kg to break even."""
    total_expenses_kes: Decimal = Field(..., gt=0)
    expected_birds_sold: int = Field(..., gt=0)
    expected_avg_weight_kg: Decimal = Field(..., gt=0)


class BreakEvenResult(AGRIOSSchema):
    break_even_per_kg_kes: Decimal
    break_even_per_bird_kes: Decimal
    total_live_weight_kg: Decimal
    total_expenses_kes: Decimal


class FeedNeedsInput(AGRIOSSchema):
    """Estimate feed required to reach target weight."""
    current_bird_count: int = Field(..., gt=0)
    current_avg_weight_kg: Decimal = Field(..., gt=0)
    target_weight_kg: Decimal = Field(..., gt=0)
    target_fcr: Decimal = Field(default=Decimal("1.9"), gt=0)
    days_remaining: Optional[int] = Field(None, gt=0)


class FeedNeedsResult(AGRIOSSchema):
    total_feed_needed_kg: Decimal
    feed_per_day_kg: Optional[Decimal]  # None if days_remaining not provided
    estimated_feed_cost_kes: Optional[Decimal]  # None — caller provides price/kg
    weight_gain_needed_kg: Decimal
    current_biomass_kg: Decimal
    target_biomass_kg: Decimal
