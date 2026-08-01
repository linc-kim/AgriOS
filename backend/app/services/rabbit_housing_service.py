"""
Greena — Rabbit Housing Service (Module 17, Milestone 2)

CRUD orchestration for the 5-level housing hierarchy (Spec Part 1 §6):
Rabbitry → Building → Room → Row → Cage. The service owns the writes and parent
validation; all capacity/occupancy figures are delegated to the PURE
:mod:`rabbit_housing_engine` (GMIS §1.3 — no calculations in services).

Occupancy is **never stored** — it is derived on read from the count of active
rabbits whose ``cage_id`` points at a cage (Spec Part 3 §14). Overcrowding is a
deterministic finding, surfaced but never auto-resolved.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.rabbit import (
    Rabbit,
    RabbitBuilding,
    RabbitCage,
    RabbitRabbitry,
    RabbitRoom,
    RabbitRow,
)
from app.schemas.rabbit import (
    BuildingCreate,
    BuildingUpdate,
    CageCreate,
    CageUpdate,
    RabbitryCreate,
    RabbitryUpdate,
    RoomCreate,
    RoomUpdate,
    RowCreate,
    RowUpdate,
)
from app.services import audit_service, rabbit_housing_engine as engine


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, model, farm_id: uuid.UUID, obj_id: uuid.UUID):
    result = await db.execute(
        select(model).where(model.id == obj_id, model.farm_id == farm_id, model.deleted_at.is_(None))
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundException(f"{model.__name__} {obj_id} not found on this farm.")
    return obj


async def _require_parent(db: AsyncSession, model, farm_id: uuid.UUID, parent_id: uuid.UUID) -> None:
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


# ── Rabbitry (L1) ──────────────────────────────────────────────────────────────

async def list_rabbitries(db: AsyncSession, farm_id: uuid.UUID) -> list[RabbitRabbitry]:
    result = await db.execute(
        select(RabbitRabbitry).where(RabbitRabbitry.farm_id == farm_id, RabbitRabbitry.deleted_at.is_(None))
        .order_by(RabbitRabbitry.name)
    )
    return list(result.scalars().all())


async def create_rabbitry(db, farm: Farm, data: RabbitryCreate, user: User) -> RabbitRabbitry:
    return await _create(db, RabbitRabbitry, farm.id, user, "rabbit.rabbitry.create",
                         data.model_dump())


async def update_rabbitry(db, farm_id, obj_id, data: RabbitryUpdate, user) -> RabbitRabbitry:
    obj = await _get_or_404(db, RabbitRabbitry, farm_id, obj_id)
    return await _update(db, obj, farm_id, user, "rabbit.rabbitry.update", data)


# ── Building (L2) ──────────────────────────────────────────────────────────────

async def list_buildings(db, farm_id, rabbitry_id: uuid.UUID | None = None) -> list[RabbitBuilding]:
    conds = [RabbitBuilding.farm_id == farm_id, RabbitBuilding.deleted_at.is_(None)]
    if rabbitry_id:
        conds.append(RabbitBuilding.rabbitry_id == rabbitry_id)
    result = await db.execute(select(RabbitBuilding).where(*conds).order_by(RabbitBuilding.name))
    return list(result.scalars().all())


async def create_building(db, farm: Farm, data: BuildingCreate, user: User) -> RabbitBuilding:
    await _require_parent(db, RabbitRabbitry, farm.id, data.rabbitry_id)
    return await _create(db, RabbitBuilding, farm.id, user, "rabbit.building.create", data.model_dump())


async def update_building(db, farm_id, obj_id, data: BuildingUpdate, user) -> RabbitBuilding:
    obj = await _get_or_404(db, RabbitBuilding, farm_id, obj_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("rabbitry_id"):
        await _require_parent(db, RabbitRabbitry, farm_id, fields["rabbitry_id"])
    return await _update(db, obj, farm_id, user, "rabbit.building.update", data)


# ── Room (L3) ──────────────────────────────────────────────────────────────────

async def list_rooms(db, farm_id, building_id: uuid.UUID | None = None) -> list[RabbitRoom]:
    conds = [RabbitRoom.farm_id == farm_id, RabbitRoom.deleted_at.is_(None)]
    if building_id:
        conds.append(RabbitRoom.building_id == building_id)
    result = await db.execute(select(RabbitRoom).where(*conds).order_by(RabbitRoom.name))
    return list(result.scalars().all())


async def create_room(db, farm: Farm, data: RoomCreate, user: User) -> RabbitRoom:
    await _require_parent(db, RabbitBuilding, farm.id, data.building_id)
    return await _create(db, RabbitRoom, farm.id, user, "rabbit.room.create", data.model_dump())


async def update_room(db, farm_id, obj_id, data: RoomUpdate, user) -> RabbitRoom:
    obj = await _get_or_404(db, RabbitRoom, farm_id, obj_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("building_id"):
        await _require_parent(db, RabbitBuilding, farm_id, fields["building_id"])
    return await _update(db, obj, farm_id, user, "rabbit.room.update", data)


# ── Row (L4) ────────────────────────────────────────────────────────────────────

async def list_rows(db, farm_id, room_id: uuid.UUID | None = None) -> list[RabbitRow]:
    conds = [RabbitRow.farm_id == farm_id, RabbitRow.deleted_at.is_(None)]
    if room_id:
        conds.append(RabbitRow.room_id == room_id)
    result = await db.execute(select(RabbitRow).where(*conds).order_by(RabbitRow.name))
    return list(result.scalars().all())


async def create_row(db, farm: Farm, data: RowCreate, user: User) -> RabbitRow:
    await _require_parent(db, RabbitRoom, farm.id, data.room_id)
    return await _create(db, RabbitRow, farm.id, user, "rabbit.row.create", data.model_dump())


async def update_row(db, farm_id, obj_id, data: RowUpdate, user) -> RabbitRow:
    obj = await _get_or_404(db, RabbitRow, farm_id, obj_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("room_id"):
        await _require_parent(db, RabbitRoom, farm_id, fields["room_id"])
    return await _update(db, obj, farm_id, user, "rabbit.row.update", data)


# ── Cage (L5) + occupancy ───────────────────────────────────────────────────────

async def list_cages(db, farm_id, row_id: uuid.UUID | None = None, cage_type: str | None = None) -> list[RabbitCage]:
    conds = [RabbitCage.farm_id == farm_id, RabbitCage.deleted_at.is_(None)]
    if row_id:
        conds.append(RabbitCage.row_id == row_id)
    if cage_type:
        conds.append(RabbitCage.cage_type == cage_type)
    result = await db.execute(select(RabbitCage).where(*conds).order_by(RabbitCage.name))
    return list(result.scalars().all())


async def create_cage(db, farm: Farm, data: CageCreate, user: User) -> RabbitCage:
    if data.row_id is not None:
        await _require_parent(db, RabbitRow, farm.id, data.row_id)
    return await _create(db, RabbitCage, farm.id, user, "rabbit.cage.create", data.model_dump())


async def update_cage(db, farm_id, obj_id, data: CageUpdate, user) -> RabbitCage:
    obj = await _get_or_404(db, RabbitCage, farm_id, obj_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("row_id"):
        await _require_parent(db, RabbitRow, farm_id, fields["row_id"])
    return await _update(db, obj, farm_id, user, "rabbit.cage.update", data)


async def _cage_occupancy_count(db, cage_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(Rabbit.id)).where(
            Rabbit.cage_id == cage_id, Rabbit.status == "active", Rabbit.deleted_at.is_(None)
        )
    )
    return result.scalar_one() or 0


async def get_cage_detail(db, farm_id, cage_id: uuid.UUID) -> tuple[RabbitCage, dict]:
    """A cage plus its deterministic occupancy (via the pure engine)."""
    cage = await _get_or_404(db, RabbitCage, farm_id, cage_id)
    occupied = await _cage_occupancy_count(db, cage_id)
    occupancy = engine.compute_occupancy(cage.capacity, occupied).as_dict()
    return cage, occupancy


async def housing_summary(db, farm_id: uuid.UUID) -> dict:
    """Deterministic farm-wide housing roll-up (Spec Part 7 §8).

    Counts each level and aggregates cage capacity vs recorded occupancy through
    the pure engine. Overcrowded cages are surfaced by id for the Housing
    workspace and Mission Control.
    """
    async def _count(model) -> int:
        r = await db.execute(
            select(func.count(model.id)).where(model.farm_id == farm_id, model.deleted_at.is_(None))
        )
        return r.scalar_one() or 0

    # Per-cage occupancy in one grouped query (avoids N+1).
    cages_rows = await db.execute(
        select(RabbitCage.id, RabbitCage.name, RabbitCage.capacity).where(
            RabbitCage.farm_id == farm_id, RabbitCage.deleted_at.is_(None)
        )
    )
    cages = [{"id": row[0], "name": row[1], "capacity": row[2]} for row in cages_rows]

    occ_rows = await db.execute(
        select(Rabbit.cage_id, func.count(Rabbit.id)).where(
            Rabbit.farm_id == farm_id, Rabbit.status == "active",
            Rabbit.cage_id.is_not(None), Rabbit.deleted_at.is_(None),
        ).group_by(Rabbit.cage_id)
    )
    occ_by_cage = {row[0]: row[1] for row in occ_rows}

    children = [{"capacity": c["capacity"], "occupied": occ_by_cage.get(c["id"], 0)} for c in cages]
    overcrowded = [
        {"cage_id": str(c["id"]), "name": c["name"],
         "capacity": c["capacity"], "occupied": occ_by_cage.get(c["id"], 0)}
        for c in cages
        if engine.is_overcrowded(c["capacity"], occ_by_cage.get(c["id"], 0))
    ]

    return {
        "counts": {
            "rabbitries": await _count(RabbitRabbitry),
            "buildings": await _count(RabbitBuilding),
            "rooms": await _count(RabbitRoom),
            "rows": await _count(RabbitRow),
            "cages": len(cages),
        },
        "capacity": engine.rollup(children),
        "overcrowded_cages": overcrowded,
    }
