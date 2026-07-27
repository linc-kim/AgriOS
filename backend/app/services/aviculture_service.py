"""
Greena — Aviculture Service (Module 15)

Collection-management business logic for individual birds. This service owns the
writes; the models stay pure and no calculations live here beyond deterministic
record-keeping (Doc 14 §2-6). Every state change:

  * is farm-scoped (organisation isolation via ``farms.organization_id``);
  * appends an immutable timeline event (Doc 06 §4) — the bird's life history is
    preserved permanently (Doc 02 §4);
  * writes an audit-log entry (Doc 10 §8);
  * never destroys history — ownership is append-only, status transitions are
    soft (Doc 02 §26, Doc 04 §6).

Ownership events (transfer / sale / purchase / death) record collection facts
only. Financial posting is deferred to Part 7, which reuses the Greena Finance
engine rather than duplicating it (Doc 13 Part 7).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.aviculture import (
    AviBird,
    AviBirdDocument,
    AviBirdEvent,
    AviBirdMedia,
    AviBirdMutation,
    AviBirdOwnership,
    AviBreed,
    AviMutation,
    AviSpecies,
    BIRD_TERMINAL_STATUSES,
)
from app.schemas.aviculture import (
    BirdCreate,
    BirdUpdate,
    BreedCreate,
    DeathInput,
    DocumentCreate,
    MediaCreate,
    MutationCreate,
    PurchaseInput,
    SaleInput,
    SpeciesCreate,
    TransferInput,
)
from app.services import audit_service


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_bird_or_404(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID) -> AviBird:
    result = await db.execute(
        select(AviBird).where(
            AviBird.id == bird_id,
            AviBird.farm_id == farm_id,
            AviBird.deleted_at.is_(None),
        )
    )
    bird = result.scalar_one_or_none()
    if bird is None:
        raise NotFoundException(f"Bird {bird_id} not found on this farm.")
    return bird


async def _generate_internal_ref(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Sequential per-farm reference (AV-00001). Uniqueness is enforced by the
    DB constraint; the count only seeds a readable starting point."""
    result = await db.execute(
        select(func.count(AviBird.id)).where(AviBird.farm_id == farm_id)
    )
    seq = (result.scalar_one() or 0) + 1
    return f"AV-{seq:05d}"


async def _append_event(
    db: AsyncSession,
    bird_id: uuid.UUID,
    event_type: str,
    title: str,
    *,
    occurred_on: date | None = None,
    actor_id: uuid.UUID | None = None,
    description: str | None = None,
    data: dict | None = None,
) -> AviBirdEvent:
    event = AviBirdEvent(
        id=uuid.uuid4(),
        bird_id=bird_id,
        event_type=event_type,
        occurred_on=occurred_on or date.today(),
        title=title,
        description=description,
        data=data or {},
        actor_id=actor_id,
    )
    db.add(event)
    await db.flush()
    return event


