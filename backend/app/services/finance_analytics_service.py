"""
Greena — Finance Analytics & Reporting Service (Module 5).

Farm-level, time-windowed financial intelligence computed fresh from the
expense and revenue ledgers. This complements (does not replace) the existing
per-flock ``financial_snapshots`` — snapshots remain the source of truth for a
single flock's P&L; this module answers farm-wide, date-ranged questions the
snapshot table cannot (today/rolling windows, trends, cash flow, reports).

Everything is farm-scoped (DB-04 Frozen) and ignores soft-deleted rows.
"""

import csv
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import Expense, ExpenseCategory, RevenueRecord
from app.models.flock import Flock, ProductionRecord
from app.schemas.finance_analytics import (
    CashflowPoint,
    CashflowResponse,
    CategoryAmount,
    CostCentre,
    FinanceAIContext,
    FinanceAnalytics,
    FinanceOverview,
    FinanceReport,
    MoneyPoint,
    PerUnitStats,
    RevenueTypeAmount,
    TransactionPage,
    TransactionRow,
    WindowStats,
)

_Q = Decimal("0.01")
_Q4 = Decimal("0.0001")

# Cost of goods sold — direct production costs. Everything else is operating.
DIRECT_COST_SLUGS = {
    "feed_purchase", "feed_supplements", "doc_purchase",
    "vaccination", "medication", "vet_fees", "biosecurity",
}


def _fid(farm_id) -> str:
    return str(farm_id)


def _pct(part: Decimal, whole: Decimal) -> Optional[Decimal]:
    if whole and whole > 0:
        return (part / whole * 100).quantize(_Q)
    return None


# ── Primitive aggregates ──────────────────────────────────────────────────────

async def _revenue_total(db, farm_id, start: Optional[date], end: date) -> Decimal:
    filters = [
        RevenueRecord.farm_id == _fid(farm_id),
        RevenueRecord.deleted_at.is_(None),
        RevenueRecord.revenue_date <= end,
    ]
    if start:
        filters.append(RevenueRecord.revenue_date >= start)
    res = await db.execute(select(func.coalesce(func.sum(RevenueRecord.amount), 0)).where(*filters))
    return Decimal(res.scalar_one())


async def _expense_total(db, farm_id, start: Optional[date], end: date) -> Decimal:
    filters = [
        Expense.farm_id == _fid(farm_id),
        Expense.deleted_at.is_(None),
        Expense.expense_date <= end,
    ]
    if start:
        filters.append(Expense.expense_date >= start)
    res = await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(*filters))
    return Decimal(res.scalar_one())


async def _direct_cost_total(db, farm_id, start: Optional[date], end: date) -> Decimal:
    filters = [
        Expense.farm_id == _fid(farm_id),
        Expense.deleted_at.is_(None),
        Expense.expense_date <= end,
        ExpenseCategory.slug.in_(DIRECT_COST_SLUGS),
    ]
    if start:
        filters.append(Expense.expense_date >= start)
    res = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*filters)
    )
    return Decimal(res.scalar_one())


async def _revenue_by_type(db, farm_id, start: Optional[date], end: date) -> list[RevenueTypeAmount]:
    filters = [
        RevenueRecord.farm_id == _fid(farm_id),
        RevenueRecord.deleted_at.is_(None),
        RevenueRecord.revenue_date <= end,
    ]
    if start:
        filters.append(RevenueRecord.revenue_date >= start)
    res = await db.execute(
        select(RevenueRecord.revenue_type, func.sum(RevenueRecord.amount), func.count(RevenueRecord.id))
        .where(*filters).group_by(RevenueRecord.revenue_type)
        .order_by(func.sum(RevenueRecord.amount).desc())
    )
    rows = res.all()
    total = sum((Decimal(r[1]) for r in rows), Decimal("0"))
    return [
        RevenueTypeAmount(
            revenue_type=rt, amount=Decimal(amt).quantize(_Q),
            pct_of_total=_pct(Decimal(amt), total), transaction_count=int(cnt),
        )
        for rt, amt, cnt in rows
    ]


