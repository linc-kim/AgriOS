"""
Greena — Rabbit Growth Engine (Module 17, Milestone 4)

A PURE, deterministic engine (GMIS §1.3, §5): growth math over recorded weight
measurements. No I/O, no mutation. Every figure is honesty-labelled (Spec Part 9
§17); missing inputs yield ``unknown`` and the concept-not-applicable case yields
``unavailable`` — a rate is never fabricated (Spec Part 4 §8: "Missing data shall
never be fabricated").

Weights are supplied as ``[{"recorded_on": date, "weight_g": number}, ...]``.
Expected growth (for deviation) comes from a breed ``growth_curve`` — a list of
``{"age_days": int, "weight_g": number}`` — linearly interpolated; outside its
range the expectation is honestly ``unknown``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
ESTIMATED = "estimated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _f(v) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, Decimal) else float(v)


def _sorted(weights: list[dict]) -> list[dict]:
    return sorted((w for w in weights if w.get("recorded_on") and w.get("weight_g") is not None),
                  key=lambda w: w["recorded_on"])


# ── Average daily gain ──────────────────────────────────────────────────────────

def average_daily_gain(weights: list[dict]) -> dict:
    """ADG (g/day) across the recorded span. Needs ≥2 measurements on distinct
    dates; otherwise ``unknown`` (never guessed)."""
    ws = _sorted(weights)
    if len(ws) < 2:
        return _lab(UNKNOWN, None, "At least two weight records on different dates are required.")
    first, last = ws[0], ws[-1]
    days = (last["recorded_on"] - first["recorded_on"]).days
    if days <= 0:
        return _lab(UNKNOWN, None, "All weights recorded on the same date.")
    gain = _f(last["weight_g"]) - _f(first["weight_g"])
    return _lab(CALCULATED, round(gain / days, 2), "(last − first weight) ÷ days between them.")


# ── Growth series ───────────────────────────────────────────────────────────────

def growth_series(weights: list[dict], dob: date | None = None) -> list[dict]:
    """Chronological growth points with age, gain and ADG from the previous point.
    All values are recorded/calculated — nothing is extrapolated."""
    ws = _sorted(weights)
    points: list[dict] = []
    prev = None
    for w in ws:
        weight = _f(w["weight_g"])
        age = (w["recorded_on"] - dob).days if dob else None
        point = {
            "recorded_on": w["recorded_on"].isoformat(),
            "weight_g": weight,
            "age_days": age,
            "gain_from_prev_g": None,
            "adg_from_prev": None,
        }
        if prev is not None:
            days = (w["recorded_on"] - prev["recorded_on"]).days
            gain = weight - _f(prev["weight_g"])
            point["gain_from_prev_g"] = round(gain, 2)
            point["adg_from_prev"] = round(gain / days, 2) if days > 0 else None
        points.append(point)
        prev = w
    return points


# ── Expected weight (breed growth curve) ────────────────────────────────────────

def expected_weight(age_days: int | None, growth_curve: list[dict] | None) -> dict:
    """Linear-interpolated expected weight at ``age_days`` from a breed growth
    curve. Outside the curve's range, or without a curve, the result is
    ``unknown`` — the engine never extrapolates a fabricated target."""
    if age_days is None or not growth_curve:
        return _lab(UNKNOWN, None, "No age or breed growth curve available.")
    pts = sorted(
        ({"age": int(p["age_days"]), "w": _f(p["weight_g"])} for p in growth_curve
         if p.get("age_days") is not None and p.get("weight_g") is not None),
        key=lambda p: p["age"],
    )
    if not pts:
        return _lab(UNKNOWN, None, "Breed growth curve has no usable points.")
    if age_days < pts[0]["age"] or age_days > pts[-1]["age"]:
        return _lab(UNKNOWN, None, "Age is outside the breed growth curve's recorded range.")
    for i in range(1, len(pts)):
        lo, hi = pts[i - 1], pts[i]
        if lo["age"] <= age_days <= hi["age"]:
            if hi["age"] == lo["age"]:
                return _lab(ESTIMATED, round(lo["w"], 1), "Breed growth curve point.")
            frac = (age_days - lo["age"]) / (hi["age"] - lo["age"])
            val = lo["w"] + frac * (hi["w"] - lo["w"])
            return _lab(ESTIMATED, round(val, 1), "Linear interpolation of the breed growth curve.")
    return _lab(UNKNOWN, None, "Age is outside the breed growth curve's recorded range.")


# ── Weight analysis (Spec Part 4 §8) ────────────────────────────────────────────

def weight_analysis(weights: list[dict], dob: date | None = None,
                    growth_curve: list[dict] | None = None) -> dict:
    """Deterministic growth analysis for a single rabbit."""
    ws = _sorted(weights)
    if not ws:
        return {
            "measurements": _lab(RECORDED, 0, "No weights recorded."),
            "latest_weight_g": _lab(UNKNOWN, None, "No weights recorded."),
            "total_gain_g": _lab(UNKNOWN, None, "No weights recorded."),
            "average_daily_gain": _lab(UNKNOWN, None, "No weights recorded."),
            "expected_weight_g": _lab(UNKNOWN, None, "No weights recorded."),
            "deviation_g": _lab(UNKNOWN, None, "No weights recorded."),
        }
    latest = ws[-1]
    latest_w = _f(latest["weight_g"])
    total_gain = latest_w - _f(ws[0]["weight_g"]) if len(ws) >= 2 else None
    age = (latest["recorded_on"] - dob).days if dob else None
    exp = expected_weight(age, growth_curve)
    deviation = (
        _lab(CALCULATED, round(latest_w - exp["value"], 1), "latest − expected weight.")
        if exp["value"] is not None else _lab(UNKNOWN, None, exp["detail"])
    )
    return {
        "measurements": _lab(RECORDED, len(ws)),
        "latest_weight_g": _lab(RECORDED, round(latest_w, 2)),
        "latest_recorded_on": _lab(RECORDED, latest["recorded_on"].isoformat()),
        "age_days": (_lab(CALCULATED, age, "latest date − DOB.") if age is not None
                     else _lab(UNKNOWN, None, "DOB not recorded.")),
        "total_gain_g": (_lab(CALCULATED, round(total_gain, 2), "latest − first weight.")
                         if total_gain is not None else _lab(UNKNOWN, None, "Only one weight recorded.")),
        "average_daily_gain": average_daily_gain(weights),
        "expected_weight_g": exp,
        "deviation_g": deviation,
    }


# ── Growth percentile among peers ───────────────────────────────────────────────

def growth_percentile(value: float | None, population: list[float]) -> dict:
    """Percentile rank of ``value`` within a peer ``population`` (both recorded).
    Empty population → ``unknown``."""
    pop = [_f(v) for v in population if v is not None]
    if value is None or not pop:
        return _lab(UNKNOWN, None, "No peer population to rank against.")
    below = sum(1 for v in pop if v < value)
    pct = round(below / len(pop) * 100, 1)
    return _lab(CALCULATED, pct, f"Share of {len(pop)} peers lighter than this rabbit.")