async def _current_ownership(db: AsyncSession, bird_id: uuid.UUID) -> AviBirdOwnership | None:
    result = await db.execute(
        select(AviBirdOwnership).where(
            AviBirdOwnership.bird_id == bird_id,
            AviBirdOwnership.is_current.is_(True),
            AviBirdOwnership.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def _close_current_ownership(db: AsyncSession, bird_id: uuid.UUID, on: date) -> None:
    current = await _current_ownership(db, bird_id)
    if current is not None:
        current.is_current = False
        current.to_date = on
        await db.flush()


def _guard_not_terminal(bird: AviBird, action: str) -> None:
    if bird.status in BIRD_TERMINAL_STATUSES:
        raise ConflictException(
            f"Cannot {action}: bird {bird.internal_ref} is already {bird.status}. "
            "Terminal records are permanent and cannot transition further."
        )


async def _resolve_names(
    db: AsyncSession, birds: list[AviBird]
) -> tuple[dict, dict, dict]:
    """Batch-resolve species / breed / aviary display names (avoids N+1)."""
    from app.models.aviculture import AviAviary

    species_ids = {b.species_id for b in birds if b.species_id}
    breed_ids = {b.breed_id for b in birds if b.breed_id}
    aviary_ids = {b.aviary_id for b in birds if b.aviary_id}

    species_names: dict = {}
    breed_names: dict = {}
    aviary_names: dict = {}

    if species_ids:
        rows = await db.execute(
            select(AviSpecies.id, AviSpecies.common_name).where(AviSpecies.id.in_(species_ids))
        )
        species_names = {r[0]: r[1] for r in rows}
    if breed_ids:
        rows = await db.execute(
            select(AviBreed.id, AviBreed.name).where(AviBreed.id.in_(breed_ids))
        )
        breed_names = {r[0]: r[1] for r in rows}
    if aviary_ids:
        rows = await db.execute(
            select(AviAviary.id, AviAviary.name).where(AviAviary.id.in_(aviary_ids))
        )
        aviary_names = {r[0]: r[1] for r in rows}
    return species_names, breed_names, aviary_names


# ── Catalog (data-driven; Doc 02 §6-8) ───────────────────────────────────────

async def list_species(db: AsyncSession, org_id: uuid.UUID | None) -> list[AviSpecies]:
    """Global system catalog (organization_id IS NULL) plus this org's custom entries."""
    conds = [AviSpecies.deleted_at.is_(None)]
    org_filter = AviSpecies.organization_id.is_(None)
    if org_id is not None:
        org_filter = or_(AviSpecies.organization_id.is_(None), AviSpecies.organization_id == org_id)
    conds.append(org_filter)
    result = await db.execute(select(AviSpecies).where(*conds).order_by(AviSpecies.common_name))
    return list(result.scalars().all())


async def create_species(
    db: AsyncSession, org_id: uuid.UUID | None, data: SpeciesCreate, user: User
) -> AviSpecies:
    species = AviSpecies(
        id=uuid.uuid4(),
        organization_id=org_id,
        common_name=data.common_name,
        scientific_name=data.scientific_name,
        species_group=data.species_group,
        conservation_status=data.conservation_status,
        profile=data.profile,
        is_system=False,
        created_by=user.id,
    )
    db.add(species)
    await db.flush()
    await audit_service.log_action(
        db, action="avi.species.create", resource_type="avi_species",
        resource_id=species.id, user_id=user.id,
        new_value={"common_name": species.common_name},
    )
    await db.commit()
    await db.refresh(species)
    return species


async def list_breeds(
    db: AsyncSession, org_id: uuid.UUID | None, species_id: uuid.UUID | None = None
) -> list[AviBreed]:
    conds = [AviBreed.deleted_at.is_(None)]
    if org_id is not None:
        conds.append(or_(AviBreed.organization_id.is_(None), AviBreed.organization_id == org_id))
    else:
        conds.append(AviBreed.organization_id.is_(None))
    if species_id is not None:
        conds.append(AviBreed.species_id == species_id)
    result = await db.execute(select(AviBreed).where(*conds).order_by(AviBreed.name))
    return list(result.scalars().all())


async def create_breed(
    db: AsyncSession, org_id: uuid.UUID | None, data: BreedCreate, user: User
) -> AviBreed:
    # Validate the species exists and is visible to this org.
    species = await db.execute(
        select(AviSpecies.id).where(AviSpecies.id == data.species_id, AviSpecies.deleted_at.is_(None))
    )
    if species.scalar_one_or_none() is None:
        raise NotFoundException(f"Species {data.species_id} not found.")
    breed = AviBreed(
        id=uuid.uuid4(), organization_id=org_id, species_id=data.species_id,
        name=data.name, profile=data.profile, is_system=False, created_by=user.id,
    )
    db.add(breed)
    await db.flush()
    await audit_service.log_action(
        db, action="avi.breed.create", resource_type="avi_breed",
        resource_id=breed.id, user_id=user.id, new_value={"name": breed.name},
    )
    await db.commit()
    await db.refresh(breed)
    return breed


async def list_mutations(
    db: AsyncSession, org_id: uuid.UUID | None, species_id: uuid.UUID | None = None
) -> list[AviMutation]:
    conds = [AviMutation.deleted_at.is_(None)]
    if org_id is not None:
        conds.append(or_(AviMutation.organization_id.is_(None), AviMutation.organization_id == org_id))
    else:
        conds.append(AviMutation.organization_id.is_(None))
    if species_id is not None:
        conds.append(or_(AviMutation.species_id == species_id, AviMutation.species_id.is_(None)))
    result = await db.execute(select(AviMutation).where(*conds).order_by(AviMutation.name))
    return list(result.scalars().all())


async def create_mutation(
    db: AsyncSession, org_id: uuid.UUID | None, data: MutationCreate, user: User
) -> AviMutation:
    mutation = AviMutation(
        id=uuid.uuid4(), organization_id=org_id, species_id=data.species_id,
        name=data.name, inheritance=data.inheritance, profile=data.profile,
        is_system=False, created_by=user.id,
    )
    db.add(mutation)
    await db.flush()
    await audit_service.log_action(
        db, action="avi.mutation.create", resource_type="avi_mutation",
        resource_id=mutation.id, user_id=user.id, new_value={"name": mutation.name},
    )
    await db.commit()
    await db.refresh(mutation)
    return mutation


# ── Birds — create / read / update ────────────────────────────────────────────

async def create_bird(db: AsyncSession, farm: Farm, data: BirdCreate, user: User) -> AviBird:
    # Validate the species exists (RESTRICT FK also protects, but give a clear error).
    species = await db.execute(
        select(AviSpecies.id).where(AviSpecies.id == data.species_id, AviSpecies.deleted_at.is_(None))
    )
    if species.scalar_one_or_none() is None:
        raise NotFoundException(f"Species {data.species_id} not found.")

    internal_ref = data.internal_ref or await _generate_internal_ref(db, farm.id)

    # Configurable duplicate-ring guard (Doc 03 §18): reject a duplicate ring in
    # the same farm among live birds.
    if data.ring_number:
        dup = await db.execute(
            select(AviBird.id).where(
                AviBird.farm_id == farm.id,
                AviBird.ring_number == data.ring_number,
                AviBird.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(
                f"Ring number {data.ring_number} already exists on this farm."
            )

    bird = AviBird(
        id=uuid.uuid4(),
        farm_id=farm.id,
        species_id=data.species_id,
        breed_id=data.breed_id,
        aviary_id=data.aviary_id,
        internal_ref=internal_ref,
        name=data.name,
        ring_number=data.ring_number,
        band_number=data.band_number,
        microchip=data.microchip,
        colour_description=data.colour_description,
        sex=data.sex,
        sex_method=data.sex_method,
        dna_status=data.dna_status,
        hatch_date=data.hatch_date,
        hatch_date_estimated=data.hatch_date_estimated,
        sire_id=data.sire_id,
        dam_id=data.dam_id,
        lifecycle_stage=data.lifecycle_stage,
        status="active",
        acquisition_type=data.acquisition_type,
        acquired_on=data.acquired_on,
        tags=data.tags,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(bird)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not create bird — duplicate reference.") from exc

    # Recorded genetics (facts only).
    for m in data.mutations:
        exists = await db.execute(
            select(AviMutation.id).where(AviMutation.id == m.mutation_id, AviMutation.deleted_at.is_(None))
        )
        if exists.scalar_one_or_none() is None:
            raise NotFoundException(f"Mutation {m.mutation_id} not found.")
        db.add(AviBirdMutation(
            id=uuid.uuid4(), bird_id=bird.id, mutation_id=m.mutation_id,
            zygosity=m.zygosity, created_by=user.id,
        ))

    # Initial ownership (defaults to the farm).
    db.add(AviBirdOwnership(
        id=uuid.uuid4(), bird_id=bird.id,
        owner_type=data.owner_type,
        owner_name=data.owner_name or farm.name,
        acquisition=data.acquisition_type,
        from_date=data.acquired_on or date.today(),
        is_current=True,
        created_by=user.id,
    ))

    await _append_event(
        db, bird.id, "created", f"Bird {internal_ref} added to the collection",
        actor_id=user.id, description=data.name,
        data={"internal_ref": internal_ref, "acquisition": data.acquisition_type},
    )
    await audit_service.log_action(
        db, action="avi.bird.create", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm.id, user_id=user.id,
        new_value={"internal_ref": internal_ref, "name": data.name},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def list_birds(
    db: AsyncSession,
    farm_id: uuid.UUID,
    *,
    status: str | None = None,
    species_id: uuid.UUID | None = None,
    aviary_id: uuid.UUID | None = None,
    sex: str | None = None,
    lifecycle_stage: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AviBird], int, tuple[dict, dict, dict]]:
    conds = [AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None)]
    if status:
        conds.append(AviBird.status == status)
    elif not include_archived:
        conds.append(AviBird.status != "archived")
    if species_id:
        conds.append(AviBird.species_id == species_id)
    if aviary_id:
        conds.append(AviBird.aviary_id == aviary_id)
    if sex:
        conds.append(AviBird.sex == sex)
    if lifecycle_stage:
        conds.append(AviBird.lifecycle_stage == lifecycle_stage)
    if search:
        like = f"%{search}%"
        conds.append(or_(
            AviBird.name.ilike(like),
            AviBird.internal_ref.ilike(like),
            AviBird.ring_number.ilike(like),
            AviBird.microchip.ilike(like),
            AviBird.band_number.ilike(like),
        ))
    if tag:
        conds.append(AviBird.tags.contains([tag]))

    total_result = await db.execute(select(func.count(AviBird.id)).where(*conds))
    total = total_result.scalar_one()

    result = await db.execute(
        select(AviBird).where(*conds)
        .order_by(AviBird.created_at.desc())
        .limit(limit).offset(offset)
    )
    birds = list(result.scalars().all())
    names = await _resolve_names(db, birds)
    return birds, total, names


async def get_bird_detail(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID):
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    names = await _resolve_names(db, [bird])

    mut_rows = await db.execute(
        select(AviBirdMutation, AviMutation.name, AviMutation.inheritance)
        .join(AviMutation, AviMutation.id == AviBirdMutation.mutation_id)
        .where(AviBirdMutation.bird_id == bird_id, AviBirdMutation.deleted_at.is_(None))
    )
    mutations = [
        {"row": r[0], "mutation_name": r[1], "inheritance": r[2]}
        for r in mut_rows.all()
    ]
    owner = await _current_ownership(db, bird_id)
    return bird, names, mutations, owner


async def update_bird(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: BirdUpdate, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    _guard_not_terminal(bird, "edit")

    changes: dict = {}
    fields = data.model_dump(exclude_unset=True)

    # Duplicate-ring guard on change.
    if "ring_number" in fields and fields["ring_number"]:
        dup = await db.execute(
            select(AviBird.id).where(
                AviBird.farm_id == farm_id,
                AviBird.ring_number == fields["ring_number"],
                AviBird.id != bird_id,
                AviBird.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ring number {fields['ring_number']} already exists on this farm.")

    # Cycle-safe parentage (Doc 03 §18 — no circular ancestry). Delegated to the
    # pure pedigree engine; imported lazily to avoid any import cycle.
    if ("sire_id" in fields and fields["sire_id"]) or ("dam_id" in fields and fields["dam_id"]):
        from app.services import pedigree_engine
        prows = await db.execute(
            select(AviBird.id, AviBird.sire_id, AviBird.dam_id).where(
                AviBird.farm_id == farm_id, AviBird.deleted_at.is_(None))
        )
        parents = {r[0]: (r[1], r[2]) for r in prows}
        for label in ("sire_id", "dam_id"):
            pid = fields.get(label)
            if pid is None:
                continue
            if pid == bird_id:
                raise ValidationException(f"A bird cannot be its own {label.replace('_id', '')}.")
            if pedigree_engine.would_create_cycle(bird_id, pid, parents):
                raise ConflictException(
                    f"Assigning that {label.replace('_id', '')} would create circular ancestry."
                )

    for field, value in fields.items():
        old = getattr(bird, field)
        if old != value:
            changes[field] = {"from": _jsonable(old), "to": _jsonable(value)}
            setattr(bird, field, value)

    if not changes:
        return bird

    await db.flush()
    await _append_event(
        db, bird.id, "updated", "Bird details updated",
        actor_id=user.id, data={"changes": changes},
    )
    await audit_service.log_action(
        db, action="avi.bird.update", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id, new_value={"changes": changes},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


def _jsonable(value):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


# ── Birds — lifecycle transitions ─────────────────────────────────────────────

async def archive_bird(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, reason: str | None, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    _guard_not_terminal(bird, "archive")
    if bird.status == "archived":
        raise ConflictException("Bird is already archived.")
    bird.status = "archived"
    await db.flush()
    await _append_event(db, bird.id, "archived", "Bird archived",
                        actor_id=user.id, description=reason)
    await audit_service.log_action(
        db, action="avi.bird.archive", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id, new_value={"reason": reason},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def restore_bird(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    if bird.status != "archived":
        raise ConflictException("Only archived birds can be restored.")
    bird.status = "active"
    await db.flush()
    await _append_event(db, bird.id, "restored", "Bird restored to the collection", actor_id=user.id)
    await audit_service.log_action(
        db, action="avi.bird.restore", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def transfer_bird(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: TransferInput, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    _guard_not_terminal(bird, "transfer")
    on = data.occurred_on or date.today()
    await _close_current_ownership(db, bird_id, on)
    db.add(AviBirdOwnership(
        id=uuid.uuid4(), bird_id=bird_id, owner_type=data.to_owner_type,
        owner_name=data.to_owner_name, owner_contact=data.to_owner_contact,
        acquisition="transferred", from_date=on, is_current=True, created_by=user.id,
        notes=data.notes,
    ))
    bird.status = "transferred"
    await db.flush()
    await _append_event(
        db, bird.id, "transferred", f"Transferred to {data.to_owner_name}",
        occurred_on=on, actor_id=user.id, description=data.destination,
        data={"to_owner": data.to_owner_name, "destination": data.destination},
    )
    await audit_service.log_action(
        db, action="avi.bird.transfer", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id,
        new_value={"to_owner": data.to_owner_name},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def sell_bird(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: SaleInput, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    _guard_not_terminal(bird, "sell")
    on = data.occurred_on or date.today()
    await _close_current_ownership(db, bird_id, on)
    db.add(AviBirdOwnership(
        id=uuid.uuid4(), bird_id=bird_id, owner_type="customer",
        owner_name=data.buyer_name, owner_contact=data.buyer_contact,
        acquisition="purchased", from_date=on, is_current=True, created_by=user.id,
    ))
    bird.status = "sold"
    await db.flush()
    price = _jsonable(data.price) if data.price is not None else None
    await _append_event(
        db, bird.id, "sold", f"Sold to {data.buyer_name}",
        occurred_on=on, actor_id=user.id, description=data.notes,
        data={"buyer": data.buyer_name, "price": price, "currency": data.currency},
    )
    await audit_service.log_action(
        db, action="avi.bird.sell", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id,
        new_value={"buyer": data.buyer_name, "price": price},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def record_purchase(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: PurchaseInput, user: User
) -> AviBird:
    """Document how an existing (active) bird was acquired by purchase. Provenance
    only — it does not change the bird's status."""
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    on = data.occurred_on or date.today()
    bird.acquisition_type = "purchased"
    if bird.acquired_on is None:
        bird.acquired_on = on
    # Reflect the seller on the current (opening) ownership record.
    current = await _current_ownership(db, bird_id)
    if current is not None:
        current.acquisition = "purchased"
    await db.flush()
    price = _jsonable(data.price) if data.price is not None else None
    await _append_event(
        db, bird.id, "purchased", f"Purchased from {data.seller_name}",
        occurred_on=on, actor_id=user.id, description=data.notes,
        data={"seller": data.seller_name, "price": price, "currency": data.currency},
    )
    await audit_service.log_action(
        db, action="avi.bird.purchase", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id,
        new_value={"seller": data.seller_name, "price": price},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


async def record_death(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: DeathInput, user: User
) -> AviBird:
    bird = await _get_bird_or_404(db, farm_id, bird_id)
    _guard_not_terminal(bird, "record death for")
    on = data.occurred_on or date.today()
    await _close_current_ownership(db, bird_id, on)
    bird.status = "deceased"
    bird.lifecycle_stage = bird.lifecycle_stage  # unchanged; death is a status
    await db.flush()
    await _append_event(
        db, bird.id, "died", "Bird deceased",
        occurred_on=on, actor_id=user.id, description=data.cause,
        data={"cause": data.cause},
    )
    await audit_service.log_action(
        db, action="avi.bird.death", resource_type="avi_bird",
        resource_id=bird.id, farm_id=farm_id, user_id=user.id, new_value={"cause": data.cause},
    )
    await db.commit()
    await db.refresh(bird)
    return bird


# ── Ownership & timeline ──────────────────────────────────────────────────────

async def list_ownership(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID) -> list[AviBirdOwnership]:
    await _get_bird_or_404(db, farm_id, bird_id)
    result = await db.execute(
        select(AviBirdOwnership).where(
            AviBirdOwnership.bird_id == bird_id, AviBirdOwnership.deleted_at.is_(None)
        ).order_by(AviBirdOwnership.from_date.desc().nullslast(), AviBirdOwnership.created_at.desc())
    )
    return list(result.scalars().all())


async def list_events(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[AviBirdEvent]:
    await _get_bird_or_404(db, farm_id, bird_id)
    result = await db.execute(
        select(AviBirdEvent).where(
            AviBirdEvent.bird_id == bird_id, AviBirdEvent.deleted_at.is_(None)
        ).order_by(AviBirdEvent.occurred_on.desc(), AviBirdEvent.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())


# ── Attachments (media / documents) ───────────────────────────────────────────

async def add_media(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: MediaCreate, user: User
) -> AviBirdMedia:
    await _get_bird_or_404(db, farm_id, bird_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Media requires a url or storage_path.")
    media = AviBirdMedia(
        id=uuid.uuid4(), bird_id=bird_id, media_type=data.media_type, url=data.url,
        storage_path=data.storage_path, filename=data.filename, content_type=data.content_type,
        size_bytes=data.size_bytes, caption=data.caption, is_primary=data.is_primary,
        taken_on=data.taken_on, uploaded_by=user.id,
    )
    db.add(media)
    await db.flush()
    await _append_event(
        db, bird_id, "media_added", f"{data.media_type.capitalize()} added",
        actor_id=user.id, description=data.caption,
    )
    await audit_service.log_action(
        db, action="avi.media.add", resource_type="avi_bird_media",
        resource_id=media.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(media)
    return media


async def list_media(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID) -> list[AviBirdMedia]:
    await _get_bird_or_404(db, farm_id, bird_id)
    result = await db.execute(
        select(AviBirdMedia).where(
            AviBirdMedia.bird_id == bird_id, AviBirdMedia.deleted_at.is_(None)
        ).order_by(AviBirdMedia.is_primary.desc(), AviBirdMedia.created_at.desc())
    )
    return list(result.scalars().all())


async def add_document(
    db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID, data: DocumentCreate, user: User
) -> AviBirdDocument:
    await _get_bird_or_404(db, farm_id, bird_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Document requires a url or storage_path.")
    doc = AviBirdDocument(
        id=uuid.uuid4(), bird_id=bird_id, document_type=data.document_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, issued_on=data.issued_on,
        expires_on=data.expires_on, is_restricted=data.is_restricted, uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await _append_event(
        db, bird_id, "document_added", f"Document added: {data.document_type}",
        actor_id=user.id, description=data.title,
    )
    await audit_service.log_action(
        db, action="avi.document.add", resource_type="avi_bird_document",
        resource_id=doc.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db: AsyncSession, farm_id: uuid.UUID, bird_id: uuid.UUID) -> list[AviBirdDocument]:
    await _get_bird_or_404(db, farm_id, bird_id)
    result = await db.execute(
        select(AviBirdDocument).where(
            AviBirdDocument.bird_id == bird_id, AviBirdDocument.deleted_at.is_(None)
        ).order_by(AviBirdDocument.created_at.desc())
    )
    return list(result.scalars().all())
