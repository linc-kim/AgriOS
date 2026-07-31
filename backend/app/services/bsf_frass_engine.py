"""
Greena — BSF Frass Engine (Module 16, Part 4)

A PURE, deterministic engine (Spec Part 4 §9). Computes frass yield, the
moisture-adjusted (dry) weight and frass-to-feed / frass-to-biomass ratios from
recorded data. No I/O, no mutation. Missing inputs → ``unknown`` (Spec Part 9
§17-19). Frass stays traceable to its originating batch at the service layer.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
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


def moisture_adjusted_dry_kg(weight_kg, moisture_pct) -> dict:
    """Dry weight = wet weight × (1 − moisture%). Absent moisture → unknown."""
    weight = _dec(weight_kg)
    moisture = _dec(moisture_pct)
    if weight is None:
        return _lbl(UNKNOWN, None, "No recorded frass weight.")
    if moisture is None:
        return _lbl(UNKNOWN, None, "No recorded moisture — cannot compute dry weight.")
    moisture = max(Decimal(0), min(moisture, Decimal(100)))
    dry = weight * (Decimal(1) - moisture / Decimal(100))
    return _lbl(CALCULATED, float(round(dry, 3)), "wet weight × (1 − moisture%).")


def frass_yield_pct(frass_kg, feed_consumed_kg) -> dict:
    """Frass yield relative to feed input = frass ÷ feed consumed × 100."""
    frass = _dec(frass_kg)
    feed = _dec(feed_consumed_kg)
    if frass is None or feed is None or feed <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded frass weight and feed consumed.")
    return _lbl(CALCULATED, float(round((frass / feed) * Decimal(100), 2)),
                "frass weight ÷ feed consumed.")


def frass_per_biomass_pct(frass_kg, biomass_gained_kg) -> dict:
    """Frass produced relative to biomass gained."""
    frass = _dec(frass_kg)
    gain = _dec(biomass_gained_kg)
    if frass is None or gain is None or gain <= 0:
        return _lbl(UNKNOWN, None, "Requires recorded frass weight and biomass gain.")
    return _lbl(CALCULATED, float(round((frass / gain) * Decimal(100), 2)),
                "frass weight ÷ biomass gained.")


def frass_summary(frass_kg, moisture_pct, feed_consumed_kg=None, biomass_gained_kg=None) -> dict:
    """Compose the frass picture for a collection (Spec Part 4 §9)."""
    return {
        "weight_kg": _lbl(
            RECORDED if _dec(frass_kg) is not None else UNKNOWN,
            float(_dec(frass_kg)) if _dec(frass_kg) is not None else None,
            "Recorded frass weight."),
        "dry_weight_kg": moisture_adjusted_dry_kg(frass_kg, moisture_pct),
        "frass_yield_pct": frass_yield_pct(frass_kg, feed_consumed_kg),
        "frass_per_biomass_pct": frass_per_biomass_pct(frass_kg, biomass_gained_kg),
    }
