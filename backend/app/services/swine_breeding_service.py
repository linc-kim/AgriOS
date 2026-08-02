"""
Greena — Swine Breeding Service (Module 20, Milestone 3)

Orchestrates the reproduction cycle up to confirmed pregnancy: service (natural or
artificial insemination) → pregnancy check, plus pedigree, compatibility and
performance reads. Farrowing, piglets and weaning arrive in Milestone 4. All math is
delegated to the PURE :mod:`swine_breeding_engine` and :mod:`swine_genetics` (which
reuses the platform pedigree engine).

Every mutation appends the dam's timeline event + an audit-log entry; breeding
history is immutable (Swine Doc 2 §7, §19).
"""

import uuid

from sqlalchemy import select

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineBreed,
    SwineBreeding,
    SwinePig,
)
from app.schemas.swine import (
    BreedingCreate,
    ServiceInput,
)
from app.services import audit_service
from app.services import swine_breeding_engine as engine
from app.services import swine_config as cfg
from app.services import swine_genetics as genetics
from app.services.swine_service import _append_event, _get_pig_or_404


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_breeding_or_404(db, farm_id, breeding_id) -> SwineBreeding:
    result = await db.execute(
        select(SwineBreeding).where(
            SwineBreeding.id == breeding_id, SwineBreeding.farm_id == farm_id,
            SwineBreeding.deleted_at.is_(None),
        )
    )
    b = result.scalar_one_or_none()
    if b is None:
        raise NotFoundException(f"Breeding {breeding_id} not found on this farm.")
    return b


async def _gestation_days(db, dam: SwinePig) -> tuple[int, bool]:
    """Resolve gestation from the dam's breed profile (recorded reference) or the
    species default (~114d). Returns (days, breed_specified)."""
    profile = None
    if dam.breed_id:
        row = await db.execute(select(SwineBreed.profile).where(SwineBreed.id == dam.breed_id))
        profile = row.scalar_one_or_none()
    breed_days = None
    if profile:
        raw = profile.get("gestation_days")
        try:
            if raw is not None and int(raw) > 0:
                breed_days = int(raw)
        except (TypeError, ValueError):
            breed_days = None
    return (breed_days or cfg.DEFAULT_GESTATION_DAYS), breed_days is not None


async def _dam_has_open_cycle(db, dam_id: uuid.UUID, exclude_id: uuid.UUID | None = None) -> bool:
    conds = [
        SwineBreeding.dam_id == dam_id,
        SwineBreeding.status.in_(("planned", "serviced", "pregnant")),
        SwineBreeding.deleted_at.is_(None),
    ]
    if exclude_id:
        conds.append(SwineBreeding.id != exclude_id)
    result = await db.execute(select(SwineBreeding.id).where(*conds).limit(1))
    return result.scalar_one_or_none() is not None


async def _parent_map(db, farm_id) -> dict:
    rows = await db.execute(
        select(SwinePig.id, SwinePig.sire_id, SwinePig.dam_id).where(SwinePig.farm_id == farm_id)
    )
    return {row[0]: (row[1], row[2]) for row in rows}


# ── Breeding cycle ─────────────────────────────────────────────────────────────

async def create_breeding(db, farm: Farm, data: BreedingCreate, user: User) -> SwineBreeding:
    """Register a breeding service (natural or artificial insemination). Eligibility
    is validated before recording (Swine Doc 3 §7); the planned farrowing date is a
    forecast from the species/breed gestation. For AI with external semen the sire
    may be omitted, but a semen source must then be recorded (traceability)."""
    dam = await _get_pig_or_404(db, farm.id, data.dam_id)
    sire = None
    if data.sire_id is not None:
        sire = await _get_pig_or_404(db, farm.id, data.sire_id)
    elif data.method == "artificial" and not data.semen_source:
        raise ValidationException("Artificial insemination requires a sire or a recorded semen source.")

    open_cycle = await _dam_has_open_cycle(db, dam.id)
    verdict = engine.validate_eligibility(
        {"sex": dam.sex, "status": dam.status},
        {"sex": sire.sex, "status": sire.status} if sire else None,
        data.method,
        open_cycle,
    )
    if not verdict["eligible"]:
        raise ConflictException("Breeding not eligible: " + " ".join(verdict["reasons"]))

    gest_days, breed_specified = await _gestation_days(db, dam)
    planned = engine.expected_farrowing_date(data.service_date, gest_days)

    status = "serviced" if data.service_date else "planned"
    b = SwineBreeding(
        id=uuid.uuid4(), farm_id=farm.id, dam_id=dam.id, sire_id=sire.id if sire else None,
        method=data.method, service_date=data.service_date, planned_farrowing_date=planned,
        semen_source=data.semen_source, semen_batch=data.semen_batch, technician=data.technician,
        status=status, notes=data.notes, created_by=user.id,
    )
    db.add(b)
    await db.flush()
    if data.service_date:
        dam.reproductive_status = "bred"
    event_type = "inseminated" if data.method == "artificial" else "bred"
    summary = (f"Inseminated ({data.semen_source or (sire.internal_ref if sire else 'AI')})"
               if data.method == "artificial"
               else f"Serviced by {sire.internal_ref}")
    await _append_event(db, dam.id, event_type, summary, operator_id=user.id,
                        details={"breeding_id": str(b.id), "method": data.method,
                                 "sire": sire.internal_ref if sire else None,
                                 "semen_source": data.semen_source,
                                 "planned_farrowing_date": planned.isoformat() if planned else None})
    await audit_service.log_action(
        db, action="swine.breeding.create", resource_type="swine_breeding",
        resource_id=b.id, farm_id=farm.id, user_id=user.id, new_value={"dam": str(dam.id), "method": data.method},
    )
    await db.commit()
    await db.refresh(b)
    return b