async def _category_breakdown(db, farm_id, start: Optional[date], end: date) -> list[CategoryAmount]:
    filters = [
        Expense.farm_id == _fid(farm_id),
        Expense.deleted_at.is_(None),
        Expense.expense_date <= end,
    ]
    if start:
        filters.append(Expense.expense_date >= start)
    res = await db.execute(
        select(
            ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.slug,
            ExpenseCategory.icon, ExpenseCategory.color,
            func.sum(Expense.amount), func.count(Expense.id),
        )
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*filters)
        .group_by(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.slug,
                  ExpenseCategory.icon, ExpenseCategory.color)
        .order_by(func.sum(Expense.amount).desc())
    )
    rows = res.all()
    total = sum((Decimal(r[5]) for r in rows), Decimal("0"))
    return [
        CategoryAmount(
            category_id=cid, name=name, slug=slug, icon=icon, color=color,
            amount=Decimal(amt).quantize(_Q), pct_of_total=_pct(Decimal(amt), total),
            transaction_count=int(cnt),
        )
        for cid, name, slug, icon, color, amt, cnt in rows
    ]


async def _daily_series(db, farm_id, start: date, end: date) -> list[MoneyPoint]:
    """Revenue/expense/profit per day across [start, end]."""
    rev_res = await db.execute(
        select(RevenueRecord.revenue_date, func.sum(RevenueRecord.amount))
        .where(
            RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None),
            RevenueRecord.revenue_date >= start, RevenueRecord.revenue_date <= end,
        ).group_by(RevenueRecord.revenue_date)
    )
    rev = {d: Decimal(a) for d, a in rev_res.all()}
    exp_res = await db.execute(
        select(Expense.expense_date, func.sum(Expense.amount))
        .where(
            Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None),
            Expense.expense_date >= start, Expense.expense_date <= end,
        ).group_by(Expense.expense_date)
    )
    exp = {d: Decimal(a) for d, a in exp_res.all()}

    points: list[MoneyPoint] = []
    cur = start
    while cur <= end:
        r = rev.get(cur, Decimal("0"))
        e = exp.get(cur, Decimal("0"))
        points.append(MoneyPoint(period=cur.isoformat(), revenue=r.quantize(_Q), expenses=e.quantize(_Q), profit=(r - e).quantize(_Q)))
        cur += timedelta(days=1)
    return points


async def _monthly_series(db, farm_id, months: int) -> list[MoneyPoint]:
    """Revenue/expense/profit per calendar month for the trailing ``months``."""
    today = date.today()
    # First day of the window's first month.
    y, m = today.year, today.month
    start_month = m - (months - 1)
    start_year = y
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)

    # Group by the labelled month expression (group_by a bind-param function twice
    # confuses Postgres, so we reference the SELECT alias by name).
    rev_period = func.to_char(RevenueRecord.revenue_date, "YYYY-MM").label("period")
    rev_res = await db.execute(
        select(rev_period, func.sum(RevenueRecord.amount))
        .where(
            RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None),
            RevenueRecord.revenue_date >= start,
        ).group_by(rev_period)
    )
    rev = {k: Decimal(a) for k, a in rev_res.all()}
    exp_period = func.to_char(Expense.expense_date, "YYYY-MM").label("period")
    exp_res = await db.execute(
        select(exp_period, func.sum(Expense.amount))
        .where(
            Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None),
            Expense.expense_date >= start,
        ).group_by(exp_period)
    )
    exp = {k: Decimal(a) for k, a in exp_res.all()}

    points: list[MoneyPoint] = []
    cy, cm = start_year, start_month
    for _ in range(months):
        key = f"{cy:04d}-{cm:02d}"
        r = rev.get(key, Decimal("0"))
        e = exp.get(key, Decimal("0"))
        points.append(MoneyPoint(period=key, revenue=r.quantize(_Q), expenses=e.quantize(_Q), profit=(r - e).quantize(_Q)))
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1
    return points


# ── Overview dashboard ────────────────────────────────────────────────────────

