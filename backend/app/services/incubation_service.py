"""
Greena — Incubation Service (Module 15, Part 5)

Writes for the hatch process. Schedule/progress/statistics come from the pure
``incubation_engine`` (Doc 14 §2); this service loads records, calls the engine,
and records history. A hatched egg produces a real ``AviBird`` chick linked to
its pair as parents — reusing the bird aggregate and its timeline rather than
inventing a parallel "chick" entity (Doc 14 §1).
"""

import uuid
from datetime import date

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.aviculture import (
    AviBird,
    AviBirdEvent,
    AviCandlingRecord,
    AviClutch,
    AviEgg,
    AviHatchEvent,
    AviIncubationBatch,
    AviIncubationLog,
    AviPair,
    AviSpecies,
)
from app.schemas.aviculture_incubation import (
    BatchCreate,
    CandlingCreate,
    ClutchCreate,
    EggCreate,
    EggUpdate,
    HatchCreate,
    IncubationLogCreate,
    SetEggsRequest,
)
from app.services import audit_service, incubation_engine
from app.services.aviculture_service import _generate_internal_ref


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_batch_or_404(db, farm_id, batch_id) -> AviIncubationBatch:
    b = (await db.execute(select(AviIncubationBatch).where(
        AviIncubationBatch.id == batch_id, AviIncubationBatch.farm_id == farm_id,
        AviIncubationBatch.deleted_at.is_(None)))).scalar_one_or_none()
    if b is None:
        raise NotFoundException("Incubation batch not found on this farm.")
    return b


async def _get_egg_or_404(db, farm_id, egg_id) -> AviEgg:
    e = (await db.execute(select(AviEgg).where(
        AviEgg.id == egg_id, AviEgg.farm_id == farm_id, AviEgg.deleted_at.is_(None)))).scalar_one_or_none()
    if e is None:
        raise NotFoundException("Egg not found on this farm.")
    return e


async def _species_profile(db, species_id) -> dict | None:
    if species_id is None:
        return None
    sp = (await db.execute(select(AviSpecies).where(AviSpecies.id == species_id))).scalar_one_or_none()
    return sp.profile if sp else None


async def _egg_dicts_for_batch(db, batch_id) -> list[dict]:
    rows = await db.execute(
        select(AviEgg.status, AviEgg.fertility_status).where(
            AviEgg.batch_id == batch_id, AviEgg.deleted_at.is_(None)))
    return [{"status": r[0], "fertility_status": r[1]} for r in rows]


# ── Clutch ────────────────────────────────────────────────────────────────────

async def create_clutch(db, farm: Farm, data: ClutchCreate, user: User) -> AviClutch:
    if data.pair_id is not None:
        p = (await db.execute(select(AviPair.id).where(
            AviPair.id == data.pair_id, AviPair.farm_id == farm.id, AviPair.deleted_at.is_(None)))).scalar_one_or_none()
        if p is None:
            raise NotFoundException("Pair not found on this farm.")
    clutch = AviClutch(id=uuid.uuid4(), farm_id=farm.id, pair_id=data.pair_id, name=data.name,
                       laid_start=data.laid_start, expected_eggs=data.expected_eggs, notes=data.notes,
                       created_by=user.id)
    db.add(clutch)
    await db.flush()
    await audit_service.log_action(db, action="avi.clutch.create", resource_type="avi_clutch",
                                   resource_id=clutch.id, farm_id=farm.id, user_id=user.id)
    await db.commit()
    await db.refresh(clutch)
    return clutch


async def list_clutches(db, farm_id) -> tuple[list[AviClutch], dict]:
    rows = list((await db.execute(select(AviClutch).where(
        AviClutch.farm_id == farm_id, AviClutch.deleted_at.is_(None)).order_by(AviClutch.created_at.desc()))).scalars().all())
    counts: dict = {}
    if rows:
        crows = await db.execute(select(AviEgg.clutch_id, func.count(AviEgg.id)).where(
            AviEgg.clutch_id.in_([c.id for c in rows]), AviEgg.deleted_at.is_(None)).group_by(AviEgg.clutch_id))
        counts = {r[0]: r[1] for r in crows}
    return rows, counts


# ── Egg ───────────────────────────────────────────────────────────────────────

async def _generate_egg_identifier(db, farm_id) -> str:
    n = ((await db.execute(select(func.count(AviEgg.id)).where(AviEgg.farm_id == farm_id))).scalar_one() or 0) + 1
    return f"EGG-{n:05d}"


