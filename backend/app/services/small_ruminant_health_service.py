"""
Greena — Small Ruminant Health Service (Modules 18/19, Milestone 5)

Health records, vaccinations, deworming, hoof care and mortality for goats and
sheep. The service owns DB writes and delegates all analytics to the PURE
:mod:`small_ruminant_health_engine`.

Reuse, not duplication:
  * Vaccination / deworming / hoof / health follow-up due dates create platform
    ``Reminder`` rows (``metadata.module=<species>``, idempotent ``dedup_key``) —
    fired by the platform scheduler into the Notification engine. No SR reminder
    table.
  * Timeline/audit reuse ``sr_event`` + :mod:`audit_service`.
  * Registry helpers (animal lookup, event append) reuse
    :mod:`small_ruminant_service`.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException
from app.models.auth import User
from app.models.automation import Reminder
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantDeworming,
    SmallRuminantHealthRecord,
    SmallRuminantHoofCare,
    SmallRuminantMortality,
    SmallRuminantVaccination,
)
from app.schemas.small_ruminant import (
    DewormingCreate,
    HealthRecordCreate,
    HoofCareCreate,
    MortalityCreate,
    VaccinationCreate,
)
from app.services import audit_service
from app.services import small_ruminant_health_engine as eng
from app.services.small_ruminant_service import _append_event, _get_animal_or_404


def _due_at(on: date) -> datetime:
    return datetime.combine(on, time(9, 0), tzinfo=timezone.utc)


def _at(on: date) -> datetime:
    return datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc)


async def _upsert_reminder(
    db: AsyncSession, farm_id: uuid.UUID, species: str, user: User, *,
    title: str, notes: str, due_on: date, kind: str, dedup_key: str, priority: str = "normal",
) -> Reminder:
    """Create a platform Reminder idempotently by dedup_key. Reuses the shared
    Reminder engine — never a small-ruminant reminder table. Tagged by species."""
    existing = await db.execute(
        select(Reminder).where(
            Reminder.farm_id == farm_id,
            Reminder.is_done.is_(False),
            Reminder.deleted_at.is_(None),
            Reminder.metadata_["module"].astext == species,
            Reminder.metadata_["dedup_key"].astext == dedup_key,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    due_at = _due_at(due_on)
    reminder = Reminder(
        id=uuid.uuid4(), farm_id=farm_id, title=title, notes=notes, due_at=due_at,
        recurrence="none", priority=priority, next_fire_at=due_at, created_by=user.id,
        metadata_={"module": species, "kind": kind, "dedup_key": dedup_key},
    )
    db.add(reminder)
    await db.flush()
    return reminder


# ── Health records ─────────────────────────────────────────────────────────────

async def record_health(db, farm: Farm, species, animal_id, data: HealthRecordCreate, user: User):
    await _get_animal_or_404(db, farm.id, species, animal_id)
    record = SmallRuminantHealthRecord(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id,
        event_type=data.event_type, title=data.title, status=data.status, severity=data.severity,
        symptoms=data.symptoms, diagnosis=data.diagnosis, treatment=data.treatment,
        medication=data.medication, withdrawal_until=data.withdrawal_until,
        veterinarian=data.veterinarian, recovery_status=data.recovery_status,
        occurred_on=data.occurred_on, next_due_on=data.next_due_on, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(record)
    await db.flush()
    if data.next_due_on is not None:
        reminder = await _upsert_reminder(
            db, farm.id, species, user,
            title=f"Follow-up: {data.title or data.event_type}",
            notes=f"Health follow-up for {species} {animal_id}.",
            due_on=data.next_due_on, kind="health_followup",
            dedup_key=f"{species}:health:{animal_id}:{record.id}",
            priority="high" if data.severity in ("severe", "critical") else "normal",
        )
        record.reminder_id = reminder.id
    await _append_event(db, animal_id, "health_recorded", f"Health event: {data.title or data.event_type}",
                        occurred_at=_at(data.occurred_on), operator_id=user.id,
                        details={"event_type": data.event_type, "severity": data.severity})
    await audit_service.log_action(
        db, action=f"sr.{species}.health.record", resource_type="sr_health_record",
        resource_id=record.id, farm_id=farm.id, user_id=user.id,
        new_value={"event_type": data.event_type, "severity": data.severity},
    )
    await db.commit()
    await db.refresh(record)
    return record


async def list_health(db, farm_id, species, animal_id):
    await _get_animal_or_404(db, farm_id, species, animal_id)
    result = await db.execute(
        select(SmallRuminantHealthRecord).where(
            SmallRuminantHealthRecord.animal_id == animal_id,
            SmallRuminantHealthRecord.deleted_at.is_(None),
        ).order_by(SmallRuminantHealthRecord.occurred_on.desc(), SmallRuminantHealthRecord.created_at.desc())
    )
    return list(result.scalars().all())


# ── Vaccinations ───────────────────────────────────────────────────────────────

async def record_vaccination(db, farm: Farm, species, animal_id, data: VaccinationCreate, user: User):
    await _get_animal_or_404(db, farm.id, species, animal_id)
    vac = SmallRuminantVaccination(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id, vaccine=data.vaccine,
        batch_number=data.batch_number, administered_on=data.administered_on,
        next_due_on=data.next_due_on, administrator=data.administrator, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(vac)
    await db.flush()
    if data.next_due_on is not None:
        reminder = await _upsert_reminder(
            db, farm.id, species, user,
            title=f"Vaccination due: {data.vaccine}",
            notes=f"Next {data.vaccine} dose for {species} {animal_id}.",
            due_on=data.next_due_on, kind="vaccination",
            dedup_key=f"{species}:vaccination:{animal_id}:{data.vaccine}:{data.next_due_on.isoformat()}",
        )
        vac.reminder_id = reminder.id
    await _append_event(db, animal_id, "vaccination_recorded", f"Vaccinated: {data.vaccine}",
                        occurred_at=_at(data.administered_on), operator_id=user.id,
                        details={"vaccine": data.vaccine})
    await audit_service.log_action(
        db, action=f"sr.{species}.vaccination.record", resource_type="sr_vaccination",
        resource_id=vac.id, farm_id=farm.id, user_id=user.id, new_value={"vaccine": data.vaccine},
    )
    await db.commit()
    await db.refresh(vac)
    return vac


async def list_vaccinations(db, farm_id, species, animal_id=None):
    conds = [SmallRuminantVaccination.farm_id == farm_id, SmallRuminantVaccination.species == species,
             SmallRuminantVaccination.deleted_at.is_(None)]
    if animal_id is not None:
        await _get_animal_or_404(db, farm_id, species, animal_id)
        conds.append(SmallRuminantVaccination.animal_id == animal_id)
    result = await db.execute(
        select(SmallRuminantVaccination).where(*conds)
        .order_by(SmallRuminantVaccination.administered_on.desc())
    )
    return list(result.scalars().all())


# ── Deworming ──────────────────────────────────────────────────────────────────

async def record_deworming(db, farm: Farm, species, animal_id, data: DewormingCreate, user: User):
    await _get_animal_or_404(db, farm.id, species, animal_id)
    dw = SmallRuminantDeworming(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id, product=data.product,
        method=data.method, dose=data.dose, famacha_score=data.famacha_score,
        administered_on=data.administered_on, next_due_on=data.next_due_on,
        withdrawal_until=data.withdrawal_until, administrator=data.administrator, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(dw)
    await db.flush()
    if data.next_due_on is not None:
        reminder = await _upsert_reminder(
            db, farm.id, species, user,
            title=f"Deworming due: {data.product}",
            notes=f"Next deworming for {species} {animal_id}.",
            due_on=data.next_due_on, kind="deworming",
            dedup_key=f"{species}:deworming:{animal_id}:{data.next_due_on.isoformat()}",
        )
        dw.reminder_id = reminder.id
    await _append_event(db, animal_id, "deworming_recorded", f"Dewormed: {data.product}",
                        occurred_at=_at(data.administered_on), operator_id=user.id,
                        details={"product": data.product, "famacha_score": data.famacha_score})
    await audit_service.log_action(
        db, action=f"sr.{species}.deworming.record", resource_type="sr_deworming",
        resource_id=dw.id, farm_id=farm.id, user_id=user.id, new_value={"product": data.product},
    )
    await db.commit()
    await db.refresh(dw)
    return dw


async def list_deworming(db, farm_id, species, animal_id=None):
    conds = [SmallRuminantDeworming.farm_id == farm_id, SmallRuminantDeworming.species == species,
             SmallRuminantDeworming.deleted_at.is_(None)]
    if animal_id is not None:
        await _get_animal_or_404(db, farm_id, species, animal_id)
        conds.append(SmallRuminantDeworming.animal_id == animal_id)
    result = await db.execute(
        select(SmallRuminantDeworming).where(*conds).order_by(SmallRuminantDeworming.administered_on.desc())
    )
    return list(result.scalars().all())


# ── Hoof care ──────────────────────────────────────────────────────────────────

async def record_hoof_care(db, farm: Farm, species, animal_id, data: HoofCareCreate, user: User):
    await _get_animal_or_404(db, farm.id, species, animal_id)
    hc = SmallRuminantHoofCare(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id, action=data.action,
        condition=data.condition, lameness_score=data.lameness_score, treatment=data.treatment,
        performed_on=data.performed_on, next_due_on=data.next_due_on, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(hc)
    await db.flush()
    if data.next_due_on is not None:
        reminder = await _upsert_reminder(
            db, farm.id, species, user,
            title=f"Hoof care due ({data.action})",
            notes=f"Next hoof care for {species} {animal_id}.",
            due_on=data.next_due_on, kind="hoof_care",
            dedup_key=f"{species}:hoof:{animal_id}:{data.next_due_on.isoformat()}",
        )
        hc.reminder_id = reminder.id
    await _append_event(db, animal_id, "hoof_care_recorded", f"Hoof {data.action}: {data.condition}",
                        occurred_at=_at(data.performed_on), operator_id=user.id,
                        details={"action": data.action, "condition": data.condition})
    await audit_service.log_action(
        db, action=f"sr.{species}.hoof.record", resource_type="sr_hoof_care",
        resource_id=hc.id, farm_id=farm.id, user_id=user.id, new_value={"action": data.action},
    )
    await db.commit()
    await db.refresh(hc)
    return hc


async def list_hoof_care(db, farm_id, species, animal_id=None):
    conds = [SmallRuminantHoofCare.farm_id == farm_id, SmallRuminantHoofCare.species == species,
             SmallRuminantHoofCare.deleted_at.is_(None)]
    if animal_id is not None:
        await _get_animal_or_404(db, farm_id, species, animal_id)
        conds.append(SmallRuminantHoofCare.animal_id == animal_id)
    result = await db.execute(
        select(SmallRuminantHoofCare).where(*conds).order_by(SmallRuminantHoofCare.performed_on.desc())
    )
    return list(result.scalars().all())


# ── Mortality (authoritative clinical death record) ────────────────────────────

async def record_mortality(db, farm: Farm, species, animal_id, data: MortalityCreate, user: User):
    a = await _get_animal_or_404(db, farm.id, species, animal_id)
    if a.status in ("sold", "transferred", "archived"):
        raise ConflictException(f"Cannot record mortality: animal is {a.status}.")
    existing = await db.execute(
        select(SmallRuminantMortality.id).where(
            SmallRuminantMortality.animal_id == animal_id, SmallRuminantMortality.deleted_at.is_(None)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictException("A mortality record already exists for this animal.")

    age_days = (data.occurred_on - a.date_of_birth).days if a.date_of_birth else None
    mortality = SmallRuminantMortality(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id,
        occurred_on=data.occurred_on, age_days=age_days, cause=data.cause,
        suspected_cause=data.suspected_cause, postmortem_notes=data.postmortem_notes,
        recorded_by=user.id,
    )
    db.add(mortality)
    a.status = "deceased"
    a.group_id = None
    a.pen_id = None
    a.pasture_id = None
    await db.flush()
    await _append_event(db, animal_id, "died", f"Deceased ({data.cause})",
                        occurred_at=_at(data.occurred_on), operator_id=user.id,
                        details={"cause": data.cause, "suspected_cause": data.suspected_cause})
    await audit_service.log_action(
        db, action=f"sr.{species}.mortality.record", resource_type="sr_mortality",
        resource_id=mortality.id, farm_id=farm.id, user_id=user.id, new_value={"cause": data.cause},
    )
    await db.commit()
    await db.refresh(mortality)
    return mortality


async def list_mortality(db, farm_id, species):
    result = await db.execute(
        select(SmallRuminantMortality).where(
            SmallRuminantMortality.farm_id == farm_id, SmallRuminantMortality.species == species,
            SmallRuminantMortality.deleted_at.is_(None),
        ).order_by(SmallRuminantMortality.occurred_on.desc())
    )
    return list(result.scalars().all())


# ── Deterministic health summary ───────────────────────────────────────────────

async def health_summary(db, farm_id, species) -> dict:
    async def _count(model, *extra):
        r = await db.execute(select(func.count(model.id)).where(
            model.farm_id == farm_id, model.species == species, model.deleted_at.is_(None), *extra))
        return r.scalar_one() or 0

    total_ever = await _count(SmallRuminant)
    deceased = await _count(SmallRuminant, SmallRuminant.status == "deceased")

    async def _rows(model, cols):
        r = await db.execute(select(*cols).where(
            model.farm_id == farm_id, model.species == species, model.deleted_at.is_(None)))
        return r.all()

    mort = [{"cause": r[0], "occurred_on": r[1]} for r in await _rows(
        SmallRuminantMortality, [SmallRuminantMortality.cause, SmallRuminantMortality.occurred_on])]
    hr = [{"event_type": r[0], "status": r[1]} for r in await _rows(
        SmallRuminantHealthRecord, [SmallRuminantHealthRecord.event_type, SmallRuminantHealthRecord.status])]
    vac = [{"next_due_on": r[0]} for r in await _rows(
        SmallRuminantVaccination, [SmallRuminantVaccination.next_due_on])]
    dew = [{"next_due_on": r[0], "famacha_score": r[1]} for r in await _rows(
        SmallRuminantDeworming, [SmallRuminantDeworming.next_due_on, SmallRuminantDeworming.famacha_score])]
    hoof = [{"condition": r[0], "next_due_on": r[1]} for r in await _rows(
        SmallRuminantHoofCare, [SmallRuminantHoofCare.condition, SmallRuminantHoofCare.next_due_on])]

    return eng.health_summary(
        deceased=deceased, total_ever=total_ever, mortality_records=mort, health_records=hr,
        vaccinations=vac, dewormings=dew, hoof_records=hoof, today=date.today(),
    )
