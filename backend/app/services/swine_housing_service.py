"""
Greena — Swine Housing Service (Module 20, Milestone 2)

CRUD orchestration for the management + physical structure (Swine Doc 2 §3):
Herd → Group (dynamic membership) and Pen (physical, housed infrastructure). The
service owns writes and parent validation; all capacity/occupancy figures are
delegated to the PURE :mod:`swine_housing_engine` (no calculations in services).

Occupancy is **never stored** — it is derived on read from the count of active pigs
whose ``pen_id`` / ``group_id`` points here. Overcrowding and flagged biosecurity
are deterministic findings, surfaced but never auto-resolved.
"""

import uuid

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineGroup,
    SwineHerd,
    SwinePen,
    SwinePig,
)
from app.schemas.swine import (
    GroupCreate,
    GroupUpdate,
    HerdCreate,
    HerdUpdate,
    PenCreate,
    PenUpdate,
)
from app.services import audit_service, swine_housing_engine as engine


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_or_404(db, model, farm_id, obj_id):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.farm_id == farm_id, model.deleted_at.is_(None))
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundException(f"{model.__name__} {obj_id} not found on this farm.")
    return obj


async def _require_parent(db, model, farm_id, parent_id) -> None:
    result = await db.execute(
        select(model.id).where(model.id == parent_id, model.farm_id == farm_id, model.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundException(f"{model.__name__} {parent_id} not found on this farm.")


async def _create(db, model, farm_id, user, action, values: dict):
    obj = model(id=uuid.uuid4(), farm_id=farm_id, created_by=user.id, **values)
    db.add(obj)
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - integrity safety net
        await db.rollback()
        raise ConflictException(f"Could not create {model.__name__} — duplicate code.") from exc
    await audit_service.log_action(
        db, action=action, resource_type=model.__tablename__,
        resource_id=obj.id, farm_id=farm_id, user_id=user.id, new_value={"name": values.get("name")},
    )
    await db.commit()
    await db.refresh(obj)
    return obj


async def _update(db, obj, farm_id, user, action, data):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action=action, resource_type=obj.__tablename__,
        resource_id=obj.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(obj)
    return obj


# ── Herd ────────────────────────────────────────────────────────────────────────

async def list_herds(db, farm_id) -> list[SwineHerd]:
    result = await db.execute(
        select(SwineHerd).where(
            SwineHerd.farm_id == farm_id, SwineHerd.deleted_at.is_(None),
        ).order_by(SwineHerd.name)
    )
    return list(result.scalars().all())


async def create_herd(db, farm: Farm, data: HerdCreate, user: User) -> SwineHerd:
    return await _create(db, SwineHerd, farm.id, user, "swine.herd.create", data.model_dump())


async def update_herd(db, farm_id, obj_id, data: HerdUpdate, user) -> SwineHerd:
    obj = await _get_or_404(db, SwineHerd, farm_id, obj_id)
    return await _update(db, obj, farm_id, user, "swine.herd.update", data)


# ── Group (dynamic membership) ─────────────────────────────────────────────────

async def list_groups(db, farm_id, herd_id: uuid.UUID | None = None, group_type: str | None = None) -> list[SwineGroup]:
    conds = [SwineGroup.farm_id == farm_id, SwineGroup.deleted_at.is_(None)]
    if herd_id:
        conds.append(SwineGroup.herd_id == herd_id)
    if group_type:
        conds.append(SwineGroup.group_type == group_type)
    result = await db.execute(select(SwineGroup).where(*conds).order_by(SwineGroup.name))
    return list(result.scalars().all())


async def create_group(db, farm: Farm, data: GroupCreate, user: User) -> SwineGroup:
    if data.herd_id is not None:
        await _require_parent(db, SwineHerd, farm.id, data.herd_id)
    return await _create(db, SwineGroup, farm.id, user, "swine.group.create", data.model_dump())


async def update_group(db, farm_id, obj_id, data: GroupUpdate, user) -> SwineGroup:
    obj = await _get_or_404(db, SwineGroup, farm_id, obj_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("herd_id"):
        await _require_parent(db, SwineHerd, farm_id, fields["herd_id"])
    return await _update(db, obj, farm_id, user, "swine.group.update", data)


async def get_group_detail(db, farm_id, group_id) -> tuple[SwineGroup, dict]:
    group = await _get_or_404(db, SwineGroup, farm_id, group_id)
    result = await db.execute(
        select(func.count(SwinePig.id)).where(
            SwinePig.group_id == group_id, SwinePig.status == "active", SwinePig.deleted_at.is_(None),
        )
    )
    occupied = result.scalar_one() or 0
    # Groups have no capacity concept; report the recorded head count only.
    return group, {"occupied": {"label": engine.RECORDED, "value": occupied,
                                "detail": "Active pigs currently in this group."}}


# ── Pen (physical housing) ──────────────────────────────────────────────────────

async def list_pens(db, farm_id, pen_type: str | None = None) -> list[SwinePen]:
    conds = [SwinePen.farm_id == farm_id, SwinePen.deleted_at.is_(None)]
    if pen_type:
        conds.append(SwinePen.pen_type == pen_type)
    result = await db.execute(select(SwinePen).where(*conds).order_by(SwinePen.name))
    return list(result.scalars().all())


async def create_pen(db, farm: Farm, data: PenCreate, user: User) -> SwinePen:
    return await _create(db, SwinePen, farm.id, user, "swine.pen.create", data.model_dump())


async def update_pen(db, farm_id, obj_id, data: PenUpdate, user) -> SwinePen:
    obj = await _get_or_404(db, SwinePen, farm_id, obj_id)
    return await _update(db, obj, farm_id, user, "swine.pen.update", data)


async def _pen_occupancy_count(db, pen_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(SwinePig.id)).where(
            SwinePig.pen_id == pen_id, SwinePig.status == "active", SwinePig.deleted_at.is_(None),
        )
    )
    return result.scalar_one() or 0


async def get_pen_detail(db, farm_id, pen_id) -> tuple[SwinePen, dict]:
    pen = await _get_or_404(db, SwinePen, farm_id, pen_id)
    occupied = await _pen_occupancy_count(db, pen_id)
    return pen, engine.compute_occupancy(pen.capacity, occupied).as_dict()


# ── Farm-wide housing summary ──────────────────────────────────────────────────

async def housing_summary(db, farm_id: uuid.UUID) -> dict:
    """Deterministic farm-wide housing roll-up for the Swine workspace.

    Pen capacity is aggregated through the pure engine against the recorded count of
    active pigs located in each pen. Overcrowded pens are surfaced by id for the
    Housing workspace and Mission Control, and pens are tallied by biosecurity status.
    """
    async def _count(model) -> int:
        r = await db.execute(
            select(func.count(model.id)).where(model.farm_id == farm_id, model.deleted_at.is_(None))
        )
        return r.scalar_one() or 0

    rows = await db.execute(
        select(SwinePen.id, SwinePen.name, SwinePen.capacity, SwinePen.biosecurity_status).where(
            SwinePen.farm_id == farm_id, SwinePen.deleted_at.is_(None)
        )
    )
    pens = [{"id": row[0], "name": row[1], "capacity": row[2], "biosecurity_status": row[3]} for row in rows]

    occ_rows = await db.execute(
        select(SwinePig.pen_id, func.count(SwinePig.id)).where(
            SwinePig.farm_id == farm_id, SwinePig.status == "active",
            SwinePig.pen_id.is_not(None), SwinePig.deleted_at.is_(None),
        ).group_by(SwinePig.pen_id)
    )
    occ = {row[0]: row[1] for row in occ_rows}

    children = [{"capacity": pen["capacity"], "occupied": occ.get(pen["id"], 0)} for pen in pens]
    overcrowded = [
        {"id": str(pen["id"]), "name": pen["name"], "capacity": pen["capacity"],
         "occupied": occ.get(pen["id"], 0)}
        for pen in pens if engine.is_overcrowded(pen["capacity"], occ.get(pen["id"], 0))
    ]

    return {
        "counts": {
            "herds": await _count(SwineHerd),
            "groups": await _count(SwineGroup),
            "pens": len(pens),
        },
        "pen_capacity": engine.rollup(children),
        "biosecurity": engine.biosecurity_rollup([pen["biosecurity_status"] for pen in pens]),
        "overcrowded_pens": overcrowded,
    }