async def create_egg(db, farm: Farm, data: EggCreate, user: User) -> AviEgg:
    species_id = data.species_id
    if data.pair_id is not None:
        pair = (await db.execute(select(AviPair).where(
            AviPair.id == data.pair_id, AviPair.farm_id == farm.id, AviPair.deleted_at.is_(None)))).scalar_one_or_none()
        if pair is None:
            raise NotFoundException("Pair not found on this farm.")
        # Infer species from the pair's male bird when not given.
        if species_id is None and pair.male_bird_id is not None:
            mb = (await db.execute(select(AviBird.species_id).where(AviBird.id == pair.male_bird_id))).scalar_one_or_none()
            species_id = mb
    identifier = data.identifier or await _generate_egg_identifier(db, farm.id)
    egg = AviEgg(
        id=uuid.uuid4(), farm_id=farm.id, clutch_id=data.clutch_id, pair_id=data.pair_id,
        species_id=species_id, identifier=identifier, laid_on=data.laid_on, weight_grams=data.weight_grams,
        length_mm=data.length_mm, width_mm=data.width_mm, quality=data.quality, source=data.source,
        storage_location=data.storage_location, status="collected", notes=data.notes, created_by=user.id,
    )
    db.add(egg)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover
        await db.rollback()
        raise ConflictException("Duplicate egg identifier.") from exc
    await audit_service.log_action(db, action="avi.egg.create", resource_type="avi_egg",
                                   resource_id=egg.id, farm_id=farm.id, user_id=user.id,
                                   new_value={"identifier": identifier})
    await db.commit()
    await db.refresh(egg)
    return egg


async def list_eggs(db, farm_id, *, batch_id=None, clutch_id=None, status=None, limit=100, offset=0):
    conds = [AviEgg.farm_id == farm_id, AviEgg.deleted_at.is_(None)]
    if batch_id:
        conds.append(AviEgg.batch_id == batch_id)
    if clutch_id:
        conds.append(AviEgg.clutch_id == clutch_id)
    if status:
        conds.append(AviEgg.status == status)
    total = (await db.execute(select(func.count(AviEgg.id)).where(*conds))).scalar_one()
    rows = list((await db.execute(select(AviEgg).where(*conds).order_by(
        AviEgg.created_at.desc()).limit(limit).offset(offset))).scalars().all())
    return rows, total


