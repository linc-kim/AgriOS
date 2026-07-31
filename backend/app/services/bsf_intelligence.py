"""
Greena — BSF Intelligence (Module 16, Part 8)

The PURE, deterministic engine behind Mission Control's BSF briefing (Spec Part 6,
Part 7 §12, §19). It **reads** the already-computed BSF deterministic outputs
(reporting dashboard, forecast, growth progress, bottlenecks) and identifies
risks, overdue/priority work, financial issues and growth deviations — every
insight citing the recorded/calculated/forecast evidence it rests on. It never
recomputes a figure; the deterministic engines remain the single source of truth.

Mirrors ``aviculture_intelligence`` (same Evidence/Insight/Briefing shape) so
Mission Control consumes both identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL, WARNING, WATCH, INFO = "critical", "warning", "watch", "info"
_SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, WATCH: 2, INFO: 3}


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
    """Compose the strategic BSF briefing from deterministic outputs (read-only)."""
    facts = dashboard.get("recorded_facts", {})
    analytics = dashboard.get("analytics", {})
    scores = dashboard.get("scores", {})
    production = analytics.get("production", {})
    health = analytics.get("health", {})
    finance = analytics.get("finance", {})

    insights: list[Insight] = []
    insights += _bottleneck_insights(bottlenecks)
    insights += _health_risks(health)
    insights += _financial_issues(finance)
    insights += _growth_deviation(growth)

    insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 99))
    counts = {sev: sum(1 for i in insights if i.severity == sev) for sev in (CRITICAL, WARNING, WATCH, INFO)}

    summaries = {
        "recorded_facts": facts, "production": production, "health": health,
        "finance": finance, "sustainability": analytics.get("sustainability", {}),
        "scores": scores, "forecast": forecast, "bottlenecks": bottlenecks,
        "growth": growth,
    }
    priorities = _priorities(insights)
    headline = _headline(counts, facts)
    return Briefing(headline=headline, summaries=summaries, insights=insights,
                    priorities=priorities, counts=counts)


def _bottleneck_insights(bottlenecks: list[dict]) -> list[Insight]:
    """Surface the deterministic bottleneck engine's constraints as insights."""
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


def _health_risks(health: dict) -> list[Insight]:
    out: list[Insight] = []
    flag = health.get("flag", {})
    if _val(flag) == "attention":
        out.append(Insight(
            "risk", WARNING, "Elevated mortality pattern",
            f"{_val(health.get('mortality_rate_pct'))}% cumulative mortality flags for review. "
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
            f"Recorded gross profit is {gross}. Costs exceed recorded harvest revenue.",
            [_ev("finance.gross_profit", finance.get("gross_profit")),
             _ev("finance.revenue", finance.get("revenue")),
             _ev("finance.operating_cost", finance.get("operating_cost"))],
            limitations="From recorded revenue facts and BSF-tagged ledger costs only."))
    elif margin is not None and margin < 15:
        out.append(Insight(
            "finance", WATCH, f"Thin margin ({margin}%)",
            "Gross margin is below a comfortable threshold; review feed cost and pricing.",
            [_ev("finance.gross_margin_pct", finance.get("gross_margin_pct"))],
            confidence="medium", limitations="Excludes costs not posted to the shared ledger."))
    return out


def _growth_deviation(growth: dict | None) -> list[Insight]:
    if not growth:
        return []
    overall = _val(growth.get("overall_percent"))
    if overall is None:
        return []
    out: list[Insight] = []
    # Behind-schedule signal from the recorded run-rate verdicts.
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
    active = _val(facts.get("active_batches"))
    if counts.get(CRITICAL):
        return f"{counts[CRITICAL]} critical issue(s) need attention across {active} active batch(es)."
    if counts.get(WARNING):
        return f"{counts[WARNING]} item(s) to watch across {active} active batch(es)."
    return f"Production on track across {active} active batch(es)."
