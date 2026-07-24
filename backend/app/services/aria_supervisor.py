"""
ARIA — the farm supervisor.

Part 4 gave ARIA the ability to answer when asked. This module is what lets it
watch without being asked: eight monitors that evaluate the farm continuously,
alerts raised only when a threshold is actually crossed, one ranking engine that
decides what matters most today, and the reports and timeline that turn all of
it into an operational history.

Pure by construction. Every function here takes a `FarmFacts` snapshot (and, for
the timeline, a list of already-gathered events) and returns plain data. No
database, no clock, no I/O — `aria_supervisor_data` does all of that and hands
the results in. That is what makes a supervisor that runs unattended safe to
reason about: the logic can be exercised exhaustively in tests, and it can only
ever see numbers a real service computed from real records.

The honesty rules from Part 4 are stricter here, because a supervisor speaks
first. Three things follow from that:

*Unmeasured is not zero.* A farm with no water readings is not a farm whose
birds drank nothing. Every monitor distinguishes "no data" from "bad data" and
returns `NORMAL` with an explicit "not enough recorded data" note rather than
inventing an emergency — or worse, silently passing.

*A threshold must actually be crossed.* Alerts are not a rephrasing of the
insights from Part 4; they fire on a specific, stated comparison, and each
carries the evidence that triggered it so a farmer can check the arithmetic.

*Ranking is a single rule set.* Priorities come from one ordered scoring
function, not from each producer guessing its own urgency, so the same farm
state always produces the same list in the same order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.services.aria_intelligence import FarmFacts


# ── Monitor states ───────────────────────────────────────────────────────────


class MonitorState(str, Enum):
    NORMAL = "normal"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


#: Ordering for ranking and for picking the farm's worst current state.
_STATE_RANK = {
    MonitorState.NORMAL: 0,
    MonitorState.WATCH: 1,
    MonitorState.WARNING: 2,
    MonitorState.CRITICAL: 3,
}

NOT_ENOUGH_DATA = "Not enough recorded data."


@dataclass
class Monitor:
    """
    One continuously-evaluated aspect of the farm.

    `why` always explains the state in a farmer's terms, and `evidence` lists
    the recorded numbers behind it — never a bare verdict.
    """

    key: str
    label: str
    state: MonitorState
    why: str
    evidence: list[str] = field(default_factory=list)
    #: True when the state is NORMAL only because nothing has been recorded.
    unmeasured: bool = False


@dataclass
class Alert:
    """A crossed threshold, with everything needed to act on or dispute it."""

    key: str                 # stable — the dedupe identity for notifications
    severity: MonitorState   # watch | warning | critical
    title: str
    reason: str
    evidence: list[str]
    action: str
    monitor: str
    raised_at: datetime


@dataclass
class PriorityItem:
    key: str
    rank: int
    label: str
    why: str
    source: str              # alert | vaccination | reminder | routine
    severity: MonitorState


@dataclass
class TimelineEvent:
    at: datetime
    kind: str                # vaccination | production | feed | mortality | reminder | weighin
    title: str
    detail: str = ""


@dataclass
class ReportSection:
    label: str
    value: str
    available: bool = True


@dataclass
class Report:
    period: str              # today | 7d | 30d
    label: str
    sections: list[ReportSection]
    notes: list[str] = field(default_factory=list)


# ── Monitors ─────────────────────────────────────────────────────────────────
#
# Each returns exactly one Monitor. The shape is uniform on purpose: the
# dashboard renders them from a list without knowing what any of them measure.


def _pct_change(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (current - prior) / prior * 100


def monitor_mortality(f: FarmFacts) -> Monitor:
    if f.days_since_any_log is None:
        return Monitor(
            "mortality", "Mortality", MonitorState.NORMAL,
            f"{NOT_ENOUGH_DATA} No daily logs recorded yet.", unmeasured=True,
        )
    if f.total_birds <= 0:
        return Monitor(
            "mortality", "Mortality", MonitorState.NORMAL,
            f"{NOT_ENOUGH_DATA} No active bird count on record.", unmeasured=True,
        )

    rate = f.mortality_this_week / f.total_birds * 100
    evidence = [
        f"{f.mortality_this_week} lost in the last 7 days",
        f"{f.mortality_prev_week} lost the previous 7 days",
        f"{f.total_birds} birds currently active",
    ]
    if rate >= 2.0:
        return Monitor("mortality", "Mortality", MonitorState.CRITICAL,
                       f"Weekly losses are {rate:.1f}% of the flock — well above the 2% line.",
                       evidence)
    if rate >= 1.0:
        return Monitor("mortality", "Mortality", MonitorState.WARNING,
                       f"Weekly losses are {rate:.1f}% of the flock, above the 1% watch line.",
                       evidence)
    if f.mortality_this_week > f.mortality_prev_week and f.mortality_this_week >= 3:
        return Monitor("mortality", "Mortality", MonitorState.WATCH,
                       "Losses are higher than last week, though still within normal range.",
                       evidence)
    return Monitor("mortality", "Mortality", MonitorState.NORMAL,
                   f"Weekly losses are {rate:.1f}% of the flock — within normal range.", evidence)


def monitor_feed(f: FarmFacts) -> Monitor:
    evidence: list[str] = []
    if f.feed_days_remaining is not None:
        evidence.append(f"about {f.feed_days_remaining} days of feed remaining")
    if f.days_since_feed_log is not None:
        evidence.append(f"last feed recorded {f.days_since_feed_log} day(s) ago")

    if f.feed_days_remaining is not None:
        if f.feed_days_remaining <= 2:
            return Monitor("feed", "Feed", MonitorState.CRITICAL,
                           f"Only {f.feed_days_remaining} day(s) of feed left.", evidence)
        if f.feed_days_remaining <= 7:
            return Monitor("feed", "Feed", MonitorState.WARNING,
                           f"Feed stock is down to {f.feed_days_remaining} days.", evidence)

    if f.days_since_feed_log is None:
        return Monitor("feed", "Feed", MonitorState.NORMAL,
                       f"{NOT_ENOUGH_DATA} No feed has been recorded.", evidence, unmeasured=True)
    if f.days_since_feed_log >= 3:
        return Monitor("feed", "Feed", MonitorState.WARNING,
                       f"No feed recorded for {f.days_since_feed_log} days — cost and intake are untracked.",
                       evidence)
    if f.days_since_feed_log >= 2:
        return Monitor("feed", "Feed", MonitorState.WATCH,
                       f"No feed recorded for {f.days_since_feed_log} days.", evidence)
    return Monitor("feed", "Feed", MonitorState.NORMAL, "Feed is being recorded and stock is adequate.", evidence)


def monitor_water(f: FarmFacts) -> Monitor:
    """
    Water is the fastest-moving failure on a poultry farm, but it is also the
    least consistently recorded. Unmeasured must therefore stay NORMAL with a
    clear note — flagging every farm that does not log water would make the
    supervisor noise, and noise is what gets it ignored.
    """
    if f.water_this_week_litres is None:
        return Monitor(
            "water", "Water", MonitorState.NORMAL,
            f"{NOT_ENOUGH_DATA} Water intake has not been recorded.",
            [], unmeasured=True,
        )

    evidence = [f"{f.water_this_week_litres}L recorded in the last 7 days"]
    if f.water_prev_week_litres is not None and f.water_prev_week_litres > 0:
        evidence.append(f"{f.water_prev_week_litres}L the previous 7 days")
        change = _pct_change(float(f.water_this_week_litres), float(f.water_prev_week_litres))
        if change is not None:
            if change <= -30:
                return Monitor("water", "Water", MonitorState.CRITICAL,
                               f"Water intake has fallen {abs(change):.0f}% week on week. "
                               "A sharp drop precedes almost every health problem.", evidence)
            if change <= -15:
                return Monitor("water", "Water", MonitorState.WARNING,
                               f"Water intake is down {abs(change):.0f}% on last week.", evidence)
            if change >= 30:
                return Monitor("water", "Water", MonitorState.WATCH,
                               f"Water intake is up {change:.0f}% — often heat stress, worth checking.",
                               evidence)

    if f.days_since_water_log is not None and f.days_since_water_log >= 3:
        return Monitor("water", "Water", MonitorState.WATCH,
                       f"No water reading for {f.days_since_water_log} days.", evidence)
    return Monitor("water", "Water", MonitorState.NORMAL, "Water intake is steady.", evidence)


def monitor_production(f: FarmFacts) -> Monitor:
    if f.days_since_egg_log is None:
        return Monitor("production", "Egg production", MonitorState.NORMAL,
                       f"{NOT_ENOUGH_DATA} No egg collection recorded.", [], unmeasured=True)

    evidence = [
        f"{f.eggs_this_week} eggs in the last 7 days",
        f"{f.eggs_prev_week} the previous 7 days",
    ]
    if f.hen_day_pct is not None:
        evidence.append(f"{f.hen_day_pct:.0f}% hen-day production")

    change = _pct_change(f.eggs_this_week, f.eggs_prev_week)
    if change is not None:
        if change <= -20:
            return Monitor("production", "Egg production", MonitorState.CRITICAL,
                           f"Collection has dropped {abs(change):.0f}% week on week.", evidence)
        if change <= -8:
            return Monitor("production", "Egg production", MonitorState.WARNING,
                           f"Collection is down {abs(change):.0f}% on last week.", evidence)
        if change <= -3:
            return Monitor("production", "Egg production", MonitorState.WATCH,
                           f"Collection is slightly down ({abs(change):.0f}%).", evidence)
    if f.days_since_egg_log >= 2:
        return Monitor("production", "Egg production", MonitorState.WATCH,
                       f"No collection recorded for {f.days_since_egg_log} days.", evidence)
    return Monitor("production", "Egg production", MonitorState.NORMAL,
                   "Production is steady or improving.", evidence)


def monitor_vaccinations(f: FarmFacts) -> Monitor:
    evidence = []
    if f.vaccinations_overdue:
        evidence.append(f"{f.vaccinations_overdue} overdue")
    if f.vaccinations_due_today:
        evidence.append(f"{f.vaccinations_due_today} due today")
    if f.vaccinations_due_week:
        evidence.append(f"{f.vaccinations_due_week} due this week")

    if f.vaccinations_overdue >= 2:
        return Monitor("vaccinations", "Vaccinations", MonitorState.CRITICAL,
                       f"{f.vaccinations_overdue} vaccinations are overdue. These diseases have no cure once they strike.",
                       evidence)
    if f.vaccinations_overdue == 1:
        return Monitor("vaccinations", "Vaccinations", MonitorState.WARNING,
                       "A vaccination is overdue.", evidence)
    if f.vaccinations_due_today:
        return Monitor("vaccinations", "Vaccinations", MonitorState.WATCH,
                       f"{f.vaccinations_due_today} vaccination(s) due today.", evidence)
    if f.vaccinations_due_week:
        return Monitor("vaccinations", "Vaccinations", MonitorState.WATCH,
                       f"{f.vaccinations_due_week} vaccination(s) due within the week.", evidence)
    return Monitor("vaccinations", "Vaccinations", MonitorState.NORMAL,
                   "Nothing due in the next 7 days.", evidence)


def monitor_population(f: FarmFacts) -> Monitor:
    if f.initial_birds <= 0 or f.total_birds <= 0:
        return Monitor("population", "Population", MonitorState.NORMAL,
                       f"{NOT_ENOUGH_DATA} No flock placement on record.", [], unmeasured=True)

    lost = f.initial_birds - f.total_birds
    loss_pct = lost / f.initial_birds * 100 if f.initial_birds else 0
    evidence = [
        f"{f.total_birds} of {f.initial_birds} placed birds remaining",
        f"{lost} lost cumulatively ({loss_pct:.1f}%)",
    ]
    if loss_pct >= 15:
        return Monitor("population", "Population", MonitorState.CRITICAL,
                       f"Cumulative losses have reached {loss_pct:.1f}% of birds placed.", evidence)
    if loss_pct >= 8:
        return Monitor("population", "Population", MonitorState.WARNING,
                       f"Cumulative losses are {loss_pct:.1f}% of birds placed.", evidence)
    if loss_pct >= 5:
        return Monitor("population", "Population", MonitorState.WATCH,
                       f"Cumulative losses are {loss_pct:.1f}% of birds placed.", evidence)
    return Monitor("population", "Population", MonitorState.NORMAL,
                   f"Flock is holding at {loss_pct:.1f}% cumulative loss.", evidence)


def monitor_inventory(f: FarmFacts) -> Monitor:
    if f.inventory_tracked == 0:
        return Monitor("inventory", "Inventory", MonitorState.NORMAL,
                       f"{NOT_ENOUGH_DATA} No inventory items are tracked.", [], unmeasured=True)

    evidence = []
    if f.inventory_out:
        evidence.append("out of stock: " + ", ".join(f.inventory_out[:5]))
    if f.inventory_low:
        evidence.append("at/below reorder level: " + ", ".join(f.inventory_low[:5]))
    evidence.append(f"{f.inventory_tracked} items tracked")

    if f.inventory_out:
        return Monitor("inventory", "Inventory", MonitorState.CRITICAL,
                       f"{len(f.inventory_out)} item(s) are completely out of stock.", evidence)
    if len(f.inventory_low) >= 3:
        return Monitor("inventory", "Inventory", MonitorState.WARNING,
                       f"{len(f.inventory_low)} items are at or below their reorder level.", evidence)
    if f.inventory_low:
        return Monitor("inventory", "Inventory", MonitorState.WATCH,
                       f"{len(f.inventory_low)} item(s) need reordering.", evidence)
    return Monitor("inventory", "Inventory", MonitorState.NORMAL, "All tracked items are above reorder level.", evidence)


def monitor_biosecurity(f: FarmFacts) -> Monitor:
    """
    Biosecurity has no direct measurement, exactly as in the Part 4 health
    score. It is inferred from disease risk and vaccination currency, and the
    state is always labelled as inferred so nobody mistakes it for an observation.
    """
    evidence = [f"disease risk {f.disease_level} ({f.disease_score}/100)"]
    if f.vaccinations_overdue:
        evidence.append(f"{f.vaccinations_overdue} vaccination(s) overdue")

    note = " Inferred from disease risk and vaccination status — ARIA cannot observe biosecurity practice directly."
    if f.disease_level == "critical":
        return Monitor("biosecurity", "Biosecurity", MonitorState.CRITICAL,
                       "Disease risk is critical." + note, evidence)
    if f.disease_level == "high" or f.vaccinations_overdue >= 2:
        return Monitor("biosecurity", "Biosecurity", MonitorState.WARNING,
                       "Elevated disease risk or multiple overdue vaccinations." + note, evidence)
    if f.disease_level == "moderate" or f.vaccinations_overdue == 1:
        return Monitor("biosecurity", "Biosecurity", MonitorState.WATCH,
                       "Some risk signals are raised." + note, evidence)
    return Monitor("biosecurity", "Biosecurity", MonitorState.NORMAL,
                   "No elevated risk signals." + note, evidence)


#: The full watch. Order is the display order on the dashboard.
_MONITORS = (
    monitor_mortality,
    monitor_feed,
    monitor_water,
    monitor_production,
    monitor_vaccinations,
    monitor_population,
    monitor_inventory,
    monitor_biosecurity,
)


def run_monitors(f: FarmFacts) -> list[Monitor]:
    return [m(f) for m in _MONITORS]


def overall_state(monitors: list[Monitor]) -> MonitorState:
    """The farm's worst current state — what the dashboard headline reports."""
    if not monitors:
        return MonitorState.NORMAL
    return max(monitors, key=lambda m: _STATE_RANK[m.state]).state


