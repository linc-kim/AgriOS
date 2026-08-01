"""
Greena — Rabbit Health Service (Module 17, Milestone 5)

Health records, vaccinations and mortality. The service owns DB writes and
delegates all analytics to the PURE :mod:`rabbit_health_engine` (GMIS §1.3).

Reuse, not duplication (ledger CON-M5):
  * Vaccination / follow-up due dates create platform ``Reminder`` rows
    (``metadata.module='rabbit'``, idempotent ``dedup_key``) — fired by the
    platform scheduler into the Notification engine. No rabbit reminder table.
  * Timeline/audit reuse ``rabbit_event`` + :mod:`audit_service`.
  * Registry helpers (rabbit lookup, event append) are reused from
    :mod:`rabbit_service`.
"""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException
from app.models.auth import User
from app.models.automation import Reminder
from app.models.farm import Farm
from app.models.rabbit import (
    Rabbit,
    RabbitHealthRecord,
    RabbitMortality,
    RabbitVaccination,
)
from app.schemas.rabbit import HealthRecordCreate, MortalityCreate, VaccinationCreate
from app.services import audit_service, rabbit_health_engine as eng, rabbit_service


def _due_at(on: date) -> datetime:
    return datetime.combine(on, time(9, 0), tzinfo=timezone.utc)


