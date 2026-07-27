"""
Greena — Aviary Service (Module 15, Part 3)

Collection-management writes for aviaries and their infrastructure. Business
calculations (occupancy, environment summaries, cleaning status, housing
suitability) are delegated to the pure ``aviary_engine`` — this service only
loads records, calls the engine, appends timeline events and writes audit logs
(Doc 14 §2-6). Occupancy is computed live from ``avi_bird.aviary_id`` and is
never stored (no duplicated fact).
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.aviculture import (
    AviAviary,
    AviAviaryEvent,
    AviAviaryFixture,
    AviAviaryMedia,
    AviAviaryTask,
    AviAviaryZone,
    AviBird,
    AviEnvironmentalReading,
    AviSpecies,
)
from app.schemas.aviculture_aviary import (
    AviaryCreate,
    AviaryUpdate,
    EnvironmentalReadingCreate,
    FixtureCreate,
    TaskComplete,
    TaskCreate,
    ZoneCreate,
)
from app.services import audit_service, aviary_engine


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_aviary_or_404(db: AsyncSession, farm_id: uuid.UUID, aviary_id: uuid.UUID) -> AviAviary:
    result = await db.execute(
        select(AviAviary).where(
            AviAviary.id == aviary_id, AviAviary.farm_id == farm_id, AviAviary.deleted_at.is_(None)
        )
    )
    aviary = result.scalar_one_or_none()
    if aviary is None:
        raise NotFoundException(f"Aviary {aviary_id} not found on this farm.")
    return aviary


async def _occupied_count(db: AsyncSession, aviary_id: uuid.UUID) -> int:
    """Recorded fact: active birds currently housed in this aviary."""
    result = await db.execute(
        select(func.count(AviBird.id)).where(
            AviBird.aviary_id == aviary_id,
            AviBird.status == "active",
            AviBird.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def _append_event(
    db: AsyncSession, aviary_id: uuid.UUID, event_type: str, title: str,
    *, actor_id: uuid.UUID | None = None, description: str | None = None, data: dict | None = None,
) -> None:
    db.add(AviAviaryEvent(
        id=uuid.uuid4(), aviary_id=aviary_id, event_type=event_type,
        occurred_on=date.today(), title=title, description=description,
        data=data or {}, actor_id=actor_id,
    ))
    await db.flush()


# ── Aviary CRUD ───────────────────────────────────────────────────────────────

async def create_aviary(db: AsyncSession, farm: Farm, data: AviaryCreate, user: User) -> AviAviary:
    aviary = AviAviary(
        id=uuid.uuid4(), farm_id=farm.id, name=data.name, code=data.code,
        aviary_type=data.aviary_type, building=data.building, purpose=data.purpose,
        biosecurity_level=data.biosecurity_level, capacity=data.capacity,
        dimensions=data.dimensions, environment=data.environment, status=data.status,
        notes=data.notes, created_by=user.id,
    )
    db.add(aviary)
    await db.flush()
    await _append_event(db, aviary.id, "created", f"Aviary '{data.name}' created", actor_id=user.id)
    await audit_service.log_action(
        db, action="avi.aviary.create", resource_type="avi_aviary",
        resource_id=aviary.id, farm_id=farm.id, user_id=user.id, new_value={"name": data.name},
    )
    await db.commit()
    await db.refresh(aviary)
    return aviary


async def list_aviaries(
    db: AsyncSession, farm_id: uuid.UUID, *, purpose: str | None = None, status: str | None = None,
    search: str | None = None, include_inactive: bool = True, limit: int = 100, offset: int = 0,
) -> tuple[list[AviAviary], int, dict[uuid.UUID, int]]:
    conds = [AviAviary.farm_id == farm_id, AviAviary.deleted_at.is_(None)]
    if purpose:
        conds.append(AviAviary.purpose == purpose)
    if status:
        conds.append(AviAviary.status == status)
    elif not include_inactive:
        conds.append(AviAviary.status == "active")
    if search:
        like = f"%{search}%"
        conds.append(or_(AviAviary.name.ilike(like), AviAviary.code.ilike(like), AviAviary.building.ilike(like)))

    total = (await db.execute(select(func.count(AviAviary.id)).where(*conds))).scalar_one()
    rows = list((await db.execute(
        select(AviAviary).where(*conds).order_by(AviAviary.name).limit(limit).offset(offset)
    )).scalars().all())

    # Batch occupancy: one grouped query for the listed aviaries.
    occ: dict[uuid.UUID, int] = {}
    if rows:
        ids = [a.id for a in rows]
        occ_rows = await db.execute(
            select(AviBird.aviary_id, func.count(AviBird.id)).where(
                AviBird.aviary_id.in_(ids), AviBird.status == "active", AviBird.deleted_at.is_(None)
            ).group_by(AviBird.aviary_id)
        )
        occ = {r[0]: r[1] for r in occ_rows}
    return rows, total, occ


async def get_aviary_detail(db: AsyncSession, farm_id: uuid.UUID, aviary_id: uuid.UUID):
    aviary = await _get_aviary_or_404(db, farm_id, aviary_id)
    occupied = await _occupied_count(db, aviary_id)
    occupancy = aviary_engine.compute_occupancy(aviary.capacity, occupied)

    readings = list((await db.execute(
        select(AviEnvironmentalReading).where(
            AviEnvironmentalReading.aviary_id == aviary_id,
            AviEnvironmentalReading.deleted_at.is_(None),
        ).order_by(AviEnvironmentalReading.recorded_at.desc()).limit(50)
    )).scalars().all())
    env_summary = aviary_engine.summarize_environment(
        [{"temperature_c": r.temperature_c, "humidity_pct": r.humidity_pct,
          "light_hours": r.light_hours, "recorded_at": r.recorded_at.isoformat()} for r in readings],
        targets=_species_targets_for(aviary),
    )

    tasks = list((await db.execute(
        select(AviAviaryTask).where(
            AviAviaryTask.aviary_id == aviary_id, AviAviaryTask.deleted_at.is_(None)
        )
    )).scalars().all())
    cleaning = aviary_engine.cleaning_status(
        [{"task_type": t.task_type, "status": t.status,
          "scheduled_for": t.scheduled_for, "completed_on": t.completed_on} for t in tasks],
        date.today(),
    )

    housing = aviary_engine.assess_housing(
        {"aviary_type": aviary.aviary_type, "environment": aviary.environment},
        await _occupant_species_profile(db, aviary_id),
    )

    zone_count = (await db.execute(
        select(func.count(AviAviaryZone.id)).where(
            AviAviaryZone.aviary_id == aviary_id, AviAviaryZone.deleted_at.is_(None))
    )).scalar_one()
    fixture_count = (await db.execute(
        select(func.count(AviAviaryFixture.id)).where(
            AviAviaryFixture.aviary_id == aviary_id, AviAviaryFixture.deleted_at.is_(None))
    )).scalar_one()

    return aviary, occupancy, env_summary, cleaning, housing, zone_count, fixture_count


def _species_targets_for(aviary: AviAviary) -> dict | None:
    """Environmental targets, if the aviary's own environment declares them."""
    env = aviary.environment or {}
    keys = ("temp_min", "temp_max", "humidity_min", "humidity_max")
    if any(env.get(k) is not None for k in keys):
        return {k: env.get(k) for k in keys}
    return None


