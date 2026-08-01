"""
Greena — Operations Planner: Workload Balancing Engine (deterministic, pure).

Distributes work fairly across workers/teams/shifts, flags overload and
imbalance, and recommends moves from the most-loaded to the least-loaded
(spec Doc 4 §15). Advisory only. Pure and deterministic.

Assignment dict::  {"worker_id":"w1","minutes":120}
Capacities::       {"w1": 480, "w2": 480}
"""

from __future__ import annotations

from collections import defaultdict

from app.services import ops_common as oc


def balance(assignments: list[dict], capacities: dict | None = None) -> dict:
    """Compute per-worker load and utilisation, flag overload and imbalance, and
    recommend a rebalancing move when the spread is material.

    Returns ``{"load": {...}, "utilisation": {...}, "overloaded": [...],
    "fairness": {...}, "recommendation": {...}|None}``.
    """
    capacities = capacities or {}
    load: dict[str, float] = defaultdict(float)
    for a in assignments:
        load[str(a.get("worker_id"))] += float(a.get("minutes") or 0)
    if not load:
        return {"load": {}, "utilisation": {}, "overloaded": [],
                "fairness": {"spread": oc.unknown("No assignments recorded.")},
                "recommendation": None}

    util = {}
    overloaded = []
    for wid, mins in load.items():
        cap = float(capacities.get(wid) or 0)
        if cap > 0:
            u = mins / cap
            util[wid] = oc.calculated(round(u, 3), "load ÷ capacity.")
            if u > 1.0:
                overloaded.append({"worker_id": wid,
                                   "over_by_minutes": oc.calculated(round(mins - cap, 1),
                                                                    "Assigned minutes above capacity.")})
        else:
            util[wid] = oc.unknown(f"No recorded capacity for '{wid}'.")

    mins_list = sorted(load.values())
    spread = mins_list[-1] - mins_list[0]
    mean = sum(mins_list) / len(mins_list)
    # Coefficient of variation as a scale-free fairness measure.
    var = sum((m - mean) ** 2 for m in mins_list) / len(mins_list)
    cov = (var ** 0.5) / mean if mean else 0.0

    busiest = max(load, key=lambda k: (load[k], k))
    idlest = min(load, key=lambda k: (load[k], k))
    rec = None
    if spread > 0 and busiest != idlest and cov > 0.15:
        move = round(spread / 2, 1)
        rec = oc.recommendation(
            f"Move ~{move} min of work from '{busiest}' to '{idlest}'",
            "Workload is uneven; shifting halves the gap.",
            evidence={"busiest_minutes": load[busiest], "idlest_minutes": load[idlest],
                      "coefficient_of_variation": round(cov, 3)},
            confidence="medium",
            limitations="Assumes the moved work matches the receiving worker's skills and shift.")

    return {
        "load": {wid: oc.calculated(round(m, 1), "Assigned minutes.") for wid, m in sorted(load.items())},
        "utilisation": dict(sorted(util.items())),
        "overloaded": sorted(overloaded, key=lambda r: r["worker_id"]),
        "fairness": {
            "spread_minutes": oc.calculated(round(spread, 1), "Busiest − idlest."),
            "coefficient_of_variation": oc.calculated(round(cov, 3), "Std-dev ÷ mean (0 = perfectly even)."),
        },
        "recommendation": rec,
    }
