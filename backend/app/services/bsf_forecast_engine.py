"""
Greena — BSF Forecast Engine (Module 16, Part 6)

A PURE, deterministic engine (Spec Part 4 §11, Part 7 §13). Produces model
projections of future biomass, harvest, feed requirement and revenue from
recorded farm history. No I/O, no mutation.

Every projection is labelled ``forecast`` and carries ``method`` / ``assumptions``
/ ``confidence`` / ``limitations`` — the same honesty structure as the platform
``analytics_engine.population_forecast`` (reused convention, not a parallel
system). **A forecast is never a confirmed value.** With no history window a
projection degrades to ``unknown`` rather than inventing a number (Spec Part 4
§11 "forecasts shall never be treated as recorded facts").
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
    return {"forecast": _lbl(UNKNOWN, None, reason), "method": "Linear extrapolation of recorded history.",
            "assumptions": [], "confidence": UNKNOWN, "limitations": [reason]}


def project_flow(amount_in_window, window_days: int, horizon_days: int, *,
                 observations: int, quantity: str, unit: str) -> dict:
    """Project a cumulative FLOW quantity (harvest, feed, revenue) over a horizon.

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
    """Project a STOCK quantity (e.g. standing biomass) = current + net_rate × horizon."""
    if current is None or net_change_in_window is None or window_days <= 0:
        return _unknown(f"Insufficient recorded {quantity} history to project from.")
    net_daily = float(net_change_in_window) / window_days
    projected = float(current) + net_daily * horizon_days
    if floor_zero:
        projected = max(0.0, projected)
    return {
        "current": _lbl(RECORDED, float(current), f"Current recorded {quantity} ({unit})."),
        "net_daily_change": _lbl(CALCULATED, round(net_daily, 4), f"net {quantity} change ÷ window days."),
        "forecast": _lbl(FORECAST, round(projected, 3),
                         f"Projected {quantity} in {horizon_days} days ({unit})."),
        "method": "Linear extrapolation of recent net change.",
        "assumptions": [f"Recent net {quantity} trend continues.", "No shocks in the horizon."],
        "confidence": _confidence(observations),
        "limitations": [f"Based on {observations} recorded observation(s) over {window_days} days.",
                        "A projection, not a promise."],
        "horizon_days": horizon_days,
    }
