"""
Greena — Small Ruminant Wool Engine (Modules 18/19, Milestone 7, Sheep wool)

A PURE, deterministic engine: fleece and wool-clip math over recorded fleece
records (kilograms, microns, centimetres). No I/O, no mutation. Every figure is
honesty-labelled; clean weight and value are calculations, the micron quality band
is a deterministic classification of a recorded measurement, and missing data is
``unknown`` — never fabricated. Wool sale *revenue* is a recorded fact handled by
the finance milestone, not invented here.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Micron quality bands (Australian-style wool classing thresholds).
_SUPERFINE_MAX = 18.5
_FINE_MAX = 20.0
_MEDIUM_MAX = 23.0
_STRONG_MAX = 32.0


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _f(v) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, Decimal) else float(v)


def micron_grade(micron: float | None) -> dict:
    """Deterministic quality band from a recorded micron measurement. Without a
    recorded micron the grade is ``unknown`` — never guessed."""
    m = _f(micron)
    if m is None:
        return _lab(UNKNOWN, None, "No micron measured.")
    if m <= _SUPERFINE_MAX:
        band = "superfine"
    elif m <= _FINE_MAX:
        band = "fine"
    elif m <= _MEDIUM_MAX:
        band = "medium"
    elif m <= _STRONG_MAX:
        band = "strong"
    else:
        band = "carpet"
    return _lab(CALCULATED, band, f"Micron {m} classified against standard wool bands.")


def clean_weight_kg(greasy_kg: float | None, clean_yield_pct: float | None) -> dict:
    """Clean fleece weight = greasy × yield%. Without a recorded yield the clean
    weight is ``unknown`` (a default yield is never assumed)."""
    g = _f(greasy_kg)
    y = _f(clean_yield_pct)
    if g is None:
        return _lab(UNKNOWN, None, "No greasy weight recorded.")
    if y is None:
        return _lab(UNKNOWN, None, "No clean yield recorded — clean weight not assumed.")
    return _lab(CALCULATED, round(g * y / 100.0, 3), "greasy_weight × clean_yield% ÷ 100.")


def wool_value(clean_or_greasy_kg: float | None, price_per_kg: float | None) -> dict:
    """Wool value = weight × price/kg. ``price_per_kg`` is a caller-supplied market
    figure; without it the value is ``unknown``, never fabricated."""
    w = _f(clean_or_greasy_kg)
    p = _f(price_per_kg)
    if w is None or p is None:
        return _lab(UNKNOWN, None, "Weight and price per kg are both required.")
    return _lab(CALCULATED, round(w * p, 2), "weight × price_per_kg.")


def fleece_analysis(fleece: dict, price_per_kg: float | None = None) -> dict:
    """Deterministic analysis for a single fleece record."""
    greasy = _f(fleece.get("greasy_weight_kg"))
    yield_pct = _f(fleece.get("clean_yield_pct"))
    clean = clean_weight_kg(greasy, yield_pct)
    value_basis = clean["value"] if clean["value"] is not None else greasy
    return {
        "greasy_weight_kg": (_lab(RECORDED, round(greasy, 3)) if greasy is not None
                             else _lab(UNKNOWN, None, "No greasy weight recorded.")),
        "clean_weight_kg": clean,
        "staple_length_cm": (_lab(RECORDED, _f(fleece.get("staple_length_cm")))
                             if fleece.get("staple_length_cm") is not None
                             else _lab(UNKNOWN, None, "No staple length recorded.")),
        "micron": (_lab(RECORDED, _f(fleece.get("micron"))) if fleece.get("micron") is not None
                   else _lab(UNKNOWN, None, "No micron recorded.")),
        "micron_grade": micron_grade(fleece.get("micron")),
        "estimated_value": wool_value(value_basis, price_per_kg),
    }


def clip_summary(fleeces: list[dict], price_per_kg: float | None = None) -> dict:
    """Flock wool-clip roll-up from recorded fleece facts."""
    n = len(fleeces)
    greasy_total = round(sum(_f(f.get("greasy_weight_kg")) or 0 for f in fleeces), 3)
    clean_vals = [clean_weight_kg(f.get("greasy_weight_kg"), f.get("clean_yield_pct"))["value"] for f in fleeces]
    clean_known = [c for c in clean_vals if c is not None]
    clean_total = round(sum(clean_known), 3) if clean_known else None
    microns = [_f(f.get("micron")) for f in fleeces if f.get("micron") is not None]
    staples = [_f(f.get("staple_length_cm")) for f in fleeces if f.get("staple_length_cm") is not None]
    grade_counts = Counter(f.get("grade") or "unknown" for f in fleeces)

    value_basis = clean_total if clean_total is not None else (greasy_total if n else None)
    return {
        "fleeces": _lab(RECORDED, n),
        "total_greasy_kg": _lab(RECORDED, greasy_total, "Σ recorded greasy fleece weights."),
        "total_clean_kg": (_lab(CALCULATED, clean_total, "Σ clean weights (fleeces with a recorded yield).")
                           if clean_total is not None else _lab(UNKNOWN, None, "No clean yields recorded.")),
        "avg_micron": (_lab(CALCULATED, round(sum(microns) / len(microns), 1), "Mean of recorded microns.")
                       if microns else _lab(UNKNOWN, None, "No micron measurements recorded.")),
        "avg_staple_length_cm": (_lab(CALCULATED, round(sum(staples) / len(staples), 1), "Mean of recorded staples.")
                                 if staples else _lab(UNKNOWN, None, "No staple lengths recorded.")),
        "grade_distribution": [{"grade": g, "count": _lab(RECORDED, c)} for g, c in grade_counts.most_common()],
        "estimated_clip_value": wool_value(value_basis, price_per_kg),
    }