async def get_overview(db: AsyncSession, farm_id: uuid.UUID) -> FinanceOverview:
    today = date.today()
    m30_start = today - timedelta(days=29)

    today_rev = await _revenue_total(db, farm_id, today, today)
    today_exp = await _expense_total(db, farm_id, today, today)
    m30_rev = await _revenue_total(db, farm_id, m30_start, today)
    m30_exp = await _expense_total(db, farm_id, m30_start, today)

    life_rev = await _revenue_total(db, farm_id, None, today)
    life_exp = await _expense_total(db, farm_id, None, today)

    # Outstanding = expenses booked on credit.
    out_res = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None),
            Expense.payment_method == "credit",
        )
    )
    outstanding = Decimal(out_res.scalar_one())

    cats = await _category_breakdown(db, farm_id, m30_start, today)
    series = await _daily_series(db, farm_id, m30_start, today)
    rev_types = await _revenue_by_type(db, farm_id, m30_start, today)
    recent = (await search_transactions(db, farm_id, page=1, page_size=8)).items

    return FinanceOverview(
        today_revenue=today_rev.quantize(_Q),
        today_expenses=today_exp.quantize(_Q),
        today_profit=(today_rev - today_exp).quantize(_Q),
        m30_revenue=m30_rev.quantize(_Q),
        m30_expenses=m30_exp.quantize(_Q),
        m30_profit=(m30_rev - m30_exp).quantize(_Q),
        cash_balance=(life_rev - life_exp).quantize(_Q),
        outstanding_costs=outstanding.quantize(_Q),
        top_expense_category=cats[0] if cats else None,
        revenue_series=series,
        profit_trend=series,
        category_breakdown=cats,
        revenue_by_type=rev_types,
        recent_transactions=recent,
    )


# ── Rolling analytics ─────────────────────────────────────────────────────────

def _window_bounds(window: str, today: date) -> tuple[Optional[date], int]:
    """Return (start_date, length_days). length is used for growth comparison."""
    if window == "7d":
        return today - timedelta(days=6), 7
    if window == "30d":
        return today - timedelta(days=29), 30
    if window == "90d":
        return today - timedelta(days=89), 90
    if window == "ytd":
        start = date(today.year, 1, 1)
        return start, (today - start).days + 1
    return None, 0  # lifetime


async def _window_stats(db, farm_id, window: str, today: date) -> WindowStats:
    start, length = _window_bounds(window, today)
    revenue = await _revenue_total(db, farm_id, start, today)
    expenses = await _expense_total(db, farm_id, start, today)
    direct = await _direct_cost_total(db, farm_id, start, today)
    gross = revenue - direct
    net = revenue - expenses

    rev_growth = exp_growth = None
    if start is not None and length > 0:
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        prev_rev = await _revenue_total(db, farm_id, prev_start, prev_end)
        prev_exp = await _expense_total(db, farm_id, prev_start, prev_end)
        if prev_rev > 0:
            rev_growth = ((revenue - prev_rev) / prev_rev * 100).quantize(_Q)
        if prev_exp > 0:
            exp_growth = ((expenses - prev_exp) / prev_exp * 100).quantize(_Q)

    return WindowStats(
        window=window, start_date=start, end_date=today,
        revenue=revenue.quantize(_Q), expenses=expenses.quantize(_Q),
        direct_costs=direct.quantize(_Q),
        gross_profit=gross.quantize(_Q), net_profit=net.quantize(_Q),
        gross_margin_pct=_pct(gross, revenue), net_margin_pct=_pct(net, revenue),
        revenue_growth_pct=rev_growth, expense_growth_pct=exp_growth,
    )


async def _per_unit(db, farm_id, today: date) -> PerUnitStats:
    revenue = await _revenue_total(db, farm_id, None, today)
    expenses = await _expense_total(db, farm_id, None, today)

    birds_res = await db.execute(
        select(func.coalesce(func.sum(Flock.initial_count), 0)).where(
            Flock.farm_id == _fid(farm_id), Flock.deleted_at.is_(None)
        )
    )
    total_birds = int(birds_res.scalar_one())

    eggs_res = await db.execute(
        select(func.coalesce(func.sum(ProductionRecord.eggs_collected), 0)).where(
            ProductionRecord.farm_id == _fid(farm_id), ProductionRecord.deleted_at.is_(None)
        )
    )
    total_eggs = int(eggs_res.scalar_one())

    kg_res = await db.execute(
        select(func.coalesce(func.sum(RevenueRecord.birds_sold * RevenueRecord.avg_weight_kg), 0)).where(
            RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None),
            RevenueRecord.revenue_type == "birds", RevenueRecord.avg_weight_kg.is_not(None),
        )
    )
    total_kg = Decimal(kg_res.scalar_one() or 0)

    def per(n_expr, count):
        return (n_expr / count).quantize(_Q) if count and count > 0 else None

    profit = revenue - expenses
    return PerUnitStats(
        total_birds=total_birds, total_eggs=total_eggs, total_kg=total_kg.quantize(Decimal("0.001")),
        cost_per_bird=per(expenses, total_birds),
        revenue_per_bird=per(revenue, total_birds),
        profit_per_bird=per(profit, total_birds),
        cost_per_egg=per(expenses, total_eggs),
        revenue_per_egg=per(revenue, total_eggs),
        profit_per_egg=per(profit, total_eggs),
        cost_per_kg=per(expenses, total_kg),
        revenue_per_kg=per(revenue, total_kg),
    )