async def _upsert_reminder(
    db: AsyncSession, farm_id: uuid.UUID, user: User, *,
    title: str, notes: str, due_on: date, kind: str, dedup_key: str, priority: str = "normal",
) -> Reminder:
    """Create a platform Reminder idempotently by dedup_key (ledger CON-M5-1).
    Reuses the shared Reminder engine — never a rabbit-specific reminder table."""
    existing = await db.execute(
        select(Reminder).where(
            Reminder.farm_id == farm_id,
            Reminder.is_done.is_(False),
            Reminder.deleted_at.is_(None),
            Reminder.metadata_["module"].astext == "rabbit",
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
        metadata_={"module": "rabbit", "kind": kind, "dedup_key": dedup_key},
    )
    db.add(reminder)
    await db.flush()
    return reminder


# ── Health records ─────────────────────────────────────────────────────────────

async def record_health(db: AsyncSession, farm: Farm, rabbit_id: uuid.UUID, data: HealthRecordCreate, user: User) -> RabbitHealthRecord:
    await rabbit_service._get_rabbit_or_404(db, farm.id, rabbit_id)
    record = RabbitHealthRecord(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=rabbit_id, event_type=data.event_type,
        title=data.title, status=data.status, severity=data.severity, symptoms=data.symptoms,
        diagnosis=data.diagnosis, treatment=data.treatment, medication=data.medication,
        veterinarian=data.veterinarian, recovery_status=data.recovery_status,
        occurred_on=data.occurred_on, next_due_on=data.next_due_on, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(record)
    await db.flush()

    if data.next_due_on is not None:
        await _upsert_reminder(
            db, farm.id, user,
            title=f"Follow-up: {data.title or data.event_type}",
            notes=f"Health follow-up for rabbit {rabbit_id}.",
            due_on=data.next_due_on, kind="health_followup",
            dedup_key=f"rabbit:health:{rabbit_id}:{record.id}",
            priority="high" if data.severity in ("severe", "critical") else "normal",
        )

    await rabbit_service._append_event(
        db, rabbit_id, "health_recorded", f"Health event: {data.title or data.event_type}",
        occurred_at=datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"event_type": data.event_type, "severity": data.severity},
    )
    await audit_service.log_action(
        db, action="rabbit.health.record", resource_type="rabbit_health_record",
        resource_id=record.id, farm_id=farm.id, user_id=user.id,
        new_value={"event_type": data.event_type, "severity": data.severity},
    )
    await db.commit()
    await db.refresh(record)
    return record


async def list_health(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> list[RabbitHealthRecord]:
    await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
    result = await db.execute(
        select(RabbitHealthRecord).where(
            RabbitHealthRecord.rabbit_id == rabbit_id, RabbitHealthRecord.deleted_at.is_(None)
        ).order_by(RabbitHealthRecord.occurred_on.desc(), RabbitHealthRecord.created_at.desc())
    )
    return list(result.scalars().all())


# ── Vaccinations (reuse the platform Reminder engine) ───────────────────────────

async def record_vaccination(db: AsyncSession, farm: Farm, rabbit_id: uuid.UUID, data: VaccinationCreate, user: User) -> RabbitVaccination:
    await rabbit_service._get_rabbit_or_404(db, farm.id, rabbit_id)
    vac = RabbitVaccination(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=rabbit_id, vaccine=data.vaccine,
        batch_number=data.batch_number, administered_on=data.administered_on,
        next_due_on=data.next_due_on, administrator=data.administrator, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(vac)
    await db.flush()

    if data.next_due_on is not None:
        reminder = await _upsert_reminder(
            db, farm.id, user,
            title=f"Vaccination due: {data.vaccine}",
            notes=f"Next {data.vaccine} dose for rabbit {rabbit_id}.",
            due_on=data.next_due_on, kind="vaccination",
            dedup_key=f"rabbit:vaccination:{rabbit_id}:{data.vaccine}:{data.next_due_on.isoformat()}",
        )
        vac.reminder_id = reminder.id

    await rabbit_service._append_event(
        db, rabbit_id, "vaccination_recorded", f"Vaccinated: {data.vaccine}",
        occurred_at=datetime.combine(data.administered_on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"vaccine": data.vaccine, "next_due_on":
                                      data.next_due_on.isoformat() if data.next_due_on else None},
    )
    await audit_service.log_action(
        db, action="rabbit.vaccination.record", resource_type="rabbit_vaccination",
        resource_id=vac.id, farm_id=farm.id, user_id=user.id, new_value={"vaccine": data.vaccine},
    )
    await db.commit()
    await db.refresh(vac)
    return vac


async def list_vaccinations(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID | None = None) -> list[RabbitVaccination]:
    conds = [RabbitVaccination.farm_id == farm_id, RabbitVaccination.deleted_at.is_(None)]
    if rabbit_id is not None:
        await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
        conds.append(RabbitVaccination.rabbit_id == rabbit_id)
    result = await db.execute(
        select(RabbitVaccination).where(*conds)
        .order_by(RabbitVaccination.administered_on.desc(), RabbitVaccination.created_at.desc())
    )
    return list(result.scalars().all())


# ── Mortality (authoritative clinical death record — ledger CON-M5-4) ───────────

async def record_mortality(db: AsyncSession, farm: Farm, rabbit_id: uuid.UUID, data: MortalityCreate, user: User) -> RabbitMortality:
    r = await rabbit_service._get_rabbit_or_404(db, farm.id, rabbit_id)
    if r.status in ("sold", "transferred", "archived"):
        raise ConflictException(f"Cannot record mortality: rabbit is {r.status}.")
    existing = await db.execute(
        select(RabbitMortality.id).where(
            RabbitMortality.rabbit_id == rabbit_id, RabbitMortality.deleted_at.is_(None)
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictException("A mortality record already exists for this rabbit.")

    age_days = (data.occurred_on - r.date_of_birth).days if r.date_of_birth else None
    mortality = RabbitMortality(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=rabbit_id, occurred_on=data.occurred_on,
        age_days=age_days, cause=data.cause, suspected_cause=data.suspected_cause,
        postmortem_notes=data.postmortem_notes, recorded_by=user.id,
    )
    db.add(mortality)
    r.status = "deceased"
    r.cage_id = None
    await db.flush()

    await rabbit_service._append_event(
        db, rabbit_id, "died", f"Deceased ({data.cause})",
        occurred_at=datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"cause": data.cause, "suspected_cause": data.suspected_cause},
    )
    await audit_service.log_action(
        db, action="rabbit.mortality.record", resource_type="rabbit_mortality",
        resource_id=mortality.id, farm_id=farm.id, user_id=user.id, new_value={"cause": data.cause},
    )
    await db.commit()
    await db.refresh(mortality)
    return mortality


async def list_mortality(db: AsyncSession, farm_id: uuid.UUID) -> list[RabbitMortality]:
    result = await db.execute(
        select(RabbitMortality).where(
            RabbitMortality.farm_id == farm_id, RabbitMortality.deleted_at.is_(None)
        ).order_by(RabbitMortality.occurred_on.desc())
    )
    return list(result.scalars().all())


# ── Deterministic health summary (Spec Part 7 §7) ──────────────────────────────

async def health_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    total_ever = (await db.execute(
        select(func.count(Rabbit.id)).where(Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None))
    )).scalar_one() or 0
    deceased = (await db.execute(
        select(func.count(Rabbit.id)).where(
            Rabbit.farm_id == farm_id, Rabbit.status == "deceased", Rabbit.deleted_at.is_(None)
        )
    )).scalar_one() or 0

    mort_rows = await db.execute(
        select(RabbitMortality.cause, RabbitMortality.occurred_on).where(
            RabbitMortality.farm_id == farm_id, RabbitMortality.deleted_at.is_(None)
        )
    )
    mortality_records = [{"cause": r[0], "occurred_on": r[1]} for r in mort_rows]

    hr_rows = await db.execute(
        select(RabbitHealthRecord.event_type, RabbitHealthRecord.status).where(
            RabbitHealthRecord.farm_id == farm_id, RabbitHealthRecord.deleted_at.is_(None)
        )
    )
    health_records = [{"event_type": r[0], "status": r[1]} for r in hr_rows]

    vac_rows = await db.execute(
        select(RabbitVaccination.next_due_on).where(
            RabbitVaccination.farm_id == farm_id, RabbitVaccination.deleted_at.is_(None)
        )
    )
    vaccinations = [{"next_due_on": r[0]} for r in vac_rows]

    return eng.health_summary(
        deceased=deceased, total_ever=total_ever, mortality_records=mortality_records,
        health_records=health_records, vaccinations=vaccinations, today=date.today(),
    )
