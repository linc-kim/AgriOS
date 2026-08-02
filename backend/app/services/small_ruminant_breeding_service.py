"""
Greena — Small Ruminant Breeding Service (Modules 18/19, Milestone 3)

Orchestrates the shared reproduction cycle for goats and sheep: service →
pregnancy check → birth (kidding/lambing) → weaning, plus pedigree, compatibility
and performance reads. One service, both species — gestation, the dam/sire roles
and the offspring noun all come from the species config, never from forked code.
All math is delegated to the PURE :mod:`small_ruminant_breeding_engine` and
:mod:`small_ruminant_genetics` (which reuses the platform pedigree engine).

Every mutation appends the dam's timeline event + an audit-log entry; breeding
history is immutable (Goat Doc 2 §8).
"""

import uuid

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantBirth,
    SmallRuminantBreed,
    SmallRuminantBreeding,
)
from app.schemas.small_ruminant import (
    BirthRecordInput,
    BreedingCreate,
    PregnancyCheckInput,
    ServiceInput,
    WeaningInput,
)
from app.services import audit_service
from app.services import small_ruminant_breeding_engine as engine
from app.services import small_ruminant_genetics as genetics
from app.services import small_ruminant_species_config as cfg
from app.services.small_ruminant_service import _append_event, _get_animal_or_404

# Per-species birth-code prefix (KD kidding, LB lambing).
_BIRTH_PREFIX = {"goat": "KD", "sheep": "LB"}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_breeding_or_404(db, farm_id, species, breeding_id) -> SmallRuminantBreeding:
    result = await db.execute(
        select(SmallRuminantBreeding).where(
            SmallRuminantBreeding.id == breeding_id, SmallRuminantBreeding.farm_id == farm_id,
            SmallRuminantBreeding.species == species, SmallRuminantBreeding.deleted_at.is_(None),
        )
    )
    b = result.scalar_one_or_none()
    if b is None:
        raise NotFoundException(f"Breeding {breeding_id} not found on this farm.")
    return b


async def _gestation_days(db, species: str, dam: SmallRuminant) -> tuple[int, bool]:
    """Resolve gestation from the dam's breed profile (recorded reference) or the
    species default. Returns (days, breed_specified)."""
    profile = None
    if dam.breed_id:
        row = await db.execute(select(SmallRuminantBreed.profile).where(SmallRuminantBreed.id == dam.breed_id))
        profile = row.scalar_one_or_none()
    breed_days = None
    if profile:
        raw = profile.get("gestation_days")
        try:
            if raw is not None and int(raw) > 0:
                breed_days = int(raw)
        except (TypeError, ValueError):
            breed_days = None
    return (breed_days or cfg.default_gestation_days(species)), breed_days is not None


async def _dam_has_open_cycle(db, dam_id: uuid.UUID, exclude_id: uuid.UUID | None = None) -> bool:
    conds = [
        SmallRuminantBreeding.dam_id == dam_id,
        SmallRuminantBreeding.status.in_(("planned", "serviced", "pregnant")),
        SmallRuminantBreeding.deleted_at.is_(None),
    ]
    if exclude_id:
        conds.append(SmallRuminantBreeding.id != exclude_id)
    result = await db.execute(select(SmallRuminantBreeding.id).where(*conds).limit(1))
    return result.scalar_one_or_none() is not None


async def _parent_map(db, farm_id, species) -> dict:
    """Build the {animal_id: (sire_id, dam_id)} pedigree map for a farm's species."""
    rows = await db.execute(
        select(SmallRuminant.id, SmallRuminant.sire_id, SmallRuminant.dam_id).where(
            SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
        )
    )
    return {row[0]: (row[1], row[2]) for row in rows}


async def _next_birth_code(db, farm_id, species) -> str:
    result = await db.execute(
        select(func.count(SmallRuminantBirth.id)).where(
            SmallRuminantBirth.farm_id == farm_id, SmallRuminantBirth.species == species
        )
    )
    seq = (result.scalar_one() or 0) + 1
    return f"{_BIRTH_PREFIX[species]}-{seq:05d}"


async def _next_ref(db, farm_id, species) -> str:
    from app.services.small_ruminant_service import _generate_internal_ref
    return await _generate_internal_ref(db, farm_id, species)


