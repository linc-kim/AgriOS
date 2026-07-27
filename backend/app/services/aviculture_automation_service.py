"""
Greena — Aviculture Automation Service (Module 15, Part 9)

Reuse-first automation. The deterministic "what is due" logic lives in the pure
``aviculture_automation_engine``; this service:

  * gathers recorded aviculture state and runs the engine (preview),
  * materialises the computed items into the EXISTING platform ``Reminder`` engine
    (tagged ``metadata.module='aviculture'``) idempotently by ``dedup_key`` — the
    scheduler's ``run_reminders`` then fires them into the Notification engine,
  * raises immediate ``Notification`` rows for overdue/critical items,
  * drives deterministic staged workflows (Doc 11 §8).

No aviculture reminder or notification table is created — the platform engines are
reused. Automation never performs irreversible actions on its own (Doc 11 §1);
generating reminders and advancing workflows are explicit, audited, user actions.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.automation import Reminder
from app.models.platform import Notification
from app.models.aviculture import (
    AviAviary, AviAviaryTask, AviBird, AviBirdDocument, AviHealthRecord,
    AviIncubationBatch, AviWorkflow, AviWorkflowEvent,
)
from app.services import audit_service, aviculture_automation_engine as engine

_ACTION_ROUTE = "/aviculture/automation"


# ── Gather recorded state ─────────────────────────────────────────────────────

async def _gather_state(db: AsyncSession, farm_id) -> dict:
    health = await db.execute(
        select(AviHealthRecord.next_due_on, AviHealthRecord.record_type,
               AviHealthRecord.bird_id, AviBird.internal_ref)
        .join(AviBird, AviBird.id == AviHealthRecord.bird_id)
        .where(AviBird.farm_id == farm_id, AviHealthRecord.next_due_on.isnot(None),
               AviHealthRecord.status != "resolved", AviHealthRecord.deleted_at.is_(None),
               AviBird.deleted_at.is_(None)))
    health_due = [{"next_due_on": r[0], "record_type": r[1], "bird_id": r[2], "bird_ref": r[3]} for r in health]

    docs = await db.execute(
        select(AviBirdDocument.expires_on, AviBirdDocument.document_type, AviBirdDocument.id,
               AviBird.internal_ref, AviBird.id)
        .join(AviBird, AviBird.id == AviBirdDocument.bird_id)
        .where(AviBird.farm_id == farm_id, AviBirdDocument.expires_on.isnot(None),
               AviBirdDocument.deleted_at.is_(None), AviBird.deleted_at.is_(None)))
    documents_expiring = [{"expires_on": r[0], "document_type": r[1], "document_id": r[2],
                           "bird_ref": r[3], "bird_id": r[4]} for r in docs]

    batches = await db.execute(
        select(AviIncubationBatch.id, AviIncubationBatch.name,
               AviIncubationBatch.expected_lockdown_on, AviIncubationBatch.expected_hatch_on)
        .where(AviIncubationBatch.farm_id == farm_id,
               AviIncubationBatch.status.in_(("setting", "incubating", "lockdown")),
               AviIncubationBatch.deleted_at.is_(None),
               or_(AviIncubationBatch.expected_lockdown_on.isnot(None),
                   AviIncubationBatch.expected_hatch_on.isnot(None))))
    incubation_batches = [{"batch_id": r[0], "name": r[1], "expected_lockdown_on": r[2],
                           "expected_hatch_on": r[3]} for r in batches]

    tasks = await db.execute(
        select(AviAviaryTask.id, AviAviaryTask.task_type, AviAviaryTask.scheduled_for,
               AviAviary.name, AviAviary.id)
        .join(AviAviary, AviAviary.id == AviAviaryTask.aviary_id)
        .where(AviAviary.farm_id == farm_id, AviAviaryTask.status == "scheduled",
               AviAviaryTask.scheduled_for.isnot(None), AviAviaryTask.deleted_at.is_(None)))
    aviary_tasks = [{"task_id": r[0], "task_type": r[1], "scheduled_for": r[2],
                     "aviary_name": r[3], "aviary_id": r[4]} for r in tasks]

    return {"health_due": health_due, "documents_expiring": documents_expiring,
            "incubation_batches": incubation_batches, "aviary_tasks": aviary_tasks}


async def preview(db: AsyncSession, farm: Farm, *, horizon_days: int = 30) -> list[dict]:
    state = await _gather_state(db, farm.id)
    return engine.compute_operational_items(today=date.today(), horizon_days=horizon_days, **state)


# ── Materialise into the platform Reminder / Notification engines ─────────────

def _due_at(day: str | None) -> datetime:
    d = date.fromisoformat(day) if day else date.today()
    return datetime.combine(d, time(9, 0), tzinfo=timezone.utc)


async def generate(db: AsyncSession, farm: Farm, user: User, *, horizon_days: int = 30) -> dict:
    """Materialise computed items as reminders (idempotent) and raise immediate
    notifications for overdue/critical items."""
    items = await preview(db, farm, horizon_days=horizon_days)

    # Existing aviculture reminder dedup keys still open.
    existing = await db.execute(
        select(Reminder.metadata_["dedup_key"].astext).where(
            Reminder.farm_id == farm.id, Reminder.deleted_at.is_(None), Reminder.is_done.is_(False),
            Reminder.metadata_["module"].astext == "aviculture"))
    open_keys = {r[0] for r in existing}

    created = skipped = notified = 0
    for it in items:
        if it["dedup_key"] in open_keys:
            skipped += 1
            continue
        due_at = _due_at(it["suggested_due_on"])
        db.add(Reminder(
            id=uuid.uuid4(), farm_id=farm.id, user_id=farm.owner_id, title=it["title"],
            notes=it["reason"], due_at=due_at, recurrence="none", priority=it["priority"],
            next_fire_at=due_at, created_by=user.id,
            metadata_={"module": "aviculture", "kind": it["kind"], "dedup_key": it["dedup_key"],
                       "evidence": it["evidence"], "reason": it["reason"]}))
        created += 1
        open_keys.add(it["dedup_key"])

        # Immediate notification for the sharpest items (Doc 11 §7).
        if it["priority"] in (engine.HIGH, engine.CRITICAL) and farm.owner_id is not None:
            db.add(Notification(
                id=uuid.uuid4(), farm_id=farm.id, user_id=farm.owner_id,
                notification_type="aviculture_reminder", title=it["title"], body=it["reason"],
                action_route=_ACTION_ROUTE, source="aviculture_automation", priority=it["priority"]))
            notified += 1

    await audit_service.log_action(
        db, action="avi.automation.generate", resource_type="reminder", farm_id=farm.id,
        user_id=user.id, new_value={"created": created, "skipped": skipped, "notified": notified})
    await db.commit()
    return {"created": created, "skipped": skipped, "notified": notified, "evaluated": len(items)}


async def list_tasks(db: AsyncSession, farm_id, *, include_done: bool = False) -> list[Reminder]:
    conds = [Reminder.farm_id == farm_id, Reminder.deleted_at.is_(None),
             Reminder.metadata_["module"].astext == "aviculture"]
    if not include_done:
        conds.append(Reminder.is_done.is_(False))
    return list((await db.execute(
        select(Reminder).where(*conds).order_by(Reminder.due_at.asc()))).scalars().all())


async def complete_task(db: AsyncSession, farm_id, reminder_id, user: User) -> Reminder:
    rem = (await db.execute(select(Reminder).where(
        Reminder.id == reminder_id, Reminder.farm_id == farm_id, Reminder.deleted_at.is_(None)))).scalar_one_or_none()
    if rem is None:
        raise NotFoundException("Task not found.")
    rem.is_done = True
    rem.done_at = datetime.now(tz=timezone.utc)
    rem.next_fire_at = None
    await db.flush()
    await audit_service.log_action(db, action="avi.automation.complete", resource_type="reminder",
                                   resource_id=rem.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(rem)
    return rem


# ── Workflows (deterministic staged processes) ────────────────────────────────

async def start_workflow(db: AsyncSession, farm: Farm, *, workflow_type: str, bird_id, notes, user: User) -> AviWorkflow:
    stage = engine.first_stage(workflow_type)
    if stage is None:
        raise ValidationException(f"Unknown workflow type '{workflow_type}'.")
    if bird_id is not None:
        b = (await db.execute(select(AviBird.id).where(
            AviBird.id == bird_id, AviBird.farm_id == farm.id, AviBird.deleted_at.is_(None)))).scalar_one_or_none()
        if b is None:
            raise NotFoundException("Bird not found on this farm.")
    wf = AviWorkflow(id=uuid.uuid4(), farm_id=farm.id, bird_id=bird_id, workflow_type=workflow_type,
                     current_stage=stage, status="active", started_on=date.today(),
                     responsible_user_id=user.id, notes=notes, created_by=user.id)
    db.add(wf)
    await db.flush()
    db.add(AviWorkflowEvent(id=uuid.uuid4(), workflow_id=wf.id, from_stage=None, to_stage=stage,
                            occurred_on=date.today(), note="Workflow started", actor_id=user.id))
    await audit_service.log_action(db, action="avi.workflow.start", resource_type="avi_workflow",
                                   resource_id=wf.id, farm_id=farm.id, user_id=user.id,
                                   new_value={"type": workflow_type})
    await db.commit()
    await db.refresh(wf)
    return wf


async def advance_workflow(db: AsyncSession, farm_id, workflow_id, *, note, user: User) -> AviWorkflow:
    wf = (await db.execute(select(AviWorkflow).where(
        AviWorkflow.id == workflow_id, AviWorkflow.farm_id == farm_id,
        AviWorkflow.deleted_at.is_(None)))).scalar_one_or_none()
    if wf is None:
        raise NotFoundException("Workflow not found.")
    if wf.status != "active":
        raise ConflictException(f"Workflow is {wf.status} and cannot advance.")
    nxt = engine.next_stage(wf.workflow_type, wf.current_stage)
    if nxt is None:
        raise ConflictException("Workflow is already at its final stage.")
    prev = wf.current_stage
    wf.current_stage = nxt
    if engine.is_terminal(wf.workflow_type, nxt):
        wf.status = "completed"
        wf.completed_on = date.today()
    await db.flush()
    db.add(AviWorkflowEvent(id=uuid.uuid4(), workflow_id=wf.id, from_stage=prev, to_stage=nxt,
                            occurred_on=date.today(), note=note, actor_id=user.id))
    await audit_service.log_action(db, action="avi.workflow.advance", resource_type="avi_workflow",
                                   resource_id=wf.id, farm_id=farm_id, user_id=user.id,
                                   new_value={"from": prev, "to": nxt})
    await db.commit()
    await db.refresh(wf)
    return wf


async def list_workflows(db: AsyncSession, farm_id, *, status=None, bird_id=None) -> list[AviWorkflow]:
    conds = [AviWorkflow.farm_id == farm_id, AviWorkflow.deleted_at.is_(None)]
    if status:
        conds.append(AviWorkflow.status == status)
    if bird_id:
        conds.append(AviWorkflow.bird_id == bird_id)
    return list((await db.execute(
        select(AviWorkflow).where(*conds).order_by(AviWorkflow.created_at.desc()))).scalars().all())


async def get_workflow_events(db: AsyncSession, farm_id, workflow_id) -> list[AviWorkflowEvent]:
    wf = (await db.execute(select(AviWorkflow.id).where(
        AviWorkflow.id == workflow_id, AviWorkflow.farm_id == farm_id,
        AviWorkflow.deleted_at.is_(None)))).scalar_one_or_none()
    if wf is None:
        raise NotFoundException("Workflow not found.")
    return list((await db.execute(
        select(AviWorkflowEvent).where(AviWorkflowEvent.workflow_id == workflow_id,
                                       AviWorkflowEvent.deleted_at.is_(None))
        .order_by(AviWorkflowEvent.occurred_on.asc(), AviWorkflowEvent.created_at.asc()))).scalars().all())
