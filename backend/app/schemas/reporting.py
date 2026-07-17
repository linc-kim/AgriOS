"""
Greena — Reporting & Business Intelligence Schemas (Module 7).

A uniform, section-based report payload: every report (and dashboard and
comparison) is a list of typed sections the frontend renders generically —
KPI tiles, charts (series), tables and breakdown bars.
"""

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import AGRIOSSchema, TimestampedSchema

ReportType = Literal[
    "farm_summary", "production", "finance", "feed", "health", "inventory",
    "mortality", "vaccination", "sales", "purchases", "assets", "maintenance",
    "staff_activity", "ai_insights",
]
DashboardRole = Literal["executive", "farm_manager", "veterinary", "finance", "production", "inventory"]
PeriodType = Literal["daily", "weekly", "monthly", "quarterly", "annual", "custom"]
ComparisonType = Literal["month_vs_month", "year_vs_year", "flock_vs_flock"]


class ReportKpi(AGRIOSSchema):
    label: str
    value: str
    sub: Optional[str] = None
    tone: Optional[str] = None       # pos | neg | warn


class BreakdownRow(AGRIOSSchema):
    label: str
    value: str
    pct: Optional[str] = None


class ReportSection(AGRIOSSchema):
    heading: str
    kind: Literal["kpis", "series", "table", "breakdown", "note"]
    kpis: list[ReportKpi] = Field(default_factory=list)
    # series: list of {period, <key>: number, ...}; series_keys names the numeric keys.
    series: list[dict] = Field(default_factory=list)
    series_keys: list[str] = Field(default_factory=list)
    table_columns: list[str] = Field(default_factory=list)
    table_rows: list[list[Any]] = Field(default_factory=list)
    breakdown: list[BreakdownRow] = Field(default_factory=list)
    note: Optional[str] = None


class Report(AGRIOSSchema):
    report_type: str
    title: str
    period_label: str
    start_date: date
    end_date: date
    generated_at: datetime
    sections: list[ReportSection]
    ai_context: dict


# ── Saved reports ─────────────────────────────────────────────────────────────

class SavedReportCreate(AGRIOSSchema):
    name: str = Field(..., min_length=1, max_length=200)
    report_type: ReportType
    config: dict = Field(default_factory=dict)
    is_pinned: bool = False


class SavedReportUpdate(AGRIOSSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict | None = None
    is_pinned: bool | None = None


class SavedReportResponse(TimestampedSchema):
    farm_id: UUID
    user_id: UUID | None
    name: str
    report_type: str
    config: dict
    is_pinned: bool
