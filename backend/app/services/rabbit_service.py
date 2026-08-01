"""
Greena — Rabbit Service (Module 17, Milestone 2)

Registry business logic for individual rabbits. This service owns the writes; the
models stay pure and no calculations live here beyond deterministic record-keeping
(GMIS §1.3, §5). Every state change:

  * is farm-scoped (organisation isolation via ``farms.organization_id``);
  * appends an immutable timeline event (Spec Part 8 §14) — the rabbit's life
    history is preserved permanently (Spec Part 2 §2);
  * writes an audit-log entry (Spec Part 8 §13);
  * never destroys history — status transitions are soft, records are archived
    not deleted (Spec Part 2 §2, Part 4 §5).

Ownership events (transfer / sale / death) record herd facts only. Financial
posting is deferred to the Sales/Finance milestone, which reuses the Greena
Finance engine rather than duplicating it (Spec Part 4 §12).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.rabbit import (
    Rabbit,
    RabbitBloodline,
    RabbitBreed,
    RabbitCage,
    RabbitDocument,
    RabbitEvent,
    RabbitMedia,
    RABBIT_TERMINAL_STATUSES,
)
from app.schemas.rabbit import (
    BloodlineCreate,
    BloodlineUpdate,
    BreedCreate,
    BreedUpdate,
    DeathInput,
    DocumentCreate,
    MediaCreate,
    MoveInput,
    RabbitCreate,
    RabbitUpdate,
    SaleInput,
    TransferInput,
)
from app.services import audit_service


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_rabbit_or_404(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> Rabbit:
    result = await db.execute(
        select(Rabbit).where(
            Rabbit.id == rabbit_id,
            Rabbit.farm_id == farm_id,
            Rabbit.deleted_at.is_(None),
        )
    )
    r = result.scalar_one_or_none()
    if r is None:
        raise NotFoundException(f"Rabbit {rabbit_id} not found on this farm.")
    return r


async def _generate_internal_ref(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Sequential per-farm reference (RB-00001). Uniqueness is enforced by the DB
    constraint; the count only seeds a readable starting point."""
    result = await db.execute(
        select(func.count(Rabbit.id)).where(Rabbit.farm_id == farm_id)
    )
    seq = (result.scalar_one() or 0) + 1
    return f"RB-{seq:05d}"


