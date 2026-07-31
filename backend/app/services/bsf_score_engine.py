"""
Greena — BSF Score Engine (Module 16, Part 6)

A PURE, deterministic engine for the executive-dashboard composite scores
(Spec Part 7 §19). Each score is a bounded 0–100 function of recorded/calculated
ratios, labelled ``calculated`` and citing its formula. A score whose inputs are
missing is ``unknown`` — never a filler number. The growth score is
``unavailable`` until the Growth Planner supplies a goal (not faked).
"""

from __future__ import annotations

CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def production_score(survival_rate_pct: float | None, capacity_utilisation_pct: float | None) -> dict:
    """Survival is the primary driver; extreme capacity pressure lightly penalises."""
    if survival_rate_pct is None:
        return _lbl(UNKNOWN, None, "Requires a recorded survival rate.")
    score = survival_rate_pct
    detail = "Survival rate as the base production score."
    if capacity_utilisation_pct is not None and capacity_utilisation_pct >= 95:
        score -= 10
        detail += " Penalised for ≥95% capacity pressure."
    return _lbl(CALCULATED, _clamp(score), detail)


def financial_score(gross_margin_pct: float | None) -> dict:
    """Maps gross margin to 0–100 (margin already a percentage, clamped)."""
    if gross_margin_pct is None:
        return _lbl(UNKNOWN, None, "Requires a calculated gross margin.")
    return _lbl(CALCULATED, _clamp(gross_margin_pct), "Gross margin, clamped to 0–100.")


def sustainability_score(waste_conversion_efficiency_pct: float | None) -> dict:
    if waste_conversion_efficiency_pct is None:
        return _lbl(UNKNOWN, None, "Requires a calculated waste-conversion efficiency.")
    return _lbl(CALCULATED, _clamp(waste_conversion_efficiency_pct),
                "Waste-conversion efficiency, clamped to 0–100.")


def health_score(mortality_rate_pct: float | None) -> dict:
    """100 minus cumulative mortality — lower mortality, higher score."""
    if mortality_rate_pct is None:
        return _lbl(UNKNOWN, None, "Requires a calculated mortality rate.")
    return _lbl(CALCULATED, _clamp(100.0 - mortality_rate_pct), "100 − cumulative mortality rate.")


def business_health_score(component_scores: list[dict]) -> dict:
    """Mean of the available calculated component scores. Unknown if none available."""
    values = [s["value"] for s in component_scores if s.get("label") == CALCULATED and s.get("value") is not None]
    if not values:
        return _lbl(UNKNOWN, None, "No component scores available yet.")
    return _lbl(CALCULATED, round(sum(values) / len(values), 1),
                f"Mean of {len(values)} available component score(s).")


def growth_score(primary_goal_progress_pct: float | None = None) -> dict:
    """Progress toward the primary growth goal (0–100). ``unavailable`` when no
    active growth plan/goal supplies a recorded progress value — never faked."""
    if primary_goal_progress_pct is None:
        return _lbl(UNAVAILABLE, None, "No active growth plan with a recorded-actual goal.")
    return _lbl(CALCULATED, _clamp(primary_goal_progress_pct),
                "Progress toward the primary growth goal (Growth Planner).")
