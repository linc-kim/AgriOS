"""
Greena — BSF Feed Conversion Engine (Module 16, Part 3)

A PURE, deterministic engine (Spec Part 4 §7). Computes feed-conversion and
waste-conversion metrics from recorded feeding and biomass data: feed consumed,
biomass produced, Feed Conversion Ratio (FCR), organic waste processed,
conversion efficiency and feed utilisation. It also detects declining-efficiency
trends across a batch's history.

No I/O, no mutation. Every metric is honesty-labelled and degrades to ``unknown``
when its recorded inputs are missing — never fabricated (Spec Part 9 §17-19,
Part 13 §13 "All calculations shall be deterministic").

Convention: masses are kilograms. FCR = feed consumed ÷ biomass gained (lower is
better). Waste-conversion / bioconversion rate = biomass gained ÷ feed consumed
× 100 (the share of input mass converted to larval biomass).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def feed_conversion_ratio(feed_consumed_kg, biomass_gained_kg) -> dict:
    """FCR = feed consumed ÷ biomass gained. Lower is better."""
    feed = _dec(feed_consumed_kg)
    gain = _dec(biomass_gained_kg)
    if feed is None or gain is None or gain <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded feed consumed and positive biomass gain.")
    return _lbl(CALCULATED, float(round(feed / gain, 3)), "feed consumed ÷ biomass gained (lower is better).")


def bioconversion_rate_pct(feed_consumed_kg, biomass_gained_kg) -> dict:
    """Share of feed mass converted to larval biomass = gain ÷ feed × 100."""
    feed = _dec(feed_consumed_kg)
    gain = _dec(biomass_gained_kg)
    if feed is None or gain is None or feed <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded feed consumed (>0) and biomass gain.")
    return _lbl(CALCULATED, float(round((gain / feed) * Decimal(100), 2)),
                "biomass gained ÷ feed consumed.")


def waste_processed_kg(feed_consumed_kg) -> dict:
    """Organic waste diverted from landfill = feedstock consumed (recorded fact)."""
    feed = _dec(feed_consumed_kg)
    if feed is None:
        return _lbl(UNKNOWN, None, "No recorded feedstock consumption.")
    return _lbl(RECORDED, float(round(feed, 3)), "Total recorded feedstock consumed by the batch.")


def feed_utilisation_pct(feed_consumed_kg, feed_supplied_kg) -> dict:
    """How much of the supplied feed was actually consumed."""
    consumed = _dec(feed_consumed_kg)
    supplied = _dec(feed_supplied_kg)
    if consumed is None or supplied is None or supplied <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded feed consumed and supplied.")
    pct = (consumed / supplied) * Decimal(100)
    return _lbl(CALCULATED, float(round(min(pct, Decimal(100)), 2)), "feed consumed ÷ feed supplied.")


def conversion_summary(feed_consumed_kg, biomass_gained_kg, feed_supplied_kg=None) -> dict:
    """Compose the full conversion picture for a batch (Spec Part 4 §7)."""
    return {
        "feed_consumed_kg": waste_processed_kg(feed_consumed_kg),
        "biomass_gained_kg": _lbl(
            RECORDED if _dec(biomass_gained_kg) is not None else UNKNOWN,
            float(_dec(biomass_gained_kg)) if _dec(biomass_gained_kg) is not None else None,
            "Recorded biomass gain."),
        "feed_conversion_ratio": feed_conversion_ratio(feed_consumed_kg, biomass_gained_kg),
        "bioconversion_rate_pct": bioconversion_rate_pct(feed_consumed_kg, biomass_gained_kg),
        "feed_utilisation_pct": feed_utilisation_pct(feed_consumed_kg, feed_supplied_kg),
    }


def efficiency_trend(fcr_series: list[float | None]) -> dict:
    """Detect declining efficiency across ordered FCR snapshots (Spec Part 4 §7).

    A *rising* FCR means worsening efficiency (more feed per unit biomass). Needs
    at least two recorded points, else ``unknown`` — no trend is invented.
    """
    points = [p for p in fcr_series if p is not None]
    if len(points) < 2:
        return _lbl(UNKNOWN, None, "Need at least two recorded FCR values to assess a trend.")
    first, last = points[0], points[-1]
    if last > first:
        direction = "declining"
        detail = f"FCR rose {first} → {last}: efficiency is declining (more feed per unit biomass)."
    elif last < first:
        direction = "improving"
        detail = f"FCR fell {first} → {last}: efficiency is improving."
    else:
        direction = "stable"
        detail = f"FCR unchanged at {first}."
    return _lbl(CALCULATED, direction, detail)
