"""
Greena — Operations Planner: Capacity Planning Engine (deterministic, pure).

Evaluates labour, equipment, infrastructure and time capacity against demand,
identifies the binding bottleneck, and projects when a growth factor would
exceed capacity — feeding the Growth Planner (spec Doc 4 §14). Pure and
deterministic; utilisation is ``calculated`` and the growth projection is
explicitly ``forecast``.

Demand/capacity dicts keyed by dimension, e.g.::
    demand   = {"labor_hours": 40, "equipment_units": 3, "time_hours": 50}
    capacity = {"labor_hours": 48, "equipment_units": 4, "time_hours": 56}
"""

from __future__ import annotations

from app.services import ops_common as oc


def analyze(demand: dict, capacity: dict, growth_factor: float | None = None) -> dict:
    """Return per-dimension utilisation, the bottleneck, and an optional
    growth projection.

    ``growth_factor`` (e.g. 1.5 for +50 %) scales demand to test headroom for an
    expansion goal. The result is a forecast, never a promise.
    """
    dimensions = {}
    bottleneck = None
    worst_util = -1.0
    for dim in sorted(set(demand) | set(capacity)):
        need = demand.get(dim)
        cap = capacity.get(dim)
        if need is None or cap is None:
            dimensions[dim] = {"utilisation": oc.unknown(
                f"Missing {'demand' if need is None else 'capacity'} for '{dim}'.")}
            continue
        need, cap = float(need), float(cap)
        if cap <= 0:
            dimensions[dim] = {"utilisation": oc.unknown(f"No recorded capacity for '{dim}'.")}
            continue
        util = need / cap
        dimensions[dim] = {
            "demand": oc.recorded(need, "Recorded/estimated demand."),
            "capacity": oc.recorded(cap, "Recorded capacity."),
            "utilisation": oc.calculated(round(util, 3), "demand ÷ capacity."),
            "headroom": oc.calculated(round(cap - need, 3), "capacity − demand."),
            "status": oc.calculated(
                "over_capacity" if util > 1.0 else "tight" if util > 0.85 else "ok",
                ">1 over capacity; >0.85 tight."),
        }
        if util > worst_util:
            worst_util, bottleneck = util, dim

    result = {
        "dimensions": dimensions,
        "bottleneck": (oc.calculated(bottleneck, f"Highest utilisation ({round(worst_util, 3)}).")
                       if bottleneck else oc.unknown("No comparable dimensions.")),
    }

    if growth_factor and bottleneck and worst_util >= 0:
        projected = worst_util * float(growth_factor)
        result["growth_projection"] = {
            "growth_factor": oc.recorded(float(growth_factor), "Applied to current demand."),
            "projected_bottleneck_utilisation": oc.forecast(
                round(projected, 3),
                "Current bottleneck utilisation × growth factor."),
            "verdict": oc.forecast(
                "exceeds_capacity" if projected > 1.0 else "within_capacity",
                "Whether the bottleneck holds at the target scale.",
                limitations="Assumes demand scales linearly and capacity is unchanged."),
        }
    return result
