"""
Greena — Mission Control schemas (Module 14).

Wire shapes for missions and everything computed from them. The recurring atom is
`MValue` — a labelled figure carrying its `fact_type` (recorded fact, calculated
forecast, strategic recommendation, or AI suggestion), so the client can render
the honesty distinction the spec demands rather than presenting every number as
equally certain.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from app.schemas.base import AGRIOSSchema


# ── Atoms ─────────────────────────────────────────────────────────────────────


class MValue(AGRIOSSchema):
    label: str
    value: str | None
    fact_type: str
    detail: str = ""
    unit: str = ""
    available: bool = True


class MetricIn(AGRIOSSchema):
    kind: str                 # birds | profit | revenue | farms | qualitative
    label: str
    target: float | None = None
    unit: str = ""
    primary: bool = False


class AssumptionIn(AGRIOSSchema):
    key: str
    label: str = ""
    value: str | int | float | bool | None = None
    unit: str = ""
    source: str = "edited"


class PolicyIn(AGRIOSSchema):
    key: str
    statement: str
    category: str = "general"     # financial | risk | expansion | supplier | general
    value: str | int | float | None = None


# ── Mission CRUD ──────────────────────────────────────────────────────────────


class MissionCreate(AGRIOSSchema):
    name: str
    description: str = ""
    target_date: date | None = None
    status: str = "active"
    is_primary: bool = False
    success_metrics: list[MetricIn] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    priorities: list[str] = Field(default_factory=list)
    assumptions: list[AssumptionIn] = Field(default_factory=list)
    policies: list[PolicyIn] = Field(default_factory=list)


class MissionUpdate(AGRIOSSchema):
    name: str | None = None
    description: str | None = None
    target_date: date | None = None
    status: str | None = None
    is_primary: bool | None = None
    success_metrics: list[MetricIn] | None = None
    constraints: list[str] | None = None
    priorities: list[str] | None = None
    assumptions: list[AssumptionIn] | None = None
    policies: list[PolicyIn] | None = None


class MissionOut(AGRIOSSchema):
    id: str
    farm_id: str
    name: str
    description: str | None
    target_date: str | None
    status: str
    is_primary: bool
    success_metrics: list[dict]
    constraints: list[str]
    priorities: list[str]
    assumptions: list[dict]
    policies: list[dict]
    baseline: dict
    created_at: str


# ── Discovery ─────────────────────────────────────────────────────────────────


class DiscoveryQuestion(AGRIOSSchema):
    key: str
    prompt: str
    kind: str
    unit: str = ""
    options: list[str] = Field(default_factory=list)
    why: str = ""


# ── Roadmap ───────────────────────────────────────────────────────────────────


class PhaseOut(AGRIOSSchema):
    index: int
    name: str
    objectives: list[str]
    infrastructure: list[str]
    bird_target: int | None
    financial_target: MValue
    operational_targets: list[str]
    start_date: str | None
    end_date: str | None
    duration_days: int | None
    completion_criteria: list[str]
    dependencies: list[str]
    risks: list[str]
    fact_type: str


class RoadmapOut(AGRIOSSchema):
    mission_name: str
    metric_kind: str
    baseline_value: float | None
    target_value: float | None
    phases: list[PhaseOut]
    method: str
    notes: list[str]


# ── Business plan ─────────────────────────────────────────────────────────────


class PlanSectionOut(AGRIOSSchema):
    heading: str
    body: list[MValue]
    fact_type: str


class BusinessPlanOut(AGRIOSSchema):
    mission_name: str
    as_of: str
    sections: list[PlanSectionOut]
    notes: list[str]


# ── Daily mission ─────────────────────────────────────────────────────────────


class DailyMissionOut(AGRIOSSchema):
    on: str
    headline: str
    phase: str
    critical_tasks: list[MValue]
    risks: list[MValue]
    opportunities: list[MValue]
    budget: MValue
    purchases: list[MValue]
    records_required: list[MValue]
    kpis: list[MValue]


# ── Progress ──────────────────────────────────────────────────────────────────


class MilestoneOut(AGRIOSSchema):
    name: str
    target: str
    done: bool
    detail: str


class ProgressOut(AGRIOSSchema):
    completion_pct: float
    completion_explanation: str
    current_phase_name: str
    current_phase_index: int
    milestones: list[MilestoneOut]
    financial: MValue
    population: MValue
    infrastructure: MValue
    profit: MValue
    cash_reserve: MValue
    time_remaining_days: int | None
    time_elapsed_pct: float | None
    forecasted_completion: MValue
    on_track: bool
    metrics: list[MValue]


# ── Adaptation / revisions ────────────────────────────────────────────────────


class AdaptationOut(AGRIOSSchema):
    needed: bool
    trigger: str
    reasons: list[str]
    recommendations: list[str]
    detail: list[MValue]


class RevisionCreate(AGRIOSSchema):
    reason: str = "Manual revision"


class ReplanRequest(AGRIOSSchema):
    assumptions: list[AssumptionIn] | None = None
    target_date: date | None = None


class RevisionOut(AGRIOSSchema):
    id: str
    revision_number: int
    reason: str | None
    trigger: str
    snapshot: dict
    created_at: str


class ReplanOut(AGRIOSSchema):
    revision_number: int
    applied: bool
    evaluation: AdaptationOut


# ── Health / reports ──────────────────────────────────────────────────────────


class HealthFactorOut(AGRIOSSchema):
    label: str
    score: int
    max_score: int
    explanation: str


class MissionHealthOut(AGRIOSSchema):
    score: int
    grade: str
    factors: list[HealthFactorOut]


class ReportOut(AGRIOSSchema):
    period: str
    label: str
    as_of: str
    mission_name: str
    health: MissionHealthOut
    progress_vs_plan: list[MValue]
    budget_vs_plan: list[MValue]
    growth_vs_plan: list[MValue]
    upcoming_decisions: list[str]
    recommended_actions: list[str]
    notes: list[str]


# ── Manual ────────────────────────────────────────────────────────────────────


class ManualSectionOut(AGRIOSSchema):
    heading: str
    items: list[str]


class ManualOut(AGRIOSSchema):
    mission_name: str
    as_of: str
    sections: list[ManualSectionOut]


# ── Dashboard ─────────────────────────────────────────────────────────────────


class DashboardOut(AGRIOSSchema):
    mission_name: str
    status: str
    completion_pct: float
    current_phase: str
    daily: DailyMissionOut
    upcoming_milestones: list[MilestoneOut]
    risks: list[MValue]
    cash_runway: MValue
    budget_status: MValue
    population: MValue
    revenue: MValue
    profit: MValue
    operations_health: MValue
    health: MissionHealthOut
    time_remaining_days: int | None


# ── CEO advisor ───────────────────────────────────────────────────────────────


class AdvisorRequest(AGRIOSSchema):
    question: str


class AdvisorOut(AGRIOSSchema):
    question: str
    answer: str
    provider: str
    grounded_context: str
    fact_type: str
    sources: list[str]


# ── Aviculture integration (Module 15, Part 11) ───────────────────────────────


class InsightEvidenceOut(AGRIOSSchema):
    source: str                 # dotted engine path the figure came from
    value: str | None
    fact_type: str              # recorded | calculated | forecast | unknown


class InsightOut(AGRIOSSchema):
    category: str               # risk | overdue_work | breeding | incubation | finance | population
    severity: str               # critical | warning | watch | info
    title: str
    detail: str                 # reasoning
    evidence: list[InsightEvidenceOut]
    confidence: str = "high"    # high | medium | low
    limitations: str = ""       # honest caveat (Doc 15 §15)


class AvicultureBriefingOut(AGRIOSSchema):
    headline: str
    summaries: dict             # consumed engine outputs, honesty labels intact
    insights: list[InsightOut]
    priorities: list[str]
    counts: dict