async def update_egg(db, farm_id, egg_id, data: EggUpdate, user: User) -> AviEgg:
    egg = await _get_egg_or_404(db, farm_id, egg_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(egg, field, value)
    await db.flush()
    await audit_service.log_action(db, action="avi.egg.update", resource_type="avi_egg",
                                   resource_id=egg.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(egg)
    return egg


# ── Batch ─────────────────────────────────────────────────────────────────────

async def create_batch(db, farm: Farm, data: BatchCreate, user: User) -> AviIncubationBatch:
    profile = await _species_profile(db, data.species_id)
    sched = incubation_engine.incubation_schedule(
        profile, data.set_on,
        override_days=data.incubation_days,
        override_temp=float(data.target_temperature_c) if data.target_temperature_c is not None else None,
        override_humidity=float(data.target_humidity_pct) if data.target_humidity_pct is not None else None,
    )
    days = sched["incubation_days"]["value"]
    lockdown = sched["expected_lockdown_on"]["value"]
    hatch = sched["expected_hatch_on"]["value"]

    batch = AviIncubationBatch(
        id=uuid.uuid4(), farm_id=farm.id, species_id=data.species_id, name=data.name, method=data.method,
        incubator_label=data.incubator_label, set_on=data.set_on,
        incubation_days=days, target_temperature_c=data.target_temperature_c,
        target_humidity_pct=data.target_humidity_pct,
        expected_lockdown_on=date.fromisoformat(lockdown) if lockdown else None,
        expected_hatch_on=date.fromisoformat(hatch) if hatch else None,
        turning_schedule={"turning_per_day": sched["turning_per_day"]["value"]},
        status="incubating" if data.set_on else "setting", notes=data.notes, created_by=user.id,
    )
    db.add(batch)
    await db.flush()
    await audit_service.log_action(db, action="avi.batch.create", resource_type="avi_incubation_batch",
                                   resource_id=batch.id, farm_id=farm.id, user_id=user.id,
                                   new_value={"name": data.name})
    await db.commit()
    await db.refresh(batch)
    return batch


async def list_batches(db, farm_id, status=None) -> tuple[list[AviIncubationBatch], dict]:
    conds = [AviIncubationBatch.farm_id == farm_id, AviIncubationBatch.deleted_at.is_(None)]
    if status:
        conds.append(AviIncubationBatch.status == status)
    rows = list((await db.execute(select(AviIncubationBatch).where(*conds).order_by(
        AviIncubationBatch.created_at.desc()))).scalars().all())
    counts: dict = {}
    if rows:
        crows = await db.execute(select(AviEgg.batch_id, func.count(AviEgg.id)).where(
            AviEgg.batch_id.in_([b.id for b in rows]), AviEgg.deleted_at.is_(None)).group_by(AviEgg.batch_id))
        counts = {r[0]: r[1] for r in crows}
    return rows, counts


async def get_batch_detail(db, farm_id, batch_id):
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    egg_dicts = await _egg_dicts_for_batch(db, batch_id)
    schedule = incubation_engine.incubation_schedule(
        await _species_profile(db, batch.species_id), batch.set_on, override_days=batch.incubation_days,
        override_temp=float(batch.target_temperature_c) if batch.target_temperature_c is not None else None,
        override_humidity=float(batch.target_humidity_pct) if batch.target_humidity_pct is not None else None,
    )
    progress = incubation_engine.incubation_progress(batch.set_on, batch.incubation_days, date.today(), batch.status)
    stats = incubation_engine.hatch_statistics(egg_dicts)
    return batch, schedule, progress, stats, len(egg_dicts)


async def set_eggs(db, farm_id, batch_id, data: SetEggsRequest, user: User) -> int:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    on = data.set_on or batch.set_on or date.today()
    count = 0
    for egg_id in data.egg_ids:
        egg = await _get_egg_or_404(db, farm_id, egg_id)
        if egg.status in ("hatched", "failed", "discarded"):
            raise ConflictException(f"Egg {egg.identifier} is {egg.status} and cannot be set.")
        egg.batch_id = batch_id
        egg.status = "set"
        egg.set_on = on
        if egg.species_id is None:
            egg.species_id = batch.species_id
        count += 1
    if batch.set_on is None:
        batch.set_on = on
        batch.status = "incubating"
        # Recompute the schedule now that a set date exists.
        sched = incubation_engine.incubation_schedule(
            await _species_profile(db, batch.species_id), on, override_days=batch.incubation_days)
        lockdown = sched["expected_lockdown_on"]["value"]
        hatch = sched["expected_hatch_on"]["value"]
        batch.expected_lockdown_on = date.fromisoformat(lockdown) if lockdown else None
        batch.expected_hatch_on = date.fromisoformat(hatch) if hatch else None
    await db.flush()
    await audit_service.log_action(db, action="avi.batch.set_eggs", resource_type="avi_incubation_batch",
                                   resource_id=batch_id, farm_id=farm_id, user_id=user.id,
                                   new_value={"eggs_set": count})
    await db.commit()
    return count


async def add_log(db, farm_id, batch_id, data: IncubationLogCreate, user: User) -> AviIncubationLog:
    await _get_batch_or_404(db, farm_id, batch_id)
    log = AviIncubationLog(id=uuid.uuid4(), batch_id=batch_id, log_date=data.log_date or date.today(),
                           temperature_c=data.temperature_c, humidity_pct=data.humidity_pct,
                           turns_count=data.turns_count, notes=data.notes, recorded_by=user.id)
    db.add(log)
    await db.flush()
    await audit_service.log_action(db, action="avi.incubation.log", resource_type="avi_incubation_log",
                                   resource_id=log.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(log)
    return log


async def list_logs(db, farm_id, batch_id) -> list[AviIncubationLog]:
    await _get_batch_or_404(db, farm_id, batch_id)
    return list((await db.execute(select(AviIncubationLog).where(
        AviIncubationLog.batch_id == batch_id, AviIncubationLog.deleted_at.is_(None)).order_by(
        AviIncubationLog.log_date.desc()))).scalars().all())


# ── Candling ──────────────────────────────────────────────────────────────────

async def add_candling(db, farm_id, egg_id, data: CandlingCreate, user: User) -> AviCandlingRecord:
    egg = await _get_egg_or_404(db, farm_id, egg_id)
    on = data.candled_on or date.today()
    day = incubation_engine.candling_day(egg.set_on, on)
    rec = AviCandlingRecord(id=uuid.uuid4(), egg_id=egg_id, candled_on=on, day_number=day,
                            result=data.result, notes=data.notes, recorded_by=user.id)
    db.add(rec)
    # Reflect a definitive candling result onto the egg's recorded fertility/status.
    if data.result in ("fertile", "infertile", "early_death", "late_death"):
        egg.fertility_status = data.result if data.result != "developing" else egg.fertility_status
    if egg.status == "set":
        egg.status = "candled"
    await db.flush()
    await audit_service.log_action(db, action="avi.egg.candle", resource_type="avi_candling_record",
                                   resource_id=rec.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(rec)
    return rec


async def list_candling(db, farm_id, egg_id) -> list[AviCandlingRecord]:
    await _get_egg_or_404(db, farm_id, egg_id)
    return list((await db.execute(select(AviCandlingRecord).where(
        AviCandlingRecord.egg_id == egg_id, AviCandlingRecord.deleted_at.is_(None)).order_by(
        AviCandlingRecord.candled_on.desc()))).scalars().all())


# ── Hatch ─────────────────────────────────────────────────────────────────────

async def record_hatch(db, farm_id, egg_id, data: HatchCreate, user: User) -> AviHatchEvent:
    egg = await _get_egg_or_404(db, farm_id, egg_id)
    if egg.status in ("hatched", "failed", "discarded"):
        raise ConflictException(f"Egg {egg.identifier} already has a final outcome ({egg.status}).")
    on = data.hatched_on or date.today()
    is_hatch = data.outcome in ("hatched", "assisted")

    chick_id = None
    if is_hatch and data.create_chick:
        # Reuse the bird aggregate: the chick becomes a first-class AviBird whose
        # parents are the egg's pair (Doc 14 §1 — no parallel "chick" entity).
        sire_id = dam_id = None
        if egg.pair_id is not None:
            pair = (await db.execute(select(AviPair).where(AviPair.id == egg.pair_id))).scalar_one_or_none()
            if pair is not None:
                sire_id, dam_id = pair.male_bird_id, pair.female_bird_id
        species_id = egg.species_id
        if species_id is None:
            raise ValidationException("Cannot create a chick without a species — set the egg's species first.")
        internal_ref = await _generate_internal_ref(db, farm_id)
        chick = AviBird(
            id=uuid.uuid4(), farm_id=farm_id, species_id=species_id, internal_ref=internal_ref,
            name=data.chick_name, sex="unknown", lifecycle_stage="chick", status="active",
            acquisition_type="bred", acquired_on=on, hatch_date=on, sire_id=sire_id, dam_id=dam_id,
            created_by=user.id,
        )
        db.add(chick)
        await db.flush()
        db.add(AviBirdEvent(id=uuid.uuid4(), bird_id=chick.id, event_type="created",
                            occurred_on=on, title=f"Hatched from egg {egg.identifier}",
                            data={"egg_id": str(egg.id), "assisted": data.assisted}, actor_id=user.id))
        chick_id = chick.id
        egg.hatched_bird_id = chick.id

    egg.status = "hatched" if is_hatch else "failed"

    event = AviHatchEvent(
        id=uuid.uuid4(), egg_id=egg_id, batch_id=egg.batch_id, hatched_on=on if is_hatch else None,
        outcome=data.outcome, assisted=data.assisted, chick_bird_id=chick_id,
        hatch_weight_grams=data.hatch_weight_grams, failure_reason=data.failure_reason,
        notes=data.notes, recorded_by=user.id,
    )
    db.add(event)
    await db.flush()
    await audit_service.log_action(db, action="avi.egg.hatch", resource_type="avi_hatch_event",
                                   resource_id=event.id, farm_id=farm_id, user_id=user.id,
                                   new_value={"outcome": data.outcome, "chick_bird_id": str(chick_id) if chick_id else None})
    await db.commit()
    await db.refresh(event)
    return event


async def list_hatch_events(db, farm_id, batch_id) -> list[AviHatchEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    return list((await db.execute(select(AviHatchEvent).where(
        AviHatchEvent.batch_id == batch_id, AviHatchEvent.deleted_at.is_(None)).order_by(
        AviHatchEvent.created_at.desc()))).scalars().all())
