"""
Greena — Small Ruminant Lactation Engine (Modules 18/19, Milestone 6, Goat dairy)

A PURE, deterministic engine: lactation and milk-yield math over recorded milk
records (litres). No I/O, no mutation. Serves any dairy small ruminant (goats
primarily; dairy sheep too). Every figure is honesty-labelled; a projection is a
forecast, a recommendation is advisory, and missing data is ``unknown`` — never
fabricated.

Milk records are supplied as ``[{"recorded_on": date, "quantity_liters": number,
"session": str}, ...]``. Daily yield sums the sessions per day.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
RECOMMENDATION = "recommendation"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Standard lactation reference points (days in milk). Goat lactation ≈ 284–305 d.
STANDARD_LACTATION_DAYS = 305
_EARLY_MAX = 70    # early lactation: rising to peak
_MID_MAX = 200     # mid lactation: gradual decline
_DRY_OFF_TARGET = 245  # typical dry-off ~2 months before next kidding


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else float(v or 0)


def _daily_yields(milk_records: list[dict]) -> list[tuple[date, float]]:
    """Sum sessions into one yield per recorded day, chronologically."""
    by_day: dict[date, float] = defaultdict(float)
    for r in milk_records:
        d = r.get("recorded_on")
        if isinstance(d, date):
            by_day[d] += _f(r.get("quantity_liters"))
    return sorted(by_day.items())


def lactation_stage(days_in_milk: int | None) -> dict:
    """Deterministic lactation stage from days in milk (recorded interval)."""
    if days_in_milk is None or days_in_milk < 0:
        return _lab(UNKNOWN, None, "No freshening date recorded.")
    if days_in_milk <= _EARLY_MAX:
        stage = "early"
    elif days_in_milk <= _MID_MAX:
        stage = "mid"
    else:
        stage = "late"
    return _lab(CALCULATED, stage, f"Days in milk = {days_in_milk} (early ≤{_EARLY_MAX}, mid ≤{_MID_MAX}, else late).")


def lactation_metrics(freshening_date: date | None, milk_records: list[dict], today: date,
                      dry_off_date: date | None = None) -> dict:
    """Deterministic lactation performance for one cycle."""
    daily = _daily_yields(milk_records)
    end = dry_off_date or today
    dim = (end - freshening_date).days if freshening_date else None

    if not daily:
        return {
            "days_in_milk": (_lab(CALCULATED, dim, "end − freshening.") if dim is not None
                             else _lab(UNKNOWN, None, "No freshening date recorded.")),
            "stage": lactation_stage(dim),
            "records": _lab(RECORDED, 0, "No milk recorded yet."),
            "total_yield_l": _lab(UNKNOWN, None, "No milk recorded."),
            "avg_daily_yield_l": _lab(UNKNOWN, None, "No milk recorded."),
            "peak_daily_yield_l": _lab(UNKNOWN, None, "No milk recorded."),
            "peak_date": _lab(UNKNOWN, None, "No milk recorded."),
            "projected_305_day_l": _lab(UNKNOWN, None, "No milk recorded."),
        }

    total = round(sum(v for _, v in daily), 3)
    peak_date, peak = max(daily, key=lambda kv: kv[1])
    recorded_days = len(daily)
    avg_daily = round(total / recorded_days, 3)

    # 305-day projection = average recorded daily × standard length (forecast).
    projected = round(avg_daily * STANDARD_LACTATION_DAYS, 1)

    return {
        "days_in_milk": (_lab(CALCULATED, dim, "end − freshening.") if dim is not None
                         else _lab(UNKNOWN, None, "No freshening date recorded.")),
        "stage": lactation_stage(dim),
        "records": _lab(RECORDED, recorded_days, "Distinct days with recorded milk."),
        "total_yield_l": _lab(RECORDED, total, "Σ recorded daily yields."),
        "avg_daily_yield_l": _lab(CALCULATED, avg_daily, "total ÷ recorded days."),
        "peak_daily_yield_l": _lab(RECORDED, round(peak, 3), "Highest recorded daily yield."),
        "peak_date": _lab(RECORDED, peak_date.isoformat()),
        "projected_305_day_l": _lab(FORECAST, projected,
                                    "avg recorded daily × 305 days (projection, not a promise)."),
    }


def dry_off_recommendation(days_in_milk: int | None, recent_avg_daily_l: float | None,
                           low_yield_threshold_l: float = 0.5) -> dict:
    """Advisory dry-off signal (Goat Doc 3 §12.4). Recommends dry-off when the doe
    is late in lactation OR recent yield has fallen below a low threshold. Advisory
    only — the farmer decides; never a directive, never a guarantee."""
    if days_in_milk is None:
        return _lab(UNKNOWN, None, "No freshening date recorded — cannot assess.")
    reasons: list[str] = []
    if days_in_milk >= _DRY_OFF_TARGET:
        reasons.append(f"Late lactation ({days_in_milk} days in milk ≥ {_DRY_OFF_TARGET}).")
    if recent_avg_daily_l is not None and recent_avg_daily_l < low_yield_threshold_l:
        reasons.append(f"Recent yield {recent_avg_daily_l} L/day is below {low_yield_threshold_l} L.")
    if reasons:
        return _lab(RECOMMENDATION, True, " ".join(reasons))
    return _lab(RECOMMENDATION, False, "No dry-off indicated by recorded data yet.")


def herd_milk_summary(records_by_animal: dict, today: date) -> dict:
    """Herd-level dairy roll-up: total litres and active-milker count from recorded
    facts. ``records_by_animal``: {animal_id: [milk_record dicts]}."""
    total = 0.0
    milkers = 0
    for _aid, recs in records_by_animal.items():
        daily = _daily_yields(recs)
        if daily:
            milkers += 1
            total += sum(v for _, v in daily)
    return {
        "active_milkers": _lab(RECORDED, milkers, "Animals with at least one recorded milk day."),
        "total_recorded_yield_l": _lab(RECORDED, round(total, 3), "Σ recorded daily yields across the herd."),
    }
