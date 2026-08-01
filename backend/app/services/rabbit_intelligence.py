"""
Greena — Rabbit Intelligence (Module 17, Milestone 10)

The PURE, deterministic engine behind Mission Control's rabbit briefing (Spec
Part 6 §13-15, Part 7 §11). It **reads** the already-computed rabbit deterministic
outputs (the executive dashboard, forecast, growth progress, bottlenecks) and
identifies risks, reproduction/health issues, financial problems and growth
deviations — every insight citing the recorded/calculated/forecast evidence it
rests on. It never recomputes a figure; the deterministic engines remain the
single source of truth.

Mirrors ``bsf_intelligence`` / ``aviculture_intelligence`` (same Evidence/Insight/
Briefing shape) so Mission Control consumes every module identically. Health
insights are patterns, never diagnoses (frozen §4.4); growth insights never
mutate the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL, WARNING, WATCH, INFO = "critical", "warning", "watch", "info"
_SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, WATCH: 2, INFO: 3}

_HIGH_MORTALITY_PCT = 15.0
_CRIT_MORTALITY_PCT = 25.0
_LOW_KINDLING_PCT = 60.0
_THIN_MARGIN_PCT = 15.0


def _val(x):
    return x.get("value") if isinstance(x, dict) else x


def _label(x) -> str:
    return x.get("label", "recorded") if isinstance(x, dict) else "recorded"


@dataclass
class Evidence:
    source: str
    value: str | None
    fact_type: str


@dataclass
class Insight:
    category: str
    severity: str
    title: str
    detail: str
    evidence: list[Evidence] = field(default_factory=list)
    confidence: str = "high"
    limitations: str = ""


@dataclass
class Briefing:
    headline: str
    summaries: dict
    insights: list[Insight]
    priorities: list[str]
    counts: dict


def _ev(source: str, figure) -> Evidence:
    v = _val(figure)
    return Evidence(source=source, value=None if v is None else str(v), fact_type=_label(figure))


def build_briefing(*, dashboard: dict, forecast: dict, growth: dict | None,
                   bottlenecks: list[dict]) -> Briefing:
    """Compose the strategic rabbit briefing from deterministic outputs (read-only)."""
    facts = dashboard.get("recorded_facts", {}).get("population", {})
    reproduction = dashboard.get("reproduction", {})
    health = dashboard.get("health", {})
    finance = dashboard.get("finance", {}).get("pnl", {})
    housing = dashboard.get("housing", {})

    insights: list[Insight] = []
    insights += _bottleneck_insights(bottlenecks)
    insights += _reproduction_risks(reproduction)
    insights += _health_risks(health)
    insights += _financial_issues(finance)
    insights += _housing_risks(housing)
    insights += _growth_deviation(growth)

    insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 99))
    counts = {sev: sum(1 for i in insights if i.severity == sev) for sev in (CRITICAL, WARNING, WATCH, INFO)}

    summaries = {
        "recorded_facts": facts, "reproduction": reproduction, "health": health,
        "finance": finance, "housing": housing, "forecast": forecast,
        "bottlenecks": bottlenecks, "growth": growth,
    }
    priorities = _priorities(insights)
    headline = _headline(counts, facts)
    return Briefing(headline=headline, summaries=summaries, insights=insights,
                    priorities=priorities, counts=counts)


def _bottleneck_insights(bottlenecks: list[dict]) -> list[Insight]:
    out: list[Insight] = []
    sev_map = {"critical": CRITICAL, "high": WARNING, "medium": WATCH, "low": INFO}
    for b in bottlenecks:
        out.append(Insight(
            "risk", sev_map.get(b.get("severity"), WATCH),
            f"Bottleneck: {b.get('constraint')}",
            f"{b.get('impact')} Recommended: {b.get('recommended_action')}",
            [Evidence(source=f"bottleneck.{b.get('constraint')}", value=str(b.get("evidence")),
                      fact_type="calculated")],
            confidence=b.get("confidence", "medium"),
            limitations="Deterministic threshold flag; ARIA explains, the farmer decides."))
    return out


def _reproduction_risks(reproduction: dict) -> list[Insight]:
    out: list[Insight] = []
    kr = _val(reproduction.get("kindling_rate_pct"))
    if kr is not None and kr < _LOW_KINDLING_PCT:
        out.append(Insight(
            "reproduction", WARNING, f"Low kindling rate ({kr}%)",
            "Below-target kindling success is limiting kit production.",
            [_ev("reproduction.kindling_rate_pct", reproduction.get("kindling_rate_pct"))],
            confidence="medium",
            limitations="From recorded services and litters; review buck fertility and doe condition."))
    return out


def _health_risks(health: dict) -> list[Insight]:
    out: list[Insight] = []
    mr = _val(health.get("mortality_rate_pct"))
    if mr is not None and mr >= _HIGH_MORTALITY_PCT:
        sev = CRITICAL if mr >= _CRIT_MORTALITY_PCT else WARNING
        out.append(Insight(
            "health", sev, f"Elevated mortality ({mr}%)",
            "Recorded mortality is above threshold and warrants review. "
            "This is an operational pattern, not a veterinary diagnosis.",
            [_ev("health.mortality_rate_pct", health.get("mortality_rate_pct"))],
            confidence="medium",
            limitations="Pattern only; cause is not assessed. Consult recorded mortality causes."))
    return out


def _financial_issues(finance: dict) -> list[Insight]:
    out: list[Insight] = []
    margin = _val(finance.get("gross_margin_pct"))
    gross = _val(finance.get("gross_profit"))
    if gross is not None and gross < 0:
        out.append(Insight(
            "finance", WARNING, "Operating at a loss",
            f"Recorded gross profit is {gross}. Costs exceed recorded sale revenue.",
            [_ev("finance.gross_profit", finance.get("gross_profit")),
             _ev("finance.revenue", finance.get("revenue")),
             _ev("finance.total_cost", finance.get("total_cost"))],
            limitations="From recorded sale facts, feed allocation and rabbit-tagged ledger costs only."))
    elif margin is not None and margin < _THIN_MARGIN_PCT:
        out.append(Insight(
            "finance", WATCH, f"Thin margin ({margin}%)",
            "Gross margin is below a comfortable threshold; review feed cost and pricing.",
            [_ev("finance.gross_margin_pct", finance.get("gross_margin_pct"))],
            confidence="medium", limitations="Excludes costs not posted to the shared ledger."))
    return out


def _housing_risks(housing: dict) -> list[Insight]:
    out: list[Insight] = []
    overcrowded = housing.get("overcrowded_cages", [])
    if overcrowded:
        out.append(Insight(
            "housing", WARNING, f"{len(overcrowded)} overcrowded cage(s)",
            "One or more cages exceed recorded capacity — welfare and disease risk.",
            [Evidence("housing.overcrowded_cages", str(len(overcrowded)), "calculated")],
            confidence="high",
            limitations="Occupancy derived from active rabbits; capacity is a recorded fact."))
    return out


def _growth_deviation(growth: dict | None) -> list[Insight]:
    if not growth:
        return []
    overall = _val(growth.get("overall_percent"))
    if overall is None:
        return []
    out: list[Insight] = []
    behind = []
    for g in growth.get("goals", []):
        verdict = _val((g.get("run_rate") or {}).get("verdict"))
        if verdict == "overdue":
            behind.append(g.get("label") or g.get("metric_key"))
    if behind:
        out.append(Insight(
            "growth", WARNING, "Growth goal overdue",
            f"Recorded progress leaves {', '.join(behind)} past its target date. "
            "ARIA can suggest a revised plan — it will not change the plan for you.",
            [Evidence("growth.overall_percent", str(overall), "calculated")],
            confidence="medium",
            limitations="Based on recorded actuals vs the plan; revise the plan explicitly if goals changed."))
    else:
        out.append(Insight(
            "growth", INFO, f"Growth progress {overall}%",
            "Progress toward the primary growth goal, from recorded operational data.",
            [Evidence("growth.overall_percent", str(overall), "calculated")]))
    return out


def _priorities(insights: list[Insight]) -> list[str]:
    return [i.title for i in insights if i.severity in (CRITICAL, WARNING)][:5]


def _headline(counts: dict, facts: dict) -> str:
    total = _val(facts.get("total_rabbits"))
    if counts.get(CRITICAL):
        return f"{counts[CRITICAL]} critical issue(s) need attention across {total} active rabbit(s)."
    if counts.get(WARNING):
        return f"{counts[WARNING]} item(s) to watch across {total} active rabbit(s)."
    return f"Operations on track across {total} active rabbit(s)."
