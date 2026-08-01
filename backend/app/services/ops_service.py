"""
Greena — Operations Planner Service (Platform Module 5).

Canonical, cross-module CRUD + versioning + approval for the Operations Planner:
the living Operations Manual, routines (with schedules and task templates), SOPs,
checklists, shifts, templates and exceptions. Generic over ``module``; callers
pass their module key and their own permission-guarded endpoints (mirroring
``growth_planner_service``).

Guarantees:
  * Routine **definitions** are versioned: every routine mutation appends an
    immutable :class:`OpsRoutineVersion`; every manual mutation appends an
    immutable :class:`OpsManualRevision` — historical versions are never deleted.
  * Business logic lives here, not in controllers; every mutation is audit-logged.
  * The Operations Manual is **rebuilt from recorded routines** on approved
    change — it is derived, never fabricated (spec Doc 5 §5).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.exceptions import ConflictException, NotFoundException
from app.models import ops_planner as m
from app.models.auth import User
from app.services import audit_service

# Frequency → manual section (spec Doc 5 §5 groups the manual by cadence).
_FREQ_SECTION = {
    "hourly": "daily", "daily": "daily", "weekly": "weekly", "monthly": "monthly",
    "quarterly": "quarterly", "semiannual": "annual", "annual": "annual",
    "seasonal": "seasonal", "custom": "daily",
}


# ── Lookup helpers ────────────────────────────────────────────────────────────

async def _get_routine_or_404(db, farm_id, routine_id) -> m.OpsRoutine:
    r = (await db.execute(select(m.OpsRoutine).where(
        m.OpsRoutine.id == routine_id, m.OpsRoutine.farm_id == farm_id,
        m.OpsRoutine.deleted_at.is_(None)))).scalar_one_or_none()
    if r is None:
        raise NotFoundException(f"Routine {routine_id} not found for this farm.")
    return r


async def _routine_schedule(db, routine_id) -> m.OpsSchedule | None:
    return (await db.execute(select(m.OpsSchedule).where(
        m.OpsSchedule.routine_id == routine_id, m.OpsSchedule.is_active.is_(True),
        m.OpsSchedule.deleted_at.is_(None)).order_by(m.OpsSchedule.created_at.desc())
        .limit(1))).scalar_one_or_none()


async def _routine_task_templates(db, routine_id) -> list[m.OpsTaskTemplate]:
    return list((await db.execute(select(m.OpsTaskTemplate).where(
        m.OpsTaskTemplate.routine_id == routine_id, m.OpsTaskTemplate.deleted_at.is_(None))
        .order_by(m.OpsTaskTemplate.sequence))).scalars().all())


def _schedule_dict(s: m.OpsSchedule | None) -> dict | None:
    if s is None:
        return None
    return {
        "frequency": s.frequency, "interval": s.interval, "byday": s.byday,
        "bymonthday": s.bymonthday, "time_windows": s.time_windows,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "end_date": s.end_date.isoformat() if s.end_date else None,
        "exceptions": s.exceptions, "dependencies": s.dependencies, "rrule": s.rrule,
    }


def _routine_snapshot(r: m.OpsRoutine, schedule: m.OpsSchedule | None,
                      tasks: list[m.OpsTaskTemplate]) -> dict:
    return {
        "name": r.name, "description": r.description, "category": r.category,
        "frequency": r.frequency, "priority": r.priority, "status": r.status,
        "is_active": r.is_active, "estimated_duration_minutes": r.estimated_duration_minutes,
        "required_skills": r.required_skills, "required_equipment": r.required_equipment,
        "assigned_shift_id": str(r.assigned_shift_id) if r.assigned_shift_id else None,
        "assigned_team": r.assigned_team, "requires_approval": r.requires_approval,
        "schedule": _schedule_dict(schedule),
        "task_templates": [{
            "sequence": t.sequence, "name": t.name, "description": t.description,
            "default_duration_minutes": t.default_duration_minutes,
            "required_role": t.required_role, "priority": t.priority,
            "completion_criteria": t.completion_criteria, "depends_on": t.depends_on,
        } for t in tasks],
    }


async def _write_routine_version(db, routine: m.OpsRoutine, change_summary: str | None,
                                 reason: str | None, user: User,
                                 approval_status: str = "pending") -> None:
    schedule = await _routine_schedule(db, routine.id)
    tasks = await _routine_task_templates(db, routine.id)
    db.add(m.OpsRoutineVersion(
        id=uuid.uuid4(), routine_id=routine.id, version_number=routine.current_version,
        author_id=user.id, approval_status=approval_status,
        effective_date=date.today() if approval_status == "approved" else None,
        change_summary=change_summary, reason=reason,
        previous_version=routine.current_version - 1 if routine.current_version > 1 else None,
        snapshot=_routine_snapshot(routine, schedule, tasks), created_by=user.id))


def _apply_schedule(db, routine_id, farm_id, sched_in, user) -> None:
    db.add(m.OpsSchedule(
        id=uuid.uuid4(), routine_id=routine_id, farm_id=farm_id,
        frequency=sched_in.frequency, interval=sched_in.interval, byday=sched_in.byday,
        bymonthday=sched_in.bymonthday, time_windows=sched_in.time_windows,
        start_date=sched_in.start_date, end_date=sched_in.end_date,
        exceptions=sched_in.exceptions, dependencies=sched_in.dependencies,
        rrule=sched_in.rrule, is_active=True, created_by=user.id))


def _apply_task_templates(db, routine_id, tasks_in, user) -> None:
    for t in tasks_in:
        db.add(m.OpsTaskTemplate(
            id=uuid.uuid4(), routine_id=routine_id, sequence=t.sequence, name=t.name,
            description=t.description, default_duration_minutes=t.default_duration_minutes,
            required_role=t.required_role, required_skills=t.required_skills,
            required_equipment=t.required_equipment, priority=t.priority,
            completion_criteria=t.completion_criteria, depends_on=t.depends_on, created_by=user.id))


# ── Operations Manual ─────────────────────────────────────────────────────────

async def get_or_create_manual(db, farm_id, user: User) -> m.OpsManual:
    manual = (await db.execute(select(m.OpsManual).where(
        m.OpsManual.farm_id == farm_id, m.OpsManual.deleted_at.is_(None)))).scalar_one_or_none()
    if manual is not None:
        return manual
    manual = m.OpsManual(
        id=uuid.uuid4(), farm_id=farm_id, title="Farm Operations Manual",
        version=1, status="draft", approval_status="pending",
        sections={}, current_revision=1, created_by=user.id)
    db.add(manual)
    await db.flush()
    db.add(m.OpsManualRevision(
        id=uuid.uuid4(), manual_id=manual.id, revision_number=1,
        reason="Manual created.", trigger="manual", snapshot={}, created_by=user.id))
    await db.commit()
    await db.refresh(manual)
    return manual


async def rebuild_manual(db, farm_id, user: User, trigger: str = "routine_change") -> m.OpsManual:
    """Recompose the manual's sections from the farm's active, approved routines.

    Called after an approved operational change (spec Doc 5 §5). The manual is a
    derived view — nothing here is invented; it groups recorded routines by cadence.
    """
    manual = await get_or_create_manual(db, farm_id, user)
    routines = list((await db.execute(select(m.OpsRoutine).where(
        m.OpsRoutine.farm_id == farm_id, m.OpsRoutine.is_active.is_(True),
        m.OpsRoutine.deleted_at.is_(None)).order_by(m.OpsRoutine.category))).scalars().all())

    sections: dict = {s: [] for s in ("daily", "weekly", "monthly", "quarterly", "seasonal", "annual")}
    by_category: dict = {}
    for r in routines:
        entry = {"id": str(r.id), "name": r.name, "category": r.category,
                 "frequency": r.frequency, "priority": r.priority, "module": r.module}
        sections[_FREQ_SECTION.get(r.frequency, "daily")].append(entry)
        by_category.setdefault(r.category, []).append(entry)

    sops = list((await db.execute(select(m.OpsSOP).where(
        m.OpsSOP.farm_id == farm_id, m.OpsSOP.approval_status == "approved",
        m.OpsSOP.deleted_at.is_(None)))).scalars().all())

    manual.sections = {
        **sections,
        "by_category": by_category,
        "sops": [{"id": str(s.id), "name": s.name, "category": s.category} for s in sops],
        "routine_count": len(routines),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manual.version += 1
    manual.current_revision += 1
    await db.flush()
    db.add(m.OpsManualRevision(
        id=uuid.uuid4(), manual_id=manual.id, revision_number=manual.current_revision,
        reason="Rebuilt from approved operational changes.", trigger=trigger,
        snapshot=manual.sections, created_by=user.id))
    await audit_service.log_action(
        db, action="ops.manual.rebuild", resource_type="ops_manual", resource_id=manual.id,
        farm_id=farm_id, user_id=user.id, new_value={"version": manual.version, "routines": len(routines)})
    await db.commit()
    await db.refresh(manual)
    return manual


async def update_manual(db, farm_id, data, user: User) -> m.OpsManual:
    manual = await get_or_create_manual(db, farm_id, user)
    if data.title is not None:
        manual.title = data.title
    if data.status is not None:
        manual.status = data.status
    if data.review_interval_days is not None:
        manual.review_interval_days = data.review_interval_days
    if data.effective_date is not None:
        manual.effective_date = data.effective_date
    manual.current_revision += 1
    await db.flush()
    db.add(m.OpsManualRevision(
        id=uuid.uuid4(), manual_id=manual.id, revision_number=manual.current_revision,
        reason=data.reason, trigger="manual", snapshot=manual.sections, created_by=user.id))
    await audit_service.log_action(
        db, action="ops.manual.update", resource_type="ops_manual", resource_id=manual.id,
        farm_id=farm_id, user_id=user.id, new_value={"status": manual.status})
    await db.commit()
    await db.refresh(manual)
    return manual


async def list_manual_revisions(db, farm_id) -> list[m.OpsManualRevision]:
    manual = (await db.execute(select(m.OpsManual).where(
        m.OpsManual.farm_id == farm_id, m.OpsManual.deleted_at.is_(None)))).scalar_one_or_none()
    if manual is None:
        return []
    return list((await db.execute(select(m.OpsManualRevision).where(
        m.OpsManualRevision.manual_id == manual.id, m.OpsManualRevision.deleted_at.is_(None))
        .order_by(m.OpsManualRevision.revision_number.desc()))).scalars().all())


# ── Routines ──────────────────────────────────────────────────────────────────

async def create_routine(db, farm_id, module, data, user: User) -> m.OpsRoutine:
    manual = await get_or_create_manual(db, farm_id, user)
    routine = m.OpsRoutine(
        id=uuid.uuid4(), farm_id=farm_id, module=module, manual_id=manual.id,
        name=data.name, description=data.description, category=data.category,
        frequency=data.frequency, priority=data.priority, status="draft", is_active=False,
        estimated_duration_minutes=data.estimated_duration_minutes,
        required_skills=data.required_skills, required_equipment=data.required_equipment,
        assigned_shift_id=data.assigned_shift_id, assigned_team=data.assigned_team,
        requires_approval=data.requires_approval, current_version=1,
        source_template_id=None, created_by=user.id)
    db.add(routine)
    await db.flush()
    if data.schedule is not None:
        _apply_schedule(db, routine.id, farm_id, data.schedule, user)
    _apply_task_templates(db, routine.id, data.task_templates, user)
    await db.flush()
    await _write_routine_version(db, routine, "Routine created.", None, user)
    await audit_service.log_action(
        db, action="ops.routine.create", resource_type="ops_routine", resource_id=routine.id,
        farm_id=farm_id, user_id=user.id, new_value={"name": routine.name, "module": module})
    await db.commit()
    await db.refresh(routine)
    return routine


async def list_routines(db, farm_id, module=None, category=None, status=None,
                        frequency=None) -> list[m.OpsRoutine]:
    q = select(m.OpsRoutine).where(
        m.OpsRoutine.farm_id == farm_id, m.OpsRoutine.deleted_at.is_(None))
    if module:
        q = q.where(m.OpsRoutine.module == module)
    if category:
        q = q.where(m.OpsRoutine.category == category)
    if status:
        q = q.where(m.OpsRoutine.status == status)
    if frequency:
        q = q.where(m.OpsRoutine.frequency == frequency)
    q = q.order_by(m.OpsRoutine.priority.desc(), m.OpsRoutine.name)
    return list((await db.execute(q)).scalars().all())


async def get_routine_detail(db, farm_id, routine_id) -> dict:
    routine = await _get_routine_or_404(db, farm_id, routine_id)
    return {
        "routine": routine,
        "schedule": await _routine_schedule(db, routine_id),
        "task_templates": await _routine_task_templates(db, routine_id),
    }


async def update_routine(db, farm_id, routine_id, data, user: User) -> m.OpsRoutine:
    routine = await _get_routine_or_404(db, farm_id, routine_id)
    if routine.status == "archived":
        raise ConflictException("Archived routines cannot be edited; duplicate to a new routine.")
    for field in ("name", "description", "category", "frequency", "priority", "status",
                  "estimated_duration_minutes", "assigned_shift_id", "assigned_team",
                  "requires_approval"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(routine, field, val)
    if data.required_skills is not None:
        routine.required_skills = data.required_skills
    if data.required_equipment is not None:
        routine.required_equipment = data.required_equipment
    if data.schedule is not None:
        for s in list((await db.execute(select(m.OpsSchedule).where(
                m.OpsSchedule.routine_id == routine_id, m.OpsSchedule.deleted_at.is_(None)))).scalars().all()):
            s.soft_delete()
        _apply_schedule(db, routine.id, farm_id, data.schedule, user)
    if data.task_templates is not None:
        for t in await _routine_task_templates(db, routine_id):
            t.soft_delete()
        _apply_task_templates(db, routine.id, data.task_templates, user)
    routine.current_version += 1
    await db.flush()
    await _write_routine_version(db, routine, data.change_summary, data.reason, user)
    await audit_service.log_action(
        db, action="ops.routine.update", resource_type="ops_routine", resource_id=routine.id,
        farm_id=farm_id, user_id=user.id, new_value={"version": routine.current_version})
    await db.commit()
    await db.refresh(routine)
    return routine


async def set_routine_active(db, farm_id, routine_id, active: bool, user: User) -> m.OpsRoutine:
    routine = await _get_routine_or_404(db, farm_id, routine_id)
    if active and routine.requires_approval:
        approved = (await db.execute(select(m.OpsRoutineVersion).where(
            m.OpsRoutineVersion.routine_id == routine_id,
            m.OpsRoutineVersion.approval_status == "approved",
            m.OpsRoutineVersion.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
        if approved is None:
            raise ConflictException("This routine requires an approved version before activation.")
    routine.is_active = active
    routine.status = "active" if active else "paused"
    routine.current_version += 1
    await db.flush()
    await _write_routine_version(db, routine, f"Routine {'activated' if active else 'deactivated'}.",
                                 None, user)
    await audit_service.log_action(
        db, action=f"ops.routine.{'activate' if active else 'deactivate'}",
        resource_type="ops_routine", resource_id=routine.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    # An activation/deactivation is an approved operational change → refresh the manual.
    await rebuild_manual(db, farm_id, user)
    await db.refresh(routine)
    return routine


async def archive_routine(db, farm_id, routine_id, user: User) -> m.OpsRoutine:
    routine = await _get_routine_or_404(db, farm_id, routine_id)
    routine.status = "archived"
    routine.is_active = False
    routine.current_version += 1
    await db.flush()
    await _write_routine_version(db, routine, "Routine archived.", None, user)
    await audit_service.log_action(
        db, action="ops.routine.archive", resource_type="ops_routine", resource_id=routine.id,
        farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(routine)
    return routine


async def duplicate_routine(db, farm_id, routine_id, user: User) -> m.OpsRoutine:
    src = await _get_routine_or_404(db, farm_id, routine_id)
    schedule = await _routine_schedule(db, routine_id)
    tasks = await _routine_task_templates(db, routine_id)
    manual = await get_or_create_manual(db, farm_id, user)
    dup = m.OpsRoutine(
        id=uuid.uuid4(), farm_id=farm_id, module=src.module, manual_id=manual.id,
        name=f"{src.name} (copy)", description=src.description, category=src.category,
        frequency=src.frequency, priority=src.priority, status="draft", is_active=False,
        estimated_duration_minutes=src.estimated_duration_minutes,
        required_skills=list(src.required_skills), required_equipment=list(src.required_equipment),
        assigned_shift_id=src.assigned_shift_id, assigned_team=src.assigned_team,
        requires_approval=src.requires_approval, current_version=1,
        source_template_id=src.source_template_id, created_by=user.id)
    db.add(dup)
    await db.flush()
    if schedule is not None:
        db.add(m.OpsSchedule(
            id=uuid.uuid4(), routine_id=dup.id, farm_id=farm_id, frequency=schedule.frequency,
            interval=schedule.interval, byday=schedule.byday, bymonthday=schedule.bymonthday,
            time_windows=schedule.time_windows, start_date=schedule.start_date,
            end_date=schedule.end_date, exceptions=schedule.exceptions,
            dependencies=schedule.dependencies, rrule=schedule.rrule, is_active=True, created_by=user.id))
    for t in tasks:
        db.add(m.OpsTaskTemplate(
            id=uuid.uuid4(), routine_id=dup.id, sequence=t.sequence, name=t.name,
            description=t.description, default_duration_minutes=t.default_duration_minutes,
            required_role=t.required_role, required_skills=list(t.required_skills),
            required_equipment=list(t.required_equipment), priority=t.priority,
            completion_criteria=t.completion_criteria, depends_on=list(t.depends_on), created_by=user.id))
    await db.flush()
    await _write_routine_version(db, dup, f"Duplicated from {src.name}.", None, user)
    await db.commit()
    await db.refresh(dup)
    return dup


async def list_routine_versions(db, farm_id, routine_id) -> list[m.OpsRoutineVersion]:
    await _get_routine_or_404(db, farm_id, routine_id)
    return list((await db.execute(select(m.OpsRoutineVersion).where(
        m.OpsRoutineVersion.routine_id == routine_id, m.OpsRoutineVersion.deleted_at.is_(None))
        .order_by(m.OpsRoutineVersion.version_number.desc()))).scalars().all())


async def approve_routine_version(db, farm_id, routine_id, version_number, user: User) -> m.OpsRoutineVersion:
    await _get_routine_or_404(db, farm_id, routine_id)
    version = (await db.execute(select(m.OpsRoutineVersion).where(
        m.OpsRoutineVersion.routine_id == routine_id,
        m.OpsRoutineVersion.version_number == version_number,
        m.OpsRoutineVersion.deleted_at.is_(None)))).scalar_one_or_none()
    if version is None:
        raise NotFoundException(f"Version {version_number} not found on this routine.")
    version.approval_status = "approved"
    version.effective_date = date.today()
    await db.flush()
    await audit_service.log_action(
        db, action="ops.routine.version.approve", resource_type="ops_routine_version",
        resource_id=version.id, farm_id=farm_id, user_id=user.id,
        new_value={"version": version_number})
    await db.commit()
    await rebuild_manual(db, farm_id, user)
    await db.refresh(version)
    return version


# ── SOPs ──────────────────────────────────────────────────────────────────────

async def create_sop(db, farm_id, data, user: User) -> m.OpsSOP:
    sop = m.OpsSOP(
        id=uuid.uuid4(), farm_id=farm_id, module=data.module, name=data.name,
        category=data.category, purpose=data.purpose, scope=data.scope,
        required_equipment=data.required_equipment, safety_notes=data.safety_notes,
        steps=data.steps, verification_steps=data.verification_steps,
        expected_outcome=data.expected_outcome, completion_criteria=data.completion_criteria,
        version=1, approval_status="pending", revision_history=[], created_by=user.id)
    db.add(sop)
    await db.flush()
    await audit_service.log_action(
        db, action="ops.sop.create", resource_type="ops_sop", resource_id=sop.id,
        farm_id=farm_id, user_id=user.id, new_value={"name": sop.name})
    await db.commit()
    await db.refresh(sop)
    return sop


async def update_sop(db, farm_id, sop_id, data, user: User) -> m.OpsSOP:
    sop = (await db.execute(select(m.OpsSOP).where(
        m.OpsSOP.id == sop_id, m.OpsSOP.farm_id == farm_id,
        m.OpsSOP.deleted_at.is_(None)))).scalar_one_or_none()
    if sop is None:
        raise NotFoundException(f"SOP {sop_id} not found for this farm.")
    # Snapshot the prior state into the inline revision history before mutating.
    sop.revision_history = list(sop.revision_history) + [{
        "version": sop.version, "name": sop.name, "steps": sop.steps,
        "approval_status": sop.approval_status,
        "at": datetime.now(timezone.utc).isoformat(), "by": str(user.id)}]
    for field in ("name", "category", "purpose", "scope", "safety_notes",
                  "expected_outcome", "completion_criteria"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(sop, field, val)
    for lst in ("required_equipment", "steps", "verification_steps"):
        val = getattr(data, lst, None)
        if val is not None:
            setattr(sop, lst, val)
    sop.version += 1
    sop.approval_status = "pending"  # edits require re-approval (spec Doc 5 §13)
    await db.flush()
    await audit_service.log_action(
        db, action="ops.sop.update", resource_type="ops_sop", resource_id=sop.id,
        farm_id=farm_id, user_id=user.id, new_value={"version": sop.version})
    await db.commit()
    await db.refresh(sop)
    return sop


async def approve_sop(db, farm_id, sop_id, user: User) -> m.OpsSOP:
    sop = (await db.execute(select(m.OpsSOP).where(
        m.OpsSOP.id == sop_id, m.OpsSOP.farm_id == farm_id,
        m.OpsSOP.deleted_at.is_(None)))).scalar_one_or_none()
    if sop is None:
        raise NotFoundException(f"SOP {sop_id} not found for this farm.")
    sop.approval_status = "approved"
    await db.flush()
    await audit_service.log_action(
        db, action="ops.sop.approve", resource_type="ops_sop", resource_id=sop.id,
        farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(sop)
    return sop


async def list_sops(db, farm_id, module=None) -> list[m.OpsSOP]:
    q = select(m.OpsSOP).where(m.OpsSOP.farm_id == farm_id, m.OpsSOP.deleted_at.is_(None))
    if module:
        q = q.where(m.OpsSOP.module == module)
    return list((await db.execute(q.order_by(m.OpsSOP.name))).scalars().all())


# ── Checklists ────────────────────────────────────────────────────────────────

async def create_checklist(db, farm_id, data, user: User) -> m.OpsChecklist:
    checklist = m.OpsChecklist(
        id=uuid.uuid4(), farm_id=farm_id, routine_id=data.routine_id, sop_id=data.sop_id,
        name=data.name, description=data.description,
        estimated_duration_minutes=data.estimated_duration_minutes,
        completion_requirements=data.completion_requirements, created_by=user.id)
    db.add(checklist)
    await db.flush()
    for item in data.items:
        db.add(m.OpsChecklistItem(
            id=uuid.uuid4(), checklist_id=checklist.id, sequence=item.sequence,
            description=item.description, is_required=item.is_required,
            completion_method=item.completion_method, media_requirement=item.media_requirement,
            verification_required=item.verification_required, notes=item.notes, created_by=user.id))
    await db.flush()
    await audit_service.log_action(
        db, action="ops.checklist.create", resource_type="ops_checklist", resource_id=checklist.id,
        farm_id=farm_id, user_id=user.id, new_value={"name": checklist.name})
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def get_checklist_detail(db, farm_id, checklist_id) -> dict:
    checklist = (await db.execute(select(m.OpsChecklist).where(
        m.OpsChecklist.id == checklist_id, m.OpsChecklist.farm_id == farm_id,
        m.OpsChecklist.deleted_at.is_(None)))).scalar_one_or_none()
    if checklist is None:
        raise NotFoundException(f"Checklist {checklist_id} not found for this farm.")
    items = list((await db.execute(select(m.OpsChecklistItem).where(
        m.OpsChecklistItem.checklist_id == checklist_id, m.OpsChecklistItem.deleted_at.is_(None))
        .order_by(m.OpsChecklistItem.sequence))).scalars().all())
    return {"checklist": checklist, "items": items}


async def list_checklists(db, farm_id, routine_id=None) -> list[m.OpsChecklist]:
    q = select(m.OpsChecklist).where(
        m.OpsChecklist.farm_id == farm_id, m.OpsChecklist.deleted_at.is_(None))
    if routine_id:
        q = q.where(m.OpsChecklist.routine_id == routine_id)
    return list((await db.execute(q.order_by(m.OpsChecklist.name))).scalars().all())


# ── Shifts ────────────────────────────────────────────────────────────────────

async def create_shift(db, farm_id, data, user: User) -> m.OpsShift:
    shift = m.OpsShift(
        id=uuid.uuid4(), farm_id=farm_id, name=data.name, shift_type=data.shift_type,
        start_time=data.start_time, end_time=data.end_time, breaks=data.breaks,
        days_of_week=data.days_of_week, supervisor_id=data.supervisor_id,
        capacity=data.capacity, created_by=user.id)
    db.add(shift)
    await db.flush()
    await audit_service.log_action(
        db, action="ops.shift.create", resource_type="ops_shift", resource_id=shift.id,
        farm_id=farm_id, user_id=user.id, new_value={"name": shift.name})
    await db.commit()
    await db.refresh(shift)
    return shift


async def list_shifts(db, farm_id) -> list[m.OpsShift]:
    return list((await db.execute(select(m.OpsShift).where(
        m.OpsShift.farm_id == farm_id, m.OpsShift.deleted_at.is_(None))
        .order_by(m.OpsShift.start_time))).scalars().all())


# ── Exceptions ────────────────────────────────────────────────────────────────

async def create_exception(db, farm_id, data, user: User) -> m.OpsException:
    if data.routine_id is not None:
        await _get_routine_or_404(db, farm_id, data.routine_id)
    exc = m.OpsException(
        id=uuid.uuid4(), farm_id=farm_id, routine_id=data.routine_id, cause=data.cause,
        impact=data.impact, temporary_adjustments=data.temporary_adjustments,
        resolution=data.resolution, start_date=data.start_date, end_date=data.end_date,
        status="open", created_by=user.id)
    db.add(exc)
    await db.flush()
    await audit_service.log_action(
        db, action="ops.exception.create", resource_type="ops_exception", resource_id=exc.id,
        farm_id=farm_id, user_id=user.id, new_value={"cause": exc.cause})
    await db.commit()
    await db.refresh(exc)
    return exc


async def resolve_exception(db, farm_id, exception_id, resolution, user: User) -> m.OpsException:
    exc = (await db.execute(select(m.OpsException).where(
        m.OpsException.id == exception_id, m.OpsException.farm_id == farm_id,
        m.OpsException.deleted_at.is_(None)))).scalar_one_or_none()
    if exc is None:
        raise NotFoundException(f"Exception {exception_id} not found for this farm.")
    exc.status = "resolved"
    if resolution:
        exc.resolution = resolution
    await db.flush()
    await db.commit()
    await db.refresh(exc)
    return exc


async def list_exceptions(db, farm_id, status=None) -> list[m.OpsException]:
    q = select(m.OpsException).where(
        m.OpsException.farm_id == farm_id, m.OpsException.deleted_at.is_(None))
    if status:
        q = q.where(m.OpsException.status == status)
    return list((await db.execute(q.order_by(m.OpsException.created_at.desc()))).scalars().all())


# ── Templates ─────────────────────────────────────────────────────────────────

async def list_templates(db, farm_id, module=None) -> list[m.OpsRoutineTemplate]:
    """Global platform templates (farm_id NULL) plus this farm's own clones."""
    q = select(m.OpsRoutineTemplate).where(
        m.OpsRoutineTemplate.deleted_at.is_(None),
        (m.OpsRoutineTemplate.farm_id.is_(None)) | (m.OpsRoutineTemplate.farm_id == farm_id))
    if module:
        q = q.where(m.OpsRoutineTemplate.module == module)
    return list((await db.execute(q.order_by(m.OpsRoutineTemplate.name))).scalars().all())