# ── Alerts ───────────────────────────────────────────────────────────────────

#: What to do about each monitor when it raises. Kept beside the alert builder
#: rather than inside each monitor so the monitors stay pure observation.
_ACTIONS = {
    "mortality": "Check the affected house, record symptoms, and call your vet if losses keep climbing.",
    "feed": "Reorder feed now and record what you are currently feeding.",
    "water": "Check drinkers, lines and pressure immediately — then record today's intake.",
    "production": "Check feed, water and lighting first, then look for signs of illness.",
    "vaccinations": "Catch up the overdue doses as soon as you can source the vaccine.",
    "population": "Review the cause of cumulative losses with your vet.",
    "inventory": "Reorder the affected items before they interrupt operations.",
    "biosecurity": "Tighten biosecurity, isolate any sick birds, and consult your vet.",
}


def build_alerts(f: FarmFacts, *, now: datetime, monitors: list[Monitor] | None = None) -> list[Alert]:
    """
    Raise an alert for every monitor above NORMAL.

    An alert is a crossed threshold, not a general observation, so a monitor
    sitting at NORMAL — including one that is NORMAL because nothing has been
    recorded — never produces one. Severity is the monitor's own state, and the
    key is stable so repeated runs recognise the same alert instead of
    duplicating it.
    """
    monitors = monitors if monitors is not None else run_monitors(f)
    alerts: list[Alert] = []
    for m in monitors:
        if m.state is MonitorState.NORMAL:
            continue
        alerts.append(Alert(
            key=f"{m.key}:{m.state.value}",
            severity=m.state,
            title=f"{m.label}: {m.state.value}",
            reason=m.why,
            evidence=list(m.evidence),
            action=_ACTIONS.get(m.key, "Review this in the matching module."),
            monitor=m.key,
            raised_at=now,
        ))
    alerts.sort(key=lambda a: -_STATE_RANK[a.severity])
    return alerts