# ── Breeding cycle ─────────────────────────────────────────────────────────────

async def create_breeding(db, farm: Farm, species: str, data: BreedingCreate, user: User) -> SmallRuminantBreeding:
    """Register a mating cycle. Eligibility is validated before recording (Goat
    Doc 3 §7); the planned birth date is a forecast from the species/breed gestation."""
    dam = await _get_animal_or_404(db, farm.id, species, data.dam_id)
    sire = await _get_animal_or_404(db, farm.id, species, data.sire_id)

    open_cycle = await _dam_has_open_cycle(db, dam.id)
    verdict = engine.validate_eligibility(
        species,
        {"sex": dam.sex, "status": dam.status},
        {"sex": sire.sex, "status": sire.status},
        open_cycle,
    )
    if not verdict["eligible"]:
        raise ConflictException("Breeding not eligible: " + " ".join(verdict["reasons"]))

    gest_days, breed_specified = await _gestation_days(db, species, dam)
    planned = engine.expected_birth_date(data.service_date, gest_days, breed_specified=breed_specified)

    status = "serviced" if data.service_date else "planned"
    b = SmallRuminantBreeding(
        id=uuid.uuid4(), species=species, farm_id=farm.id, dam_id=dam.id, sire_id=sire.id,
        method=data.method, service_date=data.service_date, planned_birth_date=planned,
        status=status, notes=data.notes, created_by=user.id,
    )
    db.add(b)
    await db.flush()
    if data.service_date:
        dam.reproductive_status = "bred"
    await _append_event(db, dam.id, "bred", f"Serviced by {sire.internal_ref}",
                        operator_id=user.id,
                        details={"breeding_id": str(b.id), "sire": sire.internal_ref,
                                 "method": data.method,
                                 "planned_birth_date": planned.isoformat() if planned else None})
    await audit_service.log_action(
        db, action=f"sr.{species}.breeding.create", resource_type="sr_breeding",
        resource_id=b.id, farm_id=farm.id, user_id=user.id, new_value={"dam": str(dam.id)},
    )
    await db.commit()
    await db.refresh(b)
    return b


