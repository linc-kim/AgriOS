"""
Greena — Rabbit Forecast Engine (Module 17, Milestone 7)

A PURE, deterministic engine (Spec Part 4 §4, Part 7 §16). Produces model
projections of future herd size, kit production, feed requirement, revenue and
housing capacity from recorded farm history. No I/O, no mutation.

Every projection is labelled ``forecast`` and carries ``method`` / ``assumptions``
/ ``confidence`` / ``limitations`` — the same honesty structure as the platform
forecast engines (a reused convention, not a parallel system). **A forecast is
never a confirmed value.** With no history window a projection degrades to
``unknown`` rather than inventing a number (Spec Part 7 §16 — "forecasts shall
clearly state assumptions").
"""

from __future__ import annotations

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _confidence(observations: int) -> str:
    return "low" if observations < 5 else ("medium" if observations < 20 else "high")


def _unknown(reason: str) -> dict:
    return {"forecast": _lbl(UNKNOWN, None, reason),
            "method": "Linear extrapolation of recorded history.",
            "assumptions": [], "confidence": UNKNOWN, "limitations": [reason]}


def project_flow(amount_in_window, window_days: int, horizon_days: int, *,
                 observations: int, quantity: str, unit: str) -> dict:
    """Project a cumulative FLOW quantity (kits, feed, revenue) over a horizon.

    rate = amount ÷ window; projection = rate × horizon. Labelled ``forecast``.
    """
    if amount_in_window is None or window_days <= 0:
        return _unknown(f"No recorded {quantity} history to project from.")
    rate = float(amount_in_window) / window_days
    projected = round(rate * horizon_days, 3)
    return {
        "daily_rate": _lbl(CALCULATED, round(rate, 4), f"recorded {quantity} ÷ {window_days} day window."),
        "forecast": _lbl(FORECAST, projected,
                         f"Projected {quantity} over the next {horizon_days} days ({unit})."),
        "method": "Linear extrapolation of the recent daily rate.",
        "assumptions": [f"Recent {quantity} rate continues unchanged.",
                        "No operational or biological shocks in the horizon."],
        "confidence": _confidence(observations),
        "limitations": [f"Based on {observations} recorded observation(s) over {window_days} days.",
                        "A projection, not a promise — biology and demand vary."],
        "horizon_days": horizon_days,
    }


def project_stock(current, net_change_in_window, window_days: int, horizon_days: int, *,
                  observations: int, quantity: str, unit: str, floor_zero: bool = True) -> dict:
    """Project a STOCK quantity (e.g. herd headcount) = current + net_rate × horizon."""
    if current is None or net_change_in_window is None or window_days <= 0:
        return _unknown(f"Insufficient recorded {quantity} history to project from.")
    net_daily = float(net_change_in_window) / window_days
    projected = float(current) + net_daily * horizon_days
    if floor_zero:
        projected = max(0.0, projected)
    return {
        "current": _lbl(RECORDED, float(current), f"Current recorded {quantity} ({unit})."),
        "net_daily_change": _lbl(CALCULATED, round(net_daily, 4), f"net {quantity} change ÷ window days."),
        "forecast": _lbl(FORECAST, round(projected, 2),
                         f"Projected {quantity} in {horizon_days} days ({unit})."),
        "method": "Linear extrapolation of recent net change.",
        "assumptions": [f"Recent net {quantity} trend continues.", "No shocks in the horizon."],
        "confidence": _confidence(observations),
        "limitations": [f"Based on {observations} recorded observation(s) over {window_days} days.",
                        "A projection, not a promise."],
        "horizon_days": horizon_days,
    }


def capacity_requirement(projected_headcount, current_capacity, *, horizon_days: int) -> dict:
    """Housing capacity forecast: does the *projected* herd fit the recorded
    capacity? The requirement derives from a forecast, so the shortfall is itself
    a ``forecast``; capacity is a recorded fact. Unknown when either input is
    missing — no fabricated capacity (Spec Part 7 §8)."""
    if projected_headcount is None:
        return {"status": _lbl(UNKNOWN, None, "No herd forecast available."),
                "current_capacity": _lbl(UNKNOWN, None, ""), "shortfall": _lbl(UNKNOWN, None, "")}
    if current_capacity is None:
        return {
            "status": _lbl(UNKNOWN, None, "No recorded cage capacity to compare against."),
            "projected_headcount": _lbl(FORECAST, round(float(projected_headcount), 2), ""),
            "current_capacity": _lbl(UNKNOWN, None, "No capacity recorded."),
            "shortfall": _lbl(UNKNOWN, None, "Capacity unknown."),
        }
    shortfall = float(projected_headcount) - float(current_capacity)
    return {
        "projected_headcount": _lbl(FORECAST, round(float(projected_headcount), 2),
                                    f"Projected herd in {horizon_days} days."),
        "current_capacity": _lbl(RECORDED, int(current_capacity), "Σ recorded cage capacity."),
        "shortfall": _lbl(FORECAST, round(shortfall, 2),
                          "projected headcount − current capacity (positive = expansion needed)."),
        "status": _lbl(FORECAST, "expansion_needed" if shortfall > 0 else "within_capacity",
                       "Whether the recorded capacity holds the projected herd."),
        "method": "Herd forecast compared against recorded cage capacity.",
        "limitations": ["Depends on the herd forecast's own assumptions and confidence."],
        "horizon_days": horizon_days,
    }