async def _cost_centres(db, farm_id, today: date) -> list[CostCentre]:
    rev_res = await db.execute(
        select(RevenueRecord.flock_id, func.sum(RevenueRecord.amount)).where(
            RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None),
            RevenueRecord.flock_id.is_not(None),
        ).group_by(RevenueRecord.flock_id)
    )
    rev = {str(f): Decimal(a) for f, a in rev_res.all()}
    exp_res = await db.execute(
        select(Expense.flock_id, func.sum(Expense.amount)).where(
            Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None),
            Expense.flock_id.is_not(None),
        ).group_by(Expense.flock_id)
    )
    exp = {str(f): Decimal(a) for f, a in exp_res.all()}

    flock_ids = set(rev) | set(exp)
    if not flock_ids:
        return []
    flocks_res = await db.execute(
        select(Flock).where(Flock.id.in_(flock_ids), Flock.deleted_at.is_(None))
    )
    centres: list[CostCentre] = []
    for flock in flocks_res.scalars().all():
        r = rev.get(str(flock.id), Decimal("0"))
        e = exp.get(str(flock.id), Decimal("0"))
        centres.append(CostCentre(
            flock_id=flock.id, flock_name=flock.name, status=flock.status,
            revenue=r.quantize(_Q), expenses=e.quantize(_Q), profit=(r - e).quantize(_Q),
            margin_pct=_pct(r - e, r),
        ))
    centres.sort(key=lambda c: c.profit, reverse=True)
    return centres


async def get_analytics(db: AsyncSession, farm_id: uuid.UUID) -> FinanceAnalytics:
    today = date.today()
    windows = [await _window_stats(db, farm_id, w, today) for w in ("7d", "30d", "90d", "ytd", "lifetime")]
    per_unit = await _per_unit(db, farm_id, today)
    centres = await _cost_centres(db, farm_id, today)
    trend = await _monthly_series(db, farm_id, 12)
    return FinanceAnalytics(
        windows=windows, per_unit=per_unit, cost_centres=centres,
        revenue_trend=trend, expense_trend=trend,
    )


# ── Unified transaction search ────────────────────────────────────────────────