async def record_service(db, farm_id, breeding_id, data: ServiceInput, user: User) -> SwineBreeding:
    b = await _get_breeding_or_404(db, farm_id, breeding_id)
    if not b.is_open:
        raise ConflictException("This breeding cycle is already closed.")
    dam = await _get_pig_or_404(db, farm_id, b.dam_id) if b.dam_id else None
    b.service_date = data.service_date
    if dam:
        gest_days, _ = await _gestation_days(db, dam)
        b.planned_farrowing_date = engine.expected_farrowing_date(data.service_date, gest_days)
        dam.reproductive_status = "bred"
    b.status = "serviced"
    await db.flush()
    if b.dam_id:
        await _append_event(db, b.dam_id, "bred", "Service recorded", operator_id=user.id,
                            details={"breeding_id": str(b.id), "service_date": data.service_date.isoformat()})
    await audit_service.log_action(
        db, action="swine.breeding.service", resource_type="swine_breeding",
        resource_id=b.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(b)
    return b


# ── Reads: list / performance / pedigree / compatibility ───────────────────────

async def list_breedings(db, farm_id, *, dam_id=None, sire_id=None, method=None, status=None, limit=100, offset=0):
    conds = [SwineBreeding.farm_id == farm_id, SwineBreeding.deleted_at.is_(None)]
    if dam_id:
        conds.append(SwineBreeding.dam_id == dam_id)
    if sire_id:
        conds.append(SwineBreeding.sire_id == sire_id)
    if method:
        conds.append(SwineBreeding.method == method)
    if status:
        conds.append(SwineBreeding.status == status)
    result = await db.execute(
        select(SwineBreeding).where(*conds)
        .order_by(SwineBreeding.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


def _breeding_dicts(rows) -> list[dict]:
    return [{"service_date": r.service_date, "outcome": r.outcome,
             "status": r.status, "method": r.method} for r in rows]


async def dam_performance(db, farm_id, dam_id) -> dict:
    await _get_pig_or_404(db, farm_id, dam_id)
    breedings = await list_breedings(db, farm_id, dam_id=dam_id, limit=1000)
    return engine.dam_service_history(_breeding_dicts(breedings))


async def sire_performance(db, farm_id, sire_id) -> dict:
    await _get_pig_or_404(db, farm_id, sire_id)
    breedings = await list_breedings(db, farm_id, sire_id=sire_id, limit=1000)
    return engine.sire_fertility(_breeding_dicts(breedings))


async def reproduction_summary(db, farm_id) -> dict:
    breedings = await list_breedings(db, farm_id, limit=100000)
    return engine.reproduction_summary(_breeding_dicts(breedings))


async def pedigree(db, farm_id, pig_id, max_generations: int = 5) -> dict:
    await _get_pig_or_404(db, farm_id, pig_id)
    parents = await _parent_map(db, farm_id)
    return genetics.pedigree_tree(pig_id, parents, max_generations=max_generations)


async def compatibility(db, farm_id, sire_id, dam_id) -> dict:
    sire = await _get_pig_or_404(db, farm_id, sire_id)
    dam = await _get_pig_or_404(db, farm_id, dam_id)
    parents = await _parent_map(db, farm_id)
    return genetics.assess_pairing({"id": sire.id, "sex": sire.sex}, {"id": dam.id, "sex": dam.sex}, parents)
