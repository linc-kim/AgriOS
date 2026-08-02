"""
Greena — Swine Farrowing & Litter Service (Module 20, Milestone 4)

Orchestrates the offspring lifecycle: farrowing → litter → (optional individual
pigs) → fostering → weaning. Litters carry aggregate counts so a smallholder manages
at litter level; the same flow lets a commercial farm individualise pigs (each an
``swine_pig`` linked via ``litter_id``). All performance math is delegated to the
PURE :mod:`swine_breeding_engine`. Every mutation appends the dam's timeline event +
an audit-log entry; history is immutable.
"""

import uuid

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineBreeding,
    SwineFarrowing,
    SwineFosterTransfer,
    SwineLitter,
    SwinePig,
    SwinePregnancy,
)
from app.schemas.swine import (
    FarrowingRecordInput,
    FosterTransferInput,
    LitterMortalityInput,
    PigletAddInput,
    WeaningInput,
)
from app.services import audit_service
from app.services import swine_breeding_engine as engine
from app.services.swine_service import (
    _append_event,
    _generate_internal_ref,
    _get_pig_or_404,
    record_movement,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_farrowing_or_404(db, farm_id, farrowing_id) -> SwineFarrowing:
    r = await db.execute(select(SwineFarrowing).where(
        SwineFarrowing.id == farrowing_id, SwineFarrowing.farm_id == farm_id,
        SwineFarrowing.deleted_at.is_(None)))
    obj = r.scalar_one_or_none()
    if obj is None:
        raise NotFoundException(f"Farrowing {farrowing_id} not found on this farm.")
    return obj


async def _get_litter_or_404(db, farm_id, litter_id) -> SwineLitter:
    r = await db.execute(select(SwineLitter).where(
        SwineLitter.id == litter_id, SwineLitter.farm_id == farm_id,
        SwineLitter.deleted_at.is_(None)))
    obj = r.scalar_one_or_none()
    if obj is None:
        raise NotFoundException(f"Litter {litter_id} not found on this farm.")
    return obj


async def _next_code(db, model, farm_id, prefix) -> str:
    r = await db.execute(select(func.count(model.id)).where(model.farm_id == farm_id))
    return f"{prefix}-{(r.scalar_one() or 0) + 1:05d}"


def _litter_dict(litter: SwineLitter) -> dict:
    return {"total_born": litter.total_born, "born_alive": litter.born_alive,
            "stillborn": litter.stillborn, "mummified": litter.mummified,
            "weaned": litter.weaned, "mortality": litter.mortality,
            "avg_birth_weight_kg": litter.avg_birth_weight_kg, "status": litter.status}


async def _create_piglet(db, farm, litter, spec: PigletAddInput, user) -> SwinePig:
    """Create one individual pig linked to a litter (production_stage=piglet)."""
    ref = spec.internal_ref or await _generate_internal_ref(db, farm.id)
    p = SwinePig(
        id=uuid.uuid4(), farm_id=farm.id, internal_ref=ref, name=spec.name,
        ear_notch=spec.ear_notch, sex="unknown", birth_sex=spec.birth_sex,
        production_stage="piglet", status="active", acquisition_type="bred",
        litter_id=litter.id, dam_id=litter.dam_id, sire_id=litter.sire_id,
        nurse_dam_id=litter.nurse_dam_id, date_of_birth=None, birth_weight_kg=spec.birth_weight_kg,
        created_by=user.id,
    )
    db.add(p)
    await db.flush()
    await _append_event(db, p.id, "created", f"Piglet {ref} registered from litter {litter.litter_code}",
                        operator_id=user.id, details={"litter_id": str(litter.id)})
    return p


# ── Farrowing ──────────────────────────────────────────────────────────────────

async def record_farrowing(db, farm: Farm, data: FarrowingRecordInput, user: User):
    """Record a farrowing and its litter, resolving the pregnancy/breeding it comes
    from, and optionally creating individual piglet records."""
    pregnancy = None
    breeding = None
    if data.pregnancy_id is not None:
        r = await db.execute(select(SwinePregnancy).where(
            SwinePregnancy.id == data.pregnancy_id, SwinePregnancy.farm_id == farm.id,
            SwinePregnancy.deleted_at.is_(None)))
        pregnancy = r.scalar_one_or_none()
        if pregnancy is None:
            raise NotFoundException(f"Pregnancy {data.pregnancy_id} not found on this farm.")
        if pregnancy.status == "farrowed":
            raise ConflictException("This pregnancy has already farrowed.")
    if data.breeding_id is not None:
        r = await db.execute(select(SwineBreeding).where(
            SwineBreeding.id == data.breeding_id, SwineBreeding.farm_id == farm.id,
            SwineBreeding.deleted_at.is_(None)))
        breeding = r.scalar_one_or_none()
        if breeding is None:
            raise NotFoundException(f"Breeding {data.breeding_id} not found on this farm.")
    if pregnancy is not None and breeding is None and pregnancy.breeding_id:
        r = await db.execute(select(SwineBreeding).where(SwineBreeding.id == pregnancy.breeding_id))
        breeding = r.scalar_one_or_none()

    dam_id = data.dam_id or (pregnancy.dam_id if pregnancy else (breeding.dam_id if breeding else None))
    sire_id = data.sire_id or (breeding.sire_id if breeding else None)

    total_born = data.born_alive + data.stillborn + data.mummified
    if total_born == 0:
        raise ValidationException("A farrowing must record at least one born piglet.")

    dam = await _get_pig_or_404(db, farm.id, dam_id) if dam_id else None
    parity = data.parity if data.parity is not None else ((dam.parity or 0) + 1 if dam else None)

    f_code = await _next_code(db, SwineFarrowing, farm.id, "FW")
    farrowing = SwineFarrowing(
        id=uuid.uuid4(), farm_id=farm.id, breeding_id=breeding.id if breeding else None,
        pregnancy_id=pregnancy.id if pregnancy else None, dam_id=dam_id, sire_id=sire_id,
        farrowing_code=f_code, farrowing_date=data.farrowing_date, parity=parity,
        assistance_required=data.assistance_required, complications=data.complications,
        colostrum_status=data.colostrum_status, location=data.location, status="active",
        notes=data.notes, created_by=user.id,
    )
    db.add(farrowing)
    await db.flush()

    l_code = await _next_code(db, SwineLitter, farm.id, "LT")
    litter = SwineLitter(
        id=uuid.uuid4(), farm_id=farm.id, farrowing_id=farrowing.id, dam_id=dam_id,
        sire_id=sire_id, nurse_dam_id=dam_id, litter_code=l_code, total_born=total_born,
        born_alive=data.born_alive, stillborn=data.stillborn, mummified=data.mummified,
        avg_birth_weight_kg=data.avg_birth_weight_kg, litter_birth_weight_kg=data.litter_birth_weight_kg,
        status="active", created_by=user.id,
    )
    db.add(litter)
    await db.flush()

    created: list[str] = []
    for spec in data.create_individuals:
        pig = await _create_piglet(db, farm, litter, spec, user)
        pig.date_of_birth = data.farrowing_date
        created.append(pig.internal_ref)

    # Resolve pregnancy + breeding, update dam.
    if pregnancy is not None:
        pregnancy.status = "farrowed"
        pregnancy.actual_farrowing_date = data.farrowing_date
    if breeding is not None:
        breeding.outcome = "pregnant"
        if breeding.status in ("planned", "serviced"):
            breeding.status = "closed"
    if dam is not None:
        dam.reproductive_status = "lactating"
        dam.parity = parity
        await _append_event(db, dam.id, "farrowed",
                            f"Farrowed {data.born_alive} live of {total_born}", operator_id=user.id,
                            details={"farrowing_id": str(farrowing.id), "litter_id": str(litter.id),
                                     "born_alive": data.born_alive})
    await audit_service.log_action(
        db, action="swine.farrowing.record", resource_type="swine_farrowing",
        resource_id=farrowing.id, farm_id=farm.id, user_id=user.id,
        new_value={"code": f_code, "born_alive": data.born_alive, "individuals": created})
    await db.commit()
    await db.refresh(farrowing)
    await db.refresh(litter)
    return farrowing, litter, created


async def list_farrowings(db, farm_id, *, dam_id=None, limit=100, offset=0):
    conds = [SwineFarrowing.farm_id == farm_id, SwineFarrowing.deleted_at.is_(None)]
    if dam_id:
        conds.append(SwineFarrowing.dam_id == dam_id)
    r = await db.execute(select(SwineFarrowing).where(*conds)
                         .order_by(SwineFarrowing.farrowing_date.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())


async def get_farrowing_detail(db, farm_id, farrowing_id):
    farrowing = await _get_farrowing_or_404(db, farm_id, farrowing_id)
    r = await db.execute(select(SwineLitter).where(
        SwineLitter.farrowing_id == farrowing_id, SwineLitter.deleted_at.is_(None)))
    litter = r.scalar_one_or_none()
    performance = engine.farrowing_performance(_litter_dict(litter)) if litter else {}
    return farrowing, litter, performance


# ── Litters ──────────────────────────────────────────────────────────────────

async def list_litters(db, farm_id, *, dam_id=None, status=None, limit=100, offset=0):
    conds = [SwineLitter.farm_id == farm_id, SwineLitter.deleted_at.is_(None)]
    if dam_id:
        conds.append(SwineLitter.dam_id == dam_id)
    if status:
        conds.append(SwineLitter.status == status)
    r = await db.execute(select(SwineLitter).where(*conds)
                         .order_by(SwineLitter.created_at.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())


async def get_litter_detail(db, farm_id, litter_id):
    litter = await _get_litter_or_404(db, farm_id, litter_id)
    r = await db.execute(select(func.count(SwinePig.id)).where(
        SwinePig.litter_id == litter_id, SwinePig.deleted_at.is_(None)))
    individuals = r.scalar_one() or 0
    return litter, engine.farrowing_performance(_litter_dict(litter)), individuals


async def add_piglet(db, farm: Farm, litter_id, data: PigletAddInput, user: User) -> SwinePig:
    litter = await _get_litter_or_404(db, farm.id, litter_id)
    if litter.status != "active":
        raise ConflictException("Cannot add a piglet to a weaned/closed litter.")
    pig = await _create_piglet(db, farm, litter, data, user)
    await audit_service.log_action(
        db, action="swine.litter.add_piglet", resource_type="swine_pig",
        resource_id=pig.id, farm_id=farm.id, user_id=user.id, new_value={"litter": litter.litter_code})
    await db.commit()
    await db.refresh(pig)
    return pig


async def record_mortality(db, farm_id, litter_id, data: LitterMortalityInput, user: User) -> SwineLitter:
    """Record pre-wean piglet mortality on a litter. If an individual pig is named,
    that pig is also marked deceased."""
    litter = await _get_litter_or_404(db, farm_id, litter_id)
    if data.count < 1:
        raise ValidationException("Mortality count must be at least 1.")
    litter.mortality += data.count
    if data.pig_id is not None:
        pig = await _get_pig_or_404(db, farm_id, data.pig_id)
        if pig.litter_id != litter.id:
            raise ValidationException("That pig does not belong to this litter.")
        pig.status = "deceased"
        pig.production_stage = "cull" if pig.production_stage == "unknown" else pig.production_stage
        await _append_event(db, pig.id, "died", f"Piglet death: {data.cause or 'unknown'}",
                            operator_id=user.id, details={"cause": data.cause})
    await db.flush()
    await audit_service.log_action(
        db, action="swine.litter.mortality", resource_type="swine_litter",
        resource_id=litter.id, farm_id=farm_id, user_id=user.id, new_value={"count": data.count})
    await db.commit()
    await db.refresh(litter)
    return litter


# ── Fostering ──────────────────────────────────────────────────────────────────

async def foster_transfer(db, farm: Farm, data: FosterTransferInput, user: User) -> SwineFosterTransfer:
    """Move piglets from one nursing sow to another. Records the count and, when the
    farm tracks individuals, the specific pigs — updating each pig's nursing sow while
    preserving its birth litter (full birth-sow → foster-sow traceability)."""
    source = await _get_litter_or_404(db, farm.id, data.source_litter_id)
    dest = await _get_litter_or_404(db, farm.id, data.dest_litter_id)
    if source.id == dest.id:
        raise ValidationException("Source and destination litters must differ.")

    count = data.piglet_count
    moved_ids: list[str] = []
    if data.pig_ids:
        for pid in data.pig_ids:
            pig = await _get_pig_or_404(db, farm.id, pid)
            if pig.litter_id != source.id:
                raise ValidationException(f"Pig {pig.internal_ref} is not in the source litter.")
            pig.nurse_dam_id = dest.nurse_dam_id or dest.dam_id
            await record_movement(db, farm.id, pig.id, movement_type="farrowing_move",
                                  moved_on=data.transfer_date, reason="cross-foster", user=user)
            await _append_event(db, pig.id, "fostered", "Cross-fostered to another sow",
                                operator_id=user.id,
                                details={"from_litter": str(source.id), "to_litter": str(dest.id)})
            moved_ids.append(str(pig.id))
        count = len(moved_ids)

    if count < 1:
        raise ValidationException("A foster transfer must move at least one piglet.")

    source.fostered_out += count
    dest.fostered_in += count
    transfer = SwineFosterTransfer(
        id=uuid.uuid4(), farm_id=farm.id, source_litter_id=source.id, dest_litter_id=dest.id,
        source_dam_id=source.dam_id, dest_dam_id=dest.nurse_dam_id or dest.dam_id,
        piglet_count=count, pig_ids=moved_ids, transfer_date=data.transfer_date,
        reason=data.reason, notes=data.notes, created_by=user.id,
    )
    db.add(transfer)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.foster.transfer", resource_type="swine_foster_transfer",
        resource_id=transfer.id, farm_id=farm.id, user_id=user.id,
        new_value={"count": count, "pig_ids": moved_ids})
    await db.commit()
    await db.refresh(transfer)
    return transfer


# ── Weaning ─────────────────────────────────────────────────────────────────────

async def record_weaning(db, farm: Farm, litter_id, data: WeaningInput, user: User) -> SwineLitter:
    """Wean a litter: record the weaned count/weight, close the litter, free the dam,
    and advance any individually-tracked piglets to the weaner stage."""
    litter = await _get_litter_or_404(db, farm.id, litter_id)
    if litter.status in ("weaned", "closed"):
        raise ConflictException("This litter is already weaned.")
    nursed = litter.nursed_count
    if data.weaned > nursed:
        raise ValidationException(f"Weaned count ({data.weaned}) cannot exceed nursing piglets ({nursed}).")
    litter.weaned = data.weaned
    litter.mortality = max(nursed - data.weaned, litter.mortality)
    litter.weaning_date = data.weaning_date
    litter.avg_weaning_weight_kg = data.avg_weaning_weight_kg
    litter.status = "weaned"
    await db.flush()

    # Advance individually-tracked live piglets in this litter to the weaner stage.
    r = await db.execute(select(SwinePig).where(
        SwinePig.litter_id == litter.id, SwinePig.status == "active",
        SwinePig.production_stage == "piglet", SwinePig.deleted_at.is_(None)))
    advanced = 0
    for pig in r.scalars().all():
        pig.production_stage = "weaner"
        if data.nursery_group_id is not None:
            before_group = pig.group_id
            pig.group_id = data.nursery_group_id
            await record_movement(db, farm.id, pig.id, movement_type="weaning_move",
                                  from_group_id=before_group, to_group_id=data.nursery_group_id,
                                  moved_on=data.weaning_date, reason="weaning", user=user)
        await _append_event(db, pig.id, "weaned", "Weaned to weaner stage", operator_id=user.id,
                            details={"litter_id": str(litter.id)})
        advanced += 1

    if litter.dam_id:
        dam = await _get_pig_or_404(db, farm.id, litter.dam_id)
        dam.reproductive_status = "weaned"
        await _append_event(db, dam.id, "weaned", f"{data.weaned} piglets weaned", operator_id=user.id,
                            details={"litter_id": str(litter.id)})
    await audit_service.log_action(
        db, action="swine.litter.wean", resource_type="swine_litter",
        resource_id=litter.id, farm_id=farm.id, user_id=user.id,
        new_value={"weaned": data.weaned, "advanced_individuals": advanced})
    await db.commit()
    await db.refresh(litter)
    return litter


# ── Analytics ────────────────────────────────────────────────────────────────

async def farrowing_summary(db, farm_id) -> dict:
    r = await db.execute(select(SwineLitter).where(
        SwineLitter.farm_id == farm_id, SwineLitter.deleted_at.is_(None)))
    litters = [_litter_dict(x) for x in r.scalars().all()]
    s = await db.execute(select(func.count(SwineBreeding.id)).where(
        SwineBreeding.farm_id == farm_id, SwineBreeding.service_date.is_not(None),
        SwineBreeding.deleted_at.is_(None)))
    services = s.scalar_one() or 0
    return engine.litter_summary(litters, services)