# ── Priority engine ──────────────────────────────────────────────────────────

#: Base weight per source. Alerts outrank scheduled work, which outranks
#: routine recording — a farmer with a water emergency should not be told to
#: log eggs first.
_SOURCE_WEIGHT = {"alert": 100, "vaccination": 60, "reminder": 40, "routine": 10}


def build_priorities(
    f: FarmFacts,
    *,
    alerts: list[Alert] | None = None,
    now: datetime | None = None,
    limit: int = 8,
) -> list[PriorityItem]:
    """
    Rank everything needing attention, from one rule set.

    Score = source weight + severity weight, with ties broken by a stable key.
    Deterministic by construction: the same FarmFacts always yields the same
    ordering, which is what makes the list trustworthy day to day.
    """
    now = now or datetime.now()
    alerts = alerts if alerts is not None else build_alerts(f, now=now)
    scored: list[tuple[int, str, PriorityItem]] = []

    for a in alerts:
        score = _SOURCE_WEIGHT["alert"] + _STATE_RANK[a.severity] * 10
        scored.append((score, a.key, PriorityItem(
            key=a.key, rank=0, label=_priority_label(a), why=a.reason,
            source="alert", severity=a.severity,
        )))

    # Scheduled vaccinations that are not already an alert (due this week).
    if f.vaccinations_due_week and not f.vaccinations_overdue and not f.vaccinations_due_today:
        vac = f.next_vaccination or {}
        name = vac.get("vaccine") or "vaccination"
        flock = f" for {vac.get('flock')}" if vac.get("flock") else ""
        scored.append((_SOURCE_WEIGHT["vaccination"], "vaccination:due", PriorityItem(
            key="vaccination:due", rank=0, label=f"{name}{flock} due this week",
            why=f"{f.vaccinations_due_week} dose(s) fall due within 7 days.",
            source="vaccination", severity=MonitorState.WATCH,
        )))

    # Reminders the farmer set themselves.
    for r in f.upcoming_reminders[:3]:
        overdue = r.get("overdue")
        scored.append((
            _SOURCE_WEIGHT["reminder"] + (15 if overdue else 0),
            f"reminder:{r.get('title')}",
            PriorityItem(
                key=f"reminder:{r.get('title')}", rank=0,
                label=("Overdue: " if overdue else "") + str(r.get("title")),
                why="A reminder you set is " + ("past due." if overdue else "coming up."),
                source="reminder",
                severity=MonitorState.WARNING if overdue else MonitorState.WATCH,
            ),
        ))

    # Routine recording — only surfaced when it hasn't been done today.
    if f.days_since_any_log is None or f.days_since_any_log > 0:
        scored.append((_SOURCE_WEIGHT["routine"], "routine:log", PriorityItem(
            key="routine:log", rank=0, label="Record today's feed, eggs and mortality",
            why="Today's log hasn't been entered — every insight is built from it.",
            source="routine", severity=MonitorState.WATCH,
        )))
    if f.eggs_today == 0 and f.days_since_egg_log is not None:
        scored.append((_SOURCE_WEIGHT["routine"] - 1, "routine:eggs", PriorityItem(
            key="routine:eggs", rank=0, label="Record today's egg collection",
            why="No eggs recorded for today yet.",
            source="routine", severity=MonitorState.WATCH,
        )))

    scored.sort(key=lambda t: (-t[0], t[1]))
    out: list[PriorityItem] = []
    for i, (_score, _tie, item) in enumerate(scored[:limit], start=1):
        item.rank = i
        out.append(item)
    return out


