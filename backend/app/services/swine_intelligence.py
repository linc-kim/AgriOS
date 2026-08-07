"""
Greena — Swine Intelligence (Module 20, Milestone 10)

The PURE, deterministic engine behind Mission Control's swine briefing and ARIA's
recommendations. It **reads** the already-computed deterministic outputs (the farm
dashboard composed in Milestone 9) and identifies risks in reproduction, health,
finance, housing and growth — every insight citing the recorded/calculated evidence
it rests on and carrying a confidence + limitation. It never recomputes a figure and
never mutates a record.

Mirrors ``rabbit_intelligence`` / ``small_ruminant_intelligence`` (same Evidence/
Insight/Briefing shape) so Mission Control consumes every module identically. Health
insights are patterns, never diagnoses (frozen §4.4): they recommend veterinary
consultation, they do not diagnose. Every insight doubles as an explainable
recommendation (recommendation + reason + supporting evidence + confidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL, WARNING, WATCH, INFO = "critical", "warning", "watch", "info"
_SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, WATCH: 2, INFO: 3}

_HIGH_MORTALITY_PCT = 8.0
_CRIT_MORTALITY_PCT = 15.0
_LOW_CONCEPTION_PCT = 75.0
_LOW_SURVIVAL_PCT = 85.0
_THIN_MARGIN_PCT = 12.0


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


def build_briefing(*, dashboard: dict) -> Briefing:
    """Compose the strategic swine briefing from the deterministic farm dashboard
    (read-only). ``dashboard`` is ``swine_reporting_service.farm_dashboard`` output."""
    population = dashboard.get("population", {})
    reproduction = dashboard.get("reproduction", {})
    farrowing = dashboard.get("farrowing", {})
    health = dashboard.get("health", {})
    finance = dashboard.get("finance", {}).get("pnl", {})
    housing = dashboard.get("housing", {})

    insights: list[Insight] = []
    insights += _health_risks(health)
    insights += _reproduction_risks(reproduction, farrowing)
    insights += _financial_issues(finance)
    insights += _housing_risks(housing)
    insights += _withdrawal_watch(health)

    insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 99))
    counts = {sev: sum(1 for i in insights if i.severity == sev) for sev in (CRITICAL, WARNING, WATCH, INFO)}

    summaries = {"population": population, "reproduction": reproduction, "farrowing": farrowing,
                 "health": health, "finance": finance, "housing": housing}
    priorities = [i.title for i in insights if i.severity in (CRITICAL, WARNING)][:5]
    active = _val(population)
    if counts.get(CRITICAL):
        headline = f"{counts[CRITICAL]} critical issue(s) need attention across {active} active pigs."
    elif counts.get(WARNING):
        headline = f"{counts[WARNING]} item(s) to watch across {active} active pigs."
    else:
        headline = f"Operations on track across {active} active pigs."
    return Briefing(headline=headline, summaries=summaries, insights=insights,
                    priorities=priorities, counts=counts)


def _health_risks(health: dict) -> list[Insight]:
    out: list[Insight] = []
    mr = _val(health.get("mortality_rate_pct"))
    if mr is not None and mr >= _HIGH_MORTALITY_PCT:
        sev = CRITICAL if mr >= _CRIT_MORTALITY_PCT else WARNING
        out.append(Insight(
            "health", sev, f"Elevated mortality ({mr}%)",
            "Recorded mortality is above threshold. Recommend a veterinary review of recent losses. "
            "This is an operational pattern, not a veterinary diagnosis.",
            [_ev("health.mortality_rate_pct", health.get("mortality_rate_pct"))],
            confidence="medium",
            limitations="Pattern only; cause is not assessed. Consult recorded mortality causes and your vet."))
    open_cases = _val(health.get("open_disease_cases"))
    if open_cases and open_cases > 0:
        out.append(Insight(
            "health", WATCH, f"{open_cases} open disease case(s)",
            "One or more disease cases are unresolved. Recommend following up recorded treatments with your vet.",
            [_ev("health.open_disease_cases", health.get("open_disease_cases"))],
            confidence="high", limitations="Counts recorded cases only; ARIA does not diagnose."))
    return out


def _reproduction_risks(reproduction: dict, farrowing: dict) -> list[Insight]:
    out: list[Insight] = []
    cr = _val(reproduction.get("conception_rate_pct"))
    if cr is not None and cr < _LOW_CONCEPTION_PCT:
        out.append(Insight(
            "reproduction", WARNING, f"Low conception rate ({cr}%)",
            "Below-target conception is limiting throughput. Recommend reviewing boar fertility, heat detection "
            "and insemination timing.",
            [_ev("reproduction.conception_rate_pct", reproduction.get("conception_rate_pct"))],
            confidence="medium", limitations="From recorded services and pregnancy checks."))
    surv = _val(farrowing.get("pre_wean_survival_pct"))
    if surv is not None and surv < _LOW_SURVIVAL_PCT:
        out.append(Insight(
            "reproduction", WARNING, f"Low pre-wean survival ({surv}%)",
            "Piglet survival to weaning is below target. Recommend reviewing farrowing supervision, "
            "cross-fostering and crushing prevention.",
            [_ev("farrowing.pre_wean_survival_pct", farrowing.get("pre_wean_survival_pct"))],
            confidence="medium", limitations="From recorded born-alive and weaned counts on weaned litters."))
    return out


def _financial_issues(finance: dict) -> list[Insight]:
    out: list[Insight] = []
    margin_pct = _val(finance.get("gross_margin_pct"))
    gross = _val(finance.get("gross_margin"))
    if gross is not None and gross < 0:
        out.append(Insight(
            "finance", WARNING, "Operating at a loss",
            f"Recorded gross margin is {gross}. Costs exceed recorded sale revenue. Recommend reviewing feed "
            "cost per kg gain and sale timing/weights.",
            [_ev("finance.gross_margin", finance.get("gross_margin")),
             _ev("finance.revenue", finance.get("revenue")),
             _ev("finance.total_cost", finance.get("total_cost"))],
            limitations="From recorded sale facts, feed allocation and swine-tagged ledger costs only."))
    elif margin_pct is not None and margin_pct < _THIN_MARGIN_PCT:
        out.append(Insight(
            "finance", WATCH, f"Thin margin ({margin_pct}%)",
            "Gross margin is below a comfortable threshold; recommend reviewing feed cost and market pricing.",
            [_ev("finance.gross_margin_pct", finance.get("gross_margin_pct"))],
            confidence="medium", limitations="Excludes costs not posted to the shared ledger."))
    return out


def _housing_risks(housing: dict) -> list[Insight]:
    out: list[Insight] = []
    over = housing.get("overcrowded_pens", []) or []
    if over:
        out.append(Insight(
            "housing", WARNING, f"{len(over)} overcrowded pen(s)",
            "One or more pens exceed recorded capacity — welfare and biosecurity risk. Recommend rebalancing "
            "stocking density.",
            [Evidence("housing.overcrowded_pens", str(len(over)), "calculated")],
            confidence="high", limitations="Occupancy derived from active pigs; capacity is a recorded fact."))
    bio = _val((housing.get("biosecurity", {}) or {}).get("flagged"))
    if bio and bio > 0:
        out.append(Insight(
            "housing", WATCH, f"{bio} pen(s) flagged on biosecurity",
            "Pens are recorded as restricted/quarantine/compromised. Recommend confirming biosecurity measures.",
            [Evidence("housing.biosecurity.flagged", str(bio), "calculated")],
            confidence="high", limitations="From recorded pen biosecurity status."))
    return out


def _withdrawal_watch(health: dict) -> list[Insight]:
    wd = _val(health.get("active_withdrawals"))
    if wd and wd > 0:
        return [Insight(
            "health", WATCH, f"{wd} treatment(s) under withdrawal",
            "Some treated pigs are within a meat withdrawal period and must not go to market yet.",
            [_ev("health.active_withdrawals", health.get("active_withdrawals"))],
            confidence="high", limitations="From recorded treatment withdrawal dates.")]
    return []