async def search_transactions(
    db: AsyncSession,
    farm_id: uuid.UUID,
    q: Optional[str] = None,
    kind: Optional[str] = None,          # revenue | expense
    category_id: Optional[uuid.UUID] = None,
    revenue_type: Optional[str] = None,
    flock_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    sort: str = "date_desc",             # date_desc|date_asc|amount_desc|amount_asc
    page: int = 1,
    page_size: int = 20,
) -> TransactionPage:
    """Unified revenue + expense ledger with search / filter / sort / paginate."""
    rows: list[TransactionRow] = []

    # ── Expenses ──────────────────────────────────────────────────────────────
    if kind != "revenue":
        ef = [Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None)]
        if category_id:
            ef.append(Expense.category_id == str(category_id))
        if flock_id:
            ef.append(Expense.flock_id == str(flock_id))
        if date_from:
            ef.append(Expense.expense_date >= date_from)
        if date_to:
            ef.append(Expense.expense_date <= date_to)
        if min_amount is not None:
            ef.append(Expense.amount >= min_amount)
        if max_amount is not None:
            ef.append(Expense.amount <= max_amount)
        if q:
            ef.append(or_(Expense.description.ilike(f"%{q}%"), Expense.supplier.ilike(f"%{q}%")))
        # revenue_type filter excludes all expenses.
        if not revenue_type:
            eres = await db.execute(
                select(Expense, ExpenseCategory, Flock.name)
                .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
                .outerjoin(Flock, Expense.flock_id == Flock.id)
                .where(*ef)
            )
            for exp, cat, flock_name in eres.all():
                rows.append(TransactionRow(
                    id=exp.id, kind="expense", txn_date=exp.expense_date,
                    label=cat.name, slug=cat.slug, icon=cat.icon, color=cat.color,
                    description=exp.description, amount=Decimal(exp.amount).quantize(_Q),
                    signed_amount=(-Decimal(exp.amount)).quantize(_Q),
                    flock_id=exp.flock_id, flock_name=flock_name,
                    payment_method=exp.payment_method,
                ))

    # ── Revenue ───────────────────────────────────────────────────────────────
    if kind != "expense":
        rf = [RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None)]
        if revenue_type:
            rf.append(RevenueRecord.revenue_type == revenue_type)
        if flock_id:
            rf.append(RevenueRecord.flock_id == str(flock_id))
        if date_from:
            rf.append(RevenueRecord.revenue_date >= date_from)
        if date_to:
            rf.append(RevenueRecord.revenue_date <= date_to)
        if min_amount is not None:
            rf.append(RevenueRecord.amount >= min_amount)
        if max_amount is not None:
            rf.append(RevenueRecord.amount <= max_amount)
        if q:
            rf.append(or_(RevenueRecord.buyer_name.ilike(f"%{q}%"), RevenueRecord.notes.ilike(f"%{q}%")))
        # category filter excludes all revenue.
        if not category_id:
            rres = await db.execute(
                select(RevenueRecord, Flock.name)
                .outerjoin(Flock, RevenueRecord.flock_id == Flock.id)
                .where(*rf)
            )
            for rev, flock_name in rres.all():
                rows.append(TransactionRow(
                    id=rev.id, kind="revenue", txn_date=rev.revenue_date,
                    label=f"{rev.revenue_type.title()} sale", slug=rev.revenue_type,
                    icon=None, color="#16a34a",
                    description=rev.buyer_name, amount=Decimal(rev.amount).quantize(_Q),
                    signed_amount=Decimal(rev.amount).quantize(_Q),
                    flock_id=rev.flock_id, flock_name=flock_name,
                    payment_method=rev.payment_method,
                ))

    # ── Sort ──────────────────────────────────────────────────────────────────
    reverse = sort in ("date_desc", "amount_desc")
    if sort in ("amount_desc", "amount_asc"):
        rows.sort(key=lambda r: r.amount, reverse=reverse)
    else:
        rows.sort(key=lambda r: (r.txn_date, r.amount), reverse=reverse)

    total = len(rows)
    total_rev = sum((r.amount for r in rows if r.kind == "revenue"), Decimal("0"))
    total_exp = sum((r.amount for r in rows if r.kind == "expense"), Decimal("0"))

    offset = (page - 1) * page_size
    page_rows = rows[offset:offset + page_size]

    return TransactionPage(
        items=page_rows, total=total, page=page, page_size=page_size,
        total_revenue=total_rev.quantize(_Q), total_expenses=total_exp.quantize(_Q),
        net=(total_rev - total_exp).quantize(_Q),
    )


# ── Cash flow ─────────────────────────────────────────────────────────────────

async def get_cashflow(db: AsyncSession, farm_id: uuid.UUID, months: int = 12) -> CashflowResponse:
    series = await _monthly_series(db, farm_id, months)
    # Opening balance = everything before the window.
    if series:
        first_period = series[0].period  # YYYY-MM
        y, m = int(first_period[:4]), int(first_period[5:7])
        window_start = date(y, m, 1)
        prior_rev = await _revenue_total(db, farm_id, None, window_start - timedelta(days=1))
        prior_exp = await _expense_total(db, farm_id, None, window_start - timedelta(days=1))
        opening = (prior_rev - prior_exp).quantize(_Q)
    else:
        opening = Decimal("0.00")

    points: list[CashflowPoint] = []
    running = opening
    for p in series:
        running = (running + p.profit).quantize(_Q)
        points.append(CashflowPoint(
            period=p.period, inflow=p.revenue, outflow=p.expenses, net=p.profit,
            running_balance=running,
        ))
    return CashflowResponse(
        months=months, points=points, opening_balance=opening,
        closing_balance=running.quantize(_Q),
    )


# ── Period reports ────────────────────────────────────────────────────────────

def _period_bounds(period_type: str, year: int, index: int) -> tuple[date, date, str]:
    if period_type == "monthly":
        start = date(year, index, 1)
        end = date(year + 1, 1, 1) - timedelta(days=1) if index == 12 else date(year, index + 1, 1) - timedelta(days=1)
        return start, end, start.strftime("%B %Y")
    if period_type == "quarterly":
        first_month = (index - 1) * 3 + 1
        start = date(year, first_month, 1)
        end_month = first_month + 2
        end = date(year + 1, 1, 1) - timedelta(days=1) if end_month == 12 else date(year, end_month + 1, 1) - timedelta(days=1)
        return start, end, f"Q{index} {year}"
    # yearly
    return date(year, 1, 1), date(year, 12, 31), str(year)


