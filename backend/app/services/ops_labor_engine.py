"""
Greena — Operations Planner: Labor Allocation Engine (deterministic, pure).

Assigns tasks to workers using skills, certifications, availability, current
workload, performance and location (spec Doc 4 §10). Deterministic greedy:
eligible workers are ranked by lowest current load, then highest performance,
then id — so the same inputs always yield the same assignment. Advisory:
supervisors may override (the engine never persists anything).

Task dict::   {"id","name","required_skills":[...],"duration":30,
              "shift":"morning","location":"barn-1","priority":"high"}
Worker dict:: {"id","skills":[...],"certifications":[...],"available_shifts":[...],
              "load":0,"performance":0.9,"location":"barn-1"}
"""

from __future__ import annotations

from app.services import ops_common as oc


def _eligible(task: dict, worker: dict) -> tuple[bool, str]:
    need_skills = set(task.get("required_skills") or [])
    have_skills = set(worker.get("skills") or [])
    if not need_skills <= have_skills:
        return False, f"missing skills {sorted(need_skills - have_skills)}"
    need_certs = set(task.get("required_certifications") or [])
    if not need_certs <= set(worker.get("certifications") or []):
        return False, f"missing certifications {sorted(need_certs - set(worker.get('certifications') or []))}"
    shift = task.get("shift")
    avail = worker.get("available_shifts")
    if shift and avail is not None and shift not in avail:
        return False, f"not available for {shift} shift"
    return True, ""


def allocate(tasks: list[dict], workers: list[dict]) -> dict:
    """Assign each task to the best-fit available worker; report the rest.

    Returns ``{"assignments": [...], "unassigned": [...], "load": {...},
    "summary": {...}}``. Load balances by minutes as work is assigned.
    """
    load = {str(w["id"]): float(w.get("load") or 0) for w in workers}
    perf = {str(w["id"]): float(w.get("performance") or 0) for w in workers}
    wmap = {str(w["id"]): w for w in workers}

    # Assign urgent/long tasks first so scarce skilled labour goes where it matters.
    ordered = sorted(
        tasks,
        key=lambda t: (-oc.priority_rank(t.get("priority", "normal")),
                       -int(t.get("duration") or 0), str(t.get("id") or "")),
    )
    assignments, unassigned = [], []
    for task in ordered:
        candidates = []
        reasons = []
        for wid, w in wmap.items():
            ok, why = _eligible(task, w)
            if ok:
                candidates.append(wid)
            else:
                reasons.append(f"{wid}: {why}")
        if not candidates:
            unassigned.append({
                "id": task.get("id"), "name": task.get("name"),
                "status": oc.unavailable("No worker meets this task's requirements."),
                "detail": reasons,
            })
            continue
        # Prefer same location, then lowest load, then highest performance, then id.
        loc = task.get("location")
        best = min(candidates, key=lambda wid: (
            0 if loc and wmap[wid].get("location") == loc else 1,
            load[wid], -perf[wid], wid))
        dur = float(task.get("duration") or 0)
        load[best] += dur
        assignments.append({
            "task_id": task.get("id"), "name": task.get("name"),
            "worker_id": best, "duration": dur,
            "basis": oc.calculated("skills+availability+load", "Deterministic best-fit."),
        })

    return {
        "assignments": assignments,
        "unassigned": unassigned,
        "load": {wid: oc.calculated(round(m, 2), "Assigned minutes.") for wid, m in load.items()},
        "summary": {
            "assigned": oc.calculated(len(assignments), "Tasks assigned."),
            "unassigned": oc.calculated(len(unassigned), "Tasks with no eligible worker.")
            if unassigned else oc.calculated(0, "All tasks assigned."),
        },
    }
