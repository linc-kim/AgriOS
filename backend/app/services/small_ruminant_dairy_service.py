"""
Greena — Small Ruminant Dairy Service (Modules 18/19, Milestone 6, Goat dairy)

Lactation cycles and milk records for dairy females. This is the first
species-specific milestone, but it stays on the shared foundation: availability is
gated by the species ``produces_milk`` capability (goats primarily; dairy sheep
too), not forked into a goat-only module. All yield/stage/dry-off math is delegated
to the PURE :mod:`small_ruminant_lactation_engine`. Milk records are immutable.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

from app.exceptions import ConflictException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminantLactation,
    SmallRuminantMilkRecord,
)
from app.schemas.small_ruminant import LactationStartInput, MilkRecordCreate
from app.services import audit_service
from app.services import small_ruminant_lactation_engine as eng
from app.services import small_ruminant_species_config as cfg
from app.services.small_ruminant_service import _append_event, _get_animal_or_404


def _require_dairy(species: str) -> None:
    """Guard: the dairy workspace applies only to milk-producing species."""
    if not cfg.produces_milk(species):
        raise ValidationException(f"Dairy is not applicable to {species} in this workspace.")


def _at(on: date) -> datetime:
    return datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc)


async def _get_lactation_or_404(db, farm_id, species, lactation_id) -> SmallRuminantLactation:
    from app.exceptions import NotFoundException
    result = await db.execute(
        select(SmallRuminantLactation).where(
            SmallRuminantLactation.id == lactation_id, SmallRuminantLactation.farm_id == farm_id,
            SmallRuminantLactation.species == species, SmallRuminantLactation.deleted_at.is_(None),
        )
    )
    lac = result.scalar_one_or_none()
    if lac is None:
        raise NotFoundException(f"Lactation {lactation_id} not found on this farm.")
    return lac


async def _active_lactation(db, animal_id) -> SmallRuminantLactation | None:
    result = await db.execute(
        select(SmallRuminantLactation).where(
            SmallRuminantLactation.animal_id == animal_id,
            SmallRuminantLactation.status == "active",
            SmallRuminantLactation.deleted_at.is_(None),
        ).order_by(SmallRuminantLactation.freshening_date.desc())
    )
    return result.scalars().first()


# ── Lactation cycle ────────────────────────────────────────────────────────────

async def start_lactation(db, farm: Farm, species: str, animal_id, data: LactationStartInput, user: User):
    _require_dairy(species)
    animal = await _get_animal_or_404(db, farm.id, species, animal_id)
    if await _active_lactation(db, animal_id) is not None:
        raise ConflictException("This animal already has an active lactation; dry her off first.")

    # Auto-number: previous lactations + 1 (recorded fact).
    prev = await db.execute(
        select(func.count(SmallRuminantLactation.id)).where(
            SmallRuminantLactation.animal_id == animal_id, SmallRuminantLactation.deleted_at.is_(None)
        )
    )
    number = data.lactation_number or ((prev.scalar_one() or 0) + 1)
    expected_dry = data.freshening_date + timedelta(days=eng.STANDARD_LACTATION_DAYS)

    lac = SmallRuminantLactation(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id, birth_id=data.birth_id,
        lactation_number=number, freshening_date=data.freshening_date,
        expected_dry_off_date=expected_dry, milking_frequency=data.milking_frequency,
        status="active", notes=data.notes, created_by=user.id,
    )
    db.add(lac)
    animal.reproductive_status = "lactating"
    await db.flush()
    await _append_event(db, animal_id, "note", f"Lactation #{number} started (freshening)",
                        occurred_at=_at(data.freshening_date), operator_id=user.id,
                        details={"lactation_id": str(lac.id), "lactation_number": number})
    await audit_service.log_action(
        db, action=f"sr.{species}.lactation.start", resource_type="sr_lactation",
        resource_id=lac.id, farm_id=farm.id, user_id=user.id, new_value={"lactation_number": number},
    )
    await db.commit()
    await db.refresh(lac)
    return lac


async def dry_off(db, farm: Farm, species: str, lactation_id, dry_off_date: date, user: User):
    _require_dairy(species)
    lac = await _get_lactation_or_404(db, farm.id, species, lactation_id)
    if lac.status != "active":
        raise ConflictException("This lactation is not active.")
    if dry_off_date < lac.freshening_date:
        raise ValidationException("Dry-off date cannot precede freshening.")
    lac.dry_off_date = dry_off_date
    lac.status = "completed"
    await db.flush()
    animal = await _get_animal_or_404(db, farm.id, species, lac.animal_id)
    animal.reproductive_status = "dry"
    await _append_event(db, lac.animal_id, "note", f"Lactation #{lac.lactation_number} dried off",
                        occurred_at=_at(dry_off_date), operator_id=user.id,
                        details={"lactation_id": str(lac.id)})
    await audit_service.log_action(
        db, action=f"sr.{species}.lactation.dry_off", resource_type="sr_lactation",
        resource_id=lac.id, farm_id=farm.id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(lac)
    return lac


async def list_lactations(db, farm_id, species, animal_id=None):
    conds = [SmallRuminantLactation.farm_id == farm_id, SmallRuminantLactation.species == species,
             SmallRuminantLactation.deleted_at.is_(None)]
    if animal_id is not None:
        await _get_animal_or_404(db, farm_id, species, animal_id)
        conds.append(SmallRuminantLactation.animal_id == animal_id)
    result = await db.execute(
        select(SmallRuminantLactation).where(*conds).order_by(SmallRuminantLactation.freshening_date.desc())
    )
    return list(result.scalars().all())


# ── Milk records ───────────────────────────────────────────────────────────────

async def record_milk(db, farm: Farm, species: str, animal_id, data: MilkRecordCreate, user: User):
    _require_dairy(species)
    await _get_animal_or_404(db, farm.id, species, animal_id)
    # Attach to the active lactation if one exists (recorded link, else None).
    lactation_id = data.lactation_id
    if lactation_id is None:
        active = await _active_lactation(db, animal_id)
        lactation_id = active.id if active else None

    rec = SmallRuminantMilkRecord(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id, lactation_id=lactation_id,
        recorded_on=data.recorded_on, session=data.session, quantity_liters=data.quantity_liters,
        fat_pct=data.fat_pct, protein_pct=data.protein_pct, somatic_cell_count=data.somatic_cell_count,
        notes=data.notes, recorded_by=user.id,
    )
    db.add(rec)
    await db.flush()
    await _append_event(db, animal_id, "milk_recorded", f"Milk {data.quantity_liters} L ({data.session})",
                        occurred_at=_at(data.recorded_on), operator_id=user.id,
                        details={"quantity_liters": str(data.quantity_liters), "session": data.session})
    await audit_service.log_action(
        db, action=f"sr.{species}.milk.record", resource_type="sr_milk_record",
        resource_id=rec.id, farm_id=farm.id, user_id=user.id,
        new_value={"quantity_liters": str(data.quantity_liters)},
    )
    await db.commit()
    await db.refresh(rec)
    return rec


async def list_milk(db, farm_id, species, *, animal_id=None, lactation_id=None, limit=200, offset=0):
    conds = [SmallRuminantMilkRecord.farm_id == farm_id, SmallRuminantMilkRecord.species == species,
             SmallRuminantMilkRecord.deleted_at.is_(None)]
    if animal_id:
        conds.append(SmallRuminantMilkRecord.animal_id == animal_id)
    if lactation_id:
        conds.append(SmallRuminantMilkRecord.lactation_id == lactation_id)
    result = await db.execute(
        select(SmallRuminantMilkRecord).where(*conds)
        .order_by(SmallRuminantMilkRecord.recorded_on.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def _milk_dicts(db, lactation_id=None, animal_id=None):
    conds = [SmallRuminantMilkRecord.deleted_at.is_(None)]
    if lactation_id:
        conds.append(SmallRuminantMilkRecord.lactation_id == lactation_id)
    if animal_id:
        conds.append(SmallRuminantMilkRecord.animal_id == animal_id)
    rows = await db.execute(
        select(SmallRuminantMilkRecord.recorded_on, SmallRuminantMilkRecord.quantity_liters,
               SmallRuminantMilkRecord.session).where(*conds)
    )
    return [{"recorded_on": r[0], "quantity_liters": r[1], "session": r[2]} for r in rows]


async def lactation_metrics(db, farm_id, species, lactation_id) -> dict:
    _require_dairy(species)
    lac = await _get_lactation_or_404(db, farm_id, species, lactation_id)
    records = await _milk_dicts(db, lactation_id=lactation_id)
    metrics = eng.lactation_metrics(lac.freshening_date, records, date.today(), dry_off_date=lac.dry_off_date)
    dim = metrics["days_in_milk"]["value"]
    avg = metrics["avg_daily_yield_l"]["value"]
    dry_rec = eng.dry_off_recommendation(dim, avg)
    return {"lactation_id": str(lactation_id), "lactation_number": lac.lactation_number,
            "status": lac.status, "metrics": metrics, "dry_off_recommendation": dry_rec}


async def dairy_summary(db, farm_id, species) -> dict:
    """Herd-level dairy roll-up from recorded milk facts."""
    _require_dairy(species)
    rows = await db.execute(
        select(SmallRuminantMilkRecord.animal_id, SmallRuminantMilkRecord.recorded_on,
               SmallRuminantMilkRecord.quantity_liters, SmallRuminantMilkRecord.session).where(
            SmallRuminantMilkRecord.farm_id == farm_id, SmallRuminantMilkRecord.species == species,
            SmallRuminantMilkRecord.deleted_at.is_(None),
        )
    )
    by_animal: dict = {}
    for aid, on, qty, session in rows:
        by_animal.setdefault(aid, []).append(
            {"recorded_on": on, "quantity_liters": qty, "session": session})
    active_lac = await db.execute(
        select(func.count(SmallRuminantLactation.id)).where(
            SmallRuminantLactation.farm_id == farm_id, SmallRuminantLactation.species == species,
            SmallRuminantLactation.status == "active", SmallRuminantLactation.deleted_at.is_(None),
        )
    )
    summary = eng.herd_milk_summary(by_animal, date.today())
    summary["active_lactations"] = {"label": eng.RECORDED, "value": active_lac.scalar_one() or 0,
                                    "detail": "Lactation cycles currently active."}
    return summary
