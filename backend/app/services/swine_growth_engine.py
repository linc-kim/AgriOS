"""
Greena — Swine Growth Engine (Module 20, Milestone 7)

A PURE, deterministic engine: growth math over immutable weight records (kilograms).
No I/O, no mutation. Every growth figure — average daily gain (ADG), total gain,
growth curve, feed conversion — is CALCULATED here from historical records and never
stored, so nothing goes stale. Market readiness is an explainable ASSESSMENT against
configurable targets (never a stored boolean). Missing inputs yield honest
``unknown``, never a fabricated number.

The shape is species-neutral (weights + configurable thresholds in, labelled facts
out), so it can back a shared livestock-growth engine for sheep / goats / dairy /
rabbits / poultry / fish where appropriate — thresholds stay configurable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _f(v) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, Decimal) else float(v)


def _sorted(weights: list[dict]) -> list[dict]:
    return sorted((w for w in weights if w.get("recorded_on") and w.get("weight_kg") is not None),
                  key=lambda w: w["recorded_on"])


def average_daily_gain(weights: list[dict]) -> dict:
    """ADG (kg/day) between the first and last recorded weights.

    ``weights``: {"recorded_on": date, "weight_kg": number}. Requires ≥2 weights on
    distinct dates; otherwise ``unknown``. A negative ADG (weight loss) is reported
    faithfully."""
    ws = _sorted(weights)
    if len(ws) < 2:
        return _lab(UNKNOWN, None, "At least two weights on distinct dates are required.")
    first, last = ws[0], ws[-1]
    days = (last["recorded_on"] - first["recorded_on"]).days
    if days <= 0:
        return _lab(UNKNOWN, None, "Weights span zero days.")
    gain = _f(last["weight_kg"]) - _f(first["weight_kg"])
    return _lab(CALCULATED, round(gain / days, 4), "(last − first weight) ÷ days between them.")


def total_gain_kg(weights: list[dict]) -> float | None:
    ws = _sorted(weights)
    if len(ws) < 2:
        return None
    return round(_f(ws[-1]["weight_kg"]) - _f(ws[0]["weight_kg"]), 3)


def growth_curve(weights: list[dict]) -> list[dict]:
    """The recorded weight trajectory (a historical fact, oldest first)."""
    return [{"recorded_on": w["recorded_on"].isoformat(), "weight_kg": _f(w["weight_kg"]),
             "age_days": w.get("age_days")} for w in _sorted(weights)]


def growth_analysis(weights: list[dict]) -> dict:
    ws = _sorted(weights)
    latest = ws[-1] if ws else None
    return {
        "measurements": _lab(RECORDED, len(ws)),
        "current_weight_kg": (_lab(RECORDED, _f(latest["weight_kg"]), "Latest recorded weight.")
                              if latest else _lab(UNKNOWN, None, "No weights recorded.")),
        "total_gain_kg": (_lab(CALCULATED, total_gain_kg(ws), "last − first weight.")
                          if len(ws) >= 2 else _lab(UNKNOWN, None, "Fewer than two weights.")),
        "average_daily_gain_kg": average_daily_gain(ws),
        "curve": growth_curve(ws),
    }


def market_readiness(*, latest_weight_kg: float | None, age_days: int | None, targets: dict,
                     adg_kg: float | None = None, active_withdrawal: bool = False,
                     health_ok: bool = True, approaching_fraction: float = 0.9) -> dict:
    """Explainable market-readiness assessment against configurable targets.

    Returns a ``status`` (ready | approaching | not_ready | withheld | unknown) plus
    ``reasons`` that explain the verdict from recorded facts. Never a stored boolean;
    ``withheld`` always wins when a meat-withdrawal period is still in effect.
    """
    target_w = targets.get("target_weight_kg")
    target_a = targets.get("target_age_days")
    reasons: list[str] = []

    if latest_weight_kg is None:
        return {"status": "unknown", "reasons": ["No weight recorded — cannot assess readiness."],
                "target_weight_kg": target_w, "target_age_days": target_a,
                "weight_pct_of_target": None, "days_to_target_weight": None,
                "target_source": {"weight": targets.get("weight_source"), "age": targets.get("age_source")}}

    weight_pct = round(latest_weight_kg / target_w * 100, 1) if target_w else None
    if weight_pct is not None:
        reasons.append(f"Weight {latest_weight_kg} kg is {weight_pct}% of the {target_w} kg target "
                       f"(target source: {targets.get('weight_source')}).")
    if age_days is not None and target_a:
        reasons.append(f"Age {age_days} d vs {target_a} d target.")

    # Estimate days to reach target weight from the current ADG (a forecast).
    days_to_target = None
    if adg_kg and adg_kg > 0 and target_w and latest_weight_kg < target_w:
        days_to_target = round((target_w - latest_weight_kg) / adg_kg)
        reasons.append(f"At the recorded ADG of {adg_kg} kg/day, ~{days_to_target} days to target (forecast).")

    if active_withdrawal:
        reasons.append("A medicine withdrawal period is still in effect — must not go to market yet.")
        status = "withheld"
    elif not health_ok:
        reasons.append("An open health concern (active disease case or isolation) is recorded.")
        status = "not_ready"
    elif target_w and latest_weight_kg >= target_w:
        reasons.append("Weight has reached the market target.")
        status = "ready"
    elif target_w and latest_weight_kg >= target_w * approaching_fraction:
        reasons.append("Weight is within reach of the market target.")
        status = "approaching"
    else:
        reasons.append("Weight is below the market target.")
        status = "not_ready"

    return {
        "status": status,
        "reasons": reasons,
        "target_weight_kg": target_w,
        "target_age_days": target_a,
        "weight_pct_of_target": weight_pct,
        "days_to_target_weight": days_to_target,
        "target_source": {"weight": targets.get("weight_source"), "age": targets.get("age_source")},
    }


def cohort_summary(members: list[dict], today: date | None = None) -> dict:
    """Aggregate growth across a cohort (pen / litter / group / breed / stage).

    ``members`` each {"latest_weight_kg": number|None, "adg_kg": number|None}. Reports
    the count, how many have a weight, and averages over those that do."""
    weighed = [m for m in members if m.get("latest_weight_kg") is not None]
    adgs = [m["adg_kg"] for m in members if m.get("adg_kg") is not None]
    return {
        "count": _lab(RECORDED, len(members)),
        "weighed_count": _lab(RECORDED, len(weighed)),
        "avg_weight_kg": (_lab(CALCULATED, round(sum(m["latest_weight_kg"] for m in weighed) / len(weighed), 3),
                               "mean latest weight over weighed members.")
                          if weighed else _lab(UNKNOWN, None, "No weights recorded.")),
        "avg_daily_gain_kg": (_lab(CALCULATED, round(sum(adgs) / len(adgs), 4), "mean ADG over members with ≥2 weights.")
                              if adgs else _lab(UNKNOWN, None, "No ADG computable.")),
    }