async def get_report(
    db: AsyncSession, farm_id: uuid.UUID, period_type: str, year: int, index: int = 1
) -> FinanceReport:
    start, end, label = _period_bounds(period_type, year, index)
    revenue = await _revenue_total(db, farm_id, start, end)
    expenses = await _expense_total(db, farm_id, start, end)
    direct = await _direct_cost_total(db, farm_id, start, end)
    rev_types = await _revenue_by_type(db, farm_id, start, end)
    cats = await _category_breakdown(db, farm_id, start, end)

    # Month-by-month breakdown within the period.
    monthly: list[MoneyPoint] = []
    cy, cm = start.year, start.month
    while date(cy, cm, 1) <= end:
        m_end = date(cy + 1, 1, 1) - timedelta(days=1) if cm == 12 else date(cy, cm + 1, 1) - timedelta(days=1)
        m_start = date(cy, cm, 1)
        r = await _revenue_total(db, farm_id, m_start, min(m_end, end))
        e = await _expense_total(db, farm_id, m_start, min(m_end, end))
        monthly.append(MoneyPoint(period=f"{cy:04d}-{cm:02d}", revenue=r.quantize(_Q), expenses=e.quantize(_Q), profit=(r - e).quantize(_Q)))
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1

    net = revenue - expenses
    return FinanceReport(
        period_type=period_type, period_label=label, start_date=start, end_date=end,
        total_revenue=revenue.quantize(_Q), total_expenses=expenses.quantize(_Q),
        direct_costs=direct.quantize(_Q), gross_profit=(revenue - direct).quantize(_Q),
        net_profit=net.quantize(_Q), net_margin_pct=_pct(net, revenue),
        revenue_by_type=rev_types, expense_by_category=cats, monthly_breakdown=monthly,
    )


async def export_transactions_csv(
    db: AsyncSession, farm_id: uuid.UUID,
    date_from: Optional[date] = None, date_to: Optional[date] = None,
) -> str:
    page = await search_transactions(
        db, farm_id, date_from=date_from, date_to=date_to, page=1, page_size=100_000
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Kind", "Category/Type", "Description", "Flock", "Payment", "Amount (KES)", "Signed (KES)"])
    for r in page.items:
        writer.writerow([
            r.txn_date.isoformat(), r.kind, r.label, r.description or "",
            r.flock_name or "", r.payment_method or "", str(r.amount), str(r.signed_amount),
        ])
    writer.writerow([])
    writer.writerow(["", "", "", "", "", "Total revenue", str(page.total_revenue)])
    writer.writerow(["", "", "", "", "", "Total expenses", str(page.total_expenses)])
    writer.writerow(["", "", "", "", "", "Net", str(page.net)])
    return buf.getvalue()


# ── AI context ────────────────────────────────────────────────────────────────

async def get_ai_context(db: AsyncSession, farm_id: uuid.UUID) -> FinanceAIContext:
    today = date.today()
    analytics = await get_analytics(db, farm_id)
    overview = await get_overview(db, farm_id)

    rolling = {
        w.window: {
            "revenue": str(w.revenue), "expenses": str(w.expenses),
            "net_profit": str(w.net_profit),
            "net_margin_pct": str(w.net_margin_pct) if w.net_margin_pct is not None else None,
            "revenue_growth_pct": str(w.revenue_growth_pct) if w.revenue_growth_pct is not None else None,
        }
        for w in analytics.windows
    }
    # Per-event structured context with profit impact (a revenue event lifts
    # profit; an expense event reduces it).
    recent_events = [
        {
            "kind": r.kind, "category": r.label, "amount": str(r.amount),
            "reason": r.description, "flock": r.flock_name, "date": r.txn_date.isoformat(),
            "profit_impact": str(r.signed_amount),
        }
        for r in overview.recent_transactions
    ]
    return FinanceAIContext(
        farm_id=farm_id, generated_at=datetime.now(tz=timezone.utc),
        cash_balance=overview.cash_balance, rolling_averages=rolling,
        revenue_by_type=[{"revenue_type": rt.revenue_type, "amount": str(rt.amount)} for rt in overview.revenue_by_type],
        expense_by_category=[{"category": c.name, "amount": str(c.amount)} for c in overview.category_breakdown],
        cost_centres=[{"flock": c.flock_name, "profit": str(c.profit), "margin_pct": str(c.margin_pct) if c.margin_pct is not None else None} for c in analytics.cost_centres],
        recent_events=recent_events,
    )
