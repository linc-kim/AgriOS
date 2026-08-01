"""
Greena — Operations Planner Scheduler Service (Platform Module 5).

Turns stored routine definitions into concrete work: expands schedules via the
Recurrence Engine, packs the day via the Scheduling Engine, and **materialises
task instances as ``reminders``** (reusing the platform Task/Reminder store — no
new task table, per spec Doc 3 §24). Also owns assignments, immutable execution
records (``ops_completion``) and the live operational calendar (computed, never
stored — like Mission Control).
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import select

from app.exceptions import NotFoundException
from app.models import ops_planner as m
from app.models.auth import User
from app.models.automation import Reminder
from app.services import audit_service
from app.services import ops_recurrence_engine as recurrence
from app.services import ops_scheduling_engine as scheduling
from app.services import ops_service


async def _active_routines_with_schedules(db, farm_id, module=None) -> list[tuple]:
    q = select(m.OpsRoutine).where(
        m.OpsRoutine.farm_id == farm_id, m.OpsRoutine.is_active.is_(True),
        m.OpsRoutine.deleted_at.is_(None))
    if module:
        q = q.where(m.OpsRoutine.module == module)
    routines = list((await db.execute(q)).scalars().all())
    out = []
    for r in routines:
        out.append((r, await ops_service._routine_schedule(db, r.id)))
    return out


async def generate_occurrences(db, farm_id, module, window_start: date, window_end: date) -> list[dict]:
    """Expand every active routine's schedule into dated occurrences in the window."""
    occurrences = []
    for routine, schedule in await _active_routines_with_schedules(db, farm_id, module):
        if schedule is None:
            continue
        rule = ops_service._schedule_dict(schedule) or {}
        for d in recurrence.expand(rule, window_start, window_end):
            occurrences.append({
                "date": d.isoformat(), "routine_id": str(routine.id), "name": routine.name,
                "module": routine.module, "category": routine.category,
                "duration": routine.estimated_duration_minutes or 0,
                "priority": routine.priority, "depends_on": schedule.dependencies or [],
            })
    return occurrences


async def build_schedule(db, farm_id, module, window_start: date, window_end: date,
                         daily_minutes: int = 480) -> dict:
    """Distribute the window's occurrences across working time (Scheduling Engine)."""
    occurrences = await generate_occurrences(db, farm_id, module, window_start, window_end)
    result = scheduling.distribute(occurrences, daily_minutes=daily_minutes)
    result["window"] = {"start": window_start.isoformat(), "end": window_end.isoformat()}
    return result


def _first_time(schedule_time_windows) -> time:
    for w in schedule_time_windows or []:
        try:
            hh, mm = str(w.get("start")).split(":")[:2]
            return time(int(hh), int(mm))
        except (ValueError, AttributeError, TypeError):
            continue
    return time(6, 0)  # sensible farm default; not fabricated data, just a due-time