def _priority_label(a: Alert) -> str:
    return {
        "mortality": "Investigate rising mortality",
        "feed": "Reorder feed",
        "water": "Check water supply",
        "production": "Investigate production drop",
        "vaccinations": "Catch up overdue vaccinations",
        "population": "Review cumulative losses",
        "inventory": "Restock inventory",
        "biosecurity": "Tighten biosecurity",
    }.get(a.monitor, a.title)


# ── Briefing (extends Part 4's) ──────────────────────────────────────────────


@dataclass
class SupervisorBriefing:
    farm_name: str
    as_of: date
    greeting: str
    overall: MonitorState
    health_score: int
    sections: list[ReportSection]
    priorities: list[str]
    suggested_actions: list[str]
    notes: list[str]


def build_supervisor_briefing(
    f: FarmFacts,
    *,
    health_score: int,
    monitors: list[Monitor],
    priorities: list[PriorityItem],
) -> SupervisorBriefing:
    """
    The daily briefing, with every section the supervisor spec asks for.

    Anything not recorded is rendered as "Not enough recorded data." rather than
    omitted or estimated — a farmer should be able to see the gap and close it.
    """
    sections: list[ReportSection] = []

    def add(label: str, value: str | None) -> None:
        sections.append(
            ReportSection(label=label, value=value if value else NOT_ENOUGH_DATA,
                          available=bool(value))
        )

    add("Overall health", f"{health_score}/100 · farm is {overall_state(monitors).value}")
    add("Production",
        f"{f.eggs_today} eggs today, {f.eggs_this_week} this week"
        if f.days_since_egg_log is not None else None)
    add("Mortality",
        f"{f.mortality_this_week} lost this week (vs {f.mortality_prev_week} last week)"
        if f.days_since_any_log is not None else None)
    add("Feed",
        f"{f.feed_today_kg}kg today, {f.feed_this_week_kg}kg this week"
        + (f" · about {f.feed_days_remaining} days remaining" if f.feed_days_remaining is not None else "")
        if f.days_since_feed_log is not None else None)
    add("Water",
        f"{f.water_this_week_litres}L this week"
        if f.water_this_week_litres is not None else None)

    if f.upcoming_reminders:
        add("Upcoming reminders",
            "; ".join(
                ("overdue — " if r.get("overdue") else "") + str(r.get("title"))
                for r in f.upcoming_reminders[:3]
            ))
    else:
        add("Upcoming reminders", "None in the next 7 days")

    due = f.vaccinations_overdue + f.vaccinations_due_today + f.vaccinations_due_week
    add("Vaccinations due",
        (f"{f.vaccinations_overdue} overdue, {f.vaccinations_due_today} today, "
         f"{f.vaccinations_due_week} this week") if due else "None in the next 7 days")

    notes = [
        f"{m.label}: {NOT_ENOUGH_DATA}" for m in monitors if m.unmeasured
    ]

    suggested = [p.label for p in priorities[:5]]
    if not suggested:
        suggested = ["Record today's feed, eggs and any mortality."]

    return SupervisorBriefing(
        farm_name=f.farm_name,
        as_of=f.as_of,
        greeting=f"Good morning. Here's {f.farm_name} today.",
        overall=overall_state(monitors),
        health_score=health_score,
        sections=sections,
        priorities=[p.label for p in priorities[:5]],
        suggested_actions=suggested,
        notes=notes,
    )


