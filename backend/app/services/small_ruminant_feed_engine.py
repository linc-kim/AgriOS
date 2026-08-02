"""
Greena — Small Ruminant Feed Efficiency Engine (Modules 18/19, Milestone 4)

A PURE, deterministic engine shared by goats and sheep: feed-consumption and
conversion math over recorded feeding + weight-gain data (kilograms throughout).
No I/O, no mutation. Feed conversion is only meaningful where both feed and a
positive weight gain exist over the same window — otherwise it is honestly
``unavailable``, never a fabricated ratio.

Feed records are supplied as ``[{"quantity_kg": number, "cost": number|None}, ...]``.
Feed stock and purchase costs live in the platform Inventory module; this engine
only aggregates the domain feeding log.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else float(v or 0)


def feed_conversion(feed_kg: float | None, weight_gain_kg: float | None) -> dict:
    """FCR = feed consumed ÷ weight gained. Requires a positive weight gain;
    otherwise ``unavailable`` (only where sufficient data exists)."""
    if feed_kg is None or weight_gain_kg is None:
        return _lab(UNKNOWN, None, "Feed and weight-gain data are both required.")
    if weight_gain_kg <= 0:
        return _lab(UNAVAILABLE, None, "No positive weight gain recorded over the window.")
    return _lab(CALCULATED, round(feed_kg / weight_gain_kg, 2), "feed_kg ÷ weight_gain_kg.")


def feed_summary(feed_records: list[dict], weight_gain_kg: float | None = None) -> dict:
    """Aggregate a feeding log into deterministic facts, and FCR where a positive
    weight gain (kg) is supplied. ``None`` → FCR unknown rather than fabricated."""
    events = len(feed_records)
    total_kg = round(sum(_f(r.get("quantity_kg")) for r in feed_records), 3)
    costed = [r for r in feed_records if r.get("cost") is not None]
    total_cost = round(sum(_f(r.get("cost")) for r in costed), 2) if costed else None

    return {
        "feeding_events": _lab(RECORDED, events),
        "total_feed_kg": _lab(RECORDED, total_kg, "Σ recorded feeding quantities."),
        "total_cost": (
            _lab(RECORDED, total_cost, "Σ recorded feed cost allocations (already expensed at purchase).")
            if total_cost is not None else _lab(UNKNOWN, None, "No feed costs recorded.")
        ),
        "cost_per_kg_feed": (
            _lab(CALCULATED, round(total_cost / total_kg, 2), "total_cost ÷ total_feed_kg.")
            if (total_cost is not None and total_kg > 0) else _lab(UNKNOWN, None, "Insufficient cost/quantity data.")
        ),
        "feed_conversion_ratio": feed_conversion(total_kg if events else None, weight_gain_kg),
    }
