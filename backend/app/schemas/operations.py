"""
Greena — Operations Director schemas (Module 13 Part 7).

Wire shapes for the organization-scale operations layer: aggregated organization
facts, cross-farm comparison, the operations dashboard, the merged timeline,
performance analytics, role-based workspace scope and organization reports.

Every aggregate mirrors the engine's honesty contract — it carries the farms that
contributed, the farms that were missing, and the calculation method — so the
client can render "not enough recorded data" and never a fabricated total.
"""

from __future__ import annotations

import uuid

from pydantic import Field

from app.schemas.base import AGRIOSSchema


# ── Provenance ────────────────────────────────────────────────────────────────


class OpsAggregate(AGRIOSSchema):
    key: str
    label: str
    value: str | None
    unit: str
    available: bool
    source_farms: list[str]
    missing_farms: list[str]
    method: str


# ── 1. Organization intelligence ──────────────────────────────────────────────


class OpsOrgPriority(AGRIOSSchema):
    rank: int
    label: str
    why: str
    farm_id: str
    farm_name: str
    severity: str
    source: str


class OpsOrganizationFacts(AGRIOSSchema):
    organization_name: str
    as_of: str
    farm_count: int
    farm_names: list[str]
    overall: str
    health: OpsAggregate
    production: OpsAggregate
    mortality: OpsAggregate
    feed_usage: OpsAggregate
    water_usage: OpsAggregate
    inventory: OpsAggregate
    financial: OpsAggregate
    priorities: list[OpsOrgPriority]
    silent_farms: list[str]


# ── 2. Cross-farm comparison ──────────────────────────────────────────────────


class OpsFarmRank(AGRIOSSchema):
    farm_id: str
    farm_name: str
    value: float | None
    display: str
    available: bool


class OpsRanking(AGRIOSSchema):
    key: str
    label: str
    unit: str
    higher_is_better: bool
    ranked: list[OpsFarmRank]
    missing: list[OpsFarmRank]
    best: OpsFarmRank | None
    needs_attention: OpsFarmRank | None
    average: str | None
    method: str


class OpsComparison(AGRIOSSchema):
    farm_count: int
    rankings: list[OpsRanking]


# ── 3/4. Workers & tasks ──────────────────────────────────────────────────────


class OpsWorker(AGRIOSSchema):
    user_id: str
    name: str
    role: str
    role_label: str
    farm_ids: list[str]
    farm_names: list[str]


class OpsTaskHistoryEvent(AGRIOSSchema):
    at: str
    action: str
    actor: str
    detail: str = ""


class OpsTask(AGRIOSSchema):
    task_id: str
    farm_id: str
    farm_name: str
    title: str
    status: str
    priority: str
    owner_id: str | None
    owner_name: str | None
    due_at: str | None
    created_at: str | None
    completed_at: str | None
    history: list[OpsTaskHistoryEvent] = Field(default_factory=list)


class OpsTaskAssign(AGRIOSSchema):
    owner_id: uuid.UUID


# ── 5. Dashboard ──────────────────────────────────────────────────────────────


class OpsFarmSummary(AGRIOSSchema):
    farm_id: str
    farm_name: str
    overall: str
    health_score: int
    open_tasks: int
    overdue_tasks: int
    alert_count: int
    silent: bool


class OpsAlert(AGRIOSSchema):
    at: str
    farm_id: str
    farm_name: str
    kind: str
    title: str
    detail: str
    severity: str


class OpsNotification(AGRIOSSchema):
    at: str
    farm_id: str
    farm_name: str
    title: str
    body: str
    severity: str


class OpsDashboard(AGRIOSSchema):
    as_of: str
    tier: str
    sections: list[str]
    organization: OpsOrganizationFacts
    farms: list[OpsFarmSummary]
    alerts: list[OpsAlert]
    priorities: list[OpsOrgPriority]
    tasks: list[OpsTask]
    workers: list[OpsWorker]
    notifications: list[OpsNotification]
    operational_status: str


# ── 6. Timeline ───────────────────────────────────────────────────────────────


class OpsTimelineEvent(AGRIOSSchema):
    at: str
    farm_id: str
    farm_name: str
    kind: str
    title: str
    detail: str
    worker: str | None
    severity: str


# ── 7. Performance analytics ──────────────────────────────────────────────────


class OpsWorkerPerformance(AGRIOSSchema):
    user_id: str
    name: str
    assigned: int
    completed: int
    overdue: int
    completion_rate: str | None
    avg_completion_hours: str | None
    method: str


class OpsMetric(AGRIOSSchema):
    key: str
    label: str
    value: str | None
    unit: str
    available: bool
    method: str
    detail: str = ""


class OpsAnalytics(AGRIOSSchema):
    workers: list[OpsWorkerPerformance]
    farm_productivity: list[OpsMetric]
    org_metrics: list[OpsMetric]
    trends: list[OpsMetric]


# ── 9. Reports ────────────────────────────────────────────────────────────────


class OpsReportSection(AGRIOSSchema):
    label: str
    value: str
    available: bool
    method: str = ""


class OpsReport(AGRIOSSchema):
    period: str
    label: str
    as_of: str
    organization_name: str
    farm_count: int
    sections: list[OpsReportSection]
    risks: list[str]
    priorities: list[str]
    notes: list[str]
