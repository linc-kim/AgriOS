"""
Greena — Operations Planner: Dependency Engine (deterministic, pure).

Orders tasks so prerequisites run first, detects dependency cycles, and reports
which tasks are blocked by unmet prerequisites (spec Doc 4 §8). Kahn's algorithm
over a stable node order → identical output for identical input.

A task is a plain dict::  {"id": "feed", "name": "Feed animals", "depends_on": ["prep"]}
"""

from __future__ import annotations

from app.services import ops_common as oc


def _index(tasks: list[dict]) -> dict[str, dict]:
    return {str(t["id"]): t for t in tasks if t.get("id") is not None}


def topological_order(tasks: list[dict]) -> dict:
    """Return a deterministic execution order plus any cycles.

    ``{"ok": bool, "order": [ids], "cycles": [[ids]], "unmet_refs": [...]}``.
    ``order`` is empty when a cycle is present (no valid total order exists).
    Ties are broken by the task's original position then id, so the order is
    stable and reproducible.
    """
    nodes = _index(tasks)
    position = {tid: i for i, tid in enumerate(nodes)}
    # Edges prereq -> task, restricted to known nodes; note dangling references.
    indeg = {tid: 0 for tid in nodes}
    adj: dict[str, list[str]] = {tid: [] for tid in nodes}
    unmet_refs: list[dict] = []
    for tid, t in nodes.items():
        for dep in t.get("depends_on") or []:
            dep = str(dep)
            if dep not in nodes:
                unmet_refs.append({"task": tid, "missing_prerequisite": dep})
                continue
            adj[dep].append(tid)
            indeg[tid] += 1

    ready = sorted((tid for tid, d in indeg.items() if d == 0),
                   key=lambda x: (position[x], x))
    order: list[str] = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        newly = []
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                newly.append(nxt)
        if newly:
            ready = sorted(ready + newly, key=lambda x: (position[x], x))

    if len(order) == len(nodes):
        return {"ok": True, "order": order, "cycles": [], "unmet_refs": unmet_refs}
    cycle_nodes = sorted((tid for tid in nodes if tid not in set(order)),
                         key=lambda x: (position[x], x))
    return {"ok": False, "order": [], "cycles": [cycle_nodes], "unmet_refs": unmet_refs}


def blocked_tasks(tasks: list[dict], completed: set[str] | None = None) -> list[dict]:
    """Tasks whose prerequisites are not all in ``completed``, with the specific
    unmet prerequisites named (so the UI can show *why* a task is blocked)."""
    completed = {str(c) for c in (completed or set())}
    nodes = _index(tasks)
    out = []
    for tid, t in nodes.items():
        if tid in completed:
            continue
        unmet = [str(d) for d in (t.get("depends_on") or []) if str(d) not in completed]
        if unmet:
            out.append({
                "id": tid,
                "name": t.get("name"),
                "blocked_by": unmet,
                "status": oc.calculated("blocked", f"Waiting on {len(unmet)} prerequisite(s)."),
            })
    return sorted(out, key=lambda r: r["id"])


def ready_tasks(tasks: list[dict], completed: set[str] | None = None) -> list[str]:
    """Ids whose prerequisites are all satisfied and which are not yet done."""
    completed = {str(c) for c in (completed or set())}
    nodes = _index(tasks)
    ready = [
        tid for tid, t in nodes.items()
        if tid not in completed
        and all(str(d) in completed for d in (t.get("depends_on") or []))
    ]
    return sorted(ready)