async def _append_event(
    db: AsyncSession,
    rabbit_id: uuid.UUID,
    event_type: str,
    summary: str,
    *,
    occurred_at: datetime | None = None,
    operator_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> RabbitEvent:
    event = RabbitEvent(
        id=uuid.uuid4(),
        rabbit_id=rabbit_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        summary=summary,
        details=details or {},
        operator_id=operator_id,
    )
    db.add(event)
    await db.flush()
    return event


def _guard_not_terminal(r: Rabbit, action: str) -> None:
    if r.status in RABBIT_TERMINAL_STATUSES:
        raise ConflictException(
            f"Cannot {action}: rabbit {r.internal_ref} is already {r.status}. "
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


async def _validate_cage(db: AsyncSession, farm_id: uuid.UUID, cage_id: uuid.UUID) -> RabbitCage:
    result = await db.execute(
        select(RabbitCage).where(
            RabbitCage.id == cage_id,
            RabbitCage.farm_id == farm_id,
            RabbitCage.deleted_at.is_(None),
        )
    )
    cage = result.scalar_one_or_none()
    if cage is None:
        raise NotFoundException(f"Cage {cage_id} not found on this farm.")
    return cage


async def _resolve_names(db: AsyncSession, rabbits: list[Rabbit]) -> tuple[dict, dict, dict]:
    """Batch-resolve breed / bloodline / cage display names (avoids N+1)."""
    breed_ids = {r.breed_id for r in rabbits if r.breed_id}
    line_ids = {r.bloodline_id for r in rabbits if r.bloodline_id}
    cage_ids = {r.cage_id for r in rabbits if r.cage_id}

    breed_names: dict = {}
    line_names: dict = {}
    cage_names: dict = {}
    if breed_ids:
        rows = await db.execute(select(RabbitBreed.id, RabbitBreed.name).where(RabbitBreed.id.in_(breed_ids)))
        breed_names = {row[0]: row[1] for row in rows}
    if line_ids:
        rows = await db.execute(select(RabbitBloodline.id, RabbitBloodline.name).where(RabbitBloodline.id.in_(line_ids)))
        line_names = {row[0]: row[1] for row in rows}
    if cage_ids:
        rows = await db.execute(select(RabbitCage.id, RabbitCage.name).where(RabbitCage.id.in_(cage_ids)))
        cage_names = {row[0]: row[1] for row in rows}
    return breed_names, line_names, cage_names


# ── Catalog: Breeds (data-driven; Spec Part 3 §5) ─────────────────────────────

async def list_breeds(db: AsyncSession, org_id: uuid.UUID | None) -> list[RabbitBreed]:
    """Global system catalog (organization_id IS NULL) plus this org's custom entries."""
    conds = [RabbitBreed.deleted_at.is_(None)]
    if org_id is not None:
        conds.append(or_(RabbitBreed.organization_id.is_(None), RabbitBreed.organization_id == org_id))
    else:
        conds.append(RabbitBreed.organization_id.is_(None))
    result = await db.execute(select(RabbitBreed).where(*conds).order_by(RabbitBreed.name))
    return list(result.scalars().all())


async def create_breed(db: AsyncSession, org_id: uuid.UUID | None, data: BreedCreate, user: User) -> RabbitBreed:
    breed = RabbitBreed(
        id=uuid.uuid4(), organization_id=org_id, name=data.name, category=data.category,
        origin=data.origin, production_purpose=data.production_purpose, profile=data.profile,
        is_system=False, created_by=user.id,
    )
    db.add(breed)
    await db.flush()
    await audit_service.log_action(
        db, action="rabbit.breed.create", resource_type="rabbit_breed",
        resource_id=breed.id, user_id=user.id, new_value={"name": breed.name},
    )
    await db.commit()
    await db.refresh(breed)
    return breed


async def update_breed(
    db: AsyncSession, org_id: uuid.UUID | None, breed_id: uuid.UUID, data: BreedUpdate, user: User
) -> RabbitBreed:
    result = await db.execute(
        select(RabbitBreed).where(RabbitBreed.id == breed_id, RabbitBreed.deleted_at.is_(None))
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
        db, action="rabbit.breed.update", resource_type="rabbit_breed",
        resource_id=breed.id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breed)
    return breed


# ── Catalog: Bloodlines (Spec Part 3 §6) ──────────────────────────────────────

async def list_bloodlines(db: AsyncSession, farm_id: uuid.UUID) -> list[RabbitBloodline]:
    result = await db.execute(
        select(RabbitBloodline).where(
            RabbitBloodline.farm_id == farm_id, RabbitBloodline.deleted_at.is_(None)
        ).order_by(RabbitBloodline.name)
    )
    return list(result.scalars().all())


async def create_bloodline(db: AsyncSession, farm: Farm, data: BloodlineCreate, user: User) -> RabbitBloodline:
    line = RabbitBloodline(
        id=uuid.uuid4(), farm_id=farm.id, breed_id=data.breed_id, name=data.name,
        code=data.code, origin=data.origin, notes=data.notes, created_by=user.id,
    )
    db.add(line)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not create bloodline — duplicate code.") from exc
    await audit_service.log_action(
        db, action="rabbit.bloodline.create", resource_type="rabbit_bloodline",
        resource_id=line.id, farm_id=farm.id, user_id=user.id, new_value={"name": line.name},
    )
    await db.commit()
    await db.refresh(line)
    return line


async def update_bloodline(
    db: AsyncSession, farm_id: uuid.UUID, line_id: uuid.UUID, data: BloodlineUpdate, user: User
) -> RabbitBloodline:
    result = await db.execute(
        select(RabbitBloodline).where(
            RabbitBloodline.id == line_id, RabbitBloodline.farm_id == farm_id,
            RabbitBloodline.deleted_at.is_(None),
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundException(f"Bloodline {line_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="rabbit.bloodline.update", resource_type="rabbit_bloodline",
        resource_id=line.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(line)
    return line


# ── Rabbits — register / read / update ────────────────────────────────────────

async def create_rabbit(db: AsyncSession, farm: Farm, data: RabbitCreate, user: User) -> Rabbit:
    if data.cage_id is not None:
        await _validate_cage(db, farm.id, data.cage_id)

    internal_ref = data.internal_ref or await _generate_internal_ref(db, farm.id)

    # Duplicate ear-tag guard among live rabbits (Spec Part 1 §5 — unique identity).
    if data.ear_tag:
        dup = await db.execute(
            select(Rabbit.id).where(
                Rabbit.farm_id == farm.id, Rabbit.ear_tag == data.ear_tag, Rabbit.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {data.ear_tag} already exists on this farm.")

    r = Rabbit(
        id=uuid.uuid4(),
        farm_id=farm.id,
        breed_id=data.breed_id,
        bloodline_id=data.bloodline_id,
        cage_id=data.cage_id,
        internal_ref=internal_ref,
        name=data.name,
        ear_tag=data.ear_tag,
        tattoo=data.tattoo,
        qr_code=data.qr_code,
        rfid=data.rfid,
        variety=data.variety,
        color=data.color,
        sex=data.sex,
        purpose=data.purpose,
        purposes=data.purposes,
        date_of_birth=data.date_of_birth,
        dob_estimated=data.dob_estimated,
        birth_weight_g=data.birth_weight_g,
        current_weight_g=data.current_weight_g,
        lifecycle_stage=data.lifecycle_stage,
        status="active",
        reproductive_status=data.reproductive_status,
        fertility_status=data.fertility_status,
        acquisition_type=data.acquisition_type,
        acquired_on=data.acquired_on,
        sire_id=data.sire_id,
        dam_id=data.dam_id,
        tags=data.tags,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(r)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not register rabbit — duplicate reference.") from exc

    await _append_event(
        db, r.id, "created", f"Rabbit {internal_ref} registered",
        operator_id=user.id,
        details={"internal_ref": internal_ref, "sex": data.sex, "purpose": data.purpose},
    )
    await audit_service.log_action(
        db, action="rabbit.create", resource_type="rabbit",
        resource_id=r.id, farm_id=farm.id, user_id=user.id,
        new_value={"internal_ref": internal_ref, "name": data.name},
    )
    await db.commit()
    await db.refresh(r)
    return r


async def list_rabbits(
    db: AsyncSession,
    farm_id: uuid.UUID,
    *,
    status: str | None = None,
    breed_id: uuid.UUID | None = None,
    bloodline_id: uuid.UUID | None = None,
    cage_id: uuid.UUID | None = None,
    sex: str | None = None,
    purpose: str | None = None,
    lifecycle_stage: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Rabbit], int, tuple[dict, dict, dict]]:
    conds = [Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None)]
    if status:
        conds.append(Rabbit.status == status)
    elif not include_archived:
        conds.append(Rabbit.status != "archived")
    if breed_id:
        conds.append(Rabbit.breed_id == breed_id)
    if bloodline_id:
        conds.append(Rabbit.bloodline_id == bloodline_id)
    if cage_id:
        conds.append(Rabbit.cage_id == cage_id)
    if sex:
        conds.append(Rabbit.sex == sex)
    if purpose:
        conds.append(Rabbit.purpose == purpose)
    if lifecycle_stage:
        conds.append(Rabbit.lifecycle_stage == lifecycle_stage)
    if search:
        like = f"%{search}%"
        conds.append(or_(
            Rabbit.name.ilike(like),
            Rabbit.internal_ref.ilike(like),
            Rabbit.ear_tag.ilike(like),
            Rabbit.tattoo.ilike(like),
            Rabbit.qr_code.ilike(like),
        ))
    if tag:
        conds.append(Rabbit.tags.contains([tag]))

    total_result = await db.execute(select(func.count(Rabbit.id)).where(*conds))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Rabbit).where(*conds)
        .order_by(Rabbit.created_at.desc())
        .limit(limit).offset(offset)
    )
    rabbits = list(result.scalars().all())
    names = await _resolve_names(db, rabbits)
    return rabbits, total, names


async def get_rabbit_detail(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID):
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    names = await _resolve_names(db, [r])

    # Parent references (recorded links only; unknown stays None).
    parent_ids = {pid for pid in (r.sire_id, r.dam_id) if pid}
    parent_refs: dict = {}
    if parent_ids:
        rows = await db.execute(select(Rabbit.id, Rabbit.internal_ref).where(Rabbit.id.in_(parent_ids)))
        parent_refs = {row[0]: row[1] for row in rows}
    return r, names, parent_refs


async def update_rabbit(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: RabbitUpdate, user: User
) -> Rabbit:
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "edit")

    fields = data.model_dump(exclude_unset=True)

    # Duplicate ear-tag guard on change.
    if "ear_tag" in fields and fields["ear_tag"]:
        dup = await db.execute(
            select(Rabbit.id).where(
                Rabbit.farm_id == farm_id, Rabbit.ear_tag == fields["ear_tag"],
                Rabbit.id != rabbit_id, Rabbit.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {fields['ear_tag']} already exists on this farm.")

    # Self-parent guard (full cycle detection arrives with the Pedigree engine).
    for label in ("sire_id", "dam_id"):
        if fields.get(label) == rabbit_id:
            raise ValidationException(f"A rabbit cannot be its own {label.replace('_id', '')}.")

    changes: dict = {}
    for field, value in fields.items():
        old = getattr(r, field)
        if old != value:
            changes[field] = {"from": _jsonable(old), "to": _jsonable(value)}
            setattr(r, field, value)

    if not changes:
        return r

    await db.flush()
    await _append_event(db, r.id, "updated", "Rabbit details updated",
                        operator_id=user.id, details={"changes": changes})
    await audit_service.log_action(
        db, action="rabbit.update", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id, new_value={"changes": changes},
    )
    await db.commit()
    await db.refresh(r)
    return r


# ── Rabbits — movement & lifecycle transitions ────────────────────────────────

async def move_rabbit(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: MoveInput, user: User
) -> Rabbit:
    """Move a rabbit to another cage (or out of any cage). Movement history is
    preserved on the timeline (Spec Part 2 §12)."""
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "move")
    if data.cage_id is not None:
        await _validate_cage(db, farm_id, data.cage_id)
    previous = r.cage_id
    if previous == data.cage_id:
        raise ConflictException("Rabbit is already in that cage.")
    r.cage_id = data.cage_id
    await db.flush()
    await _append_event(
        db, r.id, "moved", "Rabbit moved between cages",
        occurred_at=(datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc)
                     if data.occurred_on else None),
        operator_id=user.id,
        details={"from_cage_id": _jsonable(previous), "to_cage_id": _jsonable(data.cage_id),
                 "reason": data.reason, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action="rabbit.move", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id,
        old_value={"cage_id": _jsonable(previous)}, new_value={"cage_id": _jsonable(data.cage_id)},
    )
    await db.commit()
    await db.refresh(r)
    return r


async def archive_rabbit(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, reason: str | None, user: User
) -> Rabbit:
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "archive")
    if r.status == "archived":
        raise ConflictException("Rabbit is already archived.")
    r.status = "archived"
    await db.flush()
    await _append_event(db, r.id, "archived", "Rabbit archived", operator_id=user.id,
                        details={"reason": reason})
    await audit_service.log_action(
        db, action="rabbit.archive", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id, new_value={"reason": reason},
    )
    await db.commit()
    await db.refresh(r)
    return r


async def restore_rabbit(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, user: User) -> Rabbit:
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    if r.status != "archived":
        raise ConflictException("Only archived rabbits can be restored.")
    r.status = "active"
    await db.flush()
    await _append_event(db, r.id, "restored", "Rabbit restored to the herd", operator_id=user.id)
    await audit_service.log_action(
        db, action="rabbit.restore", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(r)
    return r


async def transfer_rabbit(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: TransferInput, user: User
) -> Rabbit:
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "transfer")
    on = data.occurred_on or date.today()
    r.status = "transferred"
    r.cage_id = None
    await db.flush()
    await _append_event(
        db, r.id, "transferred", f"Transferred to {data.to_owner_name}",
        occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id,
        details={"to_owner": data.to_owner_name, "destination": data.destination, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action="rabbit.transfer", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id, new_value={"to_owner": data.to_owner_name},
    )
    await db.commit()
    await db.refresh(r)
    return r


async def sell_rabbit(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: SaleInput, user: User
) -> Rabbit:
    """Record a sale as a herd fact. Revenue posting to Finance is handled by the
    Sales/Finance milestone; here the price is captured on the timeline only."""
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "sell")
    on = data.occurred_on or date.today()
    r.status = "sold"
    r.cage_id = None
    await db.flush()
    price = _jsonable(data.price) if data.price is not None else None
    await _append_event(
        db, r.id, "sold", f"Sold to {data.buyer_name}",
        occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id,
        details={"buyer": data.buyer_name, "price": price, "currency": data.currency, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action="rabbit.sell", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id, new_value={"buyer": data.buyer_name, "price": price},
    )
    await db.commit()
    await db.refresh(r)
    return r


async def record_death(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: DeathInput, user: User
) -> Rabbit:
    r = await _get_rabbit_or_404(db, farm_id, rabbit_id)
    _guard_not_terminal(r, "record death for")
    on = data.occurred_on or date.today()
    r.status = "deceased"
    r.cage_id = None
    await db.flush()
    await _append_event(
        db, r.id, "died", "Rabbit deceased",
        occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"cause": data.cause, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action="rabbit.death", resource_type="rabbit",
        resource_id=r.id, farm_id=farm_id, user_id=user.id, new_value={"cause": data.cause},
    )
    await db.commit()
    await db.refresh(r)
    return r


# ── Timeline ──────────────────────────────────────────────────────────────────

async def list_events(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[RabbitEvent]:
    await _get_rabbit_or_404(db, farm_id, rabbit_id)
    result = await db.execute(
        select(RabbitEvent).where(
            RabbitEvent.rabbit_id == rabbit_id, RabbitEvent.deleted_at.is_(None)
        ).order_by(RabbitEvent.occurred_at.desc(), RabbitEvent.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())


# ── Attachments (media / documents) ───────────────────────────────────────────

async def add_media(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: MediaCreate, user: User
) -> RabbitMedia:
    await _get_rabbit_or_404(db, farm_id, rabbit_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Media requires a url or storage_path.")
    media = RabbitMedia(
        id=uuid.uuid4(), rabbit_id=rabbit_id, media_type=data.media_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, captured_on=data.captured_on,
        uploaded_by=user.id,
    )
    db.add(media)
    await db.flush()
    await _append_event(db, rabbit_id, "media_added", f"{data.media_type.capitalize()} added",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action="rabbit.media.add", resource_type="rabbit_media",
        resource_id=media.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(media)
    return media


async def list_media(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> list[RabbitMedia]:
    await _get_rabbit_or_404(db, farm_id, rabbit_id)
    result = await db.execute(
        select(RabbitMedia).where(
            RabbitMedia.rabbit_id == rabbit_id, RabbitMedia.deleted_at.is_(None)
        ).order_by(RabbitMedia.created_at.desc())
    )
    return list(result.scalars().all())


async def add_document(
    db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID, data: DocumentCreate, user: User
) -> RabbitDocument:
    await _get_rabbit_or_404(db, farm_id, rabbit_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Document requires a url or storage_path.")
    doc = RabbitDocument(
        id=uuid.uuid4(), rabbit_id=rabbit_id, document_type=data.document_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, issued_on=data.issued_on,
        expires_on=data.expires_on, uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await _append_event(db, rabbit_id, "document_added", f"Document added: {data.document_type}",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action="rabbit.document.add", resource_type="rabbit_document",
        resource_id=doc.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> list[RabbitDocument]:
    await _get_rabbit_or_404(db, farm_id, rabbit_id)
    result = await db.execute(
        select(RabbitDocument).where(
            RabbitDocument.rabbit_id == rabbit_id, RabbitDocument.deleted_at.is_(None)
        ).order_by(RabbitDocument.created_at.desc())
    )
    return list(result.scalars().all())