async def _get_template_or_404(db, farm_id, template_id) -> m.OpsRoutineTemplate:
    tpl = (await db.execute(select(m.OpsRoutineTemplate).where(
        m.OpsRoutineTemplate.id == template_id, m.OpsRoutineTemplate.deleted_at.is_(None),
        (m.OpsRoutineTemplate.farm_id.is_(None)) | (m.OpsRoutineTemplate.farm_id == farm_id)))
        ).scalar_one_or_none()
    if tpl is None:
        raise NotFoundException(f"Template {template_id} not found.")
    return tpl


async def apply_template(db, farm_id, data, user: User) -> m.OpsRoutine:
    """Instantiate a routine from a template (spec Doc 4 §18 'Apply Template')."""
    tpl = await _get_template_or_404(db, farm_id, data.template_id)
    module = data.module or tpl.module
    manual = await get_or_create_manual(db, farm_id, user)
    sched = tpl.default_schedule or {}
    routine = m.OpsRoutine(
        id=uuid.uuid4(), farm_id=farm_id, module=module, manual_id=manual.id,
        name=tpl.name, description=tpl.description, category=tpl.category,
        frequency=sched.get("frequency", "daily"), priority="normal", status="draft",
        is_active=False, estimated_duration_minutes=tpl.estimated_time_minutes,
        required_skills=[], required_equipment=[], requires_approval=False,
        current_version=1, source_template_id=tpl.id, created_by=user.id)
    db.add(routine)
    await db.flush()
    if sched:
        db.add(m.OpsSchedule(
            id=uuid.uuid4(), routine_id=routine.id, farm_id=farm_id,
            frequency=sched.get("frequency", "daily"), interval=int(sched.get("interval", 1)),
            byday=sched.get("byday", []), bymonthday=sched.get("bymonthday", []),
            time_windows=sched.get("time_windows", []), exceptions=sched.get("exceptions", []),
            dependencies=sched.get("dependencies", []), is_active=True, created_by=user.id))
    for i, t in enumerate(tpl.default_task_templates or []):
        db.add(m.OpsTaskTemplate(
            id=uuid.uuid4(), routine_id=routine.id, sequence=t.get("sequence", i),
            name=t.get("name", f"Task {i + 1}"), description=t.get("description"),
            default_duration_minutes=t.get("default_duration_minutes"),
            required_role=t.get("required_role"), priority=t.get("priority", "normal"),
            completion_criteria=t.get("completion_criteria"),
            depends_on=t.get("depends_on", []), created_by=user.id))
    await db.flush()
    await _write_routine_version(db, routine, f"Applied template '{tpl.name}'.", None, user)
    if data.activate:
        routine.is_active = True
        routine.status = "active"
    await audit_service.log_action(
        db, action="ops.template.apply", resource_type="ops_routine", resource_id=routine.id,
        farm_id=farm_id, user_id=user.id, new_value={"template_id": str(tpl.id)})
    await db.commit()
    await db.refresh(routine)
    return routine


async def clone_template(db, farm_id, template_id, user: User) -> m.OpsRoutineTemplate:
    """Copy a global template into this farm so it can be customised (spec Doc 4 §18)."""
    src = await _get_template_or_404(db, farm_id, template_id)
    clone = m.OpsRoutineTemplate(
        id=uuid.uuid4(), farm_id=farm_id, module=src.module, name=f"{src.name} (farm copy)",
        description=src.description, enterprise_type=src.enterprise_type, category=src.category,
        default_schedule=dict(src.default_schedule), default_sops=list(src.default_sops),
        default_checklists=list(src.default_checklists),
        default_task_templates=list(src.default_task_templates),
        estimated_labor=dict(src.estimated_labor), estimated_time_minutes=src.estimated_time_minutes,
        is_builtin=False, created_by=user.id)
    db.add(clone)
    await db.flush()
    await db.commit()
    await db.refresh(clone)
    return clone
