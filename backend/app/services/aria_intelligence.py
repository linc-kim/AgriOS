"""
ARIA — the farm intelligence engine.

This is the layer that makes ARIA behave like an operations manager rather than
a logbook: it reads what the farm has recorded and produces a morning briefing,
a checklist that changes with the birds, explainable insights, trend
explanations and a farm-health score. All of it deterministic, all of it
explainable, none of it needing Gemini or Claude.

The shape of the module is deliberate. Every output is computed by a *pure*
function over a `FarmFacts` snapshot — no database, no clock, no I/O. The async
`gather_facts()` is the only part that touches the database; it assembles the
snapshot from the services that already exist (production dashboard, vaccination
schedule, finance, disease risk, daily logs, reminders) and hands it to the pure
functions. That split is what lets the intelligence be tested exhaustively
without a database, and it is what guarantees the engine can only ever reason
about numbers the farm actually recorded.

Two rules run through all of it. It never invents a cause: a trend is only
explained when a *co-recorded* factor supports it, and otherwise the change is
reported without a made-up reason. And it is honest about what it cannot see:
biosecurity has no direct measurement in the records, so it is scored from
proxies and labelled as inferred rather than dressed up as a fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


# ── Inputs ───────────────────────────────────────────────────────────────────


@dataclass
class FlockStage:
    name: str
    age_days: int | None
    species: str = "poultry"

    @property
    def is_laying_age(self) -> bool:
        return self.age_days is not None and self.age_days >= 126  # ~18 weeks

    @property
    def is_brooding(self) -> bool:
        return self.age_days is not None and self.age_days <= 21


@dataclass
class FarmFacts:
    """
    Everything the intelligence needs, as plain values. Populated by
    `gather_facts`; consumed by the pure functions below. A field being None
    means "not recorded", and the engine treats that as missing information to
    be stated honestly, never as a zero to reason from.
    """

    farm_name: str
    as_of: date

    active_flocks: int = 0
    total_birds: int = 0
    avg_bird_age_days: int | None = None
    flock_stages: list[FlockStage] = field(default_factory=list)

    # Production
    eggs_today: int = 0
    eggs_this_week: int = 0
    eggs_prev_week: int = 0
    hen_day_pct: float | None = None

    # Feed
    feed_today_kg: Decimal = Decimal("0")
    feed_this_week_kg: Decimal = Decimal("0")
    feed_prev_week_kg: Decimal = Decimal("0")
    feed_days_remaining: int | None = None

    # Mortality
    mortality_this_week: int = 0
    mortality_prev_week: int = 0

    # Recency — days since the last record of each kind. None = never recorded.
    days_since_feed_log: int | None = None
    days_since_mortality_log: int | None = None
    days_since_weighin: int | None = None
    days_since_egg_log: int | None = None
    days_since_any_log: int | None = None

    # Health
    disease_score: int = 0
    disease_level: str = "low"
    disease_factors: list[dict] = field(default_factory=list)
    disease_recommendation: str = ""
    vaccinations_overdue: int = 0
    vaccinations_due_today: int = 0
    vaccinations_due_week: int = 0
    next_vaccination: dict | None = None

    # Finance
    is_profitable: bool | None = None
    gross_profit: Decimal | None = None
    feed_cost: Decimal | None = None
    feed_cost_pct: Decimal | None = None
    revenue: Decimal | None = None
    expenses: Decimal | None = None

    # Reminders
    reminders_overdue: int = 0
    reminders_open: int = 0
    #: Titles of reminders already open, so auto-generation can avoid duplicates.
    reminder_titles: list[str] = field(default_factory=list)
    #: Reminders due in the next 7 days: {title, due_at, overdue}.
    upcoming_reminders: list[dict] = field(default_factory=list)

    # ── Water (Part 5) ────────────────────────────────────────────────────
    # Water is the first thing to fail on a farm and the fastest to hurt a
    # flock, which is why the supervisor watches it as its own monitor. None
    # means never recorded — never treated as zero consumption.
    water_today_litres: Decimal | None = None
    water_this_week_litres: Decimal | None = None
    water_prev_week_litres: Decimal | None = None
    days_since_water_log: int | None = None

    # ── Inventory (Part 5) ────────────────────────────────────────────────
    inventory_tracked: int = 0
    #: Item names at or below their reorder level, and fully exhausted ones.
    inventory_low: list[str] = field(default_factory=list)
    inventory_out: list[str] = field(default_factory=list)

    # ── Population (Part 5) ───────────────────────────────────────────────
    #: Birds placed across active flocks, so losses can be expressed as a share
    #: of the flock rather than a bare count.
    initial_birds: int = 0

    # ── Planning inputs (Part 6) ──────────────────────────────────────────
    #: Feed physically in stock, summed from inventory items in the "feed"
    #: category whose unit is kilograms. None = feed isn't tracked in inventory,
    #: which is different from having none.
    feed_stock_kg: Decimal | None = None

    #: Houses with their capacity and current occupancy, for the capacity
    #: planner: {name, capacity, birds, flock_name, occupied}.
    houses: list[dict] = field(default_factory=list)

    #: Per active flock: {name, placement_date, days_elapsed, cycle_days,
    #: days_remaining, expected_close_date, birds}.
    cycles: list[dict] = field(default_factory=list)

    #: How many distinct days each metric has been recorded over the last 30.
    #: This is the sole input to forecast confidence — a projection from three
    #: days of data must not claim the same certainty as one from thirty.
    feed_history_days: int = 0
    egg_history_days: int = 0
    water_history_days: int = 0
    mortality_history_days: int = 0

    #: Recorded expense totals by category name over the last 30 days.
    #: Only categories the farmer actually used appear — the budget never
    #: invents a line for something never spent on.
    expense_by_category: dict[str, Decimal] = field(default_factory=dict)
    expense_window_days: int = 30


# ── Outputs ──────────────────────────────────────────────────────────────────


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FactorStatus(str, Enum):
    OK = "ok"          # ✓
    WARN = "warn"      # △
    FAIL = "fail"      # ✗


@dataclass
class Insight:
    """
    One operational finding, with the full explanation the spec requires:
    problem, reason, action, benefit, confidence, and the records it drew on.
    """

    key: str
    title: str
    problem: str
    reason: str
    action: str
    benefit: str
    confidence: str            # high | medium | low
    sources: list[str]
    priority: Priority = Priority.MEDIUM


@dataclass
class ChecklistItem:
    key: str
    label: str
    done: bool
    reason: str
    priority: Priority = Priority.MEDIUM


@dataclass
class Trend:
    metric: str
    direction: str             # up | down | steady
    change_pct: float | None
    explanation: str
    grounded: bool             # True only when a co-recorded cause supports it
    sources: list[str]


@dataclass
class HealthFactor:
    key: str
    label: str
    score: int
    max_score: int
    status: FactorStatus
    explanation: str


@dataclass
class HealthScore:
    score: int
    max_score: int
    grade: str                 # excellent | good | fair | poor
    factors: list[HealthFactor]


@dataclass
class Briefing:
    farm_name: str
    as_of: date
    greeting: str
    lines: list[str]           # the bulleted status lines
    priorities: list[str]      # today's ranked priorities
    health_score: int
    notes: list[str]           # honest "not recorded" caveats


# ── Health score ─────────────────────────────────────────────────────────────
#
# Five factors, 20 points each. Each returns a status and an explanation of
# exactly why it scored what it did — the score is never a bare number.


def _score_vaccination(f: FarmFacts) -> HealthFactor:
    overdue = f.vaccinations_overdue
    if overdue == 0:
        return HealthFactor(
            "vaccination", "Vaccination", 20, 20, FactorStatus.OK,
            "No overdue vaccinations — your flocks are on schedule.",
        )
    score = max(0, 20 - overdue * 8)
    status = FactorStatus.FAIL if score == 0 else FactorStatus.WARN
    return HealthFactor(
        "vaccination", "Vaccination", score, 20, status,
        f"{overdue} vaccination(s) overdue. Each overdue dose leaves the flock "
        f"exposed and pulls this score down.",
    )


def _score_mortality(f: FarmFacts) -> HealthFactor:
    if f.total_birds <= 0:
        return HealthFactor(
            "mortality", "Mortality", 14, 20, FactorStatus.WARN,
            "No active bird count on record, so mortality can't be scored against a flock size.",
        )
    rate = f.mortality_this_week / f.total_birds * 100
    if rate < 0.5:
        return HealthFactor(
            "mortality", "Mortality", 20, 20, FactorStatus.OK,
            f"Weekly losses are low ({f.mortality_this_week} of {f.total_birds} birds, {rate:.1f}%).",
        )
    if rate < 1.0:
        return HealthFactor(
            "mortality", "Mortality", 15, 20, FactorStatus.OK,
            f"Weekly losses are within normal range ({rate:.1f}% of the flock).",
        )
    if rate < 2.0:
        return HealthFactor(
            "mortality", "Mortality", 10, 20, FactorStatus.WARN,
            f"Weekly losses are elevated ({rate:.1f}% of the flock) — worth watching closely.",
        )
    return HealthFactor(
        "mortality", "Mortality", 4, 20, FactorStatus.FAIL,
        f"Weekly losses are high ({rate:.1f}% of the flock). Investigate cause urgently.",
    )


def _score_production(f: FarmFacts) -> HealthFactor:
    if f.hen_day_pct is None:
        # No laying data — either broilers or nothing recorded. Neutral, and honest.
        return HealthFactor(
            "production", "Production", 14, 20, FactorStatus.WARN,
            "No hen-day production on record to score. Log egg collection to track this.",
        )
    p = f.hen_day_pct
    if p >= 75:
        return HealthFactor("production", "Production", 20, 20, FactorStatus.OK,
                            f"Strong laying rate ({p:.0f}% hen-day).")
    if p >= 60:
        return HealthFactor("production", "Production", 16, 20, FactorStatus.OK,
                            f"Healthy laying rate ({p:.0f}% hen-day).")
    if p >= 40:
        return HealthFactor("production", "Production", 11, 20, FactorStatus.WARN,
                            f"Laying rate is below par ({p:.0f}% hen-day) — check nutrition, light and age.")
    return HealthFactor("production", "Production", 5, 20, FactorStatus.FAIL,
                        f"Laying rate is low ({p:.0f}% hen-day). Review feed, lighting and health.")


def _score_record_keeping(f: FarmFacts) -> HealthFactor:
    d = f.days_since_any_log
    if d is None:
        return HealthFactor(
            "record_keeping", "Record keeping", 2, 20, FactorStatus.FAIL,
            "No daily records found. ARIA can only help once you're logging feed, mortality and eggs.",
        )
    if d <= 1:
        return HealthFactor("record_keeping", "Record keeping", 20, 20, FactorStatus.OK,
                            "Records are up to date — logged within the last day.")
    if d <= 3:
        return HealthFactor("record_keeping", "Record keeping", 12, 20, FactorStatus.WARN,
                            f"Last record was {d} days ago. Daily logging keeps insights accurate.")
    return HealthFactor("record_keeping", "Record keeping", 4, 20, FactorStatus.FAIL,
                        f"No records for {d} days. Gaps this long hide problems until they're serious.")


def _score_biosecurity(f: FarmFacts) -> HealthFactor:
    """
    Biosecurity has no direct measurement in the records, so it is *inferred*
    from proxies — disease risk level and vaccination currency — and labelled as
    such. Inventing a precise biosecurity number would be exactly the fabrication
    the module forbids.
    """
    penalty = 0
    reasons = []
    if f.disease_level in ("high", "critical"):
        penalty += 8
        reasons.append("area/health disease risk is elevated")
    if f.vaccinations_overdue > 0:
        penalty += 4
        reasons.append("overdue vaccinations weaken the flock's defences")
    score = max(6, 14 - penalty)  # capped below 20: we can't confirm good practice
    status = FactorStatus.WARN if penalty else FactorStatus.WARN
    if penalty >= 8:
        status = FactorStatus.FAIL
    detail = (
        "Inferred from disease risk and vaccination status — "
        + ("; ".join(reasons) if reasons else "no elevated risk signals")
        + ". ARIA can't fully assess biosecurity from records alone."
    )
    return HealthFactor("biosecurity", "Biosecurity", score, 20, status, detail)


def compute_health_score(f: FarmFacts) -> HealthScore:
    factors = [
        _score_vaccination(f),
        _score_mortality(f),
        _score_production(f),
        _score_record_keeping(f),
        _score_biosecurity(f),
    ]
    total = sum(x.score for x in factors)
    max_total = sum(x.max_score for x in factors)
    pct = total / max_total * 100 if max_total else 0
    grade = (
        "excellent" if pct >= 85
        else "good" if pct >= 70
        else "fair" if pct >= 50
        else "poor"
    )
    return HealthScore(score=total, max_score=max_total, grade=grade, factors=factors)


# ── Insights ─────────────────────────────────────────────────────────────────


def _pct_change(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (current - prior) / prior * 100


def build_insights(f: FarmFacts) -> list[Insight]:
    """Everything worth flagging, most urgent first. Each fully explained."""
    out: list[Insight] = []

    # No feed recorded recently.
    if f.days_since_feed_log is not None and f.days_since_feed_log >= 2:
        out.append(Insight(
            key="no_feed_logged",
            title="No feed recorded recently",
            problem=f"No feed has been logged for {f.days_since_feed_log} days.",
            reason="Feed is 60–70% of cost and the main driver of growth and laying. "
                   "A gap in feed records hides both overspending and underfeeding.",
            action="Record what you've been feeding, or log a purchase if you restocked.",
            benefit="Accurate feed data lets ARIA track cost per bird and catch a drop before it hits production.",
            confidence="high",
            sources=["Feed", "Daily logs"],
            priority=Priority.HIGH,
        ))

    # Mortality up vs last week.
    if f.mortality_this_week > f.mortality_prev_week and f.mortality_this_week >= 2:
        change = _pct_change(f.mortality_this_week, f.mortality_prev_week)
        change_txt = f" (up {change:.0f}%)" if change is not None else ""
        out.append(Insight(
            key="mortality_up",
            title="Mortality is rising",
            problem=f"{f.mortality_this_week} birds lost this week vs {f.mortality_prev_week} last week{change_txt}.",
            reason="A week-on-week rise in deaths is the earliest warning of disease, heat "
                   "stress or a management problem.",
            action="Record symptoms and check the affected house. If deaths keep climbing, call your vet.",
            benefit="Catching the cause early can stop a handful of losses becoming an outbreak.",
            confidence="high" if f.mortality_prev_week > 0 else "medium",
            sources=["Livestock", "Daily logs"],
            priority=Priority.HIGH,
        ))

    # Production dropped.
    egg_change = _pct_change(f.eggs_this_week, f.eggs_prev_week)
    if egg_change is not None and egg_change <= -5:
        out.append(Insight(
            key="production_drop",
            title="Egg production dropped",
            problem=f"Egg collection is down {abs(egg_change):.0f}% versus last week.",
            reason="Production falls when birds are stressed, underfed, short of water, or "
                   "reacting to disease — the earlier it's caught, the smaller the loss.",
            action="Check water and feed availability first, then look for signs of illness or heat stress.",
            benefit="A quick response protects income; a sustained drop is expensive.",
            confidence="high",
            sources=["Production"],
            priority=Priority.HIGH,
        ))

    # Vaccinations overdue.
    if f.vaccinations_overdue > 0:
        out.append(Insight(
            key="vaccination_overdue",
            title="Vaccinations overdue",
            problem=f"{f.vaccinations_overdue} vaccination(s) are past due.",
            reason="An overdue dose leaves the flock unprotected against diseases like Newcastle "
                   "and Gumboro that have no cure once they strike.",
            action="Catch up the overdue vaccinations as soon as you can source the vaccine.",
            benefit="Timely vaccination is the cheapest insurance a poultry farm can buy.",
            confidence="high",
            sources=["Health"],
            priority=Priority.HIGH,
        ))

    # Not weighed recently.
    if (f.days_since_weighin is None or f.days_since_weighin >= 14) and f.total_birds > 0:
        never = f.days_since_weighin is None
        out.append(Insight(
            key="weighin_stale",
            title="Birds not weighed recently",
            problem="No weigh-in on record." if never else f"Last weigh-in was {f.days_since_weighin} days ago.",
            reason="Weight is how you tell whether feed is doing its job. Without it, FCR and "
                   "growth are guesswork.",
            action="Weigh a sample of birds and record the average.",
            benefit="Regular weigh-ins reveal feed-efficiency problems while they're still cheap to fix.",
            confidence="medium",
            sources=["Livestock"],
            priority=Priority.MEDIUM,
        ))

    # Feed running low.
    if f.feed_days_remaining is not None and f.feed_days_remaining <= 7:
        out.append(Insight(
            key="feed_low",
            title="Feed stock running low",
            problem=f"About {f.feed_days_remaining} days of feed remaining.",
            reason="Running out of feed even for a day sets birds back and can crash laying.",
            action="Reorder feed now to avoid an emergency purchase at a worse price.",
            benefit="Planned restocking protects both production and your margin.",
            confidence="high",
            sources=["Inventory", "Feed"],
            priority=Priority.HIGH if f.feed_days_remaining <= 3 else Priority.MEDIUM,
        ))

    # Elevated disease risk.
    if f.disease_level in ("high", "critical"):
        out.append(Insight(
            key="disease_risk",
            title=f"Disease risk is {f.disease_level}",
            problem=f"ARIA's disease-risk score is {f.disease_score}/100 ({f.disease_level}).",
            reason=f.disease_recommendation or "Several risk signals are raised at once.",
            action="Tighten biosecurity, isolate any sick birds, and consult your vet. "
                   "ARIA flags risk — it does not diagnose.",
            benefit="Acting on risk early is far cheaper than managing an outbreak.",
            confidence="medium",
            sources=["Health"],
            priority=Priority.HIGH,
        ))

    # Overdue reminders.
    if f.reminders_overdue > 0:
        out.append(Insight(
            key="reminders_overdue",
            title="Overdue reminders",
            problem=f"{f.reminders_overdue} reminder(s) are past their due time.",
            reason="Reminders you set are the tasks you decided mattered — letting them slip "
                   "is how routine jobs get missed.",
            action="Clear the overdue reminders, or reschedule the ones that no longer apply.",
            benefit="Staying on top of routine tasks is most of what keeps a flock healthy.",
            confidence="high",
            sources=["Reminders"],
            priority=Priority.MEDIUM,
        ))

    order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    out.sort(key=lambda i: order[i.priority])
    return out


# ── Trends ───────────────────────────────────────────────────────────────────


def explain_trends(f: FarmFacts) -> list[Trend]:
    """
    Explain movements only where a co-recorded factor supports the explanation.
    Where a metric moved but nothing in the records explains it, the change is
    reported with `grounded=False` and no invented cause.
    """
    trends: list[Trend] = []

    # Egg production trend.
    egg_change = _pct_change(f.eggs_this_week, f.eggs_prev_week)
    if egg_change is not None and abs(egg_change) >= 3:
        direction = "up" if egg_change > 0 else "down"
        cause = None
        # Only claim a cause supported by another recorded movement.
        mortality_down = f.mortality_this_week < f.mortality_prev_week
        feed_steady = (
            f.feed_prev_week_kg > 0
            and abs(_pct_change(float(f.feed_this_week_kg), float(f.feed_prev_week_kg)) or 0) < 15
        )
        if direction == "up" and mortality_down and feed_steady:
            cause = "mortality fell and feeding stayed consistent"
        elif direction == "down" and f.mortality_this_week > f.mortality_prev_week:
            cause = "mortality rose over the same period"
        elif direction == "down" and f.feed_this_week_kg < f.feed_prev_week_kg:
            cause = "feed consumption also dropped"

        explanation = (
            f"Egg production is {direction} {abs(egg_change):.0f}% week on week"
            + (f", likely because {cause}." if cause else ". No recorded cause stands out — watch it.")
        )
        trends.append(Trend(
            metric="egg_production", direction=direction, change_pct=round(egg_change, 1),
            explanation=explanation, grounded=cause is not None, sources=["Production"],
        ))

    # Profit / cost trend.
    if f.is_profitable is not None and f.feed_cost_pct is not None:
        if not f.is_profitable and float(f.feed_cost_pct) >= 65:
            trends.append(Trend(
                metric="profit", direction="down", change_pct=None,
                explanation=f"The farm is not currently profitable, and feed is {f.feed_cost_pct}% "
                            "of costs — the largest lever you have is feed efficiency.",
                grounded=True, sources=["Finance"],
            ))

    # Mortality trend (report even without a cause).
    if f.mortality_this_week != f.mortality_prev_week and (f.mortality_this_week + f.mortality_prev_week) >= 2:
        direction = "up" if f.mortality_this_week > f.mortality_prev_week else "down"
        change = _pct_change(f.mortality_this_week, f.mortality_prev_week)
        trends.append(Trend(
            metric="mortality", direction=direction, change_pct=round(change, 1) if change is not None else None,
            explanation=f"Mortality is {direction}: {f.mortality_prev_week} last week, "
                        f"{f.mortality_this_week} this week.",
            grounded=False, sources=["Livestock"],
        ))

    return trends


# ── Checklist ────────────────────────────────────────────────────────────────


def build_checklist(f: FarmFacts) -> list[ChecklistItem]:
    """
    A dynamic list that changes with bird age, the vaccination schedule, health
    alerts and open reminders. `done` is set from whether the matching record
    already exists today, so the list reflects what's actually left to do.
    """
    items: list[ChecklistItem] = []
    has_layers = any(s.is_laying_age for s in f.flock_stages) or f.hen_day_pct is not None
    has_brooding = any(s.is_brooding for s in f.flock_stages)

    # Daily essentials.
    if has_layers:
        items.append(ChecklistItem(
            "collect_eggs", "Collect eggs", done=f.eggs_today > 0,
            reason="Daily collection reduces breakages and dirty eggs.",
            priority=Priority.HIGH,
        ))
    items.append(ChecklistItem(
        "check_drinkers", "Check drinkers and water", done=False,
        reason="Water is the first thing to fail and the fastest to hurt the flock.",
        priority=Priority.HIGH,
    ))
    items.append(ChecklistItem(
        "record_feed", "Record today's feed", done=f.feed_today_kg > 0,
        reason="Feed is your biggest cost — logging it daily keeps cost-per-bird honest.",
        priority=Priority.MEDIUM,
    ))
    items.append(ChecklistItem(
        "record_log", "Record today's mortality and observations",
        done=f.days_since_any_log == 0,
        reason="A daily log is what every insight is built from.",
        priority=Priority.MEDIUM,
    ))

    # Age-driven.
    if has_brooding:
        items.append(ChecklistItem(
            "clean_brooder", "Clean the brooder and check heat", done=False,
            reason="Chicks under 3 weeks depend on clean, warm brooding — it decides week six.",
            priority=Priority.HIGH,
        ))
    if f.days_since_weighin is None or f.days_since_weighin >= 7:
        items.append(ChecklistItem(
            "weigh_flock", "Weigh a sample of birds", done=False,
            reason="Weekly weigh-ins are how you catch feed-efficiency problems early.",
            priority=Priority.MEDIUM,
        ))

    # Schedule-driven.
    if f.vaccinations_overdue > 0 or f.vaccinations_due_today > 0:
        due = f.vaccinations_overdue + f.vaccinations_due_today
        label = "Vaccinate — " + (
            f.next_vaccination.get("vaccine") if f.next_vaccination and f.next_vaccination.get("vaccine")
            else f"{due} due"
        )
        items.append(ChecklistItem(
            "vaccinate", label, done=False,
            reason="Vaccination on time is the cheapest protection against the diseases with no cure.",
            priority=Priority.HIGH,
        ))

    # Health-driven.
    if f.disease_level in ("high", "critical"):
        items.append(ChecklistItem(
            "inspect_health", "Inspect birds for signs of illness", done=False,
            reason=f"Disease risk is {f.disease_level} — a close look now can catch an outbreak early.",
            priority=Priority.HIGH,
        ))
    if f.mortality_this_week > 0:
        items.append(ChecklistItem(
            "remove_dead", "Remove and dispose of dead birds", done=False,
            reason="Prompt, safe disposal stops disease spreading through the flock.",
            priority=Priority.HIGH,
        ))

    # Always worth a look.
    items.append(ChecklistItem(
        "inspect_ventilation", "Inspect ventilation", done=False,
        reason="Poor airflow drives respiratory disease and heat stress.",
        priority=Priority.LOW,
    ))

    # Open reminders the farmer set themselves.
    if f.reminders_overdue > 0:
        items.append(ChecklistItem(
            "reminders", f"Clear {f.reminders_overdue} overdue reminder(s)", done=False,
            reason="These are tasks you flagged as important.",
            priority=Priority.MEDIUM,
        ))

    order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    items.sort(key=lambda i: (i.done, order[i.priority]))
    return items


# ── Briefing ─────────────────────────────────────────────────────────────────


def build_briefing(f: FarmFacts, health: HealthScore, insights: list[Insight]) -> Briefing:
    """The morning brief — status lines and ranked priorities, from data only."""
    lines: list[str] = []
    notes: list[str] = []

    if f.feed_days_remaining is not None:
        lines.append(f"Feed inventory: about {f.feed_days_remaining} days remaining.")
    else:
        notes.append("Feed stock isn't tracked in inventory yet, so days-remaining is unavailable.")

    due = f.vaccinations_overdue + f.vaccinations_due_today + f.vaccinations_due_week
    if due > 0:
        parts = []
        if f.vaccinations_overdue:
            parts.append(f"{f.vaccinations_overdue} overdue")
        if f.vaccinations_due_today:
            parts.append(f"{f.vaccinations_due_today} due today")
        if f.vaccinations_due_week:
            parts.append(f"{f.vaccinations_due_week} due this week")
        lines.append(f"Vaccinations: {', '.join(parts)}.")
    else:
        lines.append("Vaccinations: none due in the next 7 days.")

    egg_change = _pct_change(f.eggs_this_week, f.eggs_prev_week)
    if egg_change is not None:
        if egg_change >= 2:
            lines.append(f"Egg production up {egg_change:.0f}% on last week.")
        elif egg_change <= -2:
            lines.append(f"Egg production down {abs(egg_change):.0f}% on last week.")
        else:
            lines.append("Egg production steady.")
    elif f.eggs_this_week > 0:
        lines.append(f"{f.eggs_this_week} eggs collected this week.")

    if f.total_birds > 0:
        if f.mortality_this_week == 0:
            lines.append("Mortality: none recorded this week.")
        else:
            change = _pct_change(f.mortality_this_week, f.mortality_prev_week)
            trend = (" and rising" if change and change > 0 else " and falling" if change and change < 0 else " and stable")
            lines.append(f"Mortality: {f.mortality_this_week} this week{trend}.")

    if f.reminders_overdue > 0:
        lines.append(f"{f.reminders_overdue} reminder(s) overdue.")

    lines.append(f"Disease risk remains {f.disease_level}.")

    # Priorities = the top few high/medium insights, phrased as actions.
    priorities = [i.action for i in insights[:3]]
    if not priorities:
        priorities = ["Record today's feed, eggs and any mortality.",
                      "Check water and feed availability.",
                      "Keep an eye on the flock during your morning walk."]

    if f.days_since_any_log is None:
        notes.append("No daily records yet — the briefing gets sharper the more you log.")

    greeting = f"Good morning. Here's {f.farm_name} today."
    return Briefing(
        farm_name=f.farm_name,
        as_of=f.as_of,
        greeting=greeting,
        lines=lines,
        priorities=priorities,
        health_score=health.score,
        notes=notes,
    )
