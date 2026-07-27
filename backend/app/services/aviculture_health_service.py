"""
Greena — Aviculture Health Service (Module 15, Part 6)

Writes for individual-bird health: medical records (on the extended
``avi_health_record``), quarantine episodes and disease events. Analytics come
from the pure ``health_engine`` (Doc 14 §2). Every health write appends a
``health_recorded`` event to the bird timeline (reuse of the Part 2 helper) and
an audit entry. Differential diagnoses are always stamped as veterinary guidance,
never a definitive diagnosis (Doc 04 §7).

Named ``aviculture_health_service`` to stay distinct from the platform's existing
flock-scoped ``health_service`` (Module 1) — different domain, no duplication.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.aviculture import (
    AviBird,
    AviDiseaseEvent,
    AviHealthRecord,
    AviQuarantine,
)
from app.schemas.aviculture_health import (
    DiseaseEventCreate,
    DiseaseEventUpdate,
    HealthRecordCreate,
    HealthRecordUpdate,
    QuarantineEnd,
    QuarantineStart,
)
from app.services import audit_service, health_engine
from app.services.aviculture_service import _append_event, _get_bird_or_404

_DISCLAIMER = "Veterinary guidance, not a definitive diagnosis. Consult a veterinarian."


# ── Health records ────────────────────────────────────────────────────────────

async def add_record(db, farm_id, bird_id, data: HealthRecordCreate, user: User) -> AviHealthRecord:
    await _get_bird_or_404(db, farm_id, bird_id)
    details = dict(data.details or {})
    # Any differential-diagnosis content is explicitly labelled as guidance.
    if "differential_diagnoses" in details or data.record_type in ("exam", "vet_visit", "lab_report"):
        details.setdefault("_disclaimer", _DISCLAIMER)

    rec = AviHealthRecord(
        id=uuid.uuid4(), bird_id=bird_id, record_type=data.record_type,
        recorded_on=data.recorded_on or date.today(), title=data.title, summary=data.summary,
        weight_grams=data.weight_grams, body_condition=data.body_condition, status=data.status,
        severity=data.severity, next_due_on=data.next_due_on, details=details, recorded_by=user.id,
    )
    db.add(rec)
    await db.flush()
    await _append_event(db, bird_id, "health_recorded",
                        data.title or f"{data.record_type.replace('_', ' ').capitalize()} recorded",
                        occurred_on=rec.recorded_on, actor_id=user.id,
                        data={"record_type": data.record_type, "severity": data.severity})
    await audit_service.log_action(db, action="avi.health.record", resource_type="avi_health_record",
                                   resource_id=rec.id, farm_id=farm_id, user_id=user.id,
                                   new_value={"record_type": data.record_type})
    await db.commit()
    await db.refresh(rec)
    return rec


async def list_records(db, farm_id, bird_id, record_type: str | None = None) -> list[AviHealthRecord]:
    await _get_bird_or_404(db, farm_id, bird_id)
    conds = [AviHealthRecord.bird_id == bird_id, AviHealthRecord.deleted_at.is_(None)]
    if record_type:
        conds.append(AviHealthRecord.record_type == record_type)
    return list((await db.execute(select(AviHealthRecord).where(*conds).order_by(
        AviHealthRecord.recorded_on.desc(), AviHealthRecord.created_at.desc()))).scalars().all())


async def update_record(db, farm_id, bird_id, record_id, data: HealthRecordUpdate, user: User) -> AviHealthRecord:
    await _get_bird_or_404(db, farm_id, bird_id)
    rec = (await db.execute(select(AviHealthRecord).where(
        AviHealthRecord.id == record_id, AviHealthRecord.bird_id == bird_id,
        AviHealthRecord.deleted_at.is_(None)))).scalar_one_or_none()
    if rec is None:
        raise NotFoundException("Health record not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rec, field, value)
    await db.flush()
    await audit_service.log_action(db, action="avi.health.update", resource_type="avi_health_record",
                                   resource_id=rec.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(rec)
    return rec


async def weight_trend(db, farm_id, bird_id) -> dict:
    await _get_bird_or_404(db, farm_id, bird_id)
    rows = await db.execute(
        select(AviHealthRecord.recorded_on, AviHealthRecord.weight_grams).where(
            AviHealthRecord.bird_id == bird_id, AviHealthRecord.weight_grams.isnot(None),
            AviHealthRecord.deleted_at.is_(None)))
    trend = health_engine.weight_trend(
        [{"recorded_on": r[0], "weight_grams": float(r[1])} for r in rows])
    return {"bird_id": bird_id, "trend": trend}


# ── Quarantine ────────────────────────────────────────────────────────────────

async def start_quarantine(db, farm_id, bird_id, data: QuarantineStart, user: User) -> AviQuarantine:
    await _get_bird_or_404(db, farm_id, bird_id)
    active = (await db.execute(select(AviQuarantine.id).where(
        AviQuarantine.bird_id == bird_id, AviQuarantine.status == "active",
        AviQuarantine.deleted_at.is_(None)))).scalar_one_or_none()
    if active is not None:
        raise ConflictException("This bird is already in an active quarantine.")
    q = AviQuarantine(id=uuid.uuid4(), farm_id=farm_id, bird_id=bird_id, aviary_id=data.aviary_id,
                      reason=data.reason, started_on=data.started_on or date.today(),
                      expected_end_on=data.expected_end_on, status="active", notes=data.notes,
                      created_by=user.id)
    db.add(q)
    await db.flush()
    await _append_event(db, bird_id, "health_recorded", "Quarantine started",
                        occurred_on=q.started_on, actor_id=user.id, description=data.reason)
    await audit_service.log_action(db, action="avi.quarantine.start", resource_type="avi_quarantine",
                                   resource_id=q.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(q)
    return q


async def end_quarantine(db, farm_id, quarantine_id, data: QuarantineEnd, user: User) -> AviQuarantine:
    q = (await db.execute(select(AviQuarantine).where(
        AviQuarantine.id == quarantine_id, AviQuarantine.farm_id == farm_id,
        AviQuarantine.deleted_at.is_(None)))).scalar_one_or_none()
    if q is None:
        raise NotFoundException("Quarantine record not found.")
    if q.status == "released":
        raise ConflictException("Quarantine is already ended.")
    q.status = "released"
    q.ended_on = data.ended_on or date.today()
    q.outcome = data.outcome
    await db.flush()
    await _append_event(db, q.bird_id, "health_recorded", "Quarantine ended",
                        occurred_on=q.ended_on, actor_id=user.id, description=data.outcome)
    await audit_service.log_action(db, action="avi.quarantine.end", resource_type="avi_quarantine",
                                   resource_id=q.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(q)
    return q


async def list_quarantine(db, farm_id, *, bird_id=None, active_only=False) -> list[AviQuarantine]:
    conds = [AviQuarantine.farm_id == farm_id, AviQuarantine.deleted_at.is_(None)]
    if bird_id:
        conds.append(AviQuarantine.bird_id == bird_id)
    if active_only:
        conds.append(AviQuarantine.status == "active")
    return list((await db.execute(select(AviQuarantine).where(*conds).order_by(
        AviQuarantine.started_on.desc()))).scalars().all())


# ── Disease events ────────────────────────────────────────────────────────────

async def create_disease_event(db, farm_id, data: DiseaseEventCreate, user: User) -> AviDiseaseEvent:
    ev = AviDiseaseEvent(id=uuid.uuid4(), farm_id=farm_id, aviary_id=data.aviary_id,
                         disease_name=data.disease_name, status=data.status,
                         started_on=data.started_on or date.today(), affected_count=data.affected_count,
                         is_notifiable=data.is_notifiable, notes=data.notes, created_by=user.id)
    db.add(ev)
    await db.flush()
    await audit_service.log_action(db, action="avi.disease.create", resource_type="avi_disease_event",
                                   resource_id=ev.id, farm_id=farm_id, user_id=user.id,
                                   new_value={"disease": data.disease_name})
    await db.commit()
    await db.refresh(ev)
    return ev


async def update_disease_event(db, farm_id, event_id, data: DiseaseEventUpdate, user: User) -> AviDiseaseEvent:
    ev = (await db.execute(select(AviDiseaseEvent).where(
        AviDiseaseEvent.id == event_id, AviDiseaseEvent.farm_id == farm_id,
        AviDiseaseEvent.deleted_at.is_(None)))).scalar_one_or_none()
    if ev is None:
        raise NotFoundException("Disease event not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ev, field, value)
    if data.status == "resolved" and ev.resolved_on is None:
        ev.resolved_on = date.today()
    await db.flush()
    await audit_service.log_action(db, action="avi.disease.update", resource_type="avi_disease_event",
                                   resource_id=ev.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(ev)
    return ev


async def list_disease_events(db, farm_id, status: str | None = None) -> list[AviDiseaseEvent]:
    conds = [AviDiseaseEvent.farm_id == farm_id, AviDiseaseEvent.deleted_at.is_(None)]
    if status:
        conds.append(AviDiseaseEvent.status == status)
    return list((await db.execute(select(AviDiseaseEvent).where(*conds).order_by(
        AviDiseaseEvent.started_on.desc()))).scalars().all())


# ── Farm health summary ───────────────────────────────────────────────────────

async def health_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Deterministic farm-wide health snapshot for Mission Control / ARIA."""
    bird_ids = [r[0] for r in (await db.execute(
        select(AviBird.id).where(AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None)))).all()]
    total_ever = len(bird_ids)
    active = (await db.execute(select(func.count(AviBird.id)).where(
        AviBird.farm_id == farm_id, AviBird.status == "active", AviBird.deleted_at.is_(None)))).scalar_one()
    deceased = (await db.execute(select(func.count(AviBird.id)).where(
        AviBird.farm_id == farm_id, AviBird.status == "deceased", AviBird.deleted_at.is_(None)))).scalar_one()

    records: list[dict] = []
    vaccinated: set = set()
    if bird_ids:
        rrows = await db.execute(select(
            AviHealthRecord.record_type, AviHealthRecord.next_due_on, AviHealthRecord.status,
            AviHealthRecord.bird_id).where(
            AviHealthRecord.bird_id.in_(bird_ids), AviHealthRecord.deleted_at.is_(None)))
        for rt, due, st, bid in rrows:
            records.append({"record_type": rt, "next_due_on": due, "status": st})
            if rt == "vaccination":
                vaccinated.add(bid)

    active_q = (await db.execute(select(func.count(AviQuarantine.id)).where(
        AviQuarantine.farm_id == farm_id, AviQuarantine.status == "active",
        AviQuarantine.deleted_at.is_(None)))).scalar_one()
    active_d = (await db.execute(select(func.count(AviDiseaseEvent.id)).where(
        AviDiseaseEvent.farm_id == farm_id, AviDiseaseEvent.status.in_(("suspected", "confirmed")),
        AviDiseaseEvent.deleted_at.is_(None)))).scalar_one()

    return health_engine.health_summary(
        records=records, active_birds=active, total_ever=total_ever, deceased=deceased,
        vaccinated_birds=len(vaccinated), active_quarantines=active_q, active_diseases=active_d,
        today=date.today())
