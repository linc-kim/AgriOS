"""
Greena — Operations Planner: Conflict Resolution Engine (deterministic, pure).

Detects worker, equipment, time, facility and duplicate-routine conflicts, plus
resource shortages, among scheduled work — and *recommends* resolutions without
mutating anything (spec Doc 4 §9: advisory unless explicitly configured).

Scheduled item dict::  {"routine_id","name","date","start","end",
                        "worker_id","equipment":[...],"facility"}
``start``/``end`` are minutes-from-midnight (ints) on the given ``date``.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from app.services import ops_common as oc


def _overlap(a: dict, b: dict) -> bool:
    if oc.parse_date(a.get("date")) != oc.parse_date(b.get("date")):
        return False
    a0, a1 = a.get("start"), a.get("end")
    b0, b1 = b.get("start"), b.get("end")
    if None in (a0, a1, b0, b1):
        return False
    return a0 < b1 and b0 < a1


def detect(items: list[dict]) -> list[dict]:
    """Return a deterministic, severity-ranked list of conflicts. Each conflict
    carries evidence and a recommended resolution (never auto-applied)."""
    conflicts: list[dict] = []

    # Duplicate routines: same name on the same day/time.
    seen: dict[tuple, list[dict]] = defaultdict(list)
    for it in items:
        key = (str(it.get("name") or "").strip().lower(),
               str(oc.parse_date(it.get("date"))), it.get("start"))
        seen[key].append(it)
    for key, group in seen.items():
        if key[0] and len(group) > 1:
            conflicts.append(_conflict(
                "duplicate_routine", "medium", group,
                f"'{group[0].get('name')}' is scheduled {len(group)} times at the same slot.",
                "Merge the duplicates or stagger their times."))

    # Pairwise overlaps for shared worker / equipment / facility.
    for a, b in combinations(items, 2):
        if not _overlap(a, b):
            continue
        if a.get("worker_id") and a.get("worker_id") == b.get("worker_id"):
            conflicts.append(_conflict(
                "worker_conflict", "high", [a, b],
                f"Worker {a.get('worker_id')} is double-booked.",
                "Reassign one task to another worker or shift its time."))
        shared_eq = set(a.get("equipment") or []) & set(b.get("equipment") or [])
        if shared_eq:
            conflicts.append(_conflict(
                "equipment_conflict", "high", [a, b],
                f"Equipment {sorted(shared_eq)} needed by two overlapping tasks.",
                "Stagger the tasks or allocate alternative equipment."))
        if a.get("facility") and a.get("facility") == b.get("facility"):
            conflicts.append(_conflict(
                "facility_conflict", "medium", [a, b],
                f"Facility '{a.get('facility')}' is used by two overlapping tasks.",
                "Move one task to a different facility or time window."))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(conflicts, key=lambda c: (severity_rank.get(c["severity"], 3), c["type"]))


def resource_shortages(demands: list[dict], inventory: dict) -> list[dict]:
    """Flag resources whose total demand exceeds recorded availability.

    ``demands``: [{"resource","quantity"}]; ``inventory``: {resource: available}.
    A resource absent from ``inventory`` yields an *unknown* (never assumed zero
    or infinite).
    """
    totals: dict[str, float] = defaultdict(float)
    for d in demands:
        totals[str(d.get("resource"))] += float(d.get("quantity") or 0)
    out = []
    for resource, needed in sorted(totals.items()):
        if resource not in inventory:
            out.append({"resource": resource,
                        "status": oc.unknown(f"No recorded stock level for '{resource}'.")})
            continue
        available = float(inventory[resource])
        if needed > available:
            out.append({
                "resource": resource,
                "needed": oc.recorded(needed, "Summed demand."),
                "available": oc.recorded(available, "Recorded stock."),
                "shortfall": oc.calculated(round(needed - available, 4), "needed − available."),
                "resolution": oc.recommendation(
                    "Procure or reduce demand", "Shortfall detected before execution.",
                    evidence={"needed": needed, "available": available}),
            })
    return out


def _conflict(ctype: str, severity: str, group: list[dict], reasoning: str,
              resolution: str) -> dict:
    return {
        "type": ctype,
        "severity": severity,
        "items": [{"routine_id": g.get("routine_id"), "name": g.get("name"),
                   "date": str(oc.parse_date(g.get("date")))} for g in group],
        "resolution": oc.recommendation(
            resolution, reasoning,
            evidence={"count": len(group)}, confidence="high"),
    }
