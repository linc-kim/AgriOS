"""
ARIA — the farm planner.

Parts 4 and 5 made ARIA explain the present and watch it continuously. This
module looks forward: how long the feed lasts, what production is likely to do,
what a decision would cost, whether the houses can take more birds, what the
month's budget looks like, and what the calendar demands.

Pure by construction, like the rest of Module 13. Every function takes a
`FarmFacts` snapshot and returns plain data — no database, no clock, no I/O.
Scenario simulation in particular is a pure function of facts plus a change: it
computes a hypothetical and returns it, and there is no code path by which it
could write anything. A "what if" that could alter production data would be a
serious hazard, so the architecture removes the possibility rather than
guarding it.

Forecasting honestly is the whole difficulty here, and three rules govern it.

*The method is simple and stated.* Every projection is a rate multiplied by a
horizon, where the rate comes from recorded history. No regression, no
smoothing, no seasonality — a farmer can check the arithmetic, and `method` on
every forecast says exactly what was done.

*Confidence comes from data completeness, not from the numbers.* A projection
built on three recorded days is Low confidence however tidy it looks; one built
on a month is High. `confidence_from_history` is the single place that decides,
so no forecast can quietly award itself more certainty than its evidence earns.

*Too little history produces no number at all.* Below `MIN_HISTORY_DAYS` the
forecast returns unavailable with "Not enough recorded data." rather than
extrapolating from noise. A confident wrong depletion date empties a feed store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

from app.services.aria_intelligence import FarmFacts

NOT_ENOUGH_DATA = "Not enough recorded data."

#: Below this many recorded days, no forecast is produced at all.
MIN_HISTORY_DAYS = 3


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


def confidence_from_history(days: int) -> Confidence:
    """
    Confidence is a function of how much was recorded, and nothing else.

    Kept in one place deliberately: if each forecast judged its own certainty,
    they would drift, and the one built on the least data would be the most
    likely to overstate itself.
    """
    if days >= 14:
        return Confidence.HIGH
    if days >= 7:
        return Confidence.MEDIUM
    if days >= MIN_HISTORY_DAYS:
        return Confidence.LOW
    return Confidence.NONE


def _q(value: Decimal | float | int, places: str = "0.01") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


# ── Outputs ──────────────────────────────────────────────────────────────────


@dataclass
class Forecast:
    """
    One projection, with everything needed to check or dispute it.

    `available=False` means the history was too thin to project from; `value`
    then carries NOT_ENOUGH_DATA and every other field explains why.
    """

    key: str
    label: str
    value: str
    unit: str = ""
    available: bool = True
    confidence: Confidence = Confidence.NONE
    method: str = ""
    assumptions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class FeedForecast:
    daily_rate_kg: Decimal | None
    days_remaining: int | None
    depletion_date: str | None
    required_7d_kg: Decimal | None
    required_30d_kg: Decimal | None
    required_cycle_kg: Decimal | None
    cycle_days_remaining: int | None
    confidence: Confidence
    method: str
    assumptions: list[str]
    evidence: list[str]
    notes: list[str]


@dataclass
class ScenarioChange:
    label: str
    current: str
    projected: str
    difference: str


@dataclass
class ScenarioResult:
    scenario: str
    description: str
    changes: list[ScenarioChange]
    implications: list[str]
    assumptions: list[str]
    available: bool = True
    note: str = ""


@dataclass
class HouseCapacity:
    name: str
    capacity: int
    birds: int
    utilisation_pct: float | None
    state: str                # empty | under | healthy | crowded | over
    note: str


@dataclass
class CapacityPlan:
    total_capacity: int
    total_birds: int
    available_space: int
    utilisation_pct: float | None
    houses: list[HouseCapacity]
    recommendations: list[str]
    notes: list[str]


@dataclass
class BudgetLine:
    category: str
    amount: Decimal
    basis: str


@dataclass
class Budget:
    period: str               # weekly | monthly | cycle
    label: str
    lines: list[BudgetLine]
    total: Decimal
    method: str
    assumptions: list[str]
    notes: list[str]
    available: bool = True


@dataclass
class CashFlow:
    period_days: int
    expected_expenses: Decimal | None
    expected_income: Decimal | None
    net: Decimal | None
    upcoming: list[str]
    outlook: str              # surplus | shortfall | unknown
    assumptions: list[str]
    notes: list[str]


@dataclass
class CalendarEntry:
    on: str                   # ISO date
    kind: str                 # vaccination | inspection | cleaning | inventory | recording
    title: str
    why: str


# ── 1. Feed forecast ─────────────────────────────────────────────────────────


def forecast_feed(f: FarmFacts) -> FeedForecast:
    """
    Days of feed remaining, depletion date, and what the next horizons need.

    Method: mean daily consumption over the recorded week, then stock divided by
    that rate. Deliberately the simplest defensible calculation — a farmer can
    reproduce it, and it degrades gracefully when the flock size changes.
    """
    assumptions: list[str] = []
    evidence: list[str] = []
    notes: list[str] = []
    confidence = confidence_from_history(f.feed_history_days)

    if f.feed_history_days < MIN_HISTORY_DAYS:
        return FeedForecast(
            daily_rate_kg=None, days_remaining=None, depletion_date=None,
            required_7d_kg=None, required_30d_kg=None, required_cycle_kg=None,
            cycle_days_remaining=None, confidence=Confidence.NONE,
            method="",
            assumptions=[],
            evidence=[f"{f.feed_history_days} day(s) of feed records in the last 30"],
            notes=[f"{NOT_ENOUGH_DATA} At least {MIN_HISTORY_DAYS} days of feed "
                   "records are needed before ARIA will project consumption."],
        )

    # Mean daily rate over the days actually recorded, not over the calendar
    # week — dividing by 7 when only 4 days were logged understates the rate
    # and would overstate how long the feed lasts.
    recorded_days = min(f.feed_history_days, 7)
    daily = Decimal(str(f.feed_this_week_kg)) / Decimal(recorded_days) if recorded_days else Decimal(0)
    daily = _q(daily, "0.001")
    evidence.append(f"{f.feed_this_week_kg}kg recorded over {recorded_days} day(s)")
    assumptions.append(
        f"Consumption continues at the recent average of {daily}kg/day."
    )
    method = (
        f"Daily rate = recorded feed in the last 7 days ÷ {recorded_days} recorded day(s). "
        "Horizons = daily rate × days."
    )

    required_7 = _q(daily * 7) if daily > 0 else Decimal("0")
    required_30 = _q(daily * 30) if daily > 0 else Decimal("0")

    # Cycle horizon — only when a cycle length is on record.
    cycle_remaining = None
    required_cycle = None
    remaining_values = [c["days_remaining"] for c in f.cycles if c.get("days_remaining") is not None]
    if remaining_values:
        cycle_remaining = max(remaining_values)
        required_cycle = _q(daily * cycle_remaining)
        evidence.append(f"{cycle_remaining} day(s) left in the current cycle")
    else:
        notes.append("No production cycle length on record, so a cycle-total isn't projected.")

    # Depletion — needs stock on record.
    days_remaining = None
    depletion = None
    if f.feed_stock_kg is None:
        notes.append(
            "Feed stock isn't tracked in inventory (category 'feed', measured in kg), "
            "so days-remaining and a depletion date can't be calculated."
        )
    elif daily <= 0:
        notes.append("Recorded consumption is zero, so a depletion date can't be projected.")
    else:
        days_remaining = int((Decimal(str(f.feed_stock_kg)) / daily).to_integral_value(rounding="ROUND_FLOOR"))
        depletion = (f.as_of + timedelta(days=days_remaining)).isoformat()
        evidence.append(f"{f.feed_stock_kg}kg currently in stock")
        assumptions.append("No further feed deliveries are counted until you record them.")

    return FeedForecast(
        daily_rate_kg=daily,
        days_remaining=days_remaining,
        depletion_date=depletion,
        required_7d_kg=required_7,
        required_30d_kg=required_30,
        required_cycle_kg=required_cycle,
        cycle_days_remaining=cycle_remaining,
        confidence=confidence,
        method=method,
        assumptions=assumptions,
        evidence=evidence,
        notes=notes,
    )


# ── 2. Production forecast ───────────────────────────────────────────────────


def _rate_forecast(
    key: str,
    label: str,
    unit: str,
    weekly_total: Decimal | float | int | None,
    history_days: int,
    horizon_days: int,
    source: str,
) -> Forecast:
    """
    One horizon of a simple rate projection.

    The shared shape for eggs, mortality, water and feed: mean daily rate from
    the recorded week, multiplied by the horizon. Anything with too little
    history returns unavailable rather than a number.
    """
    confidence = confidence_from_history(history_days)
    if weekly_total is None or history_days < MIN_HISTORY_DAYS:
        return Forecast(
            key=f"{key}_{horizon_days}d", label=label, value=NOT_ENOUGH_DATA,
            unit=unit, available=False, confidence=Confidence.NONE,
            method="",
            evidence=[f"{history_days} day(s) of {source} records in the last 30"],
            assumptions=[],
        )

    recorded = min(history_days, 7)
    daily = Decimal(str(weekly_total)) / Decimal(recorded)
    projected = _q(daily * horizon_days)
    return Forecast(
        key=f"{key}_{horizon_days}d",
        label=label,
        value=str(projected),
        unit=unit,
        available=True,
        confidence=confidence,
        method=(
            f"Daily rate = {source} recorded in the last 7 days ÷ {recorded} recorded day(s) "
            f"= {_q(daily, '0.001')}/day. Projection = rate × {horizon_days} day(s)."
        ),
        assumptions=[
            "Current conditions continue — no change in flock size, feed, weather or health.",
        ],
        evidence=[
            f"{weekly_total} {unit} recorded over {recorded} day(s)",
            f"{history_days} day(s) of history in the last 30",
        ],
    )


def forecast_production(f: FarmFacts, horizons: tuple[int, ...] = (1, 7, 30)) -> list[Forecast]:
    """Eggs, mortality, water and feed projected over each horizon."""
    out: list[Forecast] = []
    for days in horizons:
        out.append(_rate_forecast("eggs", "Egg production", "eggs",
                                  f.eggs_this_week, f.egg_history_days, days, "egg collection"))
        out.append(_rate_forecast("mortality", "Mortality", "birds",
                                  f.mortality_this_week, f.mortality_history_days, days, "daily log"))
        out.append(_rate_forecast("water", "Water", "L",
                                  f.water_this_week_litres, f.water_history_days, days, "water"))
        out.append(_rate_forecast("feed", "Feed", "kg",
                                  f.feed_this_week_kg, f.feed_history_days, days, "feed"))
    return out


# ── 3. Scenario simulator ────────────────────────────────────────────────────
#
# Pure. Takes facts and a change, returns a hypothetical. There is no write path
# here at all — a "what if" that could touch production data would be a serious
# hazard, so the design removes the possibility rather than guarding it.


def simulate(f: FarmFacts, scenario: str, magnitude: float | None = None) -> ScenarioResult:
    """
    Run a what-if. `scenario` is one of add_birds, mortality_change,
    feed_price_change, production_change.
    """
    handlers = {
        "add_birds": _sim_add_birds,
        "mortality_change": _sim_mortality,
        "feed_price_change": _sim_feed_price,
        "production_change": _sim_production,
    }
    handler = handlers.get(scenario)
    if handler is None:
        return ScenarioResult(
            scenario=scenario, description="Unknown scenario", changes=[],
            implications=[], assumptions=[], available=False,
            note=("ARIA can simulate: adding birds, a mortality change, a feed price "
                  "change, or a production change."),
        )
    return handler(f, magnitude)


def _sim_add_birds(f: FarmFacts, magnitude: float | None) -> ScenarioResult:
    count = int(magnitude or 0)
    if count <= 0:
        return ScenarioResult("add_birds", "Add birds", [], [], [], available=False,
                              note="Tell ARIA how many birds to simulate adding.")

    current_birds = f.total_birds
    projected_birds = current_birds + count
    changes = [ScenarioChange("Birds", str(current_birds), str(projected_birds), f"+{count}")]
    implications: list[str] = []
    assumptions = ["The added birds are the same type and age profile as your current flock."]

    # Feed: scale the recorded per-bird rate. Only meaningful with real history.
    if f.feed_history_days >= MIN_HISTORY_DAYS and current_birds > 0:
        recorded = min(f.feed_history_days, 7)
        daily = Decimal(str(f.feed_this_week_kg)) / Decimal(recorded)
        per_bird = daily / Decimal(current_birds)
        projected_daily = _q(per_bird * Decimal(projected_birds), "0.001")
        changes.append(ScenarioChange(
            "Feed per day", f"{_q(daily, '0.001')}kg", f"{projected_daily}kg",
            f"+{_q(projected_daily - daily, '0.001')}kg",
        ))
        assumptions.append(
            f"Feed scales linearly at the recorded {_q(per_bird, '0.0001')}kg per bird per day."
        )
        if f.feed_stock_kg is not None and projected_daily > 0:
            new_days = int((Decimal(str(f.feed_stock_kg)) / projected_daily)
                           .to_integral_value(rounding="ROUND_FLOOR"))
            old_days = int((Decimal(str(f.feed_stock_kg)) / daily)
                           .to_integral_value(rounding="ROUND_FLOOR")) if daily > 0 else None
            if old_days is not None:
                changes.append(ScenarioChange(
                    "Days of feed left", str(old_days), str(new_days), f"{new_days - old_days}",
                ))
                implications.append(
                    f"Your current feed stock would last {new_days} days instead of {old_days}."
                )
    else:
        implications.append(
            "Feed impact can't be projected — " + NOT_ENOUGH_DATA.lower()
        )

    # Housing.
    total_capacity = sum(h.get("capacity", 0) for h in f.houses)
    if total_capacity:
        changes.append(ScenarioChange(
            "Housing used", f"{current_birds}/{total_capacity}",
            f"{projected_birds}/{total_capacity}",
            f"{_pct(projected_birds, total_capacity)}% of capacity",
        ))
        if projected_birds > total_capacity:
            implications.append(
                f"This would exceed your recorded housing capacity by "
                f"{projected_birds - total_capacity} birds."
            )
    else:
        implications.append("Housing capacity isn't on record, so crowding can't be checked.")

    return ScenarioResult(
        scenario="add_birds",
        description=f"Add {count} birds to the farm",
        changes=changes, implications=implications, assumptions=assumptions,
    )


def _sim_mortality(f: FarmFacts, magnitude: float | None) -> ScenarioResult:
    pct = float(magnitude if magnitude is not None else 0)
    if pct == 0:
        return ScenarioResult("mortality_change", "Mortality change", [], [], [],
                              available=False, note="Tell ARIA the percentage change to simulate.")
    if f.total_birds <= 0:
        return ScenarioResult("mortality_change", "Mortality change", [], [], [],
                              available=False, note=NOT_ENOUGH_DATA)

    # A percentage-point change against the flock, expressed weekly.
    extra = round(f.total_birds * pct / 100)
    current = f.mortality_this_week
    projected = max(0, current + extra)
    changes = [
        ScenarioChange("Weekly mortality", str(current), str(projected),
                       f"{'+' if extra >= 0 else ''}{extra} birds"),
        ScenarioChange("Birds after a week", str(f.total_birds),
                       str(max(0, f.total_birds - projected)),
                       f"-{projected}"),
    ]
    implications = [
        f"At this rate you would lose about {projected} birds a week "
        f"({_pct(projected, f.total_birds)}% of the flock)."
    ]
    if projected / max(1, f.total_birds) * 100 >= 2:
        implications.append("That is above the 2% weekly line ARIA treats as critical.")
    return ScenarioResult(
        scenario="mortality_change",
        description=f"Mortality changes by {pct:+g}% of the flock per week",
        changes=changes, implications=implications,
        assumptions=["Applied against your current recorded bird count.",
                     "Flock size otherwise unchanged."],
    )


def _sim_feed_price(f: FarmFacts, magnitude: float | None) -> ScenarioResult:
    pct = float(magnitude if magnitude is not None else 0)
    if pct == 0:
        return ScenarioResult("feed_price_change", "Feed price change", [], [], [],
                              available=False, note="Tell ARIA the percentage change to simulate.")
    if f.feed_cost is None:
        return ScenarioResult(
            "feed_price_change", "Feed price change", [], [], [], available=False,
            note=f"{NOT_ENOUGH_DATA} No feed cost has been recorded in finance.",
        )

    current = Decimal(str(f.feed_cost))
    projected = _q(current * (Decimal(1) + Decimal(str(pct)) / Decimal(100)))
    delta = _q(projected - current)
    changes = [ScenarioChange("Feed cost (period)", f"KES {current}", f"KES {projected}",
                              f"{'+' if delta >= 0 else ''}KES {delta}")]
    implications: list[str] = []
    if f.gross_profit is not None:
        new_profit = _q(Decimal(str(f.gross_profit)) - delta)
        changes.append(ScenarioChange(
            "Gross profit", f"KES {f.gross_profit}", f"KES {new_profit}",
            f"{'+' if -delta >= 0 else ''}KES {_q(-delta)}",
        ))
        if new_profit < 0 <= Decimal(str(f.gross_profit)):
            implications.append("This change alone would push the farm into a loss.")
    else:
        implications.append("Profit impact can't be shown — no finance data recorded.")
    return ScenarioResult(
        scenario="feed_price_change",
        description=f"Feed price changes by {pct:+g}%",
        changes=changes, implications=implications,
        assumptions=["Feed volume stays the same.",
                     "Applied to the feed cost recorded for the current finance period."],
    )


def _sim_production(f: FarmFacts, magnitude: float | None) -> ScenarioResult:
    pct = float(magnitude if magnitude is not None else 0)
    if pct == 0:
        return ScenarioResult("production_change", "Production change", [], [], [],
                              available=False, note="Tell ARIA the percentage change to simulate.")
    if f.egg_history_days < MIN_HISTORY_DAYS:
        return ScenarioResult("production_change", "Production change", [], [], [],
                              available=False, note=NOT_ENOUGH_DATA)

    current = f.eggs_this_week
    projected = int(round(current * (1 + pct / 100)))
    changes = [ScenarioChange("Eggs per week", str(current), str(projected),
                              f"{projected - current:+d}")]
    implications = [
        f"Over 30 days that is about {int(round((projected - current) / 7 * 30)):+d} eggs "
        "against the current rate."
    ]
    return ScenarioResult(
        scenario="production_change",
        description=f"Egg production changes by {pct:+g}%",
        changes=changes, implications=implications,
        assumptions=["Applied to the last recorded week of collection.",
                     "Flock size and laying age otherwise unchanged."],
    )


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


# ── 4. Capacity planner ──────────────────────────────────────────────────────


def plan_capacity(f: FarmFacts) -> CapacityPlan:
    """
    Housing capacity against current occupancy.

    Thresholds are stated rather than hidden: above 95% of a house's recorded
    capacity is over-stocked, 80–95% is crowded, under 40% is under-used.
    """
    if not f.houses:
        return CapacityPlan(
            total_capacity=0, total_birds=f.total_birds, available_space=0,
            utilisation_pct=None, houses=[], recommendations=[],
            notes=[f"{NOT_ENOUGH_DATA} No houses are on record for this farm."],
        )

    houses: list[HouseCapacity] = []
    recommendations: list[str] = []
    notes: list[str] = []

    for h in f.houses:
        cap = int(h.get("capacity") or 0)
        birds = int(h.get("birds") or 0)
        if cap <= 0:
            houses.append(HouseCapacity(
                name=h.get("name", "House"), capacity=0, birds=birds,
                utilisation_pct=None, state="unknown",
                note="No capacity recorded for this house.",
            ))
            notes.append(f"{h.get('name', 'A house')} has no capacity on record.")
            continue

        util = round(birds / cap * 100, 1)
        if birds == 0:
            state, note = "empty", "Empty — available for a new flock."
        elif util > 95:
            state, note = "over", f"Over capacity at {util}% — crowding raises disease and heat stress."
            recommendations.append(
                f"{h.get('name')} is at {util}% of its recorded capacity. Reduce stocking or "
                "move birds before the next placement."
            )
        elif util >= 80:
            state, note = "crowded", f"{util}% full — close to capacity."
        elif util < 40:
            state, note = "under", f"Only {util}% used — spare space available."
            recommendations.append(
                f"{h.get('name')} is only {util}% used; there is room for more birds if you want to expand."
            )
        else:
            state, note = "healthy", f"{util}% used — comfortable."

        houses.append(HouseCapacity(name=h.get("name", "House"), capacity=cap,
                                    birds=birds, utilisation_pct=util, state=state, note=note))

    total_capacity = sum(x.capacity for x in houses)
    total_birds = f.total_birds
    available = max(0, total_capacity - total_birds)
    util = round(total_birds / total_capacity * 100, 1) if total_capacity else None

    if total_capacity and total_birds > total_capacity:
        recommendations.insert(0, (
            f"The farm is carrying {total_birds} birds against {total_capacity} of recorded "
            "capacity. Reducing density is the single cheapest health intervention available."
        ))

    return CapacityPlan(
        total_capacity=total_capacity, total_birds=total_birds,
        available_space=available, utilisation_pct=util, houses=houses,
        recommendations=recommendations, notes=notes,
    )


# ── 5. Budget planner ────────────────────────────────────────────────────────

_PERIOD_DAYS = {"weekly": 7, "monthly": 30, "cycle": None}


def plan_budget(f: FarmFacts, period: str = "monthly") -> Budget:
    """
    A budget built only from categories the farmer has actually spent on.

    Missing categories are named in `notes` rather than filled with a guess: a
    budget line for something never purchased is an invented number, and the
    farmer would plan around it.
    """
    label = {"weekly": "Next 7 days", "monthly": "Next 30 days",
             "cycle": "Rest of the production cycle"}.get(period, "Next 30 days")

    if not f.expense_by_category:
        return Budget(
            period=period, label=label, lines=[], total=Decimal("0"),
            method="", assumptions=[], available=False,
            notes=[f"{NOT_ENOUGH_DATA} No expenses have been recorded in the last "
                   f"{f.expense_window_days} days, so there is no basis for a budget."],
        )

    days = _PERIOD_DAYS.get(period)
    if period == "cycle":
        remaining = [c["days_remaining"] for c in f.cycles if c.get("days_remaining") is not None]
        days = max(remaining) if remaining else None
        if days is None:
            return Budget(
                period=period, label=label, lines=[], total=Decimal("0"),
                method="", assumptions=[], available=False,
                notes=["No production cycle length on record, so a cycle budget can't be built."],
            )

    window = f.expense_window_days or 30
    lines: list[BudgetLine] = []
    for name, amount in sorted(f.expense_by_category.items(), key=lambda kv: -kv[1]):
        daily = Decimal(str(amount)) / Decimal(window)
        lines.append(BudgetLine(
            category=name,
            amount=_q(daily * Decimal(days)),
            basis=f"KES {amount} recorded over {window} days",
        ))

    total = _q(sum((line.amount for line in lines), Decimal("0")))
    return Budget(
        period=period, label=label, lines=lines, total=total,
        method=(f"Each category's recorded spend over the last {window} days ÷ {window} "
                f"× {days} days."),
        assumptions=[
            "Spending continues at the recent recorded rate.",
            "One-off purchases in the recorded window are treated as if they recur.",
        ],
        notes=[
            "Only categories with recorded spend appear. Anything you have not yet "
            "recorded an expense for is absent rather than estimated.",
        ],
    )


# ── 6. Cash flow projection ──────────────────────────────────────────────────


def project_cashflow(f: FarmFacts, days: int = 30) -> CashFlow:
    """
    Expected money out and in over the horizon, from recorded rates only.

    Income projection requires recorded revenue; where it is absent the outlook
    is `unknown` rather than a guess dressed as a forecast.
    """
    assumptions: list[str] = []
    notes: list[str] = []
    window = f.expense_window_days or 30

    expenses = None
    if f.expense_by_category:
        total_recorded = sum(f.expense_by_category.values(), Decimal("0"))
        expenses = _q(total_recorded / Decimal(window) * Decimal(days))
        assumptions.append(f"Expenses continue at the rate recorded over the last {window} days.")
    else:
        notes.append("No recorded expenses, so outgoings can't be projected.")

    income = None
    if f.revenue is not None and Decimal(str(f.revenue)) > 0:
        income = _q(Decimal(str(f.revenue)) / Decimal(window) * Decimal(days))
        assumptions.append(f"Income continues at the rate recorded over the last {window} days.")
    else:
        notes.append("No recorded revenue, so income can't be projected.")

    net = _q(income - expenses) if (income is not None and expenses is not None) else None
    outlook = "unknown" if net is None else ("surplus" if net >= 0 else "shortfall")

    upcoming: list[str] = []
    due = f.vaccinations_overdue + f.vaccinations_due_today + f.vaccinations_due_week
    if due:
        upcoming.append(f"{due} vaccination(s) due or overdue — vaccine and labour cost.")
    for item in f.inventory_out[:3]:
        upcoming.append(f"Restock {item} (out of stock).")
    for item in f.inventory_low[:3]:
        upcoming.append(f"Reorder {item} (at or below reorder level).")
    if f.feed_stock_kg is not None and f.feed_history_days >= MIN_HISTORY_DAYS:
        feed = forecast_feed(f)
        if feed.days_remaining is not None and feed.days_remaining <= days:
            upcoming.append(
                f"Feed runs out in about {feed.days_remaining} days — a purchase falls inside this window."
            )

    if outlook == "shortfall":
        notes.append("Projected outgoings exceed projected income over this horizon.")

    return CashFlow(
        period_days=days, expected_expenses=expenses, expected_income=income,
        net=net, upcoming=upcoming, outlook=outlook,
        assumptions=assumptions, notes=notes,
    )


# ── 7. Operational calendar ──────────────────────────────────────────────────


def build_calendar(f: FarmFacts, days: int = 30) -> list[CalendarEntry]:
    """
    Scheduled work for the horizon, derived from recorded schedules and state.

    Only entries with a real basis: a vaccination that is actually due, a
    restock for an item actually low, an inspection cadence tied to the flock's
    recorded age. Nothing is invented to fill the calendar.
    """
    out: list[CalendarEntry] = []
    today = f.as_of

    # Vaccinations from the recorded schedule.
    if f.next_vaccination:
        due_in = f.next_vaccination.get("days_until_due")
        when = today + timedelta(days=max(0, int(due_in))) if isinstance(due_in, int) else today
        out.append(CalendarEntry(
            on=when.isoformat(), kind="vaccination",
            title=f"Vaccinate: {f.next_vaccination.get('vaccine', 'scheduled dose')}",
            why="From your recorded vaccination schedule.",
        ))
    if f.vaccinations_overdue:
        out.append(CalendarEntry(
            on=today.isoformat(), kind="vaccination",
            title=f"{f.vaccinations_overdue} overdue vaccination(s)",
            why="Already past due on your schedule.",
        ))

    # Restocking.
    for item in f.inventory_out[:5]:
        out.append(CalendarEntry(on=today.isoformat(), kind="inventory",
                                 title=f"Reorder {item}", why="Out of stock."))
    for item in f.inventory_low[:5]:
        out.append(CalendarEntry(on=(today + timedelta(days=2)).isoformat(), kind="inventory",
                                 title=f"Reorder {item}", why="At or below reorder level."))

    # Feed purchase, when a depletion date falls in the window.
    if f.feed_stock_kg is not None and f.feed_history_days >= MIN_HISTORY_DAYS:
        feed = forecast_feed(f)
        if feed.days_remaining is not None and feed.days_remaining <= days:
            # Order a couple of days before it actually runs out.
            order_on = today + timedelta(days=max(0, feed.days_remaining - 2))
            out.append(CalendarEntry(
                on=order_on.isoformat(), kind="inventory", title="Buy feed",
                why=f"Projected to run out on {feed.depletion_date} at the recorded rate.",
            ))

    # Routine husbandry, anchored to recorded flock age.
    for stage in f.flock_stages:
        if stage.age_days is None:
            continue
        if stage.is_brooding:
            out.append(CalendarEntry(
                on=(today + timedelta(days=1)).isoformat(), kind="cleaning",
                title=f"Clean brooder — {stage.name}",
                why=f"{stage.name} is {stage.age_days} days old and still brooding.",
            ))
    if f.days_since_weighin is None or f.days_since_weighin >= 7:
        out.append(CalendarEntry(
            on=(today + timedelta(days=1)).isoformat(), kind="inspection",
            title="Weigh a sample of birds",
            why=("No weigh-in on record." if f.days_since_weighin is None
                 else f"Last weigh-in {f.days_since_weighin} days ago."),
        ))
    out.append(CalendarEntry(
        on=(today + timedelta(days=7)).isoformat(), kind="cleaning",
        title="Disinfect drinkers and feeders",
        why="Weekly hygiene routine — prevents the build-up that drives coccidiosis.",
    ))
    if f.days_since_any_log is None or f.days_since_any_log > 0:
        out.append(CalendarEntry(
            on=today.isoformat(), kind="recording",
            title="Record today's feed, eggs and mortality",
            why="Today's log hasn't been entered.",
        ))

    horizon = today + timedelta(days=days)
    return sorted(
        (e for e in out if date.fromisoformat(e.on) <= horizon),
        key=lambda e: (e.on, e.kind),
    )


# ── 9. Planning report ───────────────────────────────────────────────────────


@dataclass
class PlanningReport:
    period: str
    label: str
    feed: FeedForecast
    production: list[Forecast]
    capacity: CapacityPlan
    budget: Budget
    cashflow: CashFlow
    calendar: list[CalendarEntry]
    risks: list[str]
    priorities: list[str]
    outstanding_reminders: list[str]


def build_planning_report(f: FarmFacts, period: str = "30d") -> PlanningReport:
    """An export-ready plan for the horizon, assembled from the pure engines."""
    days = {"7d": 7, "30d": 30, "cycle": None}.get(period, 30)
    if period == "cycle":
        remaining = [c["days_remaining"] for c in f.cycles if c.get("days_remaining") is not None]
        days = max(remaining) if remaining else 30
    label = {"7d": "Next 7 days", "30d": "Next 30 days",
             "cycle": "Rest of the production cycle"}.get(period, "Next 30 days")

    feed = forecast_feed(f)
    budget_period = "weekly" if period == "7d" else ("cycle" if period == "cycle" else "monthly")

    risks: list[str] = []
    if feed.days_remaining is not None and feed.days_remaining <= days:
        risks.append(f"Feed is projected to run out in {feed.days_remaining} days.")
    if f.vaccinations_overdue:
        risks.append(f"{f.vaccinations_overdue} vaccination(s) already overdue.")
    if f.inventory_out:
        risks.append(f"{len(f.inventory_out)} inventory item(s) out of stock.")
    capacity = plan_capacity(f)
    if capacity.utilisation_pct is not None and capacity.utilisation_pct > 95:
        risks.append(f"Housing is at {capacity.utilisation_pct}% of recorded capacity.")
    cash = project_cashflow(f, days=days)
    if cash.outlook == "shortfall":
        risks.append("Projected outgoings exceed projected income over this period.")
    if not risks:
        risks.append("No planning risks identified from recorded data.")

    return PlanningReport(
        period=period, label=label, feed=feed,
        production=forecast_production(f, horizons=(days,)),
        capacity=capacity,
        budget=plan_budget(f, budget_period),
        cashflow=cash,
        calendar=build_calendar(f, days=days),
        risks=risks,
        priorities=[e.title for e in build_calendar(f, days=days)[:5]],
        outstanding_reminders=[
            ("overdue — " if r.get("overdue") else "") + str(r.get("title"))
            for r in f.upcoming_reminders[:5]
        ],
    )
