"""
Greena — Breeding Service (Module 15, Part 4)

Writes for pairs and breeding programmes, and read-throughs to the pure
``pedigree_engine`` for pedigrees, relatedness, inbreeding and compatibility.
All genetic calculations live in the engine (Doc 04 §1, Doc 14 §2) — this
service only loads recorded parentage, calls the engine, records history and
writes audit logs. Circular ancestry is prevented at the write boundary.
"""

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.aviculture import (
    AviBird,
    AviBreedingGoal,
    AviBreedingProgram,
    AviPair,
    AviPairEvent,
)
from app.schemas.aviculture_breeding import (
    GoalCreate,
    PairCreate,
    PairDissolve,
    ProgramCreate,
    ProgramUpdate,
)
from app.services import audit_service, pedigree_engine


# ── Parentage map (recorded facts feeding the pure engine) ────────────────────

async def _parents_map(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Load every bird's recorded (sire, dam) for a farm as a plain map. Kept
    lightweight (three UUID columns) so the pure engine stays DB-free."""
    rows = await db.execute(
        select(AviBird.id, AviBird.sire_id, AviBird.dam_id).where(
            AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None))
    )
    return {r[0]: (r[1], r[2]) for r in rows}


async def _get_bird_or_404(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID) -> AviBird:
    bird = (await db.execute(select(AviBird).where(
        AviBird.id == bird_id, AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None)))).scalar_one_or_none()
    if bird is None:
        raise NotFoundException(f"Bird {bird_id} not found on this farm.")
    return bird


# ── Parents (cycle-safe write) ────────────────────────────────────────────────

async def set_parents(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID,
    sire_id: uuid.UUID | None, dam_id: uuid.UUID | None, user: User,
) -> AviBird:
    """Assign a bird's sire/dam with deterministic cycle protection (Doc 03 §18).
    Unknown ancestry is allowed (NULL); a parent that would close a loop is
    rejected rather than silently corrected."""
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    parents = await _parents_map(db, farm_id)

    for label, pid in (("sire", sire_id), ("dam", dam_id)):
        if pid is None:
            continue
        if pid == bird_id:
            raise ValidationException(f"A bird cannot be its own {label}.")
        await _get_bird_or_404(db, farm_id, pid)  # must exist on this farm
        if pedigree_engine.would_create_cycle(bird_id, pid, parents):
            raise ConflictException(
                f"Assigning that {label} would create circular ancestry — the proposed "
                f"parent is a descendant of this bird."
            )

    bird.sire_id = sire_id
    bird.dam_id = dam_id
    await db.flush()
    await audit_service.log_action(
        db, action="avi.bird.set_parents", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id,
        new_value={"sire_id": str(sire_id) if sire_id else None, "dam_id": str(dam_id) if dam_id else None},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


# ── Pedigree / relatedness / compatibility (pure engine read-through) ─────────

async def get_pedigree(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, generations: int = 5) -> dict:
    await _get_bird_or_404(db, farm_id, bird_id)
    parents = await _parents_map(db, farm_id)
    return {
        "bird_id": bird_id,
        "ancestry": pedigree_engine.build_ancestry(bird_id, parents, max_generations=generations),
        "inbreeding_coefficient": {
            "label": pedigree_engine.CALCULATED,
            "value": pedigree_engine.inbreeding_coefficient(bird_id, parents),
            "detail": "Wright's F — probability of identity by descent. 0 when a parent is unknown.",
        },
        "founders": [str(f) for f in pedigree_engine.founders(bird_id, parents)],
        "generations": generations,
    }


async def get_relatedness(db, farm_id, bird_a: uuid.UUID, bird_b: uuid.UUID) -> dict:
    await _get_bird_or_404(db, farm_id, bird_a)
    await _get_bird_or_404(db, farm_id, bird_b)
    parents = await _parents_map(db, farm_id)
    r = pedigree_engine.relatedness(bird_a, bird_b, parents)
    return {
        "bird_a": bird_a, "bird_b": bird_b,
        "relationship_coefficient": {
            "label": pedigree_engine.CALCULATED, "value": r,
            "detail": "Wright's coefficient of relationship (2 × kinship).",
        },
    }


async def assess_compatibility(db, farm_id, male_id: uuid.UUID, female_id: uuid.UUID) -> dict:
    male = await _get_bird_or_404(db, farm_id, male_id)
    female = await _get_bird_or_404(db, farm_id, female_id)
    parents = await _parents_map(db, farm_id)
    return pedigree_engine.compatibility(
        {"id": male.id, "sex": male.sex, "species_id": male.species_id},
        {"id": female.id, "sex": female.sex, "species_id": female.species_id},
        parents,
    )


async def get_offspring(db, farm_id, bird_id: uuid.UUID) -> dict:
    await _get_bird_or_404(db, farm_id, bird_id)
    rows = list((await db.execute(
        select(AviBird).where(
            AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None),
            or_(AviBird.sire_id == bird_id, AviBird.dam_id == bird_id),
        ).order_by(AviBird.created_at.desc())
    )).scalars().all())
    offspring = [{"id": str(b.id), "internal_ref": b.internal_ref, "name": b.name, "status": b.status} for b in rows]
    return {
        "bird_id": bird_id,
        "offspring": offspring,
        "performance": pedigree_engine.breeding_performance(offspring),
    }


# ── Pairs ─────────────────────────────────────────────────────────────────────

async def _append_pair_event(db, pair_id, event_type, title, *, actor_id=None, description=None, data=None):
    db.add(AviPairEvent(
        id=uuid.uuid4(), pair_id=pair_id, event_type=event_type, occurred_on=date.today(),
        title=title, description=description, data=data or {}, actor_id=actor_id))
    await db.flush()


async def create_pair(db: AsyncSession, farm: Farm, data: PairCreate, user: User) -> AviPair:
    for bid in (data.male_bird_id, data.female_bird_id):
        if bid is not None:
            await _get_bird_or_404(db, farm.id, bid)
    if data.program_id is not None:
        prog = (await db.execute(select(AviBreedingProgram.id).where(
            AviBreedingProgram.id == data.program_id, AviBreedingProgram.farm_id == farm.id,
            AviBreedingProgram.deleted_at.is_(None)))).scalar_one_or_none()
        if prog is None:
            raise NotFoundException("Breeding programme not found on this farm.")

    pair = AviPair(
        id=uuid.uuid4(), farm_id=farm.id, male_bird_id=data.male_bird_id, female_bird_id=data.female_bird_id,
        name=data.name, purpose=data.purpose, formation_type=data.formation_type,
        formed_on=data.formed_on or date.today(), status="active", program_id=data.program_id, notes=data.notes,
        created_by=user.id,
    )
    db.add(pair)
    await db.flush()
    await _append_pair_event(db, pair.id, "formed", f"Pair formed{f' — {data.name}' if data.name else ''}",
                             actor_id=user.id)
    await audit_service.log_action(db, action="avi.pair.create", resource_type="avi_pair",
                                   resource_id=pair.id, farm_id=farm.id, user_id=user.id)
    await db.commit()
    await db.refresh(pair)
    return pair


async def list_pairs(db, farm_id, *, status: str | None = None, program_id: uuid.UUID | None = None,
                     limit: int = 100, offset: int = 0) -> tuple[list[AviPair], int, dict]:
    conds = [AviPair.farm_id == farm_id, AviPair.deleted_at.is_(None)]
    if status:
        conds.append(AviPair.status == status)
    if program_id:
        conds.append(AviPair.program_id == program_id)
    total = (await db.execute(select(func.count(AviPair.id)).where(*conds))).scalar_one()
    rows = list((await db.execute(
        select(AviPair).where(*conds).order_by(AviPair.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all())

    # Resolve bird display names in one batch.
    bird_ids = {b for p in rows for b in (p.male_bird_id, p.female_bird_id) if b}
    names: dict = {}
    if bird_ids:
        nrows = await db.execute(select(AviBird.id, AviBird.name, AviBird.internal_ref).where(AviBird.id.in_(bird_ids)))
        names = {r[0]: (r[1] or r[2]) for r in nrows}
    return rows, total, names


async def get_pair(db, farm_id, pair_id) -> AviPair:
    pair = (await db.execute(select(AviPair).where(
        AviPair.id == pair_id, AviPair.farm_id == farm_id, AviPair.deleted_at.is_(None)))).scalar_one_or_none()
    if pair is None:
        raise NotFoundException("Pair not found on this farm.")
    return pair


async def pair_compatibility(db, farm_id, pair: AviPair) -> dict | None:
    if pair.male_bird_id is None or pair.female_bird_id is None:
        return None
    return await assess_compatibility(db, farm_id, pair.male_bird_id, pair.female_bird_id)


async def dissolve_pair(db, farm_id, pair_id, data: PairDissolve, user: User) -> AviPair:
    pair = await get_pair(db, farm_id, pair_id)
    if pair.status == "dissolved":
        raise ConflictException("Pair is already dissolved.")
    on = data.dissolved_on or date.today()
    pair.status = "dissolved"
    pair.dissolved_on = on
    pair.dissolution_reason = data.reason
    await db.flush()
    await _append_pair_event(db, pair.id, "dissolved", "Pair dissolved", actor_id=user.id,
                             description=data.reason)
    await audit_service.log_action(db, action="avi.pair.dissolve", resource_type="avi_pair",
                                   resource_id=pair.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(pair)
    return pair


async def list_pair_events(db, farm_id, pair_id) -> list[AviPairEvent]:
    await get_pair(db, farm_id, pair_id)
    return list((await db.execute(
        select(AviPairEvent).where(AviPairEvent.pair_id == pair_id, AviPairEvent.deleted_at.is_(None))
        .order_by(AviPairEvent.occurred_on.desc(), AviPairEvent.created_at.desc())
    )).scalars().all())


# ── Breeding programmes ───────────────────────────────────────────────────────

async def create_program(db, farm: Farm, data: ProgramCreate, user: User) -> AviBreedingProgram:
    program = AviBreedingProgram(
        id=uuid.uuid4(), farm_id=farm.id, species_id=data.species_id, name=data.name,
        objective=data.objective, strategy=data.strategy, target_traits=data.target_traits,
        status="active", notes=data.notes, created_by=user.id,
    )
    db.add(program)
    await db.flush()
    await audit_service.log_action(db, action="avi.program.create", resource_type="avi_breeding_program",
                                   resource_id=program.id, farm_id=farm.id, user_id=user.id)
    await db.commit()
    await db.refresh(program)
    return program


async def list_programs(db, farm_id, status: str | None = None) -> tuple[list[AviBreedingProgram], dict]:
    conds = [AviBreedingProgram.farm_id == farm_id, AviBreedingProgram.deleted_at.is_(None)]
    if status:
        conds.append(AviBreedingProgram.status == status)
    rows = list((await db.execute(
        select(AviBreedingProgram).where(*conds).order_by(AviBreedingProgram.created_at.desc())
    )).scalars().all())
    counts: dict = {}
    if rows:
        crows = await db.execute(
            select(AviPair.program_id, func.count(AviPair.id)).where(
                AviPair.program_id.in_([p.id for p in rows]), AviPair.deleted_at.is_(None)
            ).group_by(AviPair.program_id))
        counts = {r[0]: r[1] for r in crows}
    return rows, counts


async def get_program(db, farm_id, program_id) -> AviBreedingProgram:
    prog = (await db.execute(select(AviBreedingProgram).where(
        AviBreedingProgram.id == program_id, AviBreedingProgram.farm_id == farm_id,
        AviBreedingProgram.deleted_at.is_(None)))).scalar_one_or_none()
    if prog is None:
        raise NotFoundException("Breeding programme not found.")
    return prog


async def update_program(db, farm_id, program_id, data: ProgramUpdate, user: User) -> AviBreedingProgram:
    prog = await get_program(db, farm_id, program_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prog, field, value)
    await db.flush()
    await audit_service.log_action(db, action="avi.program.update", resource_type="avi_breeding_program",
                                   resource_id=prog.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(prog)
    return prog


async def add_goal(db, farm_id, program_id, data: GoalCreate, user: User) -> AviBreedingGoal:
    await get_program(db, farm_id, program_id)
    goal = AviBreedingGoal(
        id=uuid.uuid4(), program_id=program_id, description=data.description,
        target_metric=data.target_metric, target_value=data.target_value, status="open")
    db.add(goal)
    await db.flush()
    await audit_service.log_action(db, action="avi.goal.create", resource_type="avi_breeding_goal",
                                   resource_id=goal.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(goal)
    return goal


async def list_goals(db, farm_id, program_id) -> list[AviBreedingGoal]:
    await get_program(db, farm_id, program_id)
    return list((await db.execute(
        select(AviBreedingGoal).where(AviBreedingGoal.program_id == program_id, AviBreedingGoal.deleted_at.is_(None))
        .order_by(AviBreedingGoal.created_at)
    )).scalars().all())
