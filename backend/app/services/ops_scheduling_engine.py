"""
Greena — Operations Planner: Scheduling Engine (deterministic, pure).

Distributes routine occurrences across the available working time of each day,
respecting priority and dependency order, and reports what does not fit (spec
Doc 4 §6). Deterministic greedy packer: within a day, higher-priority and
dependency-ready work is placed first; identical input → identical schedule.

Occurrence dicts::  {"date": date, "routine_id": "r1", "name": "...",
                     "duration": 30, "priority": "high", "depends_on": []}
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.services import ops_common as oc
from app.services import ops_dependency_engine as deps


def distribute(occurrences: list[dict], daily_minutes: int = 480,
               day_start_minute: int = 6 * 60) -> dict:
    """Pack occurrences into each day up to ``daily_minutes`` of working time.

    Returns ``{"scheduled": [...], "unscheduled": [...], "summary": {...}}``.
    Each scheduled item gains ``start_minute``/``end_minute`` (minutes from
    midnight). Unscheduled items carry a labelled reason (day capacity exceeded).
    """
    by_day: dict[date, list[dict]] = defaultdict(list)
    for occ in occurrences:
        d = oc.parse_date(occ.get("date"))
        if d is not None:
            by_day[d].append(occ)

    scheduled: list[dict] = []
    unscheduled: list[dict] = []
    for d in sorted(by_day):
        items = by_day[d]
        # Dependency-ready order first, then priority desc, then stable name/id.
        order = deps.topological_order(
            [{"id": o.get("routine_id"), "name": o.get("name"),
              "depends_on": o.get("depends_on") or []} for o in items])
        rank = {tid: i for i, tid in enumerate(order["order"])} if order["ok"] else {}
        items_sorted = sorted(
            items,
            key=lambda o: (
                rank.get(str(o.get("routine_id")), 10_000),
                -oc.priority_rank(o.get("priority", "normal")),
                str(o.get("name") or ""), str(o.get("routine_id") or ""),
            ),
        )
        cursor = day_start_minute
        used = 0
        for o in items_sorted:
            dur = max(0, int(o.get("duration") or 0))
            if used + dur > daily_minutes and dur > 0:
                unscheduled.append({
                    **_slim(o, d),
                    "reason": oc.unavailable(
                        f"Day capacity of {daily_minutes} min exceeded; {dur} min did not fit."),
                })
                continue
            scheduled.append({
                **_slim(o, d),
                "start_minute": cursor,
                "end_minute": cursor + dur,
                "duration": dur,
            })
            cursor += dur
            used += dur

    total = len(scheduled) + len(unscheduled)
    return {
        "scheduled": scheduled,
        "unscheduled": unscheduled,
        "summary": {
            "total_occurrences": oc.calculated(total, "Occurrences considered."),
            "scheduled": oc.calculated(len(scheduled), "Fitted into available time."),
            "unscheduled": oc.calculated(len(unscheduled), "Did not fit — needs more time or fewer tasks.")
            if unscheduled else oc.calculated(0, "Everything fitted."),
        },
    }


def _slim(o: dict, d: date) -> dict:
    return {
        "date": d.isoformat(),
        "routine_id": o.get("routine_id"),
        "name": o.get("name"),
        "priority": o.get("priority", "normal"),
    }
