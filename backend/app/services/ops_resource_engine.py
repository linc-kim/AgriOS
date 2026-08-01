"""
Greena — Operations Planner: Resource Allocation Engine (deterministic, pure).

Coordinates equipment, vehicles, feed, medicines, tools, buildings, protective
equipment and consumables across scheduled work, and raises shortage alerts
(spec Doc 4 §11). Pure and deterministic; a resource with no recorded stock level
yields ``unknown`` rather than an assumed quantity.

Demand dict::  {"resource":"feed","quantity":50,"date":"2026-01-02","routine_id":"r1"}
Inventory::    {"feed": 200, "tractor": 1, ...}
"""

from __future__ import annotations

from collections import defaultdict

from app.services import ops_common as oc


def allocate(demands: list[dict], inventory: dict, per_day: bool = False) -> dict:
    """Sum demand per resource (optionally per day) and compare with recorded stock.

    Returns ``{"allocations": [...], "shortages": [...], "summary": {...}}``.
    When ``per_day`` is True, reusable resources (e.g. a tractor) are checked
    against same-day concurrent demand; otherwise total consumption is checked.
    """
    totals: dict = defaultdict(float)
    for d in demands:
        res = str(d.get("resource"))
        qty = float(d.get("quantity") or 0)
        key = (res, str(oc.parse_date(d.get("date")))) if per_day else res
        totals[key] += qty

    allocations, shortages = [], []
    for key in sorted(totals, key=lambda k: (k if isinstance(k, str) else k)):
        needed = totals[key]
        res = key[0] if isinstance(key, tuple) else key
        day = key[1] if isinstance(key, tuple) else None
        if res not in inventory:
            shortages.append({
                "resource": res, "date": day,
                "status": oc.unknown(f"No recorded stock level for '{res}'."),
            })
            continue
        available = float(inventory[res])
        record = {
            "resource": res, "date": day,
            "needed": oc.recorded(round(needed, 4), "Summed demand."),
            "available": oc.recorded(available, "Recorded stock."),
        }
        if needed > available:
            record["shortfall"] = oc.calculated(round(needed - available, 4), "needed − available.")
            record["alert"] = oc.recommendation(
                f"Procure {round(needed - available, 4)} more '{res}' or reduce demand",
                "Recorded stock cannot meet planned demand.",
                evidence={"needed": needed, "available": available}, confidence="high")
            shortages.append(record)
        else:
            record["headroom"] = oc.calculated(round(available - needed, 4), "available − needed.")
            allocations.append(record)

    return {
        "allocations": allocations,
        "shortages": shortages,
        "summary": {
            "resources": oc.calculated(len({k[0] if isinstance(k, tuple) else k for k in totals}),
                                       "Distinct resources considered."),
            "shortages": oc.calculated(len(shortages), "Resources short or unknown.")
            if shortages else oc.calculated(0, "No shortages."),
        },
    }
