"""
Greena — Operations Planner data layer (Platform Module 5).

Gathers ``OpsFacts`` — recorded operational data only — for the deterministic
analytics engines, mirroring ``aria_planning_data`` / ``mission_control_data``.
Never invents a value: a metric with no recorded basis is simply absent, and the
engines then label it ``unknown``.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.models import ops_planner as m
from app.services import ops_recurrence_engine as recurrence
from app.services import ops_service

_COMPLIANCE_CATEGORIES = ("compliance", "health", "safety", "biosecurity", "maintenance")


async def completion_metrics(db, farm_id, module=None, since: date | None = None,
                             as_of: date | None = None) -> dict:
    """Completion rate and status mix from recorded ``ops_completion`` vs the
    occurrences the active schedules *should* have produced in the window."""
    as_of = as_of or date.today()
    since = since or (as_of - timedelta(days=30))

    expected = 0
    for routine, schedule in await ops_scheduler_active(db, farm_id, module):
        if schedule is None:
            continue
        rule = ops_service._schedule_dict(schedule) or {}
        expected += len(recurrence.expand(rule, since, as_of))

    q = select(m.OpsCompletion).where(
        m.OpsCompletion.farm_id == farm_id, m.OpsCompletion.deleted_at.is_(None),
        m.OpsCompletion.occurrence_date >= since, m.OpsCompletion.occurrence_date <= as_of)
    if module:
        q = q.join(m.OpsRoutine, m.OpsCompletion.routine_id == m.OpsRoutine.id).where(
            m.OpsRoutine.module == module)
    completions = list((await db.execute(q)).scalars().all())

    status_counts: dict[str, int] = {}
    durations = []
    for c in completions:
        status_counts[c.status] = status_counts.get(c.status, 0) + 1
        if c.duration_minutes is not None:
            durations.append(c.duration_minutes)
    completed = status_counts.get("completed", 0)

    metrics: dict = {"sample_size": expected}
    if expected > 0:
        metrics["completion_rate"] = round(completed / expected, 4)
    if durations:
        metrics["avg_duration_minutes"] = round(sum(durations) / len(durations), 1)
    metrics["status_counts"] = status_counts
    metrics["expected"] = expected
    metrics["recorded"] = len(completions)
    metrics["window"] = {"start": since.isoformat(), "end": as_of.isoformat()}
    return metrics


async def ops_scheduler_active(db, farm_id, module=None) -> list[tuple]:
    """Active routines with their current schedule (shared by the analytics paths)."""
    q = select(m.OpsRoutine).where(
        m.OpsRoutine.farm_id == farm_id, m.OpsRoutine.is_active.is_(True),
        m.OpsRoutine.deleted_at.is_(None))
    if module:
        q = q.where(m.OpsRoutine.module == module)
    routines = list((await db.execute(q)).scalars().all())
    return [(r, await ops_service._routine_schedule(db, r.id)) for r in routines]


async def compliance_requirements(db, farm_id) -> list[dict]:
    """Derive recurring compliance requirements from the farm's active
    compliance-category routines, using their last recorded completion + interval."""
    q = select(m.OpsRoutine).where(
        m.OpsRoutine.farm_id == farm_id, m.OpsRoutine.is_active.is_(True),
        m.OpsRoutine.category.in_(_COMPLIANCE_CATEGORIES), m.OpsRoutine.deleted_at.is_(None))
    routines = list((await db.execute(q)).scalars().all())
    interval_days = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90,
                     "semiannual": 182, "annual": 365}
    reqs = []
    for r in routines:
        last = (await db.execute(select(m.OpsCompletion.occurrence_date).where(
            m.OpsCompletion.routine_id == r.id, m.OpsCompletion.status == "completed",
            m.OpsCompletion.deleted_at.is_(None))
            .order_by(m.OpsCompletion.occurrence_date.desc()).limit(1))).scalar_one_or_none()
        reqs.append({
            "key": str(r.id), "label": r.name, "category": r.category,
            "interval_days": interval_days.get(r.frequency),
            "last_completed": last.isoformat() if last else None,
        })
    return reqs


async def workload(db, farm_id) -> dict:
    """Assigned minutes per worker (from active assignments × routine duration) and
    a default capacity, for the Workload Balancing Engine."""
    rows = list((await db.execute(
        select(m.OpsAssignment, m.OpsRoutine)
        .join(m.OpsRoutine, m.OpsAssignment.routine_id == m.OpsRoutine.id)
        .where(m.OpsAssignment.farm_id == farm_id, m.OpsAssignment.status == "active",
               m.OpsAssignment.worker_id.isnot(None), m.OpsAssignment.deleted_at.is_(None))
        )).all())
    assignments = []
    workers = set()
    for assignment, routine in rows:
        wid = str(assignment.worker_id)
        workers.add(wid)
        assignments.append({"worker_id": wid,
                            "minutes": routine.estimated_duration_minutes or 0})
    # Default daily capacity per worker (8h); overridable by callers later.
    capacities = {w: 480 for w in workers}
    return {"assignments": assignments, "capacities": capacities}