async def record_service(db, farm_id, species, breeding_id, data: ServiceInput, user: User) -> SmallRuminantBreeding:
    b = await _get_breeding_or_404(db, farm_id, species, breeding_id)
    if not b.is_open:
        raise ConflictException("This breeding cycle is already closed.")
    dam = await _get_animal_or_404(db, farm_id, species, b.dam_id) if b.dam_id else None
    b.service_date = data.service_date
    if dam:
        gest_days, breed_specified = await _gestation_days(db, species, dam)
        b.planned_birth_date = engine.expected_birth_date(data.service_date, gest_days, breed_specified=breed_specified)
        dam.reproductive_status = "bred"
    b.status = "serviced"
    await db.flush()
    if b.dam_id:
        await _append_event(db, b.dam_id, "bred", "Service recorded", operator_id=user.id,
                            details={"breeding_id": str(b.id), "service_date": data.service_date.isoformat()})
    await audit_service.log_action(
        db, action=f"sr.{species}.breeding.service", resource_type="sr_breeding",
        resource_id=b.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(b)
    return b


async def record_pregnancy_check(db, farm_id, species, breeding_id, data: PregnancyCheckInput, user: User):
    b = await _get_breeding_or_404(db, farm_id, species, breeding_id)
    if b.status in ("birthed", "closed", "cancelled"):
        raise ConflictException("This breeding cycle is already resolved.")
    b.pregnancy_checked_on = data.checked_on
    b.pregnancy_result = data.result
    b.status = "pregnant" if data.result == "pregnant" else ("not_pregnant" if data.result == "not_pregnant" else b.status)
    if data.result == "not_pregnant":
        b.outcome = "failed"
    await db.flush()
    if b.dam_id:
        dam = await _get_animal_or_404(db, farm_id, species, b.dam_id)
        dam.reproductive_status = "pregnant" if data.result == "pregnant" else "open"
        await _append_event(db, b.dam_id, "pregnancy_checked", f"Pregnancy check: {data.result}",
                            operator_id=user.id, details={"breeding_id": str(b.id), "result": data.result})
    await audit_service.log_action(
        db, action=f"sr.{species}.breeding.pregnancy_check", resource_type="sr_breeding",
        resource_id=b.id, farm_id=farm_id, user_id=user.id, new_value={"result": data.result},
    )
    await db.commit()
    await db.refresh(b)
    return b


async def record_birth(db, farm: Farm, species: str, breeding_id, data: BirthRecordInput, user: User):
    """Record a birth (kidding/lambing): creates the birth record, closes the
    breeding cycle, updates the dam, and optionally auto-creates offspring animals
    with sire/dam/birth pedigree links (Goat Doc 6 §6)."""
    b = await _get_breeding_or_404(db, farm.id, species, breeding_id)
    if b.status in ("birthed", "closed", "cancelled") or b.actual_birth_date:
        raise ConflictException("A birth has already been recorded for this cycle.")

    code = await _next_birth_code(db, farm.id, species)
    birth = SmallRuminantBirth(
        id=uuid.uuid4(), species=species, farm_id=farm.id, breeding_id=b.id,
        dam_id=b.dam_id, sire_id=b.sire_id, birth_code=code, birth_date=data.birth_date,
        birth_type=data.birth_type, total_born=data.total_born, live_born=data.live_born,
        stillborn=data.stillborn, avg_birth_weight_kg=data.avg_birth_weight_kg,
        assistance_required=data.assistance_required, complications=data.complications,
        colostrum_status=data.colostrum_status, location=data.location, notes=data.notes,
        status="active", created_by=user.id,
    )
    db.add(birth)
    b.actual_birth_date = data.birth_date
    b.status = "birthed"
    b.outcome = "successful" if data.live_born > 0 else "failed"
    await db.flush()

    # Dam transitions to lactating (nursing offspring) after a live birth.
    if b.dam_id:
        dam = await _get_animal_or_404(db, farm.id, species, b.dam_id)
        dam.reproductive_status = "lactating" if data.live_born > 0 else "open"
        verb = cfg.birth_event(species)
        await _append_event(db, b.dam_id, "kidded" if species == "goat" else "lambed",
                            f"{verb.capitalize()}: {data.live_born} live of {data.total_born}",
                            operator_id=user.id,
                            details={"birth_id": str(birth.id), "birth_code": code,
                                     "birth_type": data.birth_type})

    created_offspring: list[str] = []
    if data.create_offspring and data.live_born > 0:
        for i in range(data.live_born):
            ref = await _next_ref(db, farm.id, species)
            kid = SmallRuminant(
                id=uuid.uuid4(), species=species, farm_id=farm.id, internal_ref=ref,
                sex="unknown", status="active", lifecycle_stage="newborn",
                acquisition_type="bred", birth_id=birth.id, dam_id=b.dam_id, sire_id=b.sire_id,
                date_of_birth=data.birth_date, birth_type=data.birth_type,
                herd_id=data.offspring_herd_id, group_id=data.offspring_group_id,
                created_by=user.id,
            )
            db.add(kid)
            await db.flush()
            await _append_event(db, kid.id, "created", f"{cfg.offspring_term(species).capitalize()} {ref} born",
                                operator_id=user.id, details={"birth_id": str(birth.id)})
            created_offspring.append(ref)

    await audit_service.log_action(
        db, action=f"sr.{species}.birth.record", resource_type="sr_birth",
        resource_id=birth.id, farm_id=farm.id, user_id=user.id,
        new_value={"birth_code": code, "offspring_created": created_offspring},
    )
    await db.commit()
    await db.refresh(birth)
    return birth, created_offspring


async def record_weaning(db, farm_id, species, birth_id, data: WeaningInput, user: User) -> SmallRuminantBirth:
    result = await db.execute(
        select(SmallRuminantBirth).where(
            SmallRuminantBirth.id == birth_id, SmallRuminantBirth.farm_id == farm_id,
            SmallRuminantBirth.species == species, SmallRuminantBirth.deleted_at.is_(None),
        )
    )
    birth = result.scalar_one_or_none()
    if birth is None:
        raise NotFoundException(f"Birth {birth_id} not found on this farm.")
    if birth.status in ("weaned", "closed"):
        raise ConflictException("This birth is already weaned.")
    if data.weaned > birth.live_born:
        raise ValidationException("Weaned count cannot exceed live-born count.")
    birth.weaned = data.weaned
    birth.mortality = max(birth.live_born - data.weaned, 0)
    birth.weaning_date = data.weaning_date
    birth.status = "weaned"
    await db.flush()
    if birth.dam_id:
        dam = await _get_animal_or_404(db, farm_id, species, birth.dam_id)
        dam.reproductive_status = "dry"
        await _append_event(db, birth.dam_id, "weaned", f"{data.weaned} offspring weaned",
                            operator_id=user.id, details={"birth_id": str(birth.id)})
    await audit_service.log_action(
        db, action=f"sr.{species}.birth.wean", resource_type="sr_birth",
        resource_id=birth.id, farm_id=farm_id, user_id=user.id, new_value={"weaned": data.weaned},
    )
    await db.commit()
    await db.refresh(birth)
    return birth


# ── Reads: list / performance / pedigree / compatibility ───────────────────────

async def list_breedings(db, farm_id, species, *, dam_id=None, status=None, limit=100, offset=0):
    conds = [SmallRuminantBreeding.farm_id == farm_id, SmallRuminantBreeding.species == species,
             SmallRuminantBreeding.deleted_at.is_(None)]
    if dam_id:
        conds.append(SmallRuminantBreeding.dam_id == dam_id)
    if status:
        conds.append(SmallRuminantBreeding.status == status)
    result = await db.execute(
        select(SmallRuminantBreeding).where(*conds)
        .order_by(SmallRuminantBreeding.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def list_births(db, farm_id, species, *, dam_id=None, limit=100, offset=0):
    conds = [SmallRuminantBirth.farm_id == farm_id, SmallRuminantBirth.species == species,
             SmallRuminantBirth.deleted_at.is_(None)]
    if dam_id:
        conds.append(SmallRuminantBirth.dam_id == dam_id)
    result = await db.execute(
        select(SmallRuminantBirth).where(*conds)
        .order_by(SmallRuminantBirth.birth_date.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


def _breeding_dicts(rows) -> list[dict]:
    return [{"service_date": r.service_date, "pregnancy_result": r.pregnancy_result,
             "status": r.status} for r in rows]


def _birth_dicts(rows) -> list[dict]:
    return [{"total_born": r.total_born, "live_born": r.live_born, "stillborn": r.stillborn,
             "weaned": r.weaned, "mortality": r.mortality, "status": r.status,
             "avg_birth_weight_kg": r.avg_birth_weight_kg, "birth_date": r.birth_date} for r in rows]


async def dam_performance(db, farm_id, species, dam_id) -> dict:
    await _get_animal_or_404(db, farm_id, species, dam_id)
    breedings = await list_breedings(db, farm_id, species, dam_id=dam_id, limit=1000)
    births = await list_births(db, farm_id, species, dam_id=dam_id, limit=1000)
    return engine.dam_productivity(_breeding_dicts(breedings), _birth_dicts(births))


async def sire_performance(db, farm_id, species, sire_id) -> dict:
    await _get_animal_or_404(db, farm_id, species, sire_id)
    result = await db.execute(
        select(SmallRuminantBreeding).where(
            SmallRuminantBreeding.farm_id == farm_id, SmallRuminantBreeding.species == species,
            SmallRuminantBreeding.sire_id == sire_id, SmallRuminantBreeding.deleted_at.is_(None),
        )
    )
    breedings = list(result.scalars().all())
    return engine.sire_fertility(_breeding_dicts(breedings))


async def reproduction_summary(db, farm_id, species) -> dict:
    breedings = await list_breedings(db, farm_id, species, limit=100000)
    births = await list_births(db, farm_id, species, limit=100000)
    return engine.reproduction_summary(_breeding_dicts(breedings), _birth_dicts(births))


async def pedigree(db, farm_id, species, animal_id, max_generations: int = 5) -> dict:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    parents = await _parent_map(db, farm_id, species)
    return genetics.pedigree_tree(animal_id, parents, max_generations=max_generations)


async def compatibility(db, farm_id, species, sire_id, dam_id) -> dict:
    sire = await _get_animal_or_404(db, farm_id, species, sire_id)
    dam = await _get_animal_or_404(db, farm_id, species, dam_id)
    parents = await _parent_map(db, farm_id, species)
    return genetics.assess_pairing(
        species, {"id": sire.id, "sex": sire.sex}, {"id": dam.id, "sex": dam.sex}, parents
    )