async def materialize_tasks(db, farm_id, module, window_start: date, window_end: date,
                            user: User) -> dict:
    """Create ``reminders`` for occurrences that don't yet have one (idempotent via
    a ``dedup_key`` in the reminder's metadata). Reuses the platform Task store."""
    created = 0
    for routine, schedule in await _active_routines_with_schedules(db, farm_id, module):
        if schedule is None:
            continue
        rule = ops_service._schedule_dict(schedule) or {}
        due_time = _first_time(schedule.time_windows)
        for d in recurrence.expand(rule, window_start, window_end):
            dedup_key = f"ops:{routine.id}:{d.isoformat()}"
            exists = (await db.execute(select(Reminder.id).where(
                Reminder.farm_id == farm_id,
                Reminder.metadata_["dedup_key"].astext == dedup_key,
                Reminder.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
            if exists is not None:
                continue
            due_at = datetime.combine(d, due_time, tzinfo=timezone.utc)
            db.add(Reminder(
                id=uuid.uuid4(), farm_id=farm_id, title=routine.name,
                notes=routine.description, due_at=due_at, recurrence="none",
                priority=routine.priority, next_fire_at=due_at, created_by=user.id,
                metadata_={"module": routine.module, "kind": "ops_routine",
                           "routine_id": str(routine.id), "date": d.isoformat(),
                           "dedup_key": dedup_key}))
            created += 1
    await db.commit()
    return {"created": created,
            "window": {"start": window_start.isoformat(), "end": window_end.isoformat()}}


# ── Assignments ───────────────────────────────────────────────────────────────

async def create_assignment(db, farm_id, data, user: User) -> m.OpsAssignment:
    await ops_service._get_routine_or_404(db, farm_id, data.routine_id)
    assignment = m.OpsAssignment(
        id=uuid.uuid4(), farm_id=farm_id, routine_id=data.routine_id,
        target_type=data.target_type, worker_id=data.worker_id, team=data.team,
        shift_id=data.shift_id, schedule=data.schedule, rotation=data.rotation,
        supervisor_id=data.supervisor_id, status="active",
        history=[{"action": "created", "at": datetime.now(timezone.utc).isoformat(),
                  "by": str(user.id), "worker_id": str(data.worker_id) if data.worker_id else None}],
        created_by=user.id)
    db.add(assignment)
    await db.flush()
    await audit_service.log_action(
        db, action="ops.assignment.create", resource_type="ops_assignment",
        resource_id=assignment.id, farm_id=farm_id, user_id=user.id,
        new_value={"routine_id": str(data.routine_id)})
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def reassign(db, farm_id, assignment_id, worker_id, user: User) -> m.OpsAssignment:
    assignment = (await db.execute(select(m.OpsAssignment).where(
        m.OpsAssignment.id == assignment_id, m.OpsAssignment.farm_id == farm_id,
        m.OpsAssignment.deleted_at.is_(None)))).scalar_one_or_none()
    if assignment is None:
        raise NotFoundException(f"Assignment {assignment_id} not found for this farm.")
    # Reassign the whole dict so SQLAlchemy detects the JSONB change (Part 7 pattern).
    assignment.history = list(assignment.history) + [{
        "action": "reassigned", "at": datetime.now(timezone.utc).isoformat(),
        "by": str(user.id), "from": str(assignment.worker_id) if assignment.worker_id else None,
        "to": str(worker_id) if worker_id else None}]
    assignment.worker_id = worker_id
    await db.flush()
    await audit_service.log_action(
        db, action="ops.assignment.reassign", resource_type="ops_assignment",
        resource_id=assignment.id, farm_id=farm_id, user_id=user.id,
        new_value={"worker_id": str(worker_id) if worker_id else None})
    await db.commit()
    await db.refresh(assignment)
    return assignment


async def list_assignments(db, farm_id, routine_id=None) -> list[m.OpsAssignment]:
    q = select(m.OpsAssignment).where(
        m.OpsAssignment.farm_id == farm_id, m.OpsAssignment.deleted_at.is_(None))
    if routine_id:
        q = q.where(m.OpsAssignment.routine_id == routine_id)
    return list((await db.execute(q.order_by(m.OpsAssignment.created_at.desc()))).scalars().all())


# ── Completions (immutable execution history) ─────────────────────────────────

async def record_completion(db, farm_id, data, user: User) -> m.OpsCompletion:
    await ops_service._get_routine_or_404(db, farm_id, data.routine_id)
    completion = m.OpsCompletion(
        id=uuid.uuid4(), farm_id=farm_id, routine_id=data.routine_id,
        occurrence_date=data.occurrence_date, worker_id=data.worker_id or user.id,
        status=data.status, duration_minutes=data.duration_minutes,
        deviations=data.deviations, notes=data.notes, attachments=data.attachments,
        checklist_results=data.checklist_results, verification=data.verification,
        reminder_id=data.reminder_id, created_by=user.id)
    db.add(completion)
    await db.flush()
    # If a materialised reminder is linked, mark it done (reuse the Task store).
    if data.reminder_id is not None:
        reminder = (await db.execute(select(Reminder).where(
            Reminder.id == data.reminder_id, Reminder.farm_id == farm_id))).scalar_one_or_none()
        if reminder is not None:
            reminder.is_done = True
            reminder.done_at = datetime.now(timezone.utc)
    await audit_service.log_action(
        db, action="ops.completion.record", resource_type="ops_completion",
        resource_id=completion.id, farm_id=farm_id, user_id=user.id,
        new_value={"routine_id": str(data.routine_id), "status": data.status})
    await db.commit()
    await db.refresh(completion)
    return completion


async def list_completions(db, farm_id, routine_id=None, since: date | None = None) -> list[m.OpsCompletion]:
    q = select(m.OpsCompletion).where(
        m.OpsCompletion.farm_id == farm_id, m.OpsCompletion.deleted_at.is_(None))
    if routine_id:
        q = q.where(m.OpsCompletion.routine_id == routine_id)
    if since:
        q = q.where(m.OpsCompletion.occurrence_date >= since)
    return list((await db.execute(q.order_by(m.OpsCompletion.occurrence_date.desc()))).scalars().all())


# ── Operational calendar (computed live) ──────────────────────────────────────

async def calendar(db, farm_id, module, window_start: date, window_end: date) -> dict:
    """Merge routine occurrences with Growth-Planner milestones into one calendar
    (spec Doc 5 §12). Computed on demand — nothing is stored, so it can't go stale."""
    occurrences = await generate_occurrences(db, farm_id, module, window_start, window_end)
    events = [{
        "type": "routine", "date": o["date"], "title": o["name"],
        "routine_id": o["routine_id"], "category": o["category"], "priority": o["priority"],
    } for o in occurrences]

    # Growth milestones falling in the window (reuse Growth Planner — no duplication).
    try:
        from app.models.growth import GrowthMilestone, GrowthPlan
        milestones = list((await db.execute(
            select(GrowthMilestone).join(GrowthPlan, GrowthMilestone.plan_id == GrowthPlan.id)
            .where(GrowthPlan.farm_id == farm_id, GrowthMilestone.deleted_at.is_(None),
                   GrowthMilestone.target_date.isnot(None),
                   GrowthMilestone.target_date >= window_start,
                   GrowthMilestone.target_date <= window_end))).scalars().all())
        events += [{
            "type": "growth_milestone", "date": ms.target_date.isoformat(),
            "title": ms.title, "milestone_id": str(ms.id), "status": ms.status,
        } for ms in milestones]
    except Exception:  # Growth Planner is optional context; never block the calendar.
        pass

    events.sort(key=lambda e: (e["date"], e["type"]))
    return {"window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
            "events": events, "count": len(events)}