async def _occupant_species_profile(db: AsyncSession, aviary_id: uuid.UUID) -> dict | None:
    """The profile of the (single) species housed here, when unambiguous."""
    rows = await db.execute(
        select(AviBird.species_id, func.count(AviBird.id)).where(
            AviBird.aviary_id == aviary_id, AviBird.status == "active", AviBird.deleted_at.is_(None)
        ).group_by(AviBird.species_id)
    )
    species_ids = [r[0] for r in rows]
    if len(species_ids) != 1:
        return None
    sp = (await db.execute(select(AviSpecies).where(AviSpecies.id == species_ids[0]))).scalar_one_or_none()
    return sp.profile if sp else None


async def update_aviary(
    db: AsyncSession, farm_id: uuid.UUID, aviary_id: uuid.UUID, data: AviaryUpdate, user: User
) -> AviAviary:
    aviary = await _get_aviary_or_404(db, farm_id, aviary_id)
    fields = data.model_dump(exclude_unset=True)
    changed = {}
    for field, value in fields.items():
        if getattr(aviary, field) != value:
            changed[field] = value
            setattr(aviary, field, value)
    if changed:
        await db.flush()
        await _append_event(db, aviary.id, "updated", "Aviary updated", actor_id=user.id, data={"changed": list(changed)})
        await audit_service.log_action(
            db, action="avi.aviary.update", resource_type="avi_aviary",
            resource_id=aviary.id, farm_id=farm_id, user_id=user.id, new_value={"changed": list(changed)},
        )
        await db.commit()
        await db.refresh(aviary)
    return aviary


