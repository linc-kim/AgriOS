"""
Greena — Swine Service (Module 20, Milestone 2)

Registry business logic for individual pigs. No calculations live here beyond
deterministic record-keeping. Every state change:

  * is farm-scoped (organisation isolation via ``farms.organization_id``);
  * appends an immutable timeline event — the pig's life history is preserved
    permanently (Swine Doc 2 §19);
  * writes an audit-log entry (Swine Doc 5 §15);
  * never destroys history — status transitions are soft, records are archived not
    deleted (Swine Doc 2 §19).

Business rules enforced here (Swine Doc 3 §4):
  * ear tags are unique within a farm;
  * production-stage changes may not regress along the market path (piglet →
    weaner → nursery → grower → finisher) — the pure ``swine_config`` decides;
  * parent links reference pigs that exist on the same farm and a pig may not be
    its own parent (full sire/dam breeding-eligibility is enforced when a *mating*
    is recorded, Milestone 3 — historical pedigree links are not second-guessed).

Ownership events (transfer / sale / death / culling) record herd facts only.
Financial posting is deferred to the Sales/Finance milestone, which reuses the
Greena Finance ledger rather than duplicating it (Swine Doc 5 §5).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineBloodline,
    SwineBreed,
    SwineDocument,
    SwineEvent,
    SwineGroup,
    SwineHerd,
    SwineMedia,
    SwinePen,
    SwinePig,
    TERMINAL_STATUSES,
)
from app.schemas.swine import (
    BloodlineCreate,
    BloodlineUpdate,
    BreedCreate,
    BreedUpdate,
    CullInput,
    DeathInput,
    DocumentCreate,
    MediaCreate,
    MoveInput,
    PigCreate,
    PigUpdate,
    SaleInput,
    TransferInput,
)
from app.services import audit_service, swine_config as cfg

# Internal-ref prefix (SW-00001).
_REF_PREFIX = "SW"


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_pig_or_404(db: AsyncSession, farm_id: uuid.UUID, pig_id: uuid.UUID) -> SwinePig:
    result = await db.execute(
        select(SwinePig).where(
            SwinePig.id == pig_id,
            SwinePig.farm_id == farm_id,
            SwinePig.deleted_at.is_(None),
        )
    )
    p = result.scalar_one_or_none()
    if p is None:
        raise NotFoundException(f"Pig {pig_id} not found on this farm.")
    return p


async def _generate_internal_ref(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Sequential per-farm reference (SW-00001). Uniqueness is enforced by the DB
    constraint; the count only seeds a readable start."""
    result = await db.execute(
        select(func.count(SwinePig.id)).where(SwinePig.farm_id == farm_id)
    )
    seq = (result.scalar_one() or 0) + 1
    return f"{_REF_PREFIX}-{seq:05d}"


