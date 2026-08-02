"""
Greena — Small Ruminant Service (Modules 18/19, Milestone 2)

Registry business logic for individual goats and sheep — one service, two species,
distinguished by the ``species`` argument every entry point takes. No calculations
live here beyond deterministic record-keeping. Every state change:

  * is farm-scoped (organisation isolation via ``farms.organization_id``) and
    species-scoped (the discriminator is validated against the pure config);
  * appends an immutable timeline event — the animal's life history is preserved
    permanently (Goat Doc 2 §2);
  * writes an audit-log entry (Goat Doc 7 §9);
  * never destroys history — status transitions are soft, records are archived
    not deleted (Goat Doc 2 §2).

Ownership events (transfer / sale / death / culling) record herd facts only.
Financial posting is deferred to the Sales/Finance milestone, which reuses the
Greena Finance ledger rather than duplicating it (Goat Doc 3 §12.10).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantBloodline,
    SmallRuminantBreed,
    SmallRuminantDocument,
    SmallRuminantEvent,
    SmallRuminantGroup,
    SmallRuminantHerd,
    SmallRuminantMedia,
    SmallRuminantPasture,
    SmallRuminantPen,
    TERMINAL_STATUSES,
)
from app.schemas.small_ruminant import (
    AnimalCreate,
    AnimalUpdate,
    BloodlineCreate,
    BloodlineUpdate,
    BreedCreate,
    BreedUpdate,
    CullInput,
    DeathInput,
    DocumentCreate,
    MediaCreate,
    MoveInput,
    SaleInput,
    TransferInput,
)
from app.services import audit_service, small_ruminant_species_config as cfg

# Per-species internal-ref prefix (GT-00001 goat, SH-00001 sheep).
_REF_PREFIX = {"goat": "GT", "sheep": "SH"}


# ── Internal helpers ──────────────────────────────────────────────────────────

def validate_species(species: str) -> str:
    """Guard the discriminator at the service boundary (never invent a species)."""
    if not cfg.is_supported(species):
        raise ValidationException(
            f"Unsupported species {species!r}; expected one of {cfg.SPECIES_VALUES}."
        )
    return species


async def _get_animal_or_404(
    db: AsyncSession, farm_id: uuid.UUID, species: str, animal_id: uuid.UUID
) -> SmallRuminant:
    result = await db.execute(
        select(SmallRuminant).where(
            SmallRuminant.id == animal_id,
            SmallRuminant.farm_id == farm_id,
            SmallRuminant.species == species,
            SmallRuminant.deleted_at.is_(None),
        )
    )
    a = result.scalar_one_or_none()
    if a is None:
        raise NotFoundException(f"{species.capitalize()} {animal_id} not found on this farm.")
    return a


async def _generate_internal_ref(db: AsyncSession, farm_id: uuid.UUID, species: str) -> str:
    """Sequential per-farm, per-species reference (GT-00001 / SH-00001). Uniqueness
    is enforced by the DB constraint; the count only seeds a readable start."""
    result = await db.execute(
        select(func.count(SmallRuminant.id)).where(
            SmallRuminant.farm_id == farm_id, SmallRuminant.species == species
        )
    )
    seq = (result.scalar_one() or 0) + 1
    return f"{_REF_PREFIX[species]}-{seq:05d}"


async def _append_event(
    db: AsyncSession,
    animal_id: uuid.UUID,
    event_type: str,
    summary: str,
    *,
    occurred_at: datetime | None = None,
    operator_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> SmallRuminantEvent:
    event = SmallRuminantEvent(
        id=uuid.uuid4(),
        animal_id=animal_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        summary=summary,
        details=details or {},
        operator_id=operator_id,
    )
    db.add(event)
    await db.flush()
    return event


def _guard_not_terminal(a: SmallRuminant, action: str) -> None:
    if a.status in TERMINAL_STATUSES:
        raise ConflictException(
            f"Cannot {action}: {a.internal_ref} is already {a.status}. "
            "Terminal records are permanent and cannot transition further."
        )


def _jsonable(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


async def _validate_location(
    db: AsyncSession, farm_id: uuid.UUID, species: str,
    *, herd_id=None, group_id=None, pen_id=None, pasture_id=None,
) -> None:
    """Validate that referenced groupings/locations exist on this farm (and, for
    species-scoped ones, match the species). Physical pens/pastures are
    species-neutral farm infrastructure."""
    if herd_id is not None:
        await _require(db, SmallRuminantHerd, farm_id, herd_id, species=species)
    if group_id is not None:
        await _require(db, SmallRuminantGroup, farm_id, group_id, species=species)
    if pen_id is not None:
        await _require(db, SmallRuminantPen, farm_id, pen_id)
    if pasture_id is not None:
        await _require(db, SmallRuminantPasture, farm_id, pasture_id)


async def _require(db, model, farm_id, obj_id, species: str | None = None) -> None:
    conds = [model.id == obj_id, model.farm_id == farm_id, model.deleted_at.is_(None)]
    if species is not None:
        conds.append(model.species == species)
    result = await db.execute(select(model.id).where(*conds))
    if result.scalar_one_or_none() is None:
        raise NotFoundException(f"{model.__name__} {obj_id} not found on this farm.")


async def _resolve_names(db: AsyncSession, animals: list[SmallRuminant]) -> dict:
    """Batch-resolve breed / bloodline / herd / group / pen / pasture names (no N+1)."""
    def _ids(attr):
        return {getattr(a, attr) for a in animals if getattr(a, attr)}

    async def _names(model, ids):
        if not ids:
            return {}
        rows = await db.execute(select(model.id, model.name).where(model.id.in_(ids)))
        return {row[0]: row[1] for row in rows}

    return {
        "breed": await _names(SmallRuminantBreed, _ids("breed_id")),
        "bloodline": await _names(SmallRuminantBloodline, _ids("bloodline_id")),
        "herd": await _names(SmallRuminantHerd, _ids("herd_id")),
        "group": await _names(SmallRuminantGroup, _ids("group_id")),
        "pen": await _names(SmallRuminantPen, _ids("pen_id")),
        "pasture": await _names(SmallRuminantPasture, _ids("pasture_id")),
    }


# ── Catalog: Breeds (data-driven, species-scoped) ─────────────────────────────

async def list_breeds(db: AsyncSession, species: str, org_id: uuid.UUID | None) -> list[SmallRuminantBreed]:
    """Global system catalog (organization_id IS NULL) plus this org's custom entries,
    filtered to the species."""
    conds = [SmallRuminantBreed.deleted_at.is_(None), SmallRuminantBreed.species == species]
    if org_id is not None:
        conds.append(or_(SmallRuminantBreed.organization_id.is_(None),
                         SmallRuminantBreed.organization_id == org_id))
    else:
        conds.append(SmallRuminantBreed.organization_id.is_(None))
    result = await db.execute(select(SmallRuminantBreed).where(*conds).order_by(SmallRuminantBreed.name))
    return list(result.scalars().all())


async def create_breed(
    db: AsyncSession, species: str, org_id: uuid.UUID | None, data: BreedCreate, user: User
) -> SmallRuminantBreed:
    breed = SmallRuminantBreed(
        id=uuid.uuid4(), species=species, organization_id=org_id, name=data.name,
        category=data.category, origin=data.origin, production_purpose=data.production_purpose,
        profile=data.profile, is_system=False, created_by=user.id,
    )
    db.add(breed)
    await db.flush()
    await audit_service.log_action(
        db, action=f"sr.{species}.breed.create", resource_type="sr_breed",
        resource_id=breed.id, user_id=user.id, new_value={"name": breed.name},
    )
    await db.commit()
    await db.refresh(breed)
    return breed


async def update_breed(
    db: AsyncSession, species: str, org_id: uuid.UUID | None, breed_id: uuid.UUID,
    data: BreedUpdate, user: User,
) -> SmallRuminantBreed:
    result = await db.execute(
        select(SmallRuminantBreed).where(
            SmallRuminantBreed.id == breed_id, SmallRuminantBreed.species == species,
            SmallRuminantBreed.deleted_at.is_(None),
        )
    )
    breed = result.scalar_one_or_none()
    if breed is None:
        raise NotFoundException(f"Breed {breed_id} not found.")
    if breed.organization_id is None:
        raise ConflictException("System breeds cannot be edited.")
    if breed.organization_id != org_id:
        raise NotFoundException(f"Breed {breed_id} not found.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(breed, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action=f"sr.{species}.breed.update", resource_type="sr_breed",
        resource_id=breed.id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breed)
    return breed


# ── Catalog: Bloodlines ────────────────────────────────────────────────────────

async def list_bloodlines(db: AsyncSession, farm_id: uuid.UUID, species: str) -> list[SmallRuminantBloodline]:
    result = await db.execute(
        select(SmallRuminantBloodline).where(
            SmallRuminantBloodline.farm_id == farm_id,
            SmallRuminantBloodline.species == species,
            SmallRuminantBloodline.deleted_at.is_(None),
        ).order_by(SmallRuminantBloodline.name)
    )
    return list(result.scalars().all())


async def create_bloodline(
    db: AsyncSession, farm: Farm, species: str, data: BloodlineCreate, user: User
) -> SmallRuminantBloodline:
    line = SmallRuminantBloodline(
        id=uuid.uuid4(), species=species, farm_id=farm.id, breed_id=data.breed_id,
        name=data.name, code=data.code, origin=data.origin, notes=data.notes, created_by=user.id,
    )
    db.add(line)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not create bloodline — duplicate code.") from exc
    await audit_service.log_action(
        db, action=f"sr.{species}.bloodline.create", resource_type="sr_bloodline",
        resource_id=line.id, farm_id=farm.id, user_id=user.id, new_value={"name": line.name},
    )
    await db.commit()
    await db.refresh(line)
    return line


async def update_bloodline(
    db: AsyncSession, farm_id: uuid.UUID, species: str, line_id: uuid.UUID,
    data: BloodlineUpdate, user: User,
) -> SmallRuminantBloodline:
    result = await db.execute(
        select(SmallRuminantBloodline).where(
            SmallRuminantBloodline.id == line_id, SmallRuminantBloodline.farm_id == farm_id,
            SmallRuminantBloodline.species == species, SmallRuminantBloodline.deleted_at.is_(None),
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundException(f"Bloodline {line_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action=f"sr.{species}.bloodline.update", resource_type="sr_bloodline",
        resource_id=line.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(line)
    return line


# ── Animals — register / read / update ────────────────────────────────────────

async def create_animal(
    db: AsyncSession, farm: Farm, species: str, data: AnimalCreate, user: User
) -> SmallRuminant:
    # Sex must be a valid token for this species (goat: buck/doe/wether; sheep: ram/ewe/wether).
    if not cfg.is_valid_sex(species, data.sex):
        raise ValidationException(
            f"sex {data.sex!r} is not valid for {species}; expected one of "
            f"{cfg.allowed_sex_values(species)}."
        )
    await _validate_location(
        db, farm.id, species,
        herd_id=data.herd_id, group_id=data.group_id, pen_id=data.pen_id, pasture_id=data.pasture_id,
    )

    internal_ref = data.internal_ref or await _generate_internal_ref(db, farm.id, species)

    if data.ear_tag:
        dup = await db.execute(
            select(SmallRuminant.id).where(
                SmallRuminant.farm_id == farm.id, SmallRuminant.ear_tag == data.ear_tag,
                SmallRuminant.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {data.ear_tag} already exists on this farm.")

    payload = data.model_dump(exclude={"internal_ref"})
    a = SmallRuminant(
        id=uuid.uuid4(), species=species, farm_id=farm.id, internal_ref=internal_ref,
        status="active", created_by=user.id, **payload,
    )
    db.add(a)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not register animal — duplicate reference.") from exc

    await _append_event(
        db, a.id, "created", f"{species.capitalize()} {internal_ref} registered",
        operator_id=user.id,
        details={"internal_ref": internal_ref, "sex": data.sex, "purpose": data.purpose},
    )
    await audit_service.log_action(
        db, action=f"sr.{species}.create", resource_type="sr_animal",
        resource_id=a.id, farm_id=farm.id, user_id=user.id,
        new_value={"internal_ref": internal_ref, "name": data.name},
    )
    await db.commit()
    await db.refresh(a)
    return a


async def list_animals(
    db: AsyncSession,
    farm_id: uuid.UUID,
    species: str,
    *,
    status: str | None = None,
    breed_id: uuid.UUID | None = None,
    herd_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    pen_id: uuid.UUID | None = None,
    pasture_id: uuid.UUID | None = None,
    sex: str | None = None,
    purpose: str | None = None,
    lifecycle_stage: str | None = None,
    reproductive_status: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SmallRuminant], int, dict]:
    conds = [
        SmallRuminant.farm_id == farm_id,
        SmallRuminant.species == species,
        SmallRuminant.deleted_at.is_(None),
    ]
    if status:
        conds.append(SmallRuminant.status == status)
    elif not include_archived:
        conds.append(SmallRuminant.status != "archived")
    if breed_id:
        conds.append(SmallRuminant.breed_id == breed_id)
    if herd_id:
        conds.append(SmallRuminant.herd_id == herd_id)
    if group_id:
        conds.append(SmallRuminant.group_id == group_id)
    if pen_id:
        conds.append(SmallRuminant.pen_id == pen_id)
    if pasture_id:
        conds.append(SmallRuminant.pasture_id == pasture_id)
    if sex:
        conds.append(SmallRuminant.sex == sex)
    if purpose:
        conds.append(SmallRuminant.purpose == purpose)
    if lifecycle_stage:
        conds.append(SmallRuminant.lifecycle_stage == lifecycle_stage)
    if reproductive_status:
        conds.append(SmallRuminant.reproductive_status == reproductive_status)
    if search:
        like = f"%{search}%"
        conds.append(or_(
            SmallRuminant.name.ilike(like),
            SmallRuminant.internal_ref.ilike(like),
            SmallRuminant.ear_tag.ilike(like),
            SmallRuminant.tattoo.ilike(like),
            SmallRuminant.qr_code.ilike(like),
        ))
    if tag:
        conds.append(SmallRuminant.tags.contains([tag]))

    total_result = await db.execute(select(func.count(SmallRuminant.id)).where(*conds))
    total = total_result.scalar_one()

    result = await db.execute(
        select(SmallRuminant).where(*conds)
        .order_by(SmallRuminant.created_at.desc())
        .limit(limit).offset(offset)
    )
    animals = list(result.scalars().all())
    names = await _resolve_names(db, animals)
    return animals, total, names


async def get_animal_detail(db: AsyncSession, farm_id: uuid.UUID, species: str, animal_id: uuid.UUID):
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    names = await _resolve_names(db, [a])
    parent_ids = {pid for pid in (a.sire_id, a.dam_id) if pid}
    parent_refs: dict = {}
    if parent_ids:
        rows = await db.execute(
            select(SmallRuminant.id, SmallRuminant.internal_ref).where(SmallRuminant.id.in_(parent_ids))
        )
        parent_refs = {row[0]: row[1] for row in rows}
    return a, names, parent_refs


async def update_animal(
    db: AsyncSession, farm_id: uuid.UUID, species: str, animal_id: uuid.UUID,
    data: AnimalUpdate, user: User,
) -> SmallRuminant:
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    _guard_not_terminal(a, "edit")
    fields = data.model_dump(exclude_unset=True)

    if fields.get("sex") and not cfg.is_valid_sex(species, fields["sex"]):
        raise ValidationException(
            f"sex {fields['sex']!r} is not valid for {species}; expected one of "
            f"{cfg.allowed_sex_values(species)}."
        )
    await _validate_location(
        db, farm_id, species,
        herd_id=fields.get("herd_id"), group_id=fields.get("group_id"),
    )

    if "ear_tag" in fields and fields["ear_tag"]:
        dup = await db.execute(
            select(SmallRuminant.id).where(
                SmallRuminant.farm_id == farm_id, SmallRuminant.ear_tag == fields["ear_tag"],
                SmallRuminant.id != animal_id, SmallRuminant.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {fields['ear_tag']} already exists on this farm.")

    for label in ("sire_id", "dam_id"):
        if fields.get(label) == animal_id:
            raise ValidationException(f"An animal cannot be its own {label.replace('_id', '')}.")

    changes: dict = {}
    for field, value in fields.items():
        old = getattr(a, field)
        if old != value:
            changes[field] = {"from": _jsonable(old), "to": _jsonable(value)}
            setattr(a, field, value)

    if not changes:
        return a

    await db.flush()
    await _append_event(db, a.id, "updated", "Animal details updated",
                        operator_id=user.id, details={"changes": changes})
    await audit_service.log_action(
        db, action=f"sr.{species}.update", resource_type="sr_animal",
        resource_id=a.id, farm_id=farm_id, user_id=user.id, new_value={"changes": changes},
    )
    await db.commit()
    await db.refresh(a)
    return a


# ── Animals — movement & lifecycle transitions ────────────────────────────────

async def move_animal(
    db: AsyncSession, farm_id: uuid.UUID, species: str, animal_id: uuid.UUID,
    data: MoveInput, user: User,
) -> SmallRuminant:
    """Move an animal between management group and/or physical pen/pasture.
    History is preserved on the timeline (Goat Doc 2 §18)."""
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    _guard_not_terminal(a, "move")

    fields = data.model_dump(exclude_unset=True, exclude={"clear", "reason", "occurred_on", "notes"})
    await _validate_location(
        db, farm_id, species,
        group_id=fields.get("group_id"), pen_id=fields.get("pen_id"), pasture_id=fields.get("pasture_id"),
    )

    before = {"group_id": a.group_id, "pen_id": a.pen_id, "pasture_id": a.pasture_id}
    for field, value in fields.items():
        setattr(a, field, value)
    for field in data.clear:
        if field in ("group_id", "pen_id", "pasture_id"):
            setattr(a, field, None)

    after = {"group_id": a.group_id, "pen_id": a.pen_id, "pasture_id": a.pasture_id}
    if before == after:
        raise ConflictException("No location change requested.")

    await db.flush()
    await _append_event(
        db, a.id, "moved", "Animal moved",
        occurred_at=(datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc)
                     if data.occurred_on else None),
        operator_id=user.id,
        details={"from": {k: _jsonable(v) for k, v in before.items()},
                 "to": {k: _jsonable(v) for k, v in after.items()},
                 "reason": data.reason, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action=f"sr.{species}.move", resource_type="sr_animal",
        resource_id=a.id, farm_id=farm_id, user_id=user.id,
        old_value={k: _jsonable(v) for k, v in before.items()},
        new_value={k: _jsonable(v) for k, v in after.items()},
    )
    await db.commit()
    await db.refresh(a)
    return a


async def _terminal_transition(
    db, farm_id, species, animal_id, user, *, new_status, event_type, summary, action, details, occurred_on,
):
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    _guard_not_terminal(a, event_type)
    on = occurred_on or date.today()
    a.status = new_status
    a.group_id = None
    a.pen_id = None
    a.pasture_id = None
    await db.flush()
    await _append_event(
        db, a.id, event_type, summary,
        occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details=details,
    )
    await audit_service.log_action(
        db, action=action, resource_type="sr_animal",
        resource_id=a.id, farm_id=farm_id, user_id=user.id, new_value=details,
    )
    await db.commit()
    await db.refresh(a)
    return a


async def archive_animal(db, farm_id, species, animal_id, reason: str | None, user: User) -> SmallRuminant:
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    _guard_not_terminal(a, "archive")
    if a.status == "archived":
        raise ConflictException("Animal is already archived.")
    a.status = "archived"
    await db.flush()
    await _append_event(db, a.id, "archived", "Animal archived", operator_id=user.id,
                        details={"reason": reason})
    await audit_service.log_action(
        db, action=f"sr.{species}.archive", resource_type="sr_animal",
        resource_id=a.id, farm_id=farm_id, user_id=user.id, new_value={"reason": reason},
    )
    await db.commit()
    await db.refresh(a)
    return a


async def restore_animal(db, farm_id, species, animal_id, user: User) -> SmallRuminant:
    a = await _get_animal_or_404(db, farm_id, species, animal_id)
    if a.status != "archived":
        raise ConflictException("Only archived animals can be restored.")
    a.status = "active"
    await db.flush()
    await _append_event(db, a.id, "restored", "Animal restored to the herd/flock", operator_id=user.id)
    await audit_service.log_action(
        db, action=f"sr.{species}.restore", resource_type="sr_animal",
        resource_id=a.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(a)
    return a


async def transfer_animal(db, farm_id, species, animal_id, data: TransferInput, user: User) -> SmallRuminant:
    return await _terminal_transition(
        db, farm_id, species, animal_id, user,
        new_status="transferred", event_type="transferred",
        summary=f"Transferred to {data.to_owner_name}", action=f"sr.{species}.transfer",
        details={"to_owner": data.to_owner_name, "destination": data.destination, "notes": data.notes},
        occurred_on=data.occurred_on,
    )


async def sell_animal(db, farm_id, species, animal_id, data: SaleInput, user: User) -> SmallRuminant:
    """Record a sale as a herd fact. Revenue posting to Finance is handled by the
    Sales/Finance milestone; here the price is captured on the timeline only."""
    return await _terminal_transition(
        db, farm_id, species, animal_id, user,
        new_status="sold", event_type="sold",
        summary=f"Sold to {data.buyer_name}", action=f"sr.{species}.sell",
        details={"buyer": data.buyer_name, "price": _jsonable(data.price),
                 "currency": data.currency, "notes": data.notes},
        occurred_on=data.occurred_on,
    )


async def record_death(db, farm_id, species, animal_id, data: DeathInput, user: User) -> SmallRuminant:
    return await _terminal_transition(
        db, farm_id, species, animal_id, user,
        new_status="deceased", event_type="died", summary="Animal deceased",
        action=f"sr.{species}.death",
        details={"cause": data.cause, "notes": data.notes}, occurred_on=data.occurred_on,
    )


async def cull_animal(db, farm_id, species, animal_id, data: CullInput, user: User) -> SmallRuminant:
    return await _terminal_transition(
        db, farm_id, species, animal_id, user,
        new_status="culled", event_type="culled", summary="Animal culled",
        action=f"sr.{species}.cull",
        details={"reason": data.reason, "notes": data.notes}, occurred_on=data.occurred_on,
    )


# ── Timeline ──────────────────────────────────────────────────────────────────

async def list_events(
    db: AsyncSession, farm_id: uuid.UUID, species: str, animal_id: uuid.UUID,
    limit: int = 100, offset: int = 0,
) -> list[SmallRuminantEvent]:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    result = await db.execute(
        select(SmallRuminantEvent).where(
            SmallRuminantEvent.animal_id == animal_id, SmallRuminantEvent.deleted_at.is_(None)
        ).order_by(SmallRuminantEvent.occurred_at.desc(), SmallRuminantEvent.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())


# ── Attachments (media / documents) ───────────────────────────────────────────

async def add_media(db, farm_id, species, animal_id, data: MediaCreate, user: User) -> SmallRuminantMedia:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Media requires a url or storage_path.")
    media = SmallRuminantMedia(
        id=uuid.uuid4(), animal_id=animal_id, media_type=data.media_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, captured_on=data.captured_on,
        uploaded_by=user.id,
    )
    db.add(media)
    await db.flush()
    await _append_event(db, animal_id, "media_added", f"{data.media_type.capitalize()} added",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action=f"sr.{species}.media.add", resource_type="sr_media",
        resource_id=media.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(media)
    return media


async def list_media(db, farm_id, species, animal_id) -> list[SmallRuminantMedia]:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    result = await db.execute(
        select(SmallRuminantMedia).where(
            SmallRuminantMedia.animal_id == animal_id, SmallRuminantMedia.deleted_at.is_(None)
        ).order_by(SmallRuminantMedia.created_at.desc())
    )
    return list(result.scalars().all())


async def add_document(db, farm_id, species, animal_id, data: DocumentCreate, user: User) -> SmallRuminantDocument:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Document requires a url or storage_path.")
    doc = SmallRuminantDocument(
        id=uuid.uuid4(), animal_id=animal_id, document_type=data.document_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, issued_on=data.issued_on,
        expires_on=data.expires_on, uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await _append_event(db, animal_id, "document_added", f"Document added: {data.document_type}",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action=f"sr.{species}.document.add", resource_type="sr_document",
        resource_id=doc.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db, farm_id, species, animal_id) -> list[SmallRuminantDocument]:
    await _get_animal_or_404(db, farm_id, species, animal_id)
    result = await db.execute(
        select(SmallRuminantDocument).where(
            SmallRuminantDocument.animal_id == animal_id, SmallRuminantDocument.deleted_at.is_(None)
        ).order_by(SmallRuminantDocument.created_at.desc())
    )
    return list(result.scalars().all())