async def archive_aviary(db: AsyncSession, farm_id: uuid.UUID, aviary_id: uuid.UUID, user: User) -> AviAviary:
    aviary = await _get_aviary_or_404(db, farm_id, aviary_id)
    occupied = await _occupied_count(db, aviary_id)
    if occupied > 0:
        raise ConflictException(
            f"Cannot deactivate '{aviary.name}': {occupied} bird(s) still housed here. Move them first."
        )
    aviary.status = "inactive"
    await db.flush()
    await _append_event(db, aviary.id, "archived", "Aviary deactivated", actor_id=user.id)
    await audit_service.log_action(
        db, action="avi.aviary.archive", resource_type="avi_aviary",
        resource_id=aviary.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(aviary)
    return aviary


# ── Zones & fixtures ──────────────────────────────────────────────────────────

async def add_zone(db, farm_id, aviary_id, data: ZoneCreate, user: User) -> AviAviaryZone:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    zone = AviAviaryZone(
        id=uuid.uuid4(), aviary_id=aviary_id, name=data.name, zone_type=data.zone_type,
        capacity=data.capacity, notes=data.notes, created_by=user.id,
    )
    db.add(zone)
    await db.flush()
    await audit_service.log_action(db, action="avi.zone.create", resource_type="avi_aviary_zone",
                                   resource_id=zone.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(zone)
    return zone


async def list_zones(db, farm_id, aviary_id) -> list[AviAviaryZone]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    return list((await db.execute(
        select(AviAviaryZone).where(AviAviaryZone.aviary_id == aviary_id, AviAviaryZone.deleted_at.is_(None))
        .order_by(AviAviaryZone.name)
    )).scalars().all())


async def add_fixture(db, farm_id, aviary_id, data: FixtureCreate, user: User) -> AviAviaryFixture:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    if data.zone_id is not None:
        z = await db.execute(select(AviAviaryZone.id).where(
            AviAviaryZone.id == data.zone_id, AviAviaryZone.aviary_id == aviary_id,
            AviAviaryZone.deleted_at.is_(None)))
        if z.scalar_one_or_none() is None:
            raise NotFoundException("Zone not found in this aviary.")
    fixture = AviAviaryFixture(
        id=uuid.uuid4(), aviary_id=aviary_id, zone_id=data.zone_id, fixture_type=data.fixture_type,
        label=data.label, quantity=data.quantity, status=data.status, details=data.details, created_by=user.id,
    )
    db.add(fixture)
    await db.flush()
    await audit_service.log_action(db, action="avi.fixture.create", resource_type="avi_aviary_fixture",
                                   resource_id=fixture.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(fixture)
    return fixture


async def list_fixtures(db, farm_id, aviary_id, fixture_type: str | None = None) -> list[AviAviaryFixture]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    conds = [AviAviaryFixture.aviary_id == aviary_id, AviAviaryFixture.deleted_at.is_(None)]
    if fixture_type:
        conds.append(AviAviaryFixture.fixture_type == fixture_type)
    return list((await db.execute(
        select(AviAviaryFixture).where(*conds).order_by(AviAviaryFixture.fixture_type)
    )).scalars().all())


# ── Environmental readings ────────────────────────────────────────────────────

async def add_reading(db, farm_id, aviary_id, data: EnvironmentalReadingCreate, user: User) -> AviEnvironmentalReading:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    reading = AviEnvironmentalReading(
        id=uuid.uuid4(), aviary_id=aviary_id, temperature_c=data.temperature_c,
        humidity_pct=data.humidity_pct, light_hours=data.light_hours, air_quality=data.air_quality,
        noise_level=data.noise_level, notes=data.notes, recorded_by=user.id,
        **({"recorded_at": data.recorded_at} if data.recorded_at else {}),
    )
    db.add(reading)
    await db.flush()
    await audit_service.log_action(db, action="avi.environment.record", resource_type="avi_environmental_reading",
                                   resource_id=reading.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(reading)
    return reading


async def list_readings(db, farm_id, aviary_id, limit: int = 100) -> list[AviEnvironmentalReading]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    return list((await db.execute(
        select(AviEnvironmentalReading).where(
            AviEnvironmentalReading.aviary_id == aviary_id, AviEnvironmentalReading.deleted_at.is_(None)
        ).order_by(AviEnvironmentalReading.recorded_at.desc()).limit(limit)
    )).scalars().all())


# ── Cleaning / maintenance tasks ──────────────────────────────────────────────

_RECURRENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 91, "seasonal": 91}


async def add_task(db, farm_id, aviary_id, data: TaskCreate, user: User) -> AviAviaryTask:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    task = AviAviaryTask(
        id=uuid.uuid4(), aviary_id=aviary_id, task_type=data.task_type, title=data.title,
        status="scheduled", scheduled_for=data.scheduled_for, recurrence=data.recurrence,
        notes=data.notes, assigned_to=user.id, created_by=user.id,
    )
    db.add(task)
    await db.flush()
    await audit_service.log_action(db, action="avi.task.create", resource_type="avi_aviary_task",
                                   resource_id=task.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(task)
    return task


async def complete_task(db, farm_id, aviary_id, task_id, data: TaskComplete, user: User) -> AviAviaryTask:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    task = (await db.execute(select(AviAviaryTask).where(
        AviAviaryTask.id == task_id, AviAviaryTask.aviary_id == aviary_id,
        AviAviaryTask.deleted_at.is_(None)))).scalar_one_or_none()
    if task is None:
        raise NotFoundException("Task not found.")
    if task.status == "completed":
        raise ConflictException("Task is already completed.")
    on = data.completed_on or date.today()
    task.status = "completed"
    task.completed_on = on
    task.performed_by = user.id
    if data.notes:
        task.notes = data.notes
    await db.flush()

    # Deterministic recurrence: seed the next occurrence (never silently mutate).
    step = _RECURRENCE_DAYS.get(task.recurrence)
    if step:
        base = task.scheduled_for or on
        db.add(AviAviaryTask(
            id=uuid.uuid4(), aviary_id=aviary_id, task_type=task.task_type, title=task.title,
            status="scheduled", scheduled_for=base + timedelta(days=step),
            recurrence=task.recurrence, notes=task.notes, assigned_to=task.assigned_to, created_by=user.id,
        ))
    await _append_event(db, aviary_id, "task_completed",
                        f"{task.task_type.capitalize()} completed: {task.title}", actor_id=user.id)
    await audit_service.log_action(db, action="avi.task.complete", resource_type="avi_aviary_task",
                                   resource_id=task.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(db, farm_id, aviary_id, status: str | None = None) -> list[AviAviaryTask]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    conds = [AviAviaryTask.aviary_id == aviary_id, AviAviaryTask.deleted_at.is_(None)]
    if status:
        conds.append(AviAviaryTask.status == status)
    return list((await db.execute(
        select(AviAviaryTask).where(*conds).order_by(AviAviaryTask.scheduled_for.desc().nullslast())
    )).scalars().all())


# ── Timeline & media ──────────────────────────────────────────────────────────

async def list_events(db, farm_id, aviary_id, limit: int = 100) -> list[AviAviaryEvent]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    return list((await db.execute(
        select(AviAviaryEvent).where(AviAviaryEvent.aviary_id == aviary_id, AviAviaryEvent.deleted_at.is_(None))
        .order_by(AviAviaryEvent.occurred_on.desc(), AviAviaryEvent.created_at.desc()).limit(limit)
    )).scalars().all())


async def add_media(db, farm_id, aviary_id, data, user: User) -> AviAviaryMedia:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    media = AviAviaryMedia(
        id=uuid.uuid4(), aviary_id=aviary_id, media_type=data.media_type, url=data.url,
        caption=data.caption, is_primary=data.is_primary, uploaded_by=user.id,
    )
    db.add(media)
    await db.flush()
    await audit_service.log_action(db, action="avi.aviary.media.add", resource_type="avi_aviary_media",
                                   resource_id=media.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(media)
    return media


async def list_media(db, farm_id, aviary_id) -> list[AviAviaryMedia]:
    await _get_aviary_or_404(db, farm_id, aviary_id)
    return list((await db.execute(
        select(AviAviaryMedia).where(AviAviaryMedia.aviary_id == aviary_id, AviAviaryMedia.deleted_at.is_(None))
        .order_by(AviAviaryMedia.is_primary.desc(), AviAviaryMedia.created_at.desc())
    )).scalars().all())


# ── Infrastructure summary (Mission Control / ARIA read this) ─────────────────

async def infrastructure_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Deterministic farm-wide infrastructure snapshot. Read-only; the strategic
    layer (Mission Control, Part 11) consumes this rather than recomputing —
    honouring 'Mission Control must understand available infrastructure'."""
    aviaries = list((await db.execute(
        select(AviAviary).where(
            AviAviary.farm_id == farm_id, AviAviary.deleted_at.is_(None), AviAviary.status == "active")
    )).scalars().all())

    occ_rows = await db.execute(
        select(AviBird.aviary_id, func.count(AviBird.id)).where(
            AviBird.farm_id == farm_id, AviBird.status == "active", AviBird.deleted_at.is_(None),
            AviBird.aviary_id.isnot(None),
        ).group_by(AviBird.aviary_id)
    )
    occ = {r[0]: r[1] for r in occ_rows}

    total_capacity = sum(a.capacity for a in aviaries if a.capacity is not None)
    capacity_known = all(a.capacity is not None for a in aviaries) if aviaries else True
    total_occupied = sum(occ.get(a.id, 0) for a in aviaries)
    by_purpose: dict[str, int] = {}
    for a in aviaries:
        by_purpose[a.purpose] = by_purpose.get(a.purpose, 0) + 1

    return {
        "aviary_count": len(aviaries),
        "total_capacity": aviary_engine.Labelled(
            aviary_engine.RECORDED if capacity_known else aviary_engine.UNKNOWN,
            total_capacity if aviaries else 0,
            "Sum of recorded aviary capacities." if capacity_known else "Some aviaries have no recorded capacity.",
        ).as_dict(),
        "total_occupied": aviary_engine.Labelled(
            aviary_engine.RECORDED, total_occupied, "Active birds assigned to an aviary.").as_dict(),
        "available": aviary_engine.Labelled(
            aviary_engine.CALCULATED if capacity_known else aviary_engine.UNKNOWN,
            (total_capacity - total_occupied) if capacity_known else None,
            "capacity − occupied across active aviaries.").as_dict(),
        "by_purpose": by_purpose,
        "quarantine_aviaries": sum(1 for a in aviaries if a.purpose == "quarantine" or a.biosecurity_level == "quarantine"),
    }
