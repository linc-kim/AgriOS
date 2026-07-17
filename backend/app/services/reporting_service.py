"""
Greena — Reporting & Business Intelligence Service (Module 7).

Composes uniform, section-based reports across every module: production,
finance, feed, health, inventory, mortality, vaccination, sales, purchases,
assets, maintenance, staff activity and AI insights. Also builds role
dashboards and period-over-period comparisons.

Reports are read-only compositions over existing data — this module never
mutates operational records.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.ai import AIInsight
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense, ExpenseCategory, RevenueRecord
from app.models.flock import DailyLog, Flock, ProductionRecord, WeighinRecord
from app.models.health import HealthEvent, VaccinationRecord
from app.models.platform import AuditLog
from app.models.reporting import SavedReport
from app.schemas.reporting import (
    BreakdownRow,
    Report,
    ReportKpi,
    ReportSection,
    SavedReportCreate,
    SavedReportUpdate,
)

_Q = Decimal("0.01")


def _kes(v) -> str:
    return f"KES {Decimal(v).quantize(_Q):,}"


def _fid(farm_id) -> str:
    return str(farm_id)


# ── Period resolution ─────────────────────────────────────────────────────────

def resolve_period(period_type: str, start: Optional[date], end: Optional[date]) -> tuple[date, date, str]:
    today = date.today()
    if period_type == "custom":
        if not start or not end:
            raise ValidationException("Custom period requires start and end dates.")
        if start > end:
            raise ValidationException("start date must be on or before end date.")
        return start, end, f"{start.isoformat()} – {end.isoformat()}"
    if period_type == "daily":
        d = end or today
        return d, d, d.strftime("%d %b %Y")
    if period_type == "weekly":
        e = end or today
        return e - timedelta(days=6), e, f"Week to {e.strftime('%d %b %Y')}"
    if period_type == "monthly":
        s = date(today.year, today.month, 1)
        return s, today, today.strftime("%B %Y")
    if period_type == "quarterly":
        q = (today.month - 1) // 3
        s = date(today.year, q * 3 + 1, 1)
        return s, today, f"Q{q + 1} {today.year}"
    # annual
    return date(today.year, 1, 1), today, str(today.year)


# ── Aggregate helpers ─────────────────────────────────────────────────────────

async def _sum(db, col, filters) -> Decimal:
    res = await db.execute(select(func.coalesce(func.sum(col), 0)).where(*filters))
    return Decimal(res.scalar_one())


async def _rev_total(db, farm_id, s, e) -> Decimal:
    return await _sum(db, RevenueRecord.amount, [
        RevenueRecord.farm_id == _fid(farm_id), RevenueRecord.deleted_at.is_(None),
        RevenueRecord.revenue_date >= s, RevenueRecord.revenue_date <= e])


async def _exp_total(db, farm_id, s, e) -> Decimal:
    return await _sum(db, Expense.amount, [
        Expense.farm_id == _fid(farm_id), Expense.deleted_at.is_(None),
        Expense.expense_date >= s, Expense.expense_date <= e])


async def _daily_prod_series(db, farm_id, s, e) -> list[dict]:
    res = await db.execute(
        select(ProductionRecord.record_date, func.coalesce(func.sum(ProductionRecord.eggs_collected), 0))
        .where(ProductionRecord.farm_id == _fid(farm_id), ProductionRecord.deleted_at.is_(None),
               ProductionRecord.record_date >= s, ProductionRecord.record_date <= e)
        .group_by(ProductionRecord.record_date).order_by(ProductionRecord.record_date)
    )
    return [{"period": d.isoformat(), "Eggs": int(v)} for d, v in res.all()]


async def _daily_mortality_series(db, farm_id, s, e) -> list[dict]:
    res = await db.execute(
        select(DailyLog.log_date, func.coalesce(func.sum(DailyLog.mortality_count), 0),
               func.coalesce(func.sum(DailyLog.culls), 0))
        .where(DailyLog.farm_id == _fid(farm_id), DailyLog.deleted_at.is_(None),
               DailyLog.log_date >= s, DailyLog.log_date <= e)
        .group_by(DailyLog.log_date).order_by(DailyLog.log_date)
    )
    return [{"period": d.isoformat(), "Mortality": int(m), "Culls": int(c)} for d, m, c in res.all()]


# ── Report builders ───────────────────────────────────────────────────────────

async def _finance_sections(db, farm, s, e) -> list[ReportSection]:
    rev = await _rev_total(db, farm.id, s, e)
    exp = await _exp_total(db, farm.id, s, e)
    profit = rev - exp
    # By category.
    cat_res = await db.execute(
        select(ExpenseCategory.name, func.sum(Expense.amount))
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(Expense.farm_id == _fid(farm.id), Expense.deleted_at.is_(None),
               Expense.expense_date >= s, Expense.expense_date <= e)
        .group_by(ExpenseCategory.name).order_by(func.sum(Expense.amount).desc())
    )
    cats = cat_res.all()
    exp_total = sum((Decimal(c[1]) for c in cats), Decimal("0"))
    rev_res = await db.execute(
        select(RevenueRecord.revenue_type, func.sum(RevenueRecord.amount))
        .where(RevenueRecord.farm_id == _fid(farm.id), RevenueRecord.deleted_at.is_(None),
               RevenueRecord.revenue_date >= s, RevenueRecord.revenue_date <= e)
        .group_by(RevenueRecord.revenue_type).order_by(func.sum(RevenueRecord.amount).desc())
    )
    return [
        ReportSection(heading="Financial summary", kind="kpis", kpis=[
            ReportKpi(label="Revenue", value=_kes(rev), tone="pos"),
            ReportKpi(label="Expenses", value=_kes(exp), tone="neg"),
            ReportKpi(label="Net profit", value=_kes(profit), tone="pos" if profit >= 0 else "neg"),
            ReportKpi(label="Margin", value=f"{(profit / rev * 100).quantize(_Q)}%" if rev > 0 else "—"),
        ]),
        ReportSection(heading="Revenue by type", kind="breakdown", breakdown=[
            BreakdownRow(label=rt.title(), value=_kes(a), pct=str((Decimal(a) / rev * 100).quantize(_Q)) if rev > 0 else None)
            for rt, a in rev_res.all()
        ]),
        ReportSection(heading="Expenses by category", kind="breakdown", breakdown=[
            BreakdownRow(label=n, value=_kes(a), pct=str((Decimal(a) / exp_total * 100).quantize(_Q)) if exp_total > 0 else None)
            for n, a in cats
        ]),
    ]


async def _production_sections(db, farm, s, e) -> list[ReportSection]:
    eggs = await _sum(db, ProductionRecord.eggs_collected, [
        ProductionRecord.farm_id == _fid(farm.id), ProductionRecord.deleted_at.is_(None),
        ProductionRecord.record_date >= s, ProductionRecord.record_date <= e])
    broken = await _sum(db, ProductionRecord.broken_eggs, [
        ProductionRecord.farm_id == _fid(farm.id), ProductionRecord.deleted_at.is_(None),
        ProductionRecord.record_date >= s, ProductionRecord.record_date <= e])
    feed = await _sum(db, DailyLog.feed_consumed_kg, [
        DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None),
        DailyLog.log_date >= s, DailyLog.log_date <= e])
    series = await _daily_prod_series(db, farm.id, s, e)
    return [
        ReportSection(heading="Production summary", kind="kpis", kpis=[
            ReportKpi(label="Eggs collected", value=f"{int(eggs):,}"),
            ReportKpi(label="Broken eggs", value=f"{int(broken):,}"),
            ReportKpi(label="Feed consumed", value=f"{feed:,} kg"),
        ]),
        ReportSection(heading="Egg production trend", kind="series", series=series, series_keys=["Eggs"]),
    ]


async def _mortality_sections(db, farm, s, e) -> list[ReportSection]:
    mort = await _sum(db, DailyLog.mortality_count, [
        DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None),
        DailyLog.log_date >= s, DailyLog.log_date <= e])
    culls = await _sum(db, DailyLog.culls, [
        DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None),
        DailyLog.log_date >= s, DailyLog.log_date <= e])
    series = await _daily_mortality_series(db, farm.id, s, e)
    return [
        ReportSection(heading="Mortality summary", kind="kpis", kpis=[
            ReportKpi(label="Deaths", value=f"{int(mort):,}", tone="neg"),
            ReportKpi(label="Culls", value=f"{int(culls):,}"),
            ReportKpi(label="Total loss", value=f"{int(mort) + int(culls):,}", tone="neg"),
        ]),
        ReportSection(heading="Mortality & culls trend", kind="series", series=series, series_keys=["Mortality", "Culls"]),
    ]


async def _sales_sections(db, farm, s, e) -> list[ReportSection]:
    res = await db.execute(
        select(RevenueRecord.revenue_date, RevenueRecord.revenue_type, RevenueRecord.amount, RevenueRecord.buyer_name)
        .where(RevenueRecord.farm_id == _fid(farm.id), RevenueRecord.deleted_at.is_(None),
               RevenueRecord.revenue_date >= s, RevenueRecord.revenue_date <= e)
        .order_by(RevenueRecord.revenue_date.desc()).limit(100)
    )
    rows = [[d.isoformat(), rt.title(), _kes(a), b or "—"] for d, rt, a, b in res.all()]
    total = await _rev_total(db, farm.id, s, e)
    return [
        ReportSection(heading="Sales summary", kind="kpis", kpis=[
            ReportKpi(label="Total sales", value=_kes(total), tone="pos"),
            ReportKpi(label="Transactions", value=str(len(rows))),
        ]),
        ReportSection(heading="Sales", kind="table", table_columns=["Date", "Type", "Amount", "Buyer"], table_rows=rows),
    ]


async def _purchases_sections(db, farm, s, e) -> list[ReportSection]:
    res = await db.execute(
        select(Expense.expense_date, ExpenseCategory.name, Expense.amount, Expense.supplier, Expense.description)
        .join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(Expense.farm_id == _fid(farm.id), Expense.deleted_at.is_(None),
               Expense.expense_date >= s, Expense.expense_date <= e)
        .order_by(Expense.expense_date.desc()).limit(100)
    )
    rows = [[d.isoformat(), n, _kes(a), sup or "—", (desc or "")[:40]] for d, n, a, sup, desc in res.all()]
    total = await _exp_total(db, farm.id, s, e)
    return [
        ReportSection(heading="Purchases summary", kind="kpis", kpis=[
            ReportKpi(label="Total purchases", value=_kes(total), tone="neg"),
            ReportKpi(label="Transactions", value=str(len(rows))),
        ]),
        ReportSection(heading="Purchases", kind="table", table_columns=["Date", "Category", "Amount", "Supplier", "Description"], table_rows=rows),
    ]


async def _vaccination_sections(db, farm, s, e) -> list[ReportSection]:
    res = await db.execute(
        select(VaccinationRecord.administered_date, VaccinationRecord.vaccine_name, Flock.name, VaccinationRecord.next_due_date)
        .join(Flock, VaccinationRecord.flock_id == Flock.id)
        .where(VaccinationRecord.farm_id == _fid(farm.id), VaccinationRecord.deleted_at.is_(None),
               VaccinationRecord.administered_date >= s, VaccinationRecord.administered_date <= e)
        .order_by(VaccinationRecord.administered_date.desc()).limit(100)
    )
    rows = [[d.isoformat(), v, fn, nd.isoformat() if nd else "—"] for d, v, fn, nd in res.all()]
    overdue = await db.execute(
        select(func.count(VaccinationRecord.id)).where(
            VaccinationRecord.farm_id == _fid(farm.id), VaccinationRecord.deleted_at.is_(None),
            VaccinationRecord.next_due_date.is_not(None), VaccinationRecord.next_due_date < date.today())
    )
    return [
        ReportSection(heading="Vaccination summary", kind="kpis", kpis=[
            ReportKpi(label="Administered", value=str(len(rows))),
            ReportKpi(label="Overdue", value=str(int(overdue.scalar_one())), tone="warn"),
        ]),
        ReportSection(heading="Vaccinations", kind="table", table_columns=["Date", "Vaccine", "Flock", "Next due"], table_rows=rows),
    ]


async def _health_sections(db, farm, s, e) -> list[ReportSection]:
    from app.services import health_service
    summary = await health_service.get_farm_health_summary(db, farm)
    return [ReportSection(heading="Health summary", kind="kpis", kpis=[
        ReportKpi(label="Open events", value=str(summary.open_events), tone="warn" if summary.open_events else None),
        ReportKpi(label="Critical open", value=str(summary.critical_open), tone="neg" if summary.critical_open else None),
        ReportKpi(label="Overdue vaccinations", value=str(summary.overdue_vaccinations), tone="warn" if summary.overdue_vaccinations else None),
        ReportKpi(label="Active alerts", value=str(summary.active_alert_count)),
    ])]


async def _feed_sections(db, farm, s, e) -> list[ReportSection]:
    from app.services import feed_service
    dash = await feed_service.get_dashboard(db, farm.id)
    an = await feed_service.get_analytics(db, farm.id)
    secs = [ReportSection(heading="Feed summary", kind="kpis", kpis=[
        ReportKpi(label="Stock on hand", value=f"{dash.total_stock_kg:,} kg"),
        ReportKpi(label="Stock value", value=_kes(dash.total_stock_value_kes)),
        ReportKpi(label="Consumed (30d)", value=f"{dash.consumed_kg:,} kg"),
        ReportKpi(label="Low stock", value=str(dash.low_stock_count), tone="warn" if dash.low_stock_count else None),
    ])]
    if an.by_flock:
        secs.append(ReportSection(heading="Feed cost by flock", kind="table",
            table_columns=["Flock", "Consumed (kg)", "Cost", "FCR", "Cost/bird"],
            table_rows=[[f.flock_name, str(f.consumed_kg), _kes(f.feed_cost_kes),
                         str(f.fcr) if f.fcr else "—", _kes(f.cost_per_bird_kes) if f.cost_per_bird_kes else "—"]
                        for f in an.by_flock]))
    return secs


async def _inventory_sections(db, farm, s, e) -> list[ReportSection]:
    from app.services import inventory_service
    dash = await inventory_service.get_dashboard(db, farm.id)
    return [
        ReportSection(heading="Inventory summary", kind="kpis", kpis=[
            ReportKpi(label="Inventory value", value=_kes(dash.total_inventory_value)),
            ReportKpi(label="Items", value=str(dash.item_count)),
            ReportKpi(label="Low / out", value=f"{dash.low_stock_count} / {dash.out_of_stock_count}", tone="warn"),
            ReportKpi(label="Expiring", value=str(dash.expiring_count), tone="warn" if dash.expiring_count else None),
        ]),
        ReportSection(heading="Value by category", kind="breakdown", breakdown=[
            BreakdownRow(label=c.category.replace("_", " ").title(), value=_kes(c.total_value)) for c in dash.category_valuation
        ]),
    ]


async def _assets_sections(db, farm, s, e) -> list[ReportSection]:
    from app.services import inventory_service
    assets = await inventory_service.list_assets(db, farm.id)
    total_val = sum((Decimal(a.current_value) for a in assets), Decimal("0"))
    total_dep = sum((Decimal(a.accumulated_depreciation) for a in assets), Decimal("0"))
    rows = [[a.name, a.asset_type.replace("_", " ").title(), _kes(a.purchase_price), _kes(a.current_value), a.condition.title()] for a in assets]
    return [
        ReportSection(heading="Asset summary", kind="kpis", kpis=[
            ReportKpi(label="Assets", value=str(len(assets))),
            ReportKpi(label="Current value", value=_kes(total_val)),
            ReportKpi(label="Accumulated depreciation", value=_kes(total_dep)),
        ]),
        ReportSection(heading="Assets", kind="table", table_columns=["Name", "Type", "Cost", "Value", "Condition"], table_rows=rows),
    ]


async def _maintenance_sections(db, farm, s, e) -> list[ReportSection]:
    from app.services import inventory_service
    records = await inventory_service.list_maintenance(db, farm.id)
    completed = [m for m in records if m.status == "completed"]
    cost = sum((Decimal(m.cost) for m in completed), Decimal("0"))
    rows = [[m.asset_name, m.title, m.status.title(), _kes(m.cost) if Decimal(m.cost) > 0 else "—",
             (m.completed_date or m.scheduled_date).isoformat() if (m.completed_date or m.scheduled_date) else "—"] for m in records]
    return [
        ReportSection(heading="Maintenance summary", kind="kpis", kpis=[
            ReportKpi(label="Records", value=str(len(records))),
            ReportKpi(label="Completed", value=str(len(completed))),
            ReportKpi(label="Total cost", value=_kes(cost)),
        ]),
        ReportSection(heading="Maintenance", kind="table", table_columns=["Asset", "Title", "Status", "Cost", "Date"], table_rows=rows),
    ]


async def _staff_activity_sections(db, farm, s, e) -> list[ReportSection]:
    res = await db.execute(
        select(AuditLog.user_id, User.full_name, func.count(AuditLog.id))
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(AuditLog.farm_id == _fid(farm.id),
               func.date(AuditLog.created_at) >= s, func.date(AuditLog.created_at) <= e)
        .group_by(AuditLog.user_id, User.full_name).order_by(func.count(AuditLog.id).desc())
    )
    rows = res.all()
    return [
        ReportSection(heading="Staff activity", kind="kpis", kpis=[
            ReportKpi(label="Active staff", value=str(len(rows))),
            ReportKpi(label="Total actions", value=str(sum(int(r[2]) for r in rows))),
        ]),
        ReportSection(heading="Actions by user", kind="breakdown",
                      breakdown=[BreakdownRow(label=(n or "Unknown"), value=str(int(c))) for _uid, n, c in rows]),
    ]


async def _ai_insights_sections(db, farm, s, e) -> list[ReportSection]:
    res = await db.execute(
        select(AIInsight.insight_type, func.count(AIInsight.id))
        .where(AIInsight.farm_id == _fid(farm.id), AIInsight.deleted_at.is_(None))
        .group_by(AIInsight.insight_type)
    )
    rows = res.all()
    return [ReportSection(heading="AI insights", kind="breakdown",
                          breakdown=[BreakdownRow(label=str(t).replace("_", " ").title(), value=str(int(c))) for t, c in rows],
                          note="Insights generated by ARIA across your farm.")]


async def _farm_summary_sections(db, farm, s, e) -> list[ReportSection]:
    rev = await _rev_total(db, farm.id, s, e)
    exp = await _exp_total(db, farm.id, s, e)
    eggs = await _sum(db, ProductionRecord.eggs_collected, [
        ProductionRecord.farm_id == _fid(farm.id), ProductionRecord.deleted_at.is_(None),
        ProductionRecord.record_date >= s, ProductionRecord.record_date <= e])
    mort = await _sum(db, DailyLog.mortality_count, [
        DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None),
        DailyLog.log_date >= s, DailyLog.log_date <= e])
    flock_res = await db.execute(select(func.count(Flock.id)).where(
        Flock.farm_id == _fid(farm.id), Flock.deleted_at.is_(None), Flock.status == "active"))
    sections = [ReportSection(heading="Farm at a glance", kind="kpis", kpis=[
        ReportKpi(label="Active flocks", value=str(int(flock_res.scalar_one()))),
        ReportKpi(label="Revenue", value=_kes(rev), tone="pos"),
        ReportKpi(label="Expenses", value=_kes(exp), tone="neg"),
        ReportKpi(label="Net profit", value=_kes(rev - exp), tone="pos" if rev - exp >= 0 else "neg"),
        ReportKpi(label="Eggs collected", value=f"{int(eggs):,}"),
        ReportKpi(label="Mortality", value=f"{int(mort):,}", tone="neg"),
    ])]
    sections += await _production_sections(db, farm, s, e)
    return sections


_BUILDERS = {
    "farm_summary": _farm_summary_sections,
    "production": _production_sections,
    "finance": _finance_sections,
    "feed": _feed_sections,
    "health": _health_sections,
    "inventory": _inventory_sections,
    "mortality": _mortality_sections,
    "vaccination": _vaccination_sections,
    "sales": _sales_sections,
    "purchases": _purchases_sections,
    "assets": _assets_sections,
    "maintenance": _maintenance_sections,
    "staff_activity": _staff_activity_sections,
    "ai_insights": _ai_insights_sections,
}

_TITLES = {
    "farm_summary": "Farm Summary", "production": "Production Report", "finance": "Finance Report",
    "feed": "Feed Report", "health": "Health Report", "inventory": "Inventory Report",
    "mortality": "Mortality Report", "vaccination": "Vaccination Report", "sales": "Sales Report",
    "purchases": "Purchases Report", "assets": "Asset Report", "maintenance": "Maintenance Report",
    "staff_activity": "Staff Activity Report", "ai_insights": "AI Insights Report",
}


async def generate_report(db, farm: Farm, report_type: str, period_type: str,
                          start: Optional[date], end: Optional[date]) -> Report:
    builder = _BUILDERS.get(report_type)
    if builder is None:
        raise ValidationException(f"Unknown report type '{report_type}'.")
    s, e, label = resolve_period(period_type, start, end)
    sections = await builder(db, farm, s, e)
    ai_context = {
        "report_type": report_type, "period": label,
        "sections": [{"heading": sec.heading, "kpis": {k.label: k.value for k in sec.kpis}} for sec in sections if sec.kpis],
    }
    return Report(
        report_type=report_type, title=_TITLES.get(report_type, report_type.title()),
        period_label=label, start_date=s, end_date=e, generated_at=datetime.now(tz=timezone.utc),
        sections=sections, ai_context=ai_context,
    )


# ── Role dashboards ───────────────────────────────────────────────────────────

_DASHBOARD_REPORTS = {
    "executive": ["farm_summary", "finance", "health"],
    "farm_manager": ["production", "feed", "mortality", "inventory"],
    "veterinary": ["health", "vaccination", "mortality"],
    "finance": ["finance", "sales", "purchases"],
    "production": ["production", "feed", "mortality"],
    "inventory": ["inventory", "assets", "maintenance"],
}


async def get_dashboard(db, farm: Farm, role: str) -> Report:
    types = _DASHBOARD_REPORTS.get(role)
    if types is None:
        raise ValidationException(f"Unknown dashboard '{role}'.")
    s, e, label = resolve_period("monthly", None, None)
    sections: list[ReportSection] = []
    for rt in types:
        # Take the first (summary) section of each report to keep dashboards concise.
        secs = await _BUILDERS[rt](db, farm, s, e)
        if secs:
            sections.append(secs[0])
    return Report(
        report_type=f"dashboard_{role}", title=f"{role.replace('_', ' ').title()} Dashboard",
        period_label=label, start_date=s, end_date=e, generated_at=datetime.now(tz=timezone.utc),
        sections=sections, ai_context={"dashboard": role, "period": label},
    )


# ── Comparisons ───────────────────────────────────────────────────────────────

async def get_comparison(db, farm: Farm, comparison_type: str,
                         flock_a: Optional[uuid.UUID] = None, flock_b: Optional[uuid.UUID] = None) -> Report:
    today = date.today()
    if comparison_type == "month_vs_month":
        cur_s = date(today.year, today.month, 1)
        prev_end = cur_s - timedelta(days=1)
        prev_s = date(prev_end.year, prev_end.month, 1)
        section = await _compare_windows(db, farm, ("This month", cur_s, today), ("Last month", prev_s, prev_end))
        title = "Month vs Month"
    elif comparison_type == "year_vs_year":
        cur_s = date(today.year, 1, 1)
        prev_s = date(today.year - 1, 1, 1)
        prev_e = date(today.year - 1, today.month, today.day)
        section = await _compare_windows(db, farm, (str(today.year), cur_s, today), (str(today.year - 1), prev_s, prev_e))
        title = "Year vs Year"
    elif comparison_type == "flock_vs_flock":
        if not flock_a or not flock_b:
            raise ValidationException("flock_vs_flock requires flock_a and flock_b.")
        section = await _compare_flocks(db, farm, flock_a, flock_b)
        title = "Flock vs Flock"
    else:
        raise ValidationException(f"Unknown comparison '{comparison_type}'.")
    return Report(
        report_type=f"comparison_{comparison_type}", title=title, period_label="Comparison",
        start_date=today, end_date=today, generated_at=datetime.now(tz=timezone.utc),
        sections=[section], ai_context={"comparison": comparison_type},
    )


async def _compare_windows(db, farm, a: tuple, b: tuple) -> ReportSection:
    (la, sa, ea), (lb, sb, eb) = a, b
    rev_a, rev_b = await _rev_total(db, farm.id, sa, ea), await _rev_total(db, farm.id, sb, eb)
    exp_a, exp_b = await _exp_total(db, farm.id, sa, ea), await _exp_total(db, farm.id, sb, eb)
    eggs_a = await _sum(db, ProductionRecord.eggs_collected, [ProductionRecord.farm_id == _fid(farm.id), ProductionRecord.deleted_at.is_(None), ProductionRecord.record_date >= sa, ProductionRecord.record_date <= ea])
    eggs_b = await _sum(db, ProductionRecord.eggs_collected, [ProductionRecord.farm_id == _fid(farm.id), ProductionRecord.deleted_at.is_(None), ProductionRecord.record_date >= sb, ProductionRecord.record_date <= eb])
    mort_a = await _sum(db, DailyLog.mortality_count, [DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None), DailyLog.log_date >= sa, DailyLog.log_date <= ea])
    mort_b = await _sum(db, DailyLog.mortality_count, [DailyLog.farm_id == _fid(farm.id), DailyLog.deleted_at.is_(None), DailyLog.log_date >= sb, DailyLog.log_date <= eb])
    rows = [
        ["Revenue", _kes(rev_a), _kes(rev_b), _delta(rev_a, rev_b)],
        ["Expenses", _kes(exp_a), _kes(exp_b), _delta(exp_a, exp_b)],
        ["Net profit", _kes(rev_a - exp_a), _kes(rev_b - exp_b), _delta(rev_a - exp_a, rev_b - exp_b)],
        ["Eggs", f"{int(eggs_a):,}", f"{int(eggs_b):,}", _delta(eggs_a, eggs_b)],
        ["Mortality", f"{int(mort_a):,}", f"{int(mort_b):,}", _delta(mort_a, mort_b)],
    ]
    return ReportSection(heading=f"{la} vs {lb}", kind="table", table_columns=["Metric", la, lb, "Change"], table_rows=rows)


async def _compare_flocks(db, farm, fa: uuid.UUID, fb: uuid.UUID) -> ReportSection:
    async def stats(fid):
        flock = (await db.execute(select(Flock).where(Flock.id == _fid(fid), Flock.farm_id == _fid(farm.id), Flock.deleted_at.is_(None)))).scalar_one_or_none()
        if flock is None:
            raise NotFoundException("Flock not found.")
        eggs = await _sum(db, ProductionRecord.eggs_collected, [ProductionRecord.flock_id == _fid(fid), ProductionRecord.deleted_at.is_(None)])
        mort = await _sum(db, DailyLog.mortality_count, [DailyLog.flock_id == _fid(fid), DailyLog.deleted_at.is_(None)])
        feed = await _sum(db, DailyLog.feed_consumed_kg, [DailyLog.flock_id == _fid(fid), DailyLog.deleted_at.is_(None)])
        rev = await _sum(db, RevenueRecord.amount, [RevenueRecord.flock_id == _fid(fid), RevenueRecord.deleted_at.is_(None)])
        return flock, eggs, mort, feed, rev
    (fla, ea, ma, fea, ra), (flb, eb, mb, feb, rb) = await stats(fa), await stats(fb)
    rows = [
        ["Placed", f"{fla.initial_count:,}", f"{flb.initial_count:,}", "—"],
        ["Eggs", f"{int(ea):,}", f"{int(eb):,}", _delta(ea, eb)],
        ["Mortality", f"{int(ma):,}", f"{int(mb):,}", _delta(ma, mb)],
        ["Feed (kg)", f"{fea:,}", f"{feb:,}", _delta(fea, feb)],
        ["Revenue", _kes(ra), _kes(rb), _delta(ra, rb)],
    ]
    return ReportSection(heading=f"{fla.name} vs {flb.name}", kind="table", table_columns=["Metric", fla.name, flb.name, "Change"], table_rows=rows)


def _delta(a, b) -> str:
    a, b = Decimal(a), Decimal(b)
    if b == 0:
        return "—" if a == 0 else "▲ new"
    pct = ((a - b) / b * 100).quantize(_Q)
    return f"{'▲' if pct >= 0 else '▼'} {abs(pct)}%"


# ── Saved reports ─────────────────────────────────────────────────────────────

async def create_saved_report(db, farm_id, user: User, data: SavedReportCreate) -> SavedReport:
    sr = SavedReport(farm_id=farm_id, user_id=user.id, name=data.name, report_type=data.report_type,
                     config=data.config, is_pinned=data.is_pinned)
    db.add(sr)
    await db.commit()
    await db.refresh(sr)
    return sr


async def list_saved_reports(db, farm_id) -> list[SavedReport]:
    res = await db.execute(select(SavedReport).where(
        SavedReport.farm_id == _fid(farm_id), SavedReport.deleted_at.is_(None))
        .order_by(SavedReport.is_pinned.desc(), SavedReport.updated_at.desc()))
    return list(res.scalars().all())


async def update_saved_report(db, farm_id, report_id, data: SavedReportUpdate) -> SavedReport:
    res = await db.execute(select(SavedReport).where(
        SavedReport.id == _fid(report_id), SavedReport.farm_id == _fid(farm_id), SavedReport.deleted_at.is_(None)))
    sr = res.scalar_one_or_none()
    if sr is None:
        raise NotFoundException("Saved report not found.")
    for f in ("name", "config", "is_pinned"):
        v = getattr(data, f)
        if v is not None:
            setattr(sr, f, v)
    await db.commit()
    await db.refresh(sr)
    return sr


async def delete_saved_report(db, farm_id, report_id) -> None:
    res = await db.execute(select(SavedReport).where(
        SavedReport.id == _fid(report_id), SavedReport.farm_id == _fid(farm_id), SavedReport.deleted_at.is_(None)))
    sr = res.scalar_one_or_none()
    if sr is None:
        raise NotFoundException("Saved report not found.")
    sr.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── CSV export ────────────────────────────────────────────────────────────────

def report_to_csv(report: Report) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([report.title, report.period_label])
    w.writerow([])
    for sec in report.sections:
        w.writerow([sec.heading])
        if sec.kind == "kpis":
            for k in sec.kpis:
                w.writerow([k.label, k.value])
        elif sec.kind == "breakdown":
            for b in sec.breakdown:
                w.writerow([b.label, b.value, f"{b.pct}%" if b.pct else ""])
        elif sec.kind == "table":
            w.writerow(sec.table_columns)
            for row in sec.table_rows:
                w.writerow(row)
        elif sec.kind == "series":
            w.writerow(["period", *sec.series_keys])
            for pt in sec.series:
                w.writerow([pt.get("period"), *[pt.get(k) for k in sec.series_keys]])
        w.writerow([])
    return buf.getvalue()