# ── Reports ──────────────────────────────────────────────────────────────────

_PERIODS = {
    "today": ("Today", 1),
    "7d": ("Last 7 days", 7),
    "30d": ("Last 30 days", 30),
}


def build_report(f: FarmFacts, period: str) -> Report:
    """
    A deterministic operational report.

    FarmFacts carries today- and week-scoped aggregates, so the 30-day report
    states plainly which of its lines it cannot fill rather than extrapolating
    a week into a month. Estimating there would be exactly the fabrication the
    honesty rules forbid.
    """
    label, _days = _PERIODS.get(period, _PERIODS["7d"])
    sections: list[ReportSection] = []
    notes: list[str] = []

    def add(name: str, value: str | None) -> None:
        sections.append(ReportSection(label=name, value=value or NOT_ENOUGH_DATA,
                                      available=value is not None))

    if period == "today":
        add("Production", f"{f.eggs_today} eggs" if f.days_since_egg_log is not None else None)
        add("Feed usage", f"{f.feed_today_kg}kg" if f.days_since_feed_log is not None else None)
        add("Water usage", f"{f.water_today_litres}L" if f.water_today_litres is not None else None)
        add("Mortality", None if f.days_since_any_log is None else
            ("recorded today" if f.days_since_any_log == 0 else "no log entered today"))
    elif period == "7d":
        add("Production", f"{f.eggs_this_week} eggs" if f.days_since_egg_log is not None else None)
        add("Feed usage", f"{f.feed_this_week_kg}kg" if f.days_since_feed_log is not None else None)
        add("Water usage", f"{f.water_this_week_litres}L" if f.water_this_week_litres is not None else None)
        add("Mortality", f"{f.mortality_this_week} birds" if f.days_since_any_log is not None else None)
    else:  # 30d
        add("Production", None)
        add("Feed usage", None)
        add("Water usage", None)
        add("Mortality", None)
        notes.append(
            "ARIA aggregates production, feed, water and mortality over 7-day "
            "windows. A 30-day total isn't computed from those without "
            "estimating, so it is left blank rather than guessed."
        )

    due = f.vaccinations_overdue + f.vaccinations_due_today + f.vaccinations_due_week
    add("Vaccinations", f"{due} due or overdue in the next 7 days" if due else "none due")

    if f.is_profitable is None:
        add("Financial summary", None)
        notes.append("No finance data recorded for this farm yet.")
    else:
        add("Financial summary",
            f"revenue {f.revenue}, expenses {f.expenses}, "
            f"{'profit' if f.is_profitable else 'loss'} {f.gross_profit}")

    return Report(period=period, label=label, sections=sections, notes=notes)


