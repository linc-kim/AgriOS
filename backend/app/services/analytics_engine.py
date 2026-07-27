"""
Greena — Aviculture Analytics Engine (Module 15, Part 8)

A PURE, deterministic engine for collection analytics and forecasting (Doc 09,
Doc 14 §2-3). It composes recorded facts into KPIs and a transparent population
forecast. Every figure is honesty-labelled; a forecast always states its method,
assumptions, confidence and limitations, and is never presented as a promise
(Doc 09 §5, Doc 15 §15). Nothing is invented — with insufficient data the forecast
is reported as unknown.
"""

from __future__ import annotations

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def collection_composition(birds: list[dict]) -> dict:
    """Recorded-fact breakdowns of the collection by species / status / sex /
    lifecycle stage. ``birds``: each {"species_name","status","sex","lifecycle_stage"}."""
    def tally(key: str) -> dict:
        out: dict[str, int] = {}
        for b in birds:
            k = b.get(key) or "unknown"
            out[k] = out.get(k, 0) + 1
        return out

    return {
        "total": _lbl(RECORDED, len(birds), "Birds recorded (all statuses)."),
        "by_species": tally("species_name"),
        "by_status": tally("status"),
        "by_sex": tally("sex"),
        "by_lifecycle_stage": tally("lifecycle_stage"),
    }


def population_forecast(
    *,
    current_active: int,
    births_in_window: int,
    deaths_in_window: int,
    window_days: int,
    horizon_days: int = 90,
) -> dict:
    """Deterministic linear population forecast from recorded net change.

    net_daily = (births − deaths) / window_days ; forecast = current + net_daily ×
    horizon. Honesty-labelled with method/assumptions/confidence/limitations. With
    no window it degrades to unknown rather than guessing.
    """
    if window_days <= 0:
        return {
            "current": _lbl(RECORDED, current_active),
            "forecast": _lbl(UNKNOWN, None, "No time window to measure change over."),
        }

    net_daily = (births_in_window - deaths_in_window) / window_days
    projected = round(current_active + net_daily * horizon_days)
    projected = max(0, projected)  # population cannot go negative
    events = births_in_window + deaths_in_window
    confidence = "low" if events < 5 else ("medium" if events < 20 else "high")

    return {
        "current": _lbl(RECORDED, current_active, "Active birds now."),
        "births_in_window": _lbl(RECORDED, births_in_window),
        "deaths_in_window": _lbl(RECORDED, deaths_in_window),
        "net_daily_change": _lbl(CALCULATED, round(net_daily, 4), "(births − deaths) ÷ window days."),
        "forecast": _lbl(FORECAST, projected, f"Projected active birds in {horizon_days} days."),
        "method": "Linear extrapolation of recent net change.",
        "assumptions": [
            "Recent birth/death rate continues unchanged.",
            "No sales, purchases, transfers or disease shocks in the horizon.",
        ],
        "confidence": confidence,
        "limitations": [
            f"Based on {events} recorded event(s) over {window_days} days.",
            "Not a promise — biology and operations vary.",
        ],
        "horizon_days": horizon_days,
    }