async def _append_event(
    db: AsyncSession,
    pig_id: uuid.UUID,
    event_type: str,
    summary: str,
    *,
    occurred_at: datetime | None = None,
    operator_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> SwineEvent:
    event = SwineEvent(
        id=uuid.uuid4(),
        pig_id=pig_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        summary=summary,
        details=details or {},
        operator_id=operator_id,
    )
    db.add(event)
    await db.flush()
    return event


def _guard_not_terminal(p: SwinePig, action: str) -> None:
    if p.status in TERMINAL_STATUSES:
        raise ConflictException(
            f"Cannot {action}: {p.internal_ref} is already {p.status}. "
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
    db: AsyncSession, farm_id: uuid.UUID,
    *, herd_id=None, group_id=None, pen_id=None,
) -> None:
    """Validate that referenced groupings/locations exist on this farm."""
    if herd_id is not None:
        await _require(db, SwineHerd, farm_id, herd_id)
    if group_id is not None:
        await _require(db, SwineGroup, farm_id, group_id)
    if pen_id is not None:
        await _require(db, SwinePen, farm_id, pen_id)


async def _require(db, model, farm_id, obj_id) -> None:
    result = await db.execute(
        select(model.id).where(
            model.id == obj_id, model.farm_id == farm_id, model.deleted_at.is_(None)
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundException(f"{model.__name__} {obj_id} not found on this farm.")


async def _validate_parents(
    db: AsyncSession, farm_id: uuid.UUID, self_id: uuid.UUID | None,
    *, sire_id=None, dam_id=None,
) -> None:
    """Parent links must reference pigs on this farm and never the pig itself.

    Sire/dam breeding-eligibility (a barrow is never a valid sire) is enforced when a
    *mating* is recorded (Milestone 3); a stored pedigree link is a historical fact
    and is not re-litigated here — an animal castrated after sibling was born keeps
    its recorded ancestry.
    """
    for label, pid in (("sire", sire_id), ("dam", dam_id)):
        if pid is None:
            continue
        if self_id is not None and pid == self_id:
            raise ValidationException(f"A pig cannot be its own {label}.")
        await _require(db, SwinePig, farm_id, pid)


async def _resolve_names(db: AsyncSession, pigs: list[SwinePig]) -> dict:
    """Batch-resolve breed / bloodline / herd / group / pen names (no N+1)."""
    def _ids(attr):
        return {getattr(p, attr) for p in pigs if getattr(p, attr)}

    async def _names(model, ids):
        if not ids:
            return {}
        rows = await db.execute(select(model.id, model.name).where(model.id.in_(ids)))
        return {row[0]: row[1] for row in rows}

    return {
        "breed": await _names(SwineBreed, _ids("breed_id")),
        "bloodline": await _names(SwineBloodline, _ids("bloodline_id")),
        "herd": await _names(SwineHerd, _ids("herd_id")),
        "group": await _names(SwineGroup, _ids("group_id")),
        "pen": await _names(SwinePen, _ids("pen_id")),
    }


# ── Catalog: Breeds (data-driven) ─────────────────────────────────────────────

async def list_breeds(db: AsyncSession, org_id: uuid.UUID | None) -> list[SwineBreed]:
    """Global system catalog (organization_id IS NULL) plus this org's custom entries."""
    conds = [SwineBreed.deleted_at.is_(None)]
    if org_id is not None:
        conds.append(or_(SwineBreed.organization_id.is_(None),
                         SwineBreed.organization_id == org_id))
    else:
        conds.append(SwineBreed.organization_id.is_(None))
    result = await db.execute(select(SwineBreed).where(*conds).order_by(SwineBreed.name))
    return list(result.scalars().all())


async def create_breed(
    db: AsyncSession, org_id: uuid.UUID | None, data: BreedCreate, user: User
) -> SwineBreed:
    breed = SwineBreed(
        id=uuid.uuid4(), organization_id=org_id, name=data.name,
        category=data.category, origin=data.origin, production_purpose=data.production_purpose,
        profile=data.profile, is_system=False, created_by=user.id,
    )
    db.add(breed)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.breed.create", resource_type="swine_breed",
        resource_id=breed.id, user_id=user.id, new_value={"name": breed.name},
    )
    await db.commit()
    await db.refresh(breed)
    return breed


async def update_breed(
    db: AsyncSession, org_id: uuid.UUID | None, breed_id: uuid.UUID, data: BreedUpdate, user: User
) -> SwineBreed:
    result = await db.execute(
        select(SwineBreed).where(SwineBreed.id == breed_id, SwineBreed.deleted_at.is_(None))
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
        db, action="swine.breed.update", resource_type="swine_breed",
        resource_id=breed.id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breed)
    return breed


# ── Catalog: Bloodlines ────────────────────────────────────────────────────────

async def list_bloodlines(db: AsyncSession, farm_id: uuid.UUID) -> list[SwineBloodline]:
    result = await db.execute(
        select(SwineBloodline).where(
            SwineBloodline.farm_id == farm_id, SwineBloodline.deleted_at.is_(None),
        ).order_by(SwineBloodline.name)
    )
    return list(result.scalars().all())


async def create_bloodline(db: AsyncSession, farm: Farm, data: BloodlineCreate, user: User) -> SwineBloodline:
    line = SwineBloodline(
        id=uuid.uuid4(), farm_id=farm.id, breed_id=data.breed_id,
        name=data.name, code=data.code, origin=data.origin, notes=data.notes, created_by=user.id,
    )
    db.add(line)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not create bloodline — duplicate code.") from exc
    await audit_service.log_action(
        db, action="swine.bloodline.create", resource_type="swine_bloodline",
        resource_id=line.id, farm_id=farm.id, user_id=user.id, new_value={"name": line.name},
    )
    await db.commit()
    await db.refresh(line)
    return line


async def update_bloodline(
    db: AsyncSession, farm_id: uuid.UUID, line_id: uuid.UUID, data: BloodlineUpdate, user: User
) -> SwineBloodline:
    result = await db.execute(
        select(SwineBloodline).where(
            SwineBloodline.id == line_id, SwineBloodline.farm_id == farm_id,
            SwineBloodline.deleted_at.is_(None),
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundException(f"Bloodline {line_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.bloodline.update", resource_type="swine_bloodline",
        resource_id=line.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(line)
    return line


# ── Pigs — register / read / update ───────────────────────────────────────────

async def create_pig(db: AsyncSession, farm: Farm, data: PigCreate, user: User) -> SwinePig:
    if not cfg.is_valid_sex(data.sex):
        raise ValidationException(
            f"sex {data.sex!r} is not valid; expected one of {cfg.SEX_VALUES}."
        )
    await _validate_location(db, farm.id, herd_id=data.herd_id, group_id=data.group_id, pen_id=data.pen_id)
    await _validate_parents(db, farm.id, None, sire_id=data.sire_id, dam_id=data.dam_id)

    internal_ref = data.internal_ref or await _generate_internal_ref(db, farm.id)

    if data.ear_tag:
        dup = await db.execute(
            select(SwinePig.id).where(
                SwinePig.farm_id == farm.id, SwinePig.ear_tag == data.ear_tag,
                SwinePig.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {data.ear_tag} already exists on this farm.")

    payload = data.model_dump(exclude={"internal_ref"})
    p = SwinePig(
        id=uuid.uuid4(), farm_id=farm.id, internal_ref=internal_ref,
        status="active", created_by=user.id, **payload,
    )
    db.add(p)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException("Could not register pig — duplicate reference.") from exc

    await _append_event(
        db, p.id, "created", f"Pig {internal_ref} registered",
        operator_id=user.id,
        details={"internal_ref": internal_ref, "sex": data.sex, "production_stage": data.production_stage},
    )
    await audit_service.log_action(
        db, action="swine.create", resource_type="swine_pig",
        resource_id=p.id, farm_id=farm.id, user_id=user.id,
        new_value={"internal_ref": internal_ref, "name": data.name},
    )
    await db.commit()
    await db.refresh(p)
    return p


async def list_pigs(
    db: AsyncSession,
    farm_id: uuid.UUID,
    *,
    status: str | None = None,
    breed_id: uuid.UUID | None = None,
    herd_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    pen_id: uuid.UUID | None = None,
    sex: str | None = None,
    purpose: str | None = None,
    production_stage: str | None = None,
    reproductive_status: str | None = None,
    market_status: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SwinePig], int, dict]:
    conds = [SwinePig.farm_id == farm_id, SwinePig.deleted_at.is_(None)]
    if status:
        conds.append(SwinePig.status == status)
    elif not include_archived:
        conds.append(SwinePig.status != "archived")
    if breed_id:
        conds.append(SwinePig.breed_id == breed_id)
    if herd_id:
        conds.append(SwinePig.herd_id == herd_id)
    if group_id:
        conds.append(SwinePig.group_id == group_id)
    if pen_id:
        conds.append(SwinePig.pen_id == pen_id)
    if sex:
        conds.append(SwinePig.sex == sex)
    if purpose:
        conds.append(SwinePig.purpose == purpose)
    if production_stage:
        conds.append(SwinePig.production_stage == production_stage)
    if reproductive_status:
        conds.append(SwinePig.reproductive_status == reproductive_status)
    if market_status:
        conds.append(SwinePig.market_status == market_status)
    if search:
        like = f"%{search}%"
        conds.append(or_(
            SwinePig.name.ilike(like),
            SwinePig.internal_ref.ilike(like),
            SwinePig.ear_tag.ilike(like),
            SwinePig.tattoo.ilike(like),
            SwinePig.qr_code.ilike(like),
        ))
    if tag:
        conds.append(SwinePig.tags.contains([tag]))

    total_result = await db.execute(select(func.count(SwinePig.id)).where(*conds))
    total = total_result.scalar_one()

    result = await db.execute(
        select(SwinePig).where(*conds)
        .order_by(SwinePig.created_at.desc())
        .limit(limit).offset(offset)
    )
    pigs = list(result.scalars().all())
    names = await _resolve_names(db, pigs)
    return pigs, total, names


async def get_pig_detail(db: AsyncSession, farm_id: uuid.UUID, pig_id: uuid.UUID):
    p = await _get_pig_or_404(db, farm_id, pig_id)
    names = await _resolve_names(db, [p])
    parent_ids = {pid for pid in (p.sire_id, p.dam_id) if pid}
    parent_refs: dict = {}
    if parent_ids:
        rows = await db.execute(
            select(SwinePig.id, SwinePig.internal_ref).where(SwinePig.id.in_(parent_ids))
        )
        parent_refs = {row[0]: row[1] for row in rows}
    return p, names, parent_refs


async def update_pig(
    db: AsyncSession, farm_id: uuid.UUID, pig_id: uuid.UUID, data: PigUpdate, user: User
) -> SwinePig:
    p = await _get_pig_or_404(db, farm_id, pig_id)
    _guard_not_terminal(p, "edit")
    fields = data.model_dump(exclude_unset=True)

    if fields.get("sex") and not cfg.is_valid_sex(fields["sex"]):
        raise ValidationException(
            f"sex {fields['sex']!r} is not valid; expected one of {cfg.SEX_VALUES}."
        )
    # Production stage may not regress along the linear market path (Swine Doc 3 §4).
    if "production_stage" in fields and fields["production_stage"] != p.production_stage:
        if not cfg.is_forward_stage_transition(p.production_stage, fields["production_stage"]):
            raise ValidationException(
                f"Invalid production-stage transition {p.production_stage!r} → "
                f"{fields['production_stage']!r}: a pig may not regress along the market path."
            )
    await _validate_location(db, farm_id, herd_id=fields.get("herd_id"), group_id=fields.get("group_id"))
    await _validate_parents(db, farm_id, pig_id, sire_id=fields.get("sire_id"), dam_id=fields.get("dam_id"))

    if "ear_tag" in fields and fields["ear_tag"]:
        dup = await db.execute(
            select(SwinePig.id).where(
                SwinePig.farm_id == farm_id, SwinePig.ear_tag == fields["ear_tag"],
                SwinePig.id != pig_id, SwinePig.deleted_at.is_(None),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise ConflictException(f"Ear tag {fields['ear_tag']} already exists on this farm.")

    changes: dict = {}
    for field, value in fields.items():
        old = getattr(p, field)
        if old != value:
            changes[field] = {"from": _jsonable(old), "to": _jsonable(value)}
            setattr(p, field, value)

    if not changes:
        return p

    await db.flush()
    await _append_event(db, p.id, "updated", "Pig details updated",
                        operator_id=user.id, details={"changes": changes})
    await audit_service.log_action(
        db, action="swine.update", resource_type="swine_pig",
        resource_id=p.id, farm_id=farm_id, user_id=user.id, new_value={"changes": changes},
    )
    await db.commit()
    await db.refresh(p)
    return p


# ── Pigs — movement & lifecycle transitions ───────────────────────────────────

async def move_pig(
    db: AsyncSession, farm_id: uuid.UUID, pig_id: uuid.UUID, data: MoveInput, user: User
) -> SwinePig:
    """Move a pig between management group and/or physical pen. History is preserved
    on the timeline (Swine Doc 2 §16)."""
    p = await _get_pig_or_404(db, farm_id, pig_id)
    _guard_not_terminal(p, "move")

    fields = data.model_dump(exclude_unset=True, exclude={"clear", "reason", "occurred_on", "notes"})
    await _validate_location(db, farm_id, group_id=fields.get("group_id"), pen_id=fields.get("pen_id"))

    before = {"group_id": p.group_id, "pen_id": p.pen_id}
    for field, value in fields.items():
        setattr(p, field, value)
    for field in data.clear:
        if field in ("group_id", "pen_id"):
            setattr(p, field, None)

    after = {"group_id": p.group_id, "pen_id": p.pen_id}
    if before == after:
        raise ConflictException("No location change requested.")

    await db.flush()
    await _append_event(
        db, p.id, "moved", "Pig moved",
        occurred_at=(datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc)
                     if data.occurred_on else None),
        operator_id=user.id,
        details={"from": {k: _jsonable(v) for k, v in before.items()},
                 "to": {k: _jsonable(v) for k, v in after.items()},
                 "reason": data.reason, "notes": data.notes},
    )
    await audit_service.log_action(
        db, action="swine.move", resource_type="swine_pig",
        resource_id=p.id, farm_id=farm_id, user_id=user.id,
        old_value={k: _jsonable(v) for k, v in before.items()},
        new_value={k: _jsonable(v) for k, v in after.items()},
    )
    await db.commit()
    await db.refresh(p)
    return p


async def _terminal_transition(
    db, farm_id, pig_id, user, *, new_status, event_type, summary, action, details, occurred_on,
):
    p = await _get_pig_or_404(db, farm_id, pig_id)
    _guard_not_terminal(p, event_type)
    on = occurred_on or date.today()
    p.status = new_status
    p.group_id = None
    p.pen_id = None
    await db.flush()
    await _append_event(
        db, p.id, event_type, summary,
        occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details=details,
    )
    await audit_service.log_action(
        db, action=action, resource_type="swine_pig",
        resource_id=p.id, farm_id=farm_id, user_id=user.id, new_value=details,
    )
    await db.commit()
    await db.refresh(p)
    return p


async def archive_pig(db, farm_id, pig_id, reason: str | None, user: User) -> SwinePig:
    p = await _get_pig_or_404(db, farm_id, pig_id)
    _guard_not_terminal(p, "archive")
    if p.status == "archived":
        raise ConflictException("Pig is already archived.")
    p.status = "archived"
    await db.flush()
    await _append_event(db, p.id, "archived", "Pig archived", operator_id=user.id, details={"reason": reason})
    await audit_service.log_action(
        db, action="swine.archive", resource_type="swine_pig",
        resource_id=p.id, farm_id=farm_id, user_id=user.id, new_value={"reason": reason},
    )
    await db.commit()
    await db.refresh(p)
    return p


async def restore_pig(db, farm_id, pig_id, user: User) -> SwinePig:
    p = await _get_pig_or_404(db, farm_id, pig_id)
    if p.status != "archived":
        raise ConflictException("Only archived pigs can be restored.")
    p.status = "active"
    await db.flush()
    await _append_event(db, p.id, "restored", "Pig restored to the herd", operator_id=user.id)
    await audit_service.log_action(
        db, action="swine.restore", resource_type="swine_pig",
        resource_id=p.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(p)
    return p


async def transfer_pig(db, farm_id, pig_id, data: TransferInput, user: User) -> SwinePig:
    return await _terminal_transition(
        db, farm_id, pig_id, user,
        new_status="transferred", event_type="transferred",
        summary=f"Transferred to {data.to_owner_name}", action="swine.transfer",
        details={"to_owner": data.to_owner_name, "destination": data.destination, "notes": data.notes},
        occurred_on=data.occurred_on,
    )


async def sell_pig(db, farm_id, pig_id, data: SaleInput, user: User) -> SwinePig:
    """Record a sale as a herd fact. Revenue posting to Finance is handled by the
    Sales/Finance milestone; here the price is captured on the timeline only."""
    return await _terminal_transition(
        db, farm_id, pig_id, user,
        new_status="sold", event_type="sold",
        summary=f"Sold to {data.buyer_name}", action="swine.sell",
        details={"buyer": data.buyer_name, "price": _jsonable(data.price),
                 "currency": data.currency, "notes": data.notes},
        occurred_on=data.occurred_on,
    )


async def record_death(db, farm_id, pig_id, data: DeathInput, user: User) -> SwinePig:
    return await _terminal_transition(
        db, farm_id, pig_id, user,
        new_status="deceased", event_type="died", summary="Pig deceased", action="swine.death",
        details={"cause": data.cause, "notes": data.notes}, occurred_on=data.occurred_on,
    )


async def cull_pig(db, farm_id, pig_id, data: CullInput, user: User) -> SwinePig:
    return await _terminal_transition(
        db, farm_id, pig_id, user,
        new_status="culled", event_type="culled", summary="Pig culled", action="swine.cull",
        details={"reason": data.reason, "notes": data.notes}, occurred_on=data.occurred_on,
    )


# ── Timeline ──────────────────────────────────────────────────────────────────

async def list_events(
    db: AsyncSession, farm_id: uuid.UUID, pig_id: uuid.UUID, limit: int = 100, offset: int = 0,
) -> list[SwineEvent]:
    await _get_pig_or_404(db, farm_id, pig_id)
    result = await db.execute(
        select(SwineEvent).where(
            SwineEvent.pig_id == pig_id, SwineEvent.deleted_at.is_(None)
        ).order_by(SwineEvent.occurred_at.desc(), SwineEvent.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all())


# ── Attachments (media / documents) ───────────────────────────────────────────

async def add_media(db, farm_id, pig_id, data: MediaCreate, user: User) -> SwineMedia:
    await _get_pig_or_404(db, farm_id, pig_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Media requires a url or storage_path.")
    media = SwineMedia(
        id=uuid.uuid4(), pig_id=pig_id, media_type=data.media_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, captured_on=data.captured_on,
        uploaded_by=user.id,
    )
    db.add(media)
    await db.flush()
    await _append_event(db, pig_id, "media_added", f"{data.media_type.capitalize()} added",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action="swine.media.add", resource_type="swine_media",
        resource_id=media.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(media)
    return media


async def list_media(db, farm_id, pig_id) -> list[SwineMedia]:
    await _get_pig_or_404(db, farm_id, pig_id)
    result = await db.execute(
        select(SwineMedia).where(
            SwineMedia.pig_id == pig_id, SwineMedia.deleted_at.is_(None)
        ).order_by(SwineMedia.created_at.desc())
    )
    return list(result.scalars().all())


async def add_document(db, farm_id, pig_id, data: DocumentCreate, user: User) -> SwineDocument:
    await _get_pig_or_404(db, farm_id, pig_id)
    if not data.url and not data.storage_path:
        raise ValidationException("Document requires a url or storage_path.")
    doc = SwineDocument(
        id=uuid.uuid4(), pig_id=pig_id, document_type=data.document_type, title=data.title,
        url=data.url, storage_path=data.storage_path, filename=data.filename,
        content_type=data.content_type, size_bytes=data.size_bytes, issued_on=data.issued_on,
        expires_on=data.expires_on, uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()
    await _append_event(db, pig_id, "document_added", f"Document added: {data.document_type}",
                        operator_id=user.id, details={"title": data.title})
    await audit_service.log_action(
        db, action="swine.document.add", resource_type="swine_document",
        resource_id=doc.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_documents(db, farm_id, pig_id) -> list[SwineDocument]:
    await _get_pig_or_404(db, farm_id, pig_id)
    result = await db.execute(
        select(SwineDocument).where(
            SwineDocument.pig_id == pig_id, SwineDocument.deleted_at.is_(None)
        ).order_by(SwineDocument.created_at.desc())
    )
    return list(result.scalars().all())
