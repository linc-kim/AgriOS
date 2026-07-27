"""
Greena — Mission Control (Module 14): the strategic engine.

Mission Control is not another assistant. It is the layer that turns a farmer's
long-term vision — "reach 10,000 layers", "KES 2,000,000 annual profit", "expand
to three farms" — into a roadmap, a living business plan, a daily mission, a
progress tracker and adaptive revisions. And it does so by *orchestrating the
engines already built*, never by re-deriving their numbers: it calls the pure
`aria_planning`, `aria_supervisor` and `aria_intelligence` functions over the
same `FarmFacts` snapshot the rest of ARIA uses, and composes their outputs.

Everything here is pure and deterministic, exactly like the engines it stands on.
No database, no clock beyond a passed-in `today`, no model. That is what lets the
whole strategy be tested exhaustively, and what lets the honesty rules be
enforced rather than hoped for. Every figure it emits carries a `fact_type`:

  * RECORDED    — a number the farm actually logged.
  * FORECAST    — a deterministic projection, with its method stated.
  * RECOMMENDATION — a strategic suggestion from the deterministic rules.
  * AI          — reserved for the Gemini advisor layer (added by the data layer).

Projections are never presented as promises, assumptions are never invented, and
where the future is uncertain the output says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from math import ceil

from app.services import aria_intelligence, aria_planning, aria_supervisor
from app.services.aria_intelligence import FarmFacts
from app.services.aria_supervisor import MonitorState


class FactType(str, Enum):
    RECORDED = "recorded_fact"
    FORECAST = "calculated_forecast"
    RECOMMENDATION = "strategic_recommendation"
    AI = "ai_suggestion"


class MetricKind(str, Enum):
    BIRDS = "birds"
    PROFIT = "profit"
    REVENUE = "revenue"
    FARMS = "farms"
    QUALITATIVE = "qualitative"


UNKNOWN = "Not enough recorded data."


# ── Inputs ────────────────────────────────────────────────────────────────────


@dataclass
class Metric:
    kind: str
    label: str
    target: float | None
    unit: str = ""
    primary: bool = False


@dataclass
class MissionSpec:
    name: str
    description: str
    target_date: date | None
    metrics: list[Metric] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    priorities: list[str] = field(default_factory=list)
    assumptions: list[dict] = field(default_factory=list)   # {key,label,value,unit,source}
    policies: list[dict] = field(default_factory=list)       # {key,statement,category,value}
    baseline: dict = field(default_factory=dict)             # {metric_kind: value} at creation
    status: str = "active"
    created_on: date | None = None

    @property
    def primary_metric(self) -> Metric | None:
        for m in self.metrics:
            if m.primary:
                return m
        return self.metrics[0] if self.metrics else None

    def assumption(self, key: str, default=None):
        for a in self.assumptions:
            if a.get("key") == key:
                return a.get("value", default)
        return default


@dataclass
class Value:
    """A labelled figure — the atom of every Mission Control output."""

    label: str
    value: str | None
    fact_type: FactType
    detail: str = ""
    unit: str = ""

    @property
    def available(self) -> bool:
        return self.value is not None


def recorded(label, value, unit="", detail="") -> Value:
    return Value(label, _fmt(value), FactType.RECORDED, detail, unit)


def forecast(label, value, unit="", detail="") -> Value:
    return Value(label, _fmt(value), FactType.FORECAST, detail, unit)


def recommend(label, value, detail="") -> Value:
    return Value(label, value, FactType.RECOMMENDATION, detail)


def _fmt(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v % 1 else str(int(v))
    if isinstance(v, float):
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return str(v)


# ── Live metric reads ─────────────────────────────────────────────────────────


def current_metric_value(kind: str, facts: FarmFacts, *, farm_count: int = 1) -> float | None:
    if kind == MetricKind.BIRDS:
        return float(facts.total_birds) if facts.total_birds else 0.0
    if kind == MetricKind.PROFIT:
        return float(facts.gross_profit) if facts.gross_profit is not None else None
    if kind == MetricKind.REVENUE:
        return float(facts.revenue) if facts.revenue is not None else None
    if kind == MetricKind.FARMS:
        return float(farm_count)
    return None  # qualitative


# ── 2. Discovery interview ────────────────────────────────────────────────────


@dataclass
class Question:
    key: str
    prompt: str
    kind: str                 # number | choice | boolean | text
    unit: str = ""
    options: list[str] = field(default_factory=list)
    why: str = ""


def discovery_questions() -> list[Question]:
    """
    The structured interview that turns a vision into planning assumptions.

    Deterministic and fixed — the same questions every time — so the assumptions
    they produce are auditable. The Gemini advisor may *rephrase* these
    conversationally, but the assumption keys they populate are stable.
    """
    return [
        Question("current_birds", "How many birds do you keep today?", "number", "birds",
                 why="Anchors the roadmap's starting point."),
        Question("capital_available", "How much capital can you invest now?", "number", "KES",
                 why="Sets how fast the first phase can move."),
        Question("take_loans", "Are you willing to take loans?", "boolean",
                 why="Decides whether financing appears in the plan."),
        Question("risk_tolerance", "How much risk are you comfortable with?", "choice",
                 options=["low", "medium", "high"], why="Tunes expansion pace and cash buffers."),
        Question("land_available", "How much land is available (in units of a poultry house)?",
                 "number", "houses", why="Caps infrastructure growth."),
        Question("will_hire", "Do you plan to hire workers?", "boolean",
                 why="Feeds the operational and cost plan."),
        Question("production_system", "Which production system do you prefer?", "choice",
                 options=["deep litter", "battery cage", "free range"],
                 why="Affects capacity and cost assumptions."),
        Question("hours_per_day", "How many hours can you personally dedicate each day?", "number",
                 "hours", why="Sizes the daily mission realistically."),
        Question("reinvest_profits", "Will you reinvest profits into growth?", "boolean",
                 why="Determines the self-funding expansion path."),
        Question("monthly_reinvest_pct", "What share of profit will you reinvest each month?",
                 "number", "%", why="Drives the retained-earnings expansion rate."),
    ]


def assumptions_from_answers(answers: dict) -> list[dict]:
    """Turn interview answers into structured, editable assumptions."""
    labels = {q.key: (q.prompt, q.unit) for q in discovery_questions()}
    out: list[dict] = []
    for key, value in answers.items():
        prompt, unit = labels.get(key, (key, ""))
        out.append({"key": key, "label": prompt, "value": value, "unit": unit, "source": "interview"})
    return out


# ── 3. Master roadmap ─────────────────────────────────────────────────────────


@dataclass
class Phase:
    index: int
    name: str
    objectives: list[str]
    infrastructure: list[str]
    bird_target: int | None
    financial_target: Value
    operational_targets: list[str]
    start_date: date | None
    end_date: date | None
    duration_days: int | None
    completion_criteria: list[str]
    dependencies: list[str]
    risks: list[str]
    fact_type: FactType = FactType.FORECAST


@dataclass
class Roadmap:
    mission_name: str
    metric_kind: str
    baseline_value: float | None
    target_value: float | None
    phases: list[Phase]
    method: str
    notes: list[str] = field(default_factory=list)


def _house_capacity(facts: FarmFacts) -> int:
    caps = [int(h.get("capacity") or 0) for h in facts.houses if h.get("capacity")]
    return max(caps) if caps else 1000  # conventional default, stated in notes


def build_roadmap(
    mission: MissionSpec, facts: FarmFacts, *, today: date, phases: int = 3, farm_count: int = 1
) -> Roadmap:
    """
    Phase the journey from where the farm is to the mission's target.

    The gap between baseline and target is divided into equal phases across the
    time to the target date. Infrastructure need is derived from house capacity,
    financial targets from the deterministic cash-flow projection. Nothing is
    promised — every phase is a FORECAST with its completion criteria stated.
    """
    metric = mission.primary_metric
    notes: list[str] = []
    if metric is None or metric.target is None or metric.kind == MetricKind.QUALITATIVE:
        return _qualitative_roadmap(mission, facts, today=today, phases=phases)

    baseline = mission.baseline.get(metric.kind)
    if baseline is None:
        baseline = current_metric_value(metric.kind, facts, farm_count=farm_count) or 0.0
    target = float(metric.target)
    gap = target - baseline

    # Time split.
    horizon_days = (mission.target_date - today).days if mission.target_date else 365
    horizon_days = max(horizon_days, phases)  # at least a day per phase
    per_phase_days = horizon_days // phases

    cap = _house_capacity(facts)
    if not facts.houses:
        notes.append(f"No house capacity on record — assuming {cap} birds/house for infrastructure estimates.")

    monthly_cash = _monthly_net(facts)

    out_phases: list[Phase] = [_current_state_phase(mission, facts, baseline, metric)]
    for i in range(1, phases + 1):
        phase_target = baseline + gap * (i / phases)
        start = today + timedelta(days=per_phase_days * (i - 1))
        end = today + timedelta(days=per_phase_days * i) if i < phases else (mission.target_date or today + timedelta(days=horizon_days))

        bird_target = int(round(phase_target)) if metric.kind == MetricKind.BIRDS else None
        infra: list[str] = []
        if metric.kind == MetricKind.BIRDS:
            houses_needed = ceil(phase_target / cap)
            have = len(facts.houses) or 0
            if houses_needed > have:
                infra.append(f"{houses_needed - have} additional house(s) (to hold {bird_target} birds at {cap}/house)")
            else:
                infra.append("Existing housing is sufficient for this phase")

        fin_target = _phase_financial_target(metric, phase_target, facts, monthly_cash, per_phase_days)

        out_phases.append(Phase(
            index=i,
            name=f"Phase {i}",
            objectives=_phase_objectives(metric, phase_target, i, phases),
            infrastructure=infra,
            bird_target=bird_target,
            financial_target=fin_target,
            operational_targets=_phase_ops_targets(mission, facts),
            start_date=start,
            end_date=end,
            duration_days=(end - start).days if end and start else None,
            completion_criteria=_phase_completion(metric, phase_target),
            dependencies=([] if i == 1 else [f"Phase {i-1} complete"]) + _capital_dependency(mission),
            risks=_phase_risks(mission, facts),
        ))

    # Final goal marker.
    out_phases.append(Phase(
        index=phases + 1, name="Mission achieved",
        objectives=[f"{metric.label}: {_fmt(target)} {metric.unit}".strip()],
        infrastructure=[], bird_target=int(target) if metric.kind == MetricKind.BIRDS else None,
        financial_target=recommend("Goal", f"{metric.label} reached"),
        operational_targets=[], start_date=mission.target_date, end_date=mission.target_date,
        duration_days=0, completion_criteria=[f"{metric.label} ≥ {_fmt(target)}"],
        dependencies=[f"Phase {phases} complete"], risks=[], fact_type=FactType.RECOMMENDATION,
    ))

    method = (f"Baseline {_fmt(baseline)} → target {_fmt(target)} {metric.unit}, "
              f"split into {phases} equal phases over {horizon_days} days.")
    return Roadmap(mission.name, metric.kind, baseline, target, out_phases, method, notes)


def _current_state_phase(mission, facts, baseline, metric) -> Phase:
    return Phase(
        index=0, name="Current state",
        objectives=[f"{metric.label} now: {_fmt(baseline)} {metric.unit}".strip()],
        infrastructure=[f"{len(facts.houses)} house(s) on record"],
        bird_target=facts.total_birds if metric.kind == MetricKind.BIRDS else None,
        financial_target=recorded("Net position",
                                  facts.gross_profit if facts.is_profitable is not None else None, "KES"),
        operational_targets=[], start_date=mission.created_on, end_date=mission.created_on,
        duration_days=0, completion_criteria=[], dependencies=[], risks=[],
        fact_type=FactType.RECORDED,
    )


def _qualitative_roadmap(mission, facts, *, today, phases) -> Roadmap:
    horizon = (mission.target_date - today).days if mission.target_date else 365
    per = max(1, horizon // phases)
    ph = [_current_state_phase(mission, facts, None, Metric("qualitative", mission.name, None))]
    stages = ["Assess & prepare", "Transition", "Certify & scale"]
    for i in range(1, phases + 1):
        ph.append(Phase(
            index=i, name=f"Phase {i}: {stages[(i-1) % len(stages)]}",
            objectives=[f"Advance '{mission.name}' — {stages[(i-1) % len(stages)].lower()}"],
            infrastructure=[], bird_target=None,
            financial_target=recommend("Budget", "Scoped during this phase"),
            operational_targets=mission.priorities[:3],
            start_date=today + timedelta(days=per * (i - 1)),
            end_date=today + timedelta(days=per * i),
            duration_days=per, completion_criteria=[f"{stages[(i-1) % len(stages)]} milestones met"],
            dependencies=([] if i == 1 else [f"Phase {i-1} complete"]),
            risks=_phase_risks(mission, facts),
        ))
    return Roadmap(mission.name, "qualitative", None, None, ph,
                   "Qualitative mission — phased into assess, transition and certify/scale stages.",
                   ["This mission has no single numeric target, so phases track milestones, not numbers."])


def _phase_objectives(metric, target, i, n) -> list[str]:
    if metric.kind == MetricKind.BIRDS:
        return [f"Grow flock to {int(target)} birds", "Keep mortality within target", "Maintain production per bird"]
    if metric.kind in (MetricKind.PROFIT, MetricKind.REVENUE):
        return [f"Reach {metric.label.lower()} of {_fmt(target)}", "Control feed cost share", "Protect margins"]
    if metric.kind == MetricKind.FARMS:
        return [f"Operate {int(target)} farm(s)", "Standardise operations across sites"]
    return [f"Advance toward {metric.label}"]


def _phase_ops_targets(mission, facts) -> list[str]:
    targets = ["Record feed, eggs and mortality daily", "Keep vaccinations on schedule"]
    for p in mission.policies:
        if p.get("category") == "risk" and "mortality" in (p.get("key", "") + p.get("statement", "")).lower():
            targets.append(f"Policy: {p.get('statement')}")
    return targets


def _phase_completion(metric, target) -> list[str]:
    if metric.kind == MetricKind.BIRDS:
        return [f"Active flock ≥ {int(target)} birds", "Housing in place for the new birds"]
    if metric.kind in (MetricKind.PROFIT, MetricKind.REVENUE):
        return [f"{metric.label} run-rate ≥ {_fmt(target)}"]
    return [f"{metric.label} milestone reached"]


def _capital_dependency(mission) -> list[str]:
    if str(mission.assumption("take_loans")).lower() in ("false", "no", "0", "none"):
        return ["Funded from retained earnings (no loans)"]
    return []


def _phase_risks(mission, facts) -> list[str]:
    risks: list[str] = []
    monitors = aria_supervisor.run_monitors(facts)
    for m in monitors:
        if m.state in (MonitorState.WARNING, MonitorState.CRITICAL):
            risks.append(f"{m.label}: {m.why}")
    if str(mission.assumption("risk_tolerance")).lower() == "low":
        risks.append("Low risk tolerance — pace expansion conservatively.")
    if not risks:
        risks.append("No elevated operational risks on record right now.")
    return risks[:5]


def _monthly_net(facts: FarmFacts) -> Decimal | None:
    if facts.gross_profit is None:
        return None
    # gross_profit is a period figure already; treat as monthly proxy, stated in method.
    return facts.gross_profit


def _phase_financial_target(metric, phase_target, facts, monthly_cash, days) -> Value:
    if metric.kind in (MetricKind.PROFIT, MetricKind.REVENUE):
        return forecast(metric.label, phase_target, "KES",
                        "Interpolated from baseline to target across phases.")
    if monthly_cash is not None:
        est = monthly_cash * Decimal(days) / Decimal(30)
        return forecast("Expected net over phase", est, "KES",
                        "Recent net position projected across the phase length.")
    return Value("Expected net over phase", None, FactType.FORECAST,
                 "No finance recorded yet — cannot project.", "KES")


# ── 4. Master business plan ───────────────────────────────────────────────────


@dataclass
class PlanSection:
    heading: str
    body: list[Value]
    fact_type: FactType = FactType.FORECAST


@dataclass
class BusinessPlan:
    mission_name: str
    as_of: date
    sections: list[PlanSection]
    notes: list[str] = field(default_factory=list)


def build_business_plan(mission: MissionSpec, facts: FarmFacts, roadmap: Roadmap, *, today: date) -> BusinessPlan:
    """
    A living business plan, composed from recorded facts and deterministic
    projections. It never freezes a number: because it is computed on demand from
    the current facts, it updates itself and cannot go stale.
    """
    cashflow = aria_planning.project_cashflow(facts, days=30)
    budget = aria_planning.plan_budget(facts, "monthly")
    health = aria_intelligence.compute_health_score(facts)
    metric = mission.primary_metric

    sections = [
        PlanSection("Executive summary", [
            recommend("Mission", mission.name),
            recommend("In one line",
                      f"Move {metric.label if metric else 'the farm'} from "
                      f"{_fmt(roadmap.baseline_value)} to {_fmt(roadmap.target_value)} "
                      f"by {mission.target_date or 'the target date'}."),
            recorded("Farm health today", health.score, "/100", health.grade),
        ], FactType.RECOMMENDATION),
        PlanSection("Current position", [
            recorded("Active birds", facts.total_birds, "birds"),
            recorded("Houses", len(facts.houses), "houses"),
            recorded("Weekly production", facts.eggs_this_week if facts.days_since_egg_log is not None else None, "eggs"),
            recorded("Net position",
                     facts.gross_profit if facts.is_profitable is not None else None, "KES"),
        ], FactType.RECORDED),
        PlanSection("Expansion strategy",
                    [recommend(f"Phase {p.index}", "; ".join(p.objectives)) for p in roadmap.phases if p.index >= 1],
                    FactType.RECOMMENDATION),
        PlanSection("Financial strategy", [
            forecast("30-day expected income", cashflow.expected_income, "KES"),
            forecast("30-day expected expenses", cashflow.expected_expenses, "KES"),
            forecast("30-day net", cashflow.net, "KES", cashflow.outlook),
            recommend("Funding approach",
                      "Retained earnings only (no loans)"
                      if str(mission.assumption("take_loans")).lower() in ("false", "no", "none")
                      else "Mix of retained earnings and financing"),
        ]),
        PlanSection("Operational strategy", [
            recommend("Cadence", "Daily recording of feed, eggs and mortality; weekly weigh-ins"),
            recommend("Staffing",
                      "Plan to hire" if str(mission.assumption("will_hire")).lower() in ("true", "yes") else "Owner-operated for now"),
        ]),
        PlanSection("Marketing strategy", [
            recommend("Channel", "Local off-take and repeat buyers; track egg price against the market"),
        ]),
        PlanSection("Risk register",
                    [recommend("Risk", r) for r in (roadmap.phases[1].risks if len(roadmap.phases) > 1 else [])]
                    or [recommend("Risk", "No elevated operational risks on record right now.")],
                    FactType.RECOMMENDATION),
        PlanSection("Capital requirements", _capital_requirements(mission, facts, roadmap)),
        PlanSection("Projected cash flow", [
            forecast("Expected income (30d)", cashflow.expected_income, "KES"),
            forecast("Expected expenses (30d)", cashflow.expected_expenses, "KES"),
            forecast("Net (30d)", cashflow.net, "KES"),
        ]),
        PlanSection("Projected costs",
                    [forecast(line.category, line.amount, "KES", line.basis) for line in budget.lines]
                    if budget.available else [Value("Costs", None, FactType.FORECAST, "; ".join(budget.notes) or UNKNOWN)]),
    ]
    notes = [
        "This plan is computed live from your recorded data every time it is opened, "
        "so it stays current as the farm changes.",
        "Figures are labelled: recorded facts, calculated forecasts, or strategic recommendations.",
    ]
    return BusinessPlan(mission.name, today, sections, notes)


def _capital_requirements(mission, facts, roadmap) -> list[Value]:
    cap = _house_capacity(facts)
    out: list[Value] = []
    for p in roadmap.phases:
        if p.index >= 1 and p.infrastructure and "additional" in " ".join(p.infrastructure):
            out.append(recommend(f"Phase {p.index} infrastructure", "; ".join(p.infrastructure)))
    if not out:
        out.append(recommend("Infrastructure", "No additional housing required by the current plan."))
    out.append(forecast("Assumed house capacity", cap, "birds/house",
                        "From your largest recorded house" if facts.houses else "Default — no houses on record."))
    return out


# ── 5. Daily mission engine ───────────────────────────────────────────────────


@dataclass
class DailyMission:
    on: date
    headline: str
    phase: str
    critical_tasks: list[Value]
    risks: list[Value]
    opportunities: list[Value]
    budget: Value
    purchases: list[Value]
    records_required: list[Value]
    kpis: list[Value]


def daily_mission(mission: MissionSpec, facts: FarmFacts, roadmap: Roadmap, progress: "Progress", *, today: date) -> DailyMission:
    """
    Today's slice of the mission, tying each task back to a phase objective.

    Reuses the supervisor's ranked priorities and the planner's calendar rather
    than inventing a separate to-do list — the daily mission is the strategic
    framing of work the existing engines already surface.
    """
    monitors = aria_supervisor.run_monitors(facts)
    now_dt = _as_dt(today)
    priorities = aria_supervisor.build_priorities(facts, now=now_dt)
    alerts = aria_supervisor.build_alerts(facts, now=now_dt, monitors=monitors)
    calendar = aria_planning.build_calendar(facts, days=1)
    budget = aria_planning.plan_budget(facts, "weekly")

    phase = progress.current_phase_name
    tasks = [Value(p.label, p.why, FactType.RECOMMENDATION,
                   detail=f"Serves: {phase}") for p in priorities[:5]]
    if not tasks:
        tasks = [recommend("Record today's feed, eggs and mortality", "The mission runs on daily data.")]

    risks = [Value(a.title, a.reason, FactType.RECORDED, a.action) for a in alerts[:3]]
    if not risks:
        risks = [recorded("No thresholds crossed", "All monitors normal today.")]

    opportunities = _daily_opportunities(facts, roadmap, progress)

    day_budget = (budget.total / Decimal(7)) if budget.available else None
    records = [recommend("Feed used (kg)", "Log today's feed"),
               recommend("Eggs collected", "Log today's collection"),
               recommend("Mortality", "Log any losses, even one bird")]

    purchases = [Value(e.title, e.why, FactType.RECOMMENDATION, e.on) for e in calendar
                 if e.kind in ("feed", "inventory", "purchase")][:3]
    if not purchases:
        purchases = [recorded("No purchases scheduled today", "")]

    kpis = [
        recorded("Health score", aria_intelligence.compute_health_score(facts).score, "/100"),
        recorded("Eggs this week", facts.eggs_this_week if facts.days_since_egg_log is not None else None, "eggs"),
        recorded("Mortality this week", facts.mortality_this_week if facts.days_since_any_log is not None else None, "birds"),
        forecast("Mission progress", progress.completion_pct, "%", progress.completion_explanation),
    ]

    headline = f"Today: advance {mission.name} — you are in {phase}."
    return DailyMission(
        on=today, headline=headline, phase=phase, critical_tasks=tasks, risks=risks,
        opportunities=opportunities,
        budget=forecast("Today's budget", day_budget, "KES", "Weekly budget ÷ 7") if day_budget is not None
               else Value("Today's budget", None, FactType.FORECAST, "No spend recorded to base a budget on.", "KES"),
        purchases=purchases, records_required=records, kpis=kpis,
    )


def _daily_opportunities(facts, roadmap, progress) -> list[Value]:
    out: list[Value] = []
    if facts.feed_days_remaining is not None and facts.feed_days_remaining > 14:
        out.append(recommend("Feed well-stocked", f"~{facts.feed_days_remaining} days of feed — good buffer."))
    if progress.on_track:
        out.append(recommend("On track", "You are ahead of or on the plan — consider bringing a milestone forward."))
    if not out:
        out.append(recommend("Steady progress", "Keep recording daily — consistency is the opportunity."))
    return out[:3]


# ── 6. Progress tracker ───────────────────────────────────────────────────────


@dataclass
class Milestone:
    name: str
    target: str
    done: bool
    detail: str


@dataclass
class Progress:
    completion_pct: float
    completion_explanation: str
    current_phase_name: str
    current_phase_index: int
    milestones: list[Milestone]
    financial: Value
    population: Value
    infrastructure: Value
    profit: Value
    cash_reserve: Value
    time_remaining_days: int | None
    time_elapsed_pct: float | None
    forecasted_completion: Value
    on_track: bool
    metrics: list[Value]


def build_progress(mission: MissionSpec, facts: FarmFacts, roadmap: Roadmap, *, today: date, farm_count: int = 1) -> Progress:
    """
    Where the mission stands, with every percentage explained.

    Completion is measured against the mission's primary metric, from an honest
    baseline captured at creation. Forecasted completion is a linear extrapolation
    of the progress rate — clearly a FORECAST, never a promise.
    """
    metric = mission.primary_metric
    baseline = (mission.baseline.get(metric.kind) if metric else None)
    current = current_metric_value(metric.kind, facts, farm_count=farm_count) if metric else None
    target = metric.target if metric else None

    if metric is None or metric.kind == MetricKind.QUALITATIVE or target is None:
        pct, explanation = _phase_based_completion(roadmap, today)
    elif baseline is None or current is None:
        pct, explanation = 0.0, "Not enough recorded data to measure progress yet."
    else:
        denom = (target - baseline)
        pct = 0.0 if denom == 0 else max(0.0, min(100.0, (current - baseline) / denom * 100))
        explanation = (f"{metric.label}: {_fmt(current)} of {_fmt(target)} target "
                       f"(started at {_fmt(baseline)}) = {pct:.1f}%.")

    # Time.
    total_days = (mission.target_date - (mission.created_on or today)).days if mission.target_date else None
    remaining = (mission.target_date - today).days if mission.target_date else None
    elapsed_pct = None
    if total_days and total_days > 0:
        elapsed = (today - (mission.created_on or today)).days
        elapsed_pct = max(0.0, min(100.0, elapsed / total_days * 100))

    on_track = elapsed_pct is None or pct >= elapsed_pct - 5

    forecasted = _forecast_completion(mission, pct, today)
    current_phase_idx, current_phase_name = _current_phase(roadmap, today)

    milestones = [
        Milestone(p.name, "; ".join(p.completion_criteria) or "—",
                  done=_phase_done(p, current_phase_idx),
                  detail=f"{p.start_date} → {p.end_date}" if p.start_date else "")
        for p in roadmap.phases if p.index >= 1
    ]

    return Progress(
        completion_pct=round(pct, 1), completion_explanation=explanation,
        current_phase_name=current_phase_name, current_phase_index=current_phase_idx,
        milestones=milestones,
        financial=_financial_progress(mission, facts),
        population=_population_progress(facts, baseline if metric and metric.kind == MetricKind.BIRDS else None, target if metric and metric.kind == MetricKind.BIRDS else None),
        infrastructure=recorded("Houses", len(facts.houses), "houses"),
        profit=recorded("Net position", facts.gross_profit if facts.is_profitable is not None else None, "KES"),
        cash_reserve=_cash_reserve(facts),
        time_remaining_days=remaining, time_elapsed_pct=round(elapsed_pct, 1) if elapsed_pct is not None else None,
        forecasted_completion=forecasted, on_track=on_track,
        metrics=_all_metric_progress(mission, facts, farm_count),
    )


def _phase_based_completion(roadmap, today) -> tuple[float, str]:
    phases = [p for p in roadmap.phases if p.index >= 1]
    if not phases:
        return 0.0, "No phases defined."
    done = sum(1 for p in phases if p.end_date and p.end_date < today)
    pct = done / len(phases) * 100
    return pct, f"{done} of {len(phases)} phases past their end date = {pct:.0f}% (time-based, qualitative mission)."


def _forecast_completion(mission, pct, today) -> Value:
    if not mission.created_on or pct <= 0:
        return Value("Forecasted completion", None, FactType.FORECAST,
                     "Not enough progress yet to project a completion date.")
    elapsed = max(1, (today - mission.created_on).days)
    rate = pct / elapsed  # pct per day
    if rate <= 0:
        return Value("Forecasted completion", None, FactType.FORECAST, "Progress has stalled.")
    remaining_days = (100 - pct) / rate
    eta = today + timedelta(days=int(remaining_days))
    on_time = mission.target_date is None or eta <= mission.target_date
    detail = (f"At the current rate ({rate:.2f}%/day since start). "
              + ("On track for the target date." if on_time else "Later than the target date at this pace."))
    return forecast("Forecasted completion", eta.isoformat(), detail=detail)


def _current_phase(roadmap, today) -> tuple[int, str]:
    for p in roadmap.phases:
        if p.index >= 1 and p.start_date and p.end_date and p.start_date <= today <= p.end_date:
            return p.index, p.name
    active = [p for p in roadmap.phases if p.index >= 1 and p.start_date and p.start_date <= today]
    if active:
        last = active[-1]
        return last.index, last.name
    first = next((p for p in roadmap.phases if p.index >= 1), None)
    return (first.index, first.name) if first else (0, "Current state")


def _phase_done(phase, current_idx) -> bool:
    return phase.index < current_idx


def _financial_progress(mission, facts) -> Value:
    metric = mission.primary_metric
    if metric and metric.kind in (MetricKind.PROFIT, MetricKind.REVENUE) and metric.target:
        current = current_metric_value(metric.kind, facts)
        if current is None:
            return Value(metric.label, None, FactType.RECORDED, "No finance recorded yet.")
        pct = max(0.0, min(100.0, current / metric.target * 100))
        return forecast(metric.label, f"{pct:.0f}%", detail=f"{_fmt(current)} of {_fmt(metric.target)} target.")
    return recorded("Net position", facts.gross_profit if facts.is_profitable is not None else None, "KES")


def _population_progress(facts, baseline, target) -> Value:
    if target is None:
        return recorded("Population", facts.total_birds, "birds")
    base = baseline or 0
    denom = target - base
    pct = 0.0 if denom == 0 else max(0.0, min(100.0, (facts.total_birds - base) / denom * 100))
    return forecast("Population", f"{pct:.0f}%", detail=f"{facts.total_birds} of {int(target)} birds (from {int(base)}).")


def _cash_reserve(facts) -> Value:
    # Deterministic proxy: recent net as a reserve indicator; stated honestly.
    if facts.gross_profit is None:
        return Value("Cash reserve", None, FactType.RECORDED, "No finance recorded — reserve unknown.")
    return recorded("Recent net (reserve proxy)", facts.gross_profit, "KES",
                    "Recorded revenue minus expenses for the period. Not a live bank balance.")


def _all_metric_progress(mission, facts, farm_count) -> list[Value]:
    out: list[Value] = []
    for m in mission.metrics:
        cur = current_metric_value(m.kind, facts, farm_count=farm_count)
        if m.target and cur is not None:
            pct = max(0.0, min(100.0, cur / m.target * 100)) if m.kind not in (MetricKind.BIRDS,) or not mission.baseline.get(m.kind) else None
            out.append(forecast(m.label, f"{_fmt(cur)}/{_fmt(m.target)} {m.unit}".strip(),
                                detail=f"{pct:.0f}% of target" if pct is not None else ""))
        else:
            out.append(recorded(m.label, cur, m.unit) if cur is not None
                       else Value(m.label, None, FactType.RECORDED, UNKNOWN))
    return out


# ── 7. Adaptive strategy ──────────────────────────────────────────────────────


@dataclass
class RevisionProposal:
    needed: bool
    trigger: str                 # assumption_drift | metric_change | none
    reasons: list[str]
    recommendations: list[str]
    detail: list[Value]


def evaluate_adaptation(mission: MissionSpec, facts: FarmFacts, *, today: date, farm_count: int = 1) -> RevisionProposal:
    """
    Continuously check whether the plan's assumptions still hold.

    Detects drift — production off track, mortality above policy, cash turning
    negative, being behind schedule — and *proposes* a revision. It never rewrites
    the original plan; the data layer records a new revision if the farmer accepts.
    """
    reasons: list[str] = []
    recs: list[str] = []
    detail: list[Value] = []

    progress = build_progress(mission, facts, build_roadmap(mission, facts, today=today, farm_count=farm_count),
                              today=today, farm_count=farm_count)

    if progress.time_elapsed_pct is not None and progress.completion_pct < progress.time_elapsed_pct - 10:
        reasons.append(f"Behind schedule: {progress.completion_pct:.0f}% done vs {progress.time_elapsed_pct:.0f}% of time elapsed.")
        recs.append("Extend the target date or increase the phase pace.")
        detail.append(forecast("Schedule gap",
                               f"{progress.time_elapsed_pct - progress.completion_pct:.0f}", "pts behind"))

    # Mortality vs policy.
    mortality_policy = _numeric_policy(mission, "mortality")
    if mortality_policy is not None and facts.total_birds > 0 and facts.days_since_any_log is not None:
        rate = facts.mortality_this_week / facts.total_birds * 100
        if rate > mortality_policy:
            reasons.append(f"Mortality {rate:.1f}%/wk exceeds your {mortality_policy:.0f}% policy.")
            recs.append("Pause expansion until mortality is back within policy.")
            detail.append(recorded("Weekly mortality", f"{rate:.1f}", "%"))

    # Cash turning negative.
    cashflow = aria_planning.project_cashflow(facts, days=30)
    if cashflow.net is not None and cashflow.net < 0:
        reasons.append("Projected 30-day cash flow is negative.")
        recs.append("Defer discretionary spend; revisit the financial assumptions.")
        detail.append(forecast("30-day net", cashflow.net, "KES", cashflow.outlook))

    # Production trend.
    if facts.days_since_egg_log is not None and facts.eggs_prev_week > 0:
        change = (facts.eggs_this_week - facts.eggs_prev_week) / facts.eggs_prev_week * 100
        if change <= -15:
            reasons.append(f"Egg production fell {abs(change):.0f}% week on week.")
            recs.append("Investigate the production drop before committing to the next phase.")

    return RevisionProposal(
        needed=bool(reasons),
        trigger="assumption_drift" if reasons else "none",
        reasons=reasons or ["Assumptions still hold — no revision needed."],
        recommendations=recs, detail=detail,
    )


def _numeric_policy(mission, keyword) -> float | None:
    for p in mission.policies:
        blob = (p.get("key", "") + " " + p.get("statement", "")).lower()
        if keyword in blob:
            val = p.get("value")
            try:
                if isinstance(val, (int, float)):
                    return float(val)
                import re
                m = re.search(r"(\d+(?:\.\d+)?)", str(val) or p.get("statement", ""))
                return float(m.group(1)) if m else None
            except Exception:
                return None
    return None


# ── Mission health score ──────────────────────────────────────────────────────


@dataclass
class HealthFactor:
    label: str
    score: int
    max_score: int
    explanation: str


@dataclass
class MissionHealth:
    score: int
    grade: str
    factors: list[HealthFactor]


def mission_health(mission: MissionSpec, facts: FarmFacts, progress: Progress) -> MissionHealth:
    """A composite of on-track-ness, operations, finance and policy compliance."""
    factors: list[HealthFactor] = []

    # On-track (40).
    if progress.time_elapsed_pct is None:
        on_track = 30
        expl = "No target date — pace not scored."
    else:
        gap = progress.completion_pct - progress.time_elapsed_pct
        on_track = max(0, min(40, int(20 + gap)))
        expl = f"{progress.completion_pct:.0f}% done vs {progress.time_elapsed_pct:.0f}% time elapsed."
    factors.append(HealthFactor("On schedule", on_track, 40, expl))

    # Operations (30) — reuse farm health.
    farm_health = aria_intelligence.compute_health_score(facts)
    ops = int(farm_health.score / 100 * 30)
    factors.append(HealthFactor("Operations", ops, 30, f"Farm health {farm_health.score}/100 ({farm_health.grade})."))

    # Finance (20).
    if facts.is_profitable is None:
        fin, fexpl = 10, "No finance recorded — scored neutral."
    elif facts.is_profitable:
        fin, fexpl = 20, "Currently profitable on recorded data."
    else:
        fin, fexpl = 5, "Currently running at a recorded loss."
    factors.append(HealthFactor("Finance", fin, 20, fexpl))

    # Policy compliance (10).
    pol = 10
    pexpl = "No policy breaches detected."
    mortality_policy = _numeric_policy(mission, "mortality")
    if mortality_policy is not None and facts.total_birds > 0 and facts.days_since_any_log is not None:
        rate = facts.mortality_this_week / facts.total_birds * 100
        if rate > mortality_policy:
            pol, pexpl = 3, f"Mortality {rate:.1f}%/wk over the {mortality_policy:.0f}% policy."
    factors.append(HealthFactor("Policy compliance", pol, 10, pexpl))

    total = sum(f.score for f in factors)
    grade = "excellent" if total >= 80 else "good" if total >= 60 else "fair" if total >= 40 else "poor"
    return MissionHealth(total, grade, factors)


# ── 10. Living operations manual ──────────────────────────────────────────────


@dataclass
class ManualSection:
    heading: str
    items: list[str]


@dataclass
class OperationsManual:
    mission_name: str
    as_of: date
    sections: list[ManualSection]


def build_manual(mission: MissionSpec, facts: FarmFacts, roadmap: Roadmap, *, today: date) -> OperationsManual:
    """
    A living operations manual, regenerated from current facts so it never drifts
    from how the farm actually runs today.
    """
    cap = _house_capacity(facts)
    sections = [
        ManualSection("Daily routine", [
            "Record feed used (kg), eggs collected, and any mortality — even one bird.",
            "Check feed and water lines first thing.",
            "Walk the houses; note anything unusual for your vet.",
        ]),
        ManualSection("Weekly routine", [
            "Weigh a sample of birds and log it.",
            "Reconcile feed stock against consumption.",
            "Review the week's mortality and production trend.",
        ]),
        ManualSection("Monthly routine", [
            "Review finances: revenue, expenses, net.",
            "Check progress against the mission roadmap.",
            "Reorder consumables ahead of stock-outs.",
        ]),
        ManualSection("Expansion procedure", [
            f"Each new house holds ~{cap} birds (from your records).",
            "Prepare housing and biosecurity before new birds arrive.",
            "Fund from retained earnings" + (" only (per policy)." if _no_loans(mission) else " or agreed financing."),
        ]),
        ManualSection("Emergency procedures", [
            "Sudden water-intake drop: check drinkers, lines and pressure immediately.",
            "Rising mortality: isolate affected birds, record symptoms, call your vet. ARIA does not diagnose disease.",
            "Feed stock-out risk: reorder when under 7 days remaining.",
        ]),
        ManualSection("Hiring checklist", [
            "Define the role against the daily routine above.",
            "Confirm it against your labour budget.",
            "Add the worker to the farm and assign their tasks in the Operations Center.",
        ]),
        ManualSection("Infrastructure checklist", [
            "Confirm land and housing for the next phase's bird target.",
            "Verify ventilation, lighting and biosecurity before stocking.",
        ]),
        ManualSection("Supplier checklist", list(_supplier_items(mission))),
        ManualSection("Equipment checklist", [
            "Feeders and drinkers sized for the target flock.",
            "Weighing scale for weekly weigh-ins.",
            "Records device or notebook for daily logging.",
        ]),
    ]
    return OperationsManual(mission.name, today, sections)


def _no_loans(mission) -> bool:
    return str(mission.assumption("take_loans")).lower() in ("false", "no", "none") or any(
        "no loan" in (p.get("statement", "").lower()) for p in mission.policies)


def _supplier_items(mission) -> list[str]:
    preferred = [p.get("statement") for p in mission.policies if p.get("category") == "supplier"]
    base = ["Keep two feed suppliers to avoid stock-out risk.",
            "Track egg price against the market before selling.",
            "Confirm vaccine cold-chain with your supplier."]
    return ([f"Preferred: {s}" for s in preferred] + base) if preferred else base


# ── 12. Mission reports ───────────────────────────────────────────────────────


@dataclass
class MissionReport:
    period: str                # weekly | monthly | quarterly | annual
    label: str
    as_of: date
    mission_name: str
    health: MissionHealth
    progress_vs_plan: list[Value]
    budget_vs_plan: list[Value]
    growth_vs_plan: list[Value]
    upcoming_decisions: list[str]
    recommended_actions: list[str]
    notes: list[str]


_REPORT_LABELS = {
    "weekly": "Weekly CEO report", "monthly": "Monthly CEO report",
    "quarterly": "Quarterly strategy review", "annual": "Annual mission review",
}


def build_report(mission: MissionSpec, facts: FarmFacts, roadmap: Roadmap, progress: Progress,
                 *, period: str, today: date) -> MissionReport:
    """A CEO report: mission health, progress/budget/growth vs plan, and what to decide next."""
    health = mission_health(mission, facts, progress)
    budget = aria_planning.plan_budget(facts, "monthly")
    adaptation = evaluate_adaptation(mission, facts, today=today)

    progress_vs_plan = [
        forecast("Completion", progress.completion_pct, "%", progress.completion_explanation),
        forecast("Time elapsed", progress.time_elapsed_pct, "%") if progress.time_elapsed_pct is not None
        else Value("Time elapsed", None, FactType.FORECAST, "No target date set."),
        recommend("Status", "On track" if progress.on_track else "Behind plan"),
    ]
    budget_vs_plan = ([forecast(line.category, line.amount, "KES", line.basis) for line in budget.lines]
                      if budget.available else [Value("Budget", None, FactType.FORECAST, UNKNOWN)])
    growth_vs_plan = [
        progress.population, progress.profit, progress.infrastructure,
    ]
    decisions = _upcoming_decisions(mission, roadmap, progress, today)
    actions = adaptation.recommendations or ["Keep executing the current phase; no changes needed."]

    notes = ["Recorded facts, calculated forecasts and recommendations are labelled throughout."]
    if not mission.target_date:
        notes.append("No target date is set, so schedule-based figures are omitted.")
    return MissionReport(
        period=period, label=_REPORT_LABELS.get(period, "CEO report"), as_of=today,
        mission_name=mission.name, health=health, progress_vs_plan=progress_vs_plan,
        budget_vs_plan=budget_vs_plan, growth_vs_plan=growth_vs_plan,
        upcoming_decisions=decisions, recommended_actions=actions, notes=notes,
    )


def _upcoming_decisions(mission, roadmap, progress, today) -> list[str]:
    out: list[str] = []
    for p in roadmap.phases:
        if p.index >= 1 and p.start_date and today <= p.start_date <= today + timedelta(days=30):
            out.append(f"{p.name} starts {p.start_date} — confirm infrastructure and capital.")
    if not progress.on_track:
        out.append("Decide whether to extend the target date or accelerate the current phase.")
    if not out:
        out.append("No major decisions due in the next 30 days.")
    return out[:5]


# ── Dashboard bundle ──────────────────────────────────────────────────────────


@dataclass
class MissionDashboard:
    mission_name: str
    status: str
    completion_pct: float
    current_phase: str
    daily: DailyMission
    upcoming_milestones: list[Milestone]
    risks: list[Value]
    cash_runway: Value
    budget_status: Value
    population: Value
    revenue: Value
    profit: Value
    operations_health: Value
    health: MissionHealth
    time_remaining_days: int | None


def build_dashboard(mission: MissionSpec, facts: FarmFacts, *, today: date, farm_count: int = 1) -> MissionDashboard:
    """One deterministic pass assembling the CEO dashboard from the engines."""
    roadmap = build_roadmap(mission, facts, today=today, farm_count=farm_count)
    progress = build_progress(mission, facts, roadmap, today=today, farm_count=farm_count)
    daily = daily_mission(mission, facts, roadmap, progress, today=today)
    health = mission_health(mission, facts, progress)
    cashflow = aria_planning.project_cashflow(facts, days=30)
    farm_health = aria_intelligence.compute_health_score(facts)

    upcoming = [m for m in progress.milestones if not m.done][:4]
    runway = _cash_reserve(facts)

    return MissionDashboard(
        mission_name=mission.name, status=mission.status,
        completion_pct=progress.completion_pct, current_phase=progress.current_phase_name,
        daily=daily, upcoming_milestones=upcoming, risks=daily.risks,
        cash_runway=forecast("30-day net", cashflow.net, "KES", cashflow.outlook),
        budget_status=runway,
        population=recorded("Population", facts.total_birds, "birds"),
        revenue=recorded("Revenue", facts.revenue if facts.revenue is not None else None, "KES"),
        profit=recorded("Net position", facts.gross_profit if facts.is_profitable is not None else None, "KES"),
        operations_health=recorded("Operations health", farm_health.score, "/100", farm_health.grade),
        health=health, time_remaining_days=progress.time_remaining_days,
    )


def _as_dt(d: date):
    from datetime import datetime
    return datetime(d.year, d.month, d.day, 6, 0, 0)
