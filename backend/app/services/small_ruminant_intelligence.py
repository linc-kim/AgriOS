"""
Greena — Small Ruminant Intelligence (Modules 18/19, Milestone 10)

The PURE, deterministic engine behind Mission Control's goat/sheep briefing. It
**reads** the already-computed deterministic outputs (the executive dashboard,
forecast, growth progress, bottlenecks) and identifies risks, reproduction/health
issues, financial problems and growth deviations — every insight citing the
recorded/calculated/forecast evidence it rests on. It never recomputes a figure.

Mirrors ``bsf_intelligence`` / ``rabbit_intelligence`` (same Evidence/Insight/
Briefing shape) so Mission Control consumes every module identically. Health
insights are patterns, never diagnoses (frozen §4.4); growth insights never mutate
the plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL, WARNING, WATCH, INFO = "critical", "warning", "watch", "info"
_SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, WATCH: 2, INFO: 3}

_HIGH_MORTALITY_PCT = 10.0
_CRIT_MORTALITY_PCT = 20.0
_LOW_BIRTH_RATE_PCT = 60.0
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


def build_briefing(*, species: str, dashboard: dict, forecast: dict, growth: dict | None,
                   bottlenecks: list[dict]) -> Briefing:
    """Compose the strategic goat/sheep briefing from deterministic outputs (read-only)."""
    population = dashboard.get("population", {})
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
        "population": population, "reproduction": reproduction, "health": health,
        "finance": finance, "housing": housing, "forecast": forecast,
        "bottlenecks": bottlenecks, "growth": growth,
    }
    priorities = [i.title for i in insights if i.severity in (CRITICAL, WARNING)][:5]
    active = _val(population.get("active"))
    noun = "goat(s)" if species == "goat" else "sheep"
    if counts.get(CRITICAL):
        headline = f"{counts[CRITICAL]} critical issue(s) need attention across {active} active {noun}."
    elif counts.get(WARNING):
        headline = f"{counts[WARNING]} item(s) to watch across {active} active {noun}."
    else:
        headline = f"Operations on track across {active} active {noun}."
    return Briefing(headline=headline, summaries=summaries, insights=insights,
                    priorities=priorities, counts=counts)


def _bottleneck_insights(bottlenecks: list[dict]) -> list[Insight]:
    out: list[Insight] = []
    sev_map = {"high": WARNING, "medium": WATCH, "low": INFO}
    for b in bottlenecks:
        out.append(Insight(
            "risk", sev_map.get(b.get("severity"), WATCH),
            f"Bottleneck: {b.get('area')}",
            f"{b.get('impact')} Recommended: {b.get('action')}",
            [Evidence(source=f"bottleneck.{b.get('area')}", value=str(b.get("evidence")),
                      fact_type="calculated")],
            confidence=b.get("confidence", "medium"),
            limitations="Deterministic threshold flag; ARIA explains, the farmer decides."))
    return out


def _reproduction_risks(reproduction: dict) -> list[Insight]:
    out: list[Insight] = []
    br = _val(reproduction.get("birth_rate_pct"))
    if br is not None and br < _LOW_BIRTH_RATE_PCT:
        out.append(Insight(
            "reproduction", WARNING, f"Low birth rate ({br}%)",
            "Below-target birthing success is limiting offspring production.",
            [_ev("reproduction.birth_rate_pct", reproduction.get("birth_rate_pct"))],
            confidence="medium",
            limitations="From recorded services and births; review sire fertility and dam condition."))
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
    margin_pct = _val(finance.get("gross_margin_pct"))
    gross = _val(finance.get("gross_margin"))
    if gross is not None and gross < 0:
        out.append(Insight(
            "finance", WARNING, "Operating at a loss",
            f"Recorded gross margin is {gross}. Costs exceed recorded sale revenue.",
            [_ev("finance.gross_margin", finance.get("gross_margin")),
             _ev("finance.revenue", finance.get("revenue")),
             _ev("finance.total_cost", finance.get("total_cost"))],
            limitations="From recorded sale facts, feed allocation and species-tagged ledger costs only."))
    elif margin_pct is not None and margin_pct < _THIN_MARGIN_PCT:
        out.append(Insight(
            "finance", WATCH, f"Thin margin ({margin_pct}%)",
            "Gross margin is below a comfortable threshold; review feed cost and pricing.",
            [_ev("finance.gross_margin_pct", finance.get("gross_margin_pct"))],
            confidence="medium", limitations="Excludes costs not posted to the shared ledger."))
    return out


def _housing_risks(housing: dict) -> list[Insight]:
    out: list[Insight] = []
    over = (housing.get("overcrowded_pens", []) or []) + (housing.get("overcrowded_pastures", []) or [])
    if over:
        out.append(Insight(
            "housing", WARNING, f"{len(over)} overcrowded location(s)",
            "One or more pens/pastures exceed recorded capacity — welfare and grazing risk.",
            [Evidence("housing.overcrowded", str(len(over)), "calculated")],
            confidence="high",
            limitations="Occupancy derived from active animals; capacity is a recorded fact."))
    return out


def _growth_deviation(growth: dict | None) -> list[Insight]:
    if not growth:
        return []
    overall = _val(growth.get("overall_percent"))
    if overall is None:
        return []
    behind = []
    for g in growth.get("goals", []):
        verdict = _val((g.get("run_rate") or {}).get("verdict"))
        if verdict == "overdue":
            behind.append(g.get("label") or g.get("metric_key"))
    if behind:
        return [Insight(
            "growth", WARNING, "Growth goal overdue",
            f"Recorded progress leaves {', '.join(behind)} past its target date. "
            "ARIA can suggest a revised plan — it will not change the plan for you.",
            [Evidence("growth.overall_percent", str(overall), "calculated")],
            confidence="medium",
            limitations="Based on recorded actuals vs the plan; revise the plan explicitly if goals changed.")]
    return [Insight(
        "growth", INFO, f"Growth progress {overall}%",
        "Progress toward the primary growth goal, from recorded operational data.",
        [Evidence("growth.overall_percent", str(overall), "calculated")])]
