"""
Greena — Small Ruminant Forecast Engine (Modules 18/19, Milestone 9)

A PURE, deterministic short-range forecast engine shared by goats and sheep. It
projects herd size, offspring/feed/revenue flow and capacity requirements from
recorded run-rates. No I/O, no mutation.

Every projection is explicitly ``forecast``-labelled and carries its method,
assumptions, confidence and limitations — it is never presented as a recorded
fact, and without an input window the result is honestly ``unknown`` (Goat Doc 6
§16). This is the module short-range forecaster; the long-range strategic Growth
Planner is separate (M10, reuses the platform planner).
"""

from __future__ import annotations

from decimal import Decimal

FORECAST = "forecast"
UNKNOWN = "unknown"


def _f(v) -> float:
    return float(v) if isinstance(v, Decimal) else float(v or 0)


def _forecast(value, *, method: str, assumptions: list[str], confidence: str,
              limitations: list[str]) -> dict:
    return {"label": FORECAST, "value": value, "method": method, "assumptions": assumptions,
            "confidence": confidence, "limitations": limitations}


def _unknown(reason: str) -> dict:
    return {"label": UNKNOWN, "value": None, "detail": reason}


def project_stock(current_head: int | None, monthly_births: float | None,
                  monthly_deaths: float | None, monthly_sales: float | None, months: int) -> dict:
    """Project herd/flock size ``months`` ahead from recorded monthly run-rates.
    Net change per month = births − deaths − sales. Never a promise."""
    if current_head is None or months <= 0:
        return _unknown("No current head count or projection window.")
    b, d, s = _f(monthly_births), _f(monthly_deaths), _f(monthly_sales)
    net = b - d - s
    projected = max(int(round(current_head + net * months)), 0)
    return _forecast(
        projected,
        method="current_head + (monthly_births − monthly_deaths − monthly_sales) × months.",
        assumptions=[f"Recorded run-rates hold for {months} month(s).",
                     f"births={b}/mo, deaths={d}/mo, sales={s}/mo."],
        confidence="low" if (b == 0 and d == 0 and s == 0) else "medium",
        limitations=["Run-rates are averages of recorded history; seasonality and shocks are not modelled."],
    )


def project_flow(monthly_rate: float | None, months: int, *, metric: str) -> dict:
    """Project a cumulative flow (offspring / feed kg / revenue) over ``months``
    from a recorded monthly rate."""
    if monthly_rate is None or months <= 0:
        return _unknown(f"No recorded monthly {metric} rate or projection window.")
    total = round(_f(monthly_rate) * months, 3)
    return _forecast(
        total, method=f"monthly_{metric} × months.",
        assumptions=[f"Recorded {metric} rate of {_f(monthly_rate)}/month holds for {months} month(s)."],
        confidence="medium" if monthly_rate else "low",
        limitations=["A linear projection of recorded history; not a guarantee."],
    )


def capacity_requirement(projected_head: int | None, per_head: float | None, *, resource: str) -> dict:
    """Deterministic resource requirement for a projected head count (e.g. pen
    space m², daily feed kg). ``per_head`` is a recorded/standard rate."""
    if projected_head is None or per_head is None:
        return _unknown(f"Projected head or per-head {resource} rate not available.")
    return _forecast(
        round(projected_head * _f(per_head), 2),
        method=f"projected_head × per_head_{resource}.",
        assumptions=[f"{_f(per_head)} {resource} per head.", f"Projected head = {projected_head}."],
        confidence="medium", limitations=["Depends on the accuracy of the head-count projection."],
    )
