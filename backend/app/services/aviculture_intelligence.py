"""
Greena — Aviculture Intelligence Engine (Module 15, Part 11)

A PURE, deterministic engine that turns the aviculture domain's already-computed
deterministic outputs into a *strategic briefing* for Mission Control. It is the
aviculture analogue of ``aria_intelligence`` (which does the same for poultry
flocks): Mission Control orchestrates, this engine supplies the business logic,
and no farm figure is ever re-derived here — every number is read from the health,
finance, valuation, breeding, incubation, population-forecast, automation and
workflow engines that already produced it.

Like every ARIA/aviculture engine it is pure by construction (Doc 14 §2-3): no
database, no clock beyond a passed-in ``today``, no model. That is what lets the
whole briefing be tested exhaustively and the honesty rules be *enforced* rather
than hoped for. Every insight cites the recorded/calculated/forecast evidence it
rests on and carries that evidence's honesty label; nothing is invented, and where
the data is insufficient the briefing says so instead of guessing (Doc 15 §15).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Honesty labels — the shared vocabulary the source engines already assign.
RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"

# Severity of a strategic insight (ranked, most-serious first).
CRITICAL = "critical"
WARNING = "warning"
WATCH = "watch"
INFO = "info"

_SEVERITY_RANK = {CRITICAL: 0, WARNING: 1, WATCH: 2, INFO: 3}

# Thresholds are deterministic constants, stated so they are auditable.
_HIGH_MORTALITY_PCT = 10.0
_LOW_VACCINATION_PCT = 50.0
_LOW_HATCH_PCT = 40.0
_MIN_EGGS_FOR_HATCH_JUDGEMENT = 5  # don't call a hatch rate "low" on a tiny sample


# ── Reading labelled figures ──────────────────────────────────────────────────


def _val(x):
    """The value out of a ``{label,value,detail}`` figure (or the raw scalar)."""
    return x.get("value") if isinstance(x, dict) else x


def _label(x) -> str:
    return x.get("label", UNKNOWN) if isinstance(x, dict) else UNKNOWN


# ── Structures ────────────────────────────────────────────────────────────────


@dataclass
class Evidence:
    """A single recorded/calculated/forecast figure an insight rests on."""

    source: str                 # dotted path of the engine figure, e.g. "health.mortality_rate_pct"
    value: str | None           # its value as a string, or None when unavailable
    fact_type: str              # the honesty label the source engine assigned


@dataclass
class Insight:
    category: str               # risk | overdue_work | breeding | incubation | finance | population | operations
    severity: str               # critical | warning | watch | info
    title: str
    detail: str                 # the reasoning (Doc 15 §15)
    evidence: list[Evidence] = field(default_factory=list)
    confidence: str = "high"    # high | medium | low — how firmly the evidence supports the flag
    limitations: str = ""       # the honest caveat on this insight (Doc 15 §15)


@dataclass
class Briefing:
    """The strategic aviculture briefing Mission Control consumes."""

    headline: str
    summaries: dict             # the consumed engine outputs, surfaced verbatim (honesty labels intact)
    insights: list[Insight]
    priorities: list[str]       # ranked operational priorities, evidence-backed
    counts: dict                # {critical, warning, watch, info}


def _ev(source: str, figure) -> Evidence:
    v = _val(figure)
    return Evidence(source=source, value=None if v is None else str(v), fact_type=_label(figure))


# ── The engine ────────────────────────────────────────────────────────────────


def build_briefing(*, dashboard: dict, forecast: dict, due_items: list[dict],
                   workflows: list[dict]) -> Briefing:
    """
    Compose a strategic aviculture briefing from the deterministic engine outputs.

    ``dashboard`` is ``aviculture_reporting_service.dashboard`` (collection,
    infrastructure, breeding, incubation, health, finance); ``forecast`` is the
    population forecast; ``due_items`` are the automation engine's operational
    items; ``workflows`` are the active staged processes. This function reads them,
    it never recomputes them.
    """
    collection = dashboard.get("collection", {})
    breeding = dashboard.get("breeding", {})
    incubation = dashboard.get("incubation", {})
    stats = incubation.get("statistics", {})
    health = dashboard.get("health", {})
    finance = dashboard.get("finance", {})

    insights: list[Insight] = []
    insights += _health_risks(health)
    insights += _overdue_work(due_items, health)
    insights += _breeding_bottlenecks(breeding, incubation, stats)
    insights += _incubation_failures(stats)
    insights += _financial_issues(finance)
    insights += _population_trends(forecast)

    # Rank most-serious first; stable within a severity so output is deterministic.
    insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 99))

    counts = {
        CRITICAL: sum(1 for i in insights if i.severity == CRITICAL),
        WARNING: sum(1 for i in insights if i.severity == WARNING),
        WATCH: sum(1 for i in insights if i.severity == WATCH),
        INFO: sum(1 for i in insights if i.severity == INFO),
    }

    summaries = {
        "health": health,
        "finance": finance,
        "valuation": finance.get("collection_value"),
        "breeding": breeding,
        "incubation": incubation,
        "population_forecast": forecast,
        "collection": collection,
        "infrastructure": dashboard.get("infrastructure", {}),
        "automation": _automation_workload(due_items),
        "workflows": _workflow_status(workflows),
    }

    priorities = _priorities(insights, due_items)
    headline = _headline(counts, collection)

    return Briefing(headline=headline, summaries=summaries, insights=insights,
                    priorities=priorities, counts=counts)


# ── Risk detection (each cites its recorded/calculated evidence) ───────────────


def _health_risks(health: dict) -> list[Insight]:
    out: list[Insight] = []
    diseases = _val(health.get("active_disease_events")) or 0
    quarantines = _val(health.get("active_quarantines")) or 0
    mortality = _val(health.get("mortality_rate_pct"))
    vaccination = _val(health.get("vaccination_coverage_pct"))
    active_birds = _val(health.get("active_birds")) or 0

    if diseases and diseases > 0:
        out.append(Insight(
            "risk", CRITICAL, f"{diseases} active disease event(s)",
            "Suspected or confirmed disease is recorded. Isolate affected birds and consult a vet — "
            "ARIA does not diagnose disease.",
            [_ev("health.active_disease_events", health.get("active_disease_events"))],
            limitations="Counts recorded suspected/confirmed events; severity and cause are not assessed here."))

    if quarantines and quarantines > 0:
        out.append(Insight(
            "risk", WARNING, f"{quarantines} bird(s) in active quarantine",
            "Quarantine is in progress. Keep biosecurity separation until the recorded quarantine is cleared.",
            [_ev("health.active_quarantines", health.get("active_quarantines"))],
            limitations="Reflects open quarantine records only; does not assess whether quarantine is warranted."))

    if mortality is not None and mortality > _HIGH_MORTALITY_PCT:
        out.append(Insight(
            "risk", WARNING, f"Mortality rate {mortality}%",
            f"Recorded mortality exceeds the {_HIGH_MORTALITY_PCT:.0f}% attention threshold. "
            "Review recent losses and husbandry.",
            [_ev("health.mortality_rate_pct", health.get("mortality_rate_pct"))],
            limitations="Deceased ÷ all birds ever recorded; a small or young collection makes this volatile."))

    if vaccination is not None and active_birds > 0 and vaccination < _LOW_VACCINATION_PCT:
        out.append(Insight(
            "risk", WATCH, f"Vaccination coverage {vaccination}%",
            f"Under {_LOW_VACCINATION_PCT:.0f}% of active birds have a vaccination record. "
            "Confirm the preventive schedule.",
            [_ev("health.vaccination_coverage_pct", health.get("vaccination_coverage_pct"))],
            limitations="Counts birds with any vaccination record; species schedules vary and are not modelled."))

    return out


def _overdue_work(due_items: list[dict], health: dict) -> list[Insight]:
    out: list[Insight] = []
    critical = [d for d in due_items if d.get("priority") == "critical"]
    high = [d for d in due_items if d.get("priority") == "high"]

    if critical or high:
        titles = "; ".join(d.get("title", "item") for d in (critical + high)[:4])
        out.append(Insight(
            "overdue_work", CRITICAL if critical else WARNING,
            f"{len(critical) + len(high)} urgent operational item(s)",
            f"Overdue or high-priority work computed from recorded facts: {titles}.",
            [Evidence(source=f"automation.{d.get('kind', 'item')}",
                      value=d.get("suggested_due_on"), fact_type=RECORDED)
             for d in (critical + high)[:4]],
            limitations="Priority is from due-date proximity within the automation horizon; up to 4 items shown."))

    # Preventive-care items already past due are a distinct, health-sourced signal.
    overdue = health.get("preventive_due", {}).get("overdue_count")
    if overdue is not None and (_val(overdue) or 0) > 0:
        out.append(Insight(
            "overdue_work", WARNING, f"{_val(overdue)} preventive item(s) past due",
            "Recorded preventive-care items have passed their next-due date.",
            [_ev("health.preventive_due.overdue_count", overdue)],
            limitations="Counts records whose next-due date is in the past; excludes items with no due date set."))
    return out


def _breeding_bottlenecks(breeding: dict, incubation: dict, stats: dict) -> list[Insight]:
    out: list[Insight] = []
    pairs = breeding.get("active_pairs") or 0
    programs = breeding.get("active_programs") or 0
    batches = incubation.get("active_batches") or 0
    eggs_set = _val(stats.get("eggs_set")) or 0
    fertility = _val(stats.get("fertility_rate_pct"))

    if pairs > 0 and programs == 0:
        out.append(Insight(
            "breeding", WATCH, "Active pairs, no breeding programme",
            f"{pairs} active pair(s) but no active breeding programme with recorded goals — "
            "breeding effort is untracked against an objective.",
            [Evidence("breeding.active_pairs", str(pairs), RECORDED),
             Evidence("breeding.active_programs", str(programs), RECORDED)],
            limitations="Structural signal only; a programme may be intentionally omitted for casual pairings."))

    if pairs > 0 and batches == 0 and eggs_set == 0:
        out.append(Insight(
            "breeding", WATCH, "Pairs producing nothing in incubation",
            f"{pairs} active pair(s) but no eggs are set and no incubation batch is running — "
            "a possible production bottleneck.",
            [Evidence("breeding.active_pairs", str(pairs), RECORDED),
             _ev("incubation.statistics.eggs_set", stats.get("eggs_set"))],
            limitations="Expected outside the breeding season or for non-breeding pairs; not an error on its own."))

    if fertility is not None and eggs_set >= _MIN_EGGS_FOR_HATCH_JUDGEMENT and fertility < _LOW_HATCH_PCT:
        out.append(Insight(
            "breeding", WARNING, f"Fertility rate {fertility}%",
            f"Recorded fertility is below {_LOW_HATCH_PCT:.0f}% over {eggs_set} eggs set — "
            "review pairings, condition and timing.",
            [_ev("incubation.statistics.fertility_rate_pct", stats.get("fertility_rate_pct"))],
            confidence="medium" if eggs_set < 20 else "high",
            limitations=f"Based on {eggs_set} recorded egg(s) set; small samples swing the rate."))
    return out


def _incubation_failures(stats: dict) -> list[Insight]:
    out: list[Insight] = []
    eggs_set = _val(stats.get("eggs_set")) or 0
    hatch = _val(stats.get("hatch_rate_pct"))
    failed = _val(stats.get("failed")) or 0

    if hatch is not None and eggs_set >= _MIN_EGGS_FOR_HATCH_JUDGEMENT and hatch < _LOW_HATCH_PCT:
        out.append(Insight(
            "incubation", WARNING, f"Hatch rate {hatch}%",
            f"Recorded hatch rate is below {_LOW_HATCH_PCT:.0f}% over {eggs_set} eggs set. "
            "Check incubation temperature, humidity and turning against the species schedule.",
            [_ev("incubation.statistics.hatch_rate_pct", stats.get("hatch_rate_pct")),
             _ev("incubation.statistics.eggs_set", stats.get("eggs_set"))],
            confidence="medium" if eggs_set < 20 else "high",
            limitations=f"Based on {eggs_set} recorded egg(s) set; hatch rate lags real time until eggs resolve."))
    elif failed and eggs_set and failed >= max(_MIN_EGGS_FOR_HATCH_JUDGEMENT, eggs_set / 2):
        out.append(Insight(
            "incubation", WATCH, f"{failed} egg(s) failed",
            "A large share of recorded eggs have failed. Review the incubation logs for a cause.",
            [_ev("incubation.statistics.failed", stats.get("failed"))],
            limitations="Counts eggs marked failed; the cause is not inferred from the record."))
    return out


def _financial_issues(finance: dict) -> list[Insight]:
    out: list[Insight] = []
    net = _val(finance.get("net"))
    valuation = finance.get("collection_value")

    if net is not None and net < 0:
        out.append(Insight(
            "finance", WARNING, "Operating at a recorded loss",
            f"Recorded sale income minus purchase and operational costs is {net}. "
            "This is a recorded position, not a forecast.",
            [_ev("finance.net", finance.get("net"))],
            limitations="Reflects recorded sale/purchase events and tagged expenses only; timing and unrecorded costs excluded."))

    if valuation is None or _val(valuation) is None:
        out.append(Insight(
            "finance", WATCH, "No collection valuation recorded",
            "The collection has no recorded valuation, so its worth is unknown rather than estimated.",
            [Evidence("finance.collection_value", None, UNKNOWN)],
            limitations="Absence of a recorded valuation; ARIA does not estimate an unrecorded value."))
    return out


def _population_trends(forecast: dict) -> list[Insight]:
    out: list[Insight] = []
    net_daily = forecast.get("net_daily_change")
    projected = forecast.get("forecast")
    current = forecast.get("current")
    nd = _val(net_daily)
    proj = _val(projected)
    cur = _val(current)

    if nd is not None and nd < 0 and proj is not None and cur is not None and proj < cur:
        confidence = forecast.get("confidence") or "low"
        sev = WARNING if confidence == "high" else WATCH
        limits = forecast.get("limitations") or []
        out.append(Insight(
            "population", sev, "Population projected to decline",
            f"On recent recorded net change, the active population is projected to fall from {cur} to "
            f"{proj} over {forecast.get('horizon_days', 90)} days. A projection, not a promise.",
            [_ev("population_forecast.net_daily_change", net_daily),
             _ev("population_forecast.forecast", projected)],
            confidence=confidence,
            limitations=(" ".join(limits) if limits
                         else "Linear extrapolation of recent net change; assumes no sales, purchases or shocks.")))
    return out


# ── Consumed-summary shaping ──────────────────────────────────────────────────


def _automation_workload(due_items: list[dict]) -> dict:
    by_priority: dict[str, int] = {}
    for d in due_items:
        p = d.get("priority", "normal")
        by_priority[p] = by_priority.get(p, 0) + 1
    return {"label": CALCULATED, "value": len(due_items), "by_priority": by_priority,
            "detail": "Operational items due within the horizon (from recorded facts)."}


def _workflow_status(workflows: list[dict]) -> dict:
    active = sum(1 for w in workflows if w.get("status") == "active")
    completed = sum(1 for w in workflows if w.get("status") == "completed")
    by_type: dict[str, int] = {}
    for w in workflows:
        t = w.get("workflow_type", "workflow")
        by_type[t] = by_type.get(t, 0) + 1
    return {"label": RECORDED, "value": len(workflows), "active": active,
            "completed": completed, "by_type": by_type,
            "detail": "Staged operational processes on record."}


# ── Operational priorities ────────────────────────────────────────────────────


def _priorities(insights: list[Insight], due_items: list[dict]) -> list[str]:
    """A ranked, evidence-backed list of what to act on — derived from the
    insights (already severity-sorted) and the sharpest due items. No fabrication:
    every line traces to a recorded/calculated signal above."""
    out: list[str] = []
    for ins in insights:
        if ins.severity in (CRITICAL, WARNING):
            out.append(f"{ins.title} — {ins.detail}")
    joined = "".join(out)
    for d in due_items:
        title = d.get("title") or ""
        if d.get("priority") == "critical" and title not in joined:
            out.append(f"{title} — {d.get('reason', '')}".strip())
    if not out:
        out.append("No elevated risks on record — keep recording daily and maintain the schedule.")
    return out[:6]


def _headline(counts: dict, collection: dict) -> str:
    total = _val(collection.get("total")) or 0
    if counts[CRITICAL]:
        return f"{counts[CRITICAL]} critical issue(s) need attention across {total} recorded bird(s)."
    if counts[WARNING]:
        return f"{counts[WARNING]} issue(s) to review across {total} recorded bird(s)."
    if counts[WATCH]:
        return f"Collection stable — {counts[WATCH]} item(s) worth watching across {total} recorded bird(s)."
    return f"Collection healthy on recorded data — {total} bird(s), no elevated risks."