# ── Timeline ─────────────────────────────────────────────────────────────────


def build_timeline(events: list[TimelineEvent], limit: int = 50) -> list[TimelineEvent]:
    """
    Order gathered events newest-first.

    The events themselves are read from the database by the data layer; this
    only sorts and caps them, so the engine stays pure and the timeline can
    never contain anything that was not actually recorded.
    """
    return sorted(events, key=lambda e: e.at, reverse=True)[:limit]


# ── Auto-reminder proposals ──────────────────────────────────────────────────


@dataclass
class ReminderProposal:
    title: str
    reason: str
    due_in_days: int


def propose_reminders(f: FarmFacts) -> list[ReminderProposal]:
    """
    Reminders the supervisor thinks should exist.

    Returns *proposals*, not reminders — the data layer decides what already
    exists and writes only the genuinely new ones. Anything whose title already
    matches an open reminder is filtered here as a first pass, so the common
    case never reaches the database at all.
    """
    existing = {t.strip().lower() for t in f.reminder_titles}
    out: list[ReminderProposal] = []

    def add(title: str, reason: str, due_in_days: int) -> None:
        if title.strip().lower() in existing:
            return
        out.append(ReminderProposal(title=title, reason=reason, due_in_days=due_in_days))

    if f.vaccinations_overdue or f.vaccinations_due_today or f.vaccinations_due_week:
        vac = f.next_vaccination or {}
        name = vac.get("vaccine") or "vaccination"
        days = vac.get("days_until_due")
        add(f"Vaccinate: {name}",
            "Scheduled from your vaccination plan.",
            max(0, int(days)) if isinstance(days, int) and days > 0 else 0)

    for item in f.inventory_out[:3]:
        add(f"Reorder {item}", "This item is out of stock.", 0)
    for item in f.inventory_low[:3]:
        add(f"Reorder {item}", "This item is at or below its reorder level.", 2)

    if f.days_since_weighin is None or f.days_since_weighin >= 7:
        add("Weigh a sample of birds",
            "Weekly weigh-ins are how feed efficiency problems get caught early.", 1)

    return out
