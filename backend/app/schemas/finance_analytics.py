"""
Greena — Finance Analytics & Reporting Schemas (Module 5).

These extend the existing Finance module (expenses, revenue, per-flock
snapshots) with farm-level, time-windowed intelligence computed fresh from the
expense / revenue ledgers:

  * Overview dashboard (today / 30-day, cash balance, top category, chart series)
  * Rolling analytics (7d / 30d / 90d / YTD / lifetime) with growth + margins
  * Per-bird / per-egg / per-kg economics
  * Cost centres (per-flock P&L)
  * Unified transaction search (revenue + expense) with filter/sort/paginate
  * Cash flow, period reports (monthly / quarterly / yearly), AI context
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from app.schemas.base import AGRIOSSchema


# ── Shared building blocks ────────────────────────────────────────────────────

class MoneyPoint(AGRIOSSchema):
    """One point on a revenue/expense/profit time series."""
    period: str            # ISO date (daily) or "YYYY-MM" (monthly)
    revenue: Decimal
    expenses: Decimal
    profit: Decimal


class CategoryAmount(AGRIOSSchema):
    category_id: Optional[UUID]
    name: str
    slug: str
    icon: Optional[str]
    color: Optional[str]
    amount: Decimal
    pct_of_total: Optional[Decimal]
    transaction_count: int


class RevenueTypeAmount(AGRIOSSchema):
    revenue_type: str
    amount: Decimal
    pct_of_total: Optional[Decimal]
    transaction_count: int


# ── Overview dashboard ────────────────────────────────────────────────────────

class FinanceOverview(AGRIOSSchema):
    today_revenue: Decimal
    today_expenses: Decimal
    today_profit: Decimal
    m30_revenue: Decimal
    m30_expenses: Decimal
    m30_profit: Decimal
    cash_balance: Decimal            # lifetime revenue − lifetime expenses
    outstanding_costs: Decimal       # expenses booked on credit (unpaid)
    top_expense_category: Optional[CategoryAmount]
    revenue_series: list[MoneyPoint]  # last 30 days, daily
    profit_trend: list[MoneyPoint]    # last 30 days, daily cumulative-friendly
    category_breakdown: list[CategoryAmount]   # last 30 days
    revenue_by_type: list[RevenueTypeAmount]   # last 30 days
    recent_transactions: list["TransactionRow"]


# ── Rolling analytics ─────────────────────────────────────────────────────────

WindowKey = Literal["7d", "30d", "90d", "ytd", "lifetime"]


class WindowStats(AGRIOSSchema):
    window: str
    start_date: Optional[date]
    end_date: date
    revenue: Decimal
    expenses: Decimal
    direct_costs: Decimal            # COGS: feed, DOC, health
    gross_profit: Decimal            # revenue − direct costs
    net_profit: Decimal              # revenue − all expenses
    gross_margin_pct: Optional[Decimal]
    net_margin_pct: Optional[Decimal]
    revenue_growth_pct: Optional[Decimal]   # vs previous equal window
    expense_growth_pct: Optional[Decimal]


class PerUnitStats(AGRIOSSchema):
    total_birds: int
    total_eggs: int
    total_kg: Decimal
    cost_per_bird: Optional[Decimal]
    revenue_per_bird: Optional[Decimal]
    profit_per_bird: Optional[Decimal]
    cost_per_egg: Optional[Decimal]
    revenue_per_egg: Optional[Decimal]
    profit_per_egg: Optional[Decimal]
    cost_per_kg: Optional[Decimal]
    revenue_per_kg: Optional[Decimal]


class CostCentre(AGRIOSSchema):
    flock_id: UUID
    flock_name: str
    status: str
    revenue: Decimal
    expenses: Decimal
    profit: Decimal
    margin_pct: Optional[Decimal]


class FinanceAnalytics(AGRIOSSchema):
    windows: list[WindowStats]       # 7d, 30d, 90d, ytd, lifetime
    per_unit: PerUnitStats           # lifetime economics
    cost_centres: list[CostCentre]
    revenue_trend: list[MoneyPoint]  # monthly, last 12 months
    expense_trend: list[MoneyPoint]  # monthly, last 12 months


# ── Unified transactions ──────────────────────────────────────────────────────

class TransactionRow(AGRIOSSchema):
    id: UUID
    kind: str                        # "revenue" | "expense"
    txn_date: date
    label: str                       # revenue_type or category name
    slug: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    description: Optional[str]
    amount: Decimal
    signed_amount: Decimal           # +revenue / −expense
    flock_id: Optional[UUID]
    flock_name: Optional[str]
    payment_method: Optional[str]


class TransactionPage(AGRIOSSchema):
    items: list[TransactionRow]
    total: int
    page: int
    page_size: int
    total_revenue: Decimal
    total_expenses: Decimal
    net: Decimal


# ── Cash flow ─────────────────────────────────────────────────────────────────

class CashflowPoint(AGRIOSSchema):
    period: str                      # "YYYY-MM"
    inflow: Decimal
    outflow: Decimal
    net: Decimal
    running_balance: Decimal


class CashflowResponse(AGRIOSSchema):
    months: int
    points: list[CashflowPoint]
    opening_balance: Decimal
    closing_balance: Decimal


# ── Period reports ────────────────────────────────────────────────────────────

class FinanceReport(AGRIOSSchema):
    period_type: str                 # monthly | quarterly | yearly
    period_label: str
    start_date: date
    end_date: date
    total_revenue: Decimal
    total_expenses: Decimal
    direct_costs: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    net_margin_pct: Optional[Decimal]
    revenue_by_type: list[RevenueTypeAmount]
    expense_by_category: list[CategoryAmount]
    monthly_breakdown: list[MoneyPoint]


# ── AI context ────────────────────────────────────────────────────────────────

class FinanceAIContext(AGRIOSSchema):
    farm_id: UUID
    generated_at: datetime
    cash_balance: Decimal
    rolling_averages: dict           # window → {revenue, expenses, profit}
    revenue_by_type: list[dict]
    expense_by_category: list[dict]
    cost_centres: list[dict]
    recent_events: list[dict]        # per-event structured context with profit impact


FinanceOverview.model_rebuild()
