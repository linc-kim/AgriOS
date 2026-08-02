"""
Greena — Small Ruminant Housing Service (Modules 18/19, Milestone 2)

CRUD orchestration for the management + physical structure (Goat Doc 2 §3):
Herd/Flock → Group (species-scoped, dynamic membership) and Pen / Pasture
(species-neutral physical infrastructure). The service owns writes and parent
validation; all capacity/occupancy figures are delegated to the PURE
:mod:`small_ruminant_housing_engine` (no calculations in services).

Occupancy is **never stored** — it is derived on read from the count of active
animals whose ``pen_id`` / ``pasture_id`` / ``group_id`` points here. Overcrowding
is a deterministic finding, surfaced but never auto-resolved.
"""

import uuid

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantGroup,
    SmallRuminantHerd,
    SmallRuminantPasture,
    SmallRuminantPen,
)
from app.schemas.small_ruminant import (
    GroupCreate,
    GroupUpdate,
    HerdCreate,
    HerdUpdate,
    PastureCreate,
    PastureUpdate,
    PenCreate,
    PenUpdate,
)
from app.services import audit_service, small_ruminant_housing_engine as engine


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_or_404(db, model, farm_id, obj_id, species: str | None = None):
    conds = [model.id == obj_id, model.farm_id == farm_id, model.deleted_at.is_(None)]
    if species is not None:
        conds.append(model.species == species)
    result = await db.execute(select(model).where(*conds))
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundException(f"{model.__name__} {obj_id} not found on this farm.")
    return obj


async def _require_parent(db, model, farm_id, parent_id, species: str | None = None) -> None:
    conds = [model.id == parent_id, model.farm_id == farm_id, model.deleted_at.is_(None)]
    if species is not None:
        conds.append(model.species == species)
    result = await db.execute(select(model.id).where(*conds))
    if result.scalar_one_or_none() is None:
        raise NotFoundException(f"{model.__name__} {parent_id} not found on this farm.")


async def _create(db, model, farm_id, user, action, values: dict, *, species: str | None = None):
    extra = {"species": species} if species is not None else {}
    obj = model(id=uuid.uuid4(), farm_id=farm_id, created_by=user.id, **extra, **values)
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


# ── Herd / Flock (species-scoped) ──────────────────────────────────────────────

async def list_herds(db, farm_id, species: str) -> list[SmallRuminantHerd]:
    result = await db.execute(
        select(SmallRuminantHerd).where(
            SmallRuminantHerd.farm_id == farm_id, SmallRuminantHerd.species == species,
            SmallRuminantHerd.deleted_at.is_(None),
        ).order_by(SmallRuminantHerd.name)
    )
    return list(result.scalars().all())


async def create_herd(db, farm: Farm, species: str, data: HerdCreate, user: User) -> SmallRuminantHerd:
    return await _create(db, SmallRuminantHerd, farm.id, user, f"sr.{species}.herd.create",
                         data.model_dump(), species=species)


async def update_herd(db, farm_id, species, obj_id, data: HerdUpdate, user) -> SmallRuminantHerd:
    obj = await _get_or_404(db, SmallRuminantHerd, farm_id, obj_id, species=species)
    return await _update(db, obj, farm_id, user, f"sr.{species}.herd.update", data)


# ── Group (species-scoped, dynamic membership) ─────────────────────────────────

async def list_groups(db, farm_id, species: str, herd_id: uuid.UUID | None = None) -> list[SmallRuminantGroup]:
    conds = [SmallRuminantGroup.farm_id == farm_id, SmallRuminantGroup.species == species,
             SmallRuminantGroup.deleted_at.is_(None)]
    if herd_id:
        conds.append(SmallRuminantGroup.herd_id == herd_id)
    result = await db.execute(select(SmallRuminantGroup).where(*conds).order_by(SmallRuminantGroup.name))
    return list(result.scalars().all())


async def create_group(db, farm: Farm, species: str, data: GroupCreate, user: User) -> SmallRuminantGroup:
    if data.herd_id is not None:
        await _require_parent(db, SmallRuminantHerd, farm.id, data.herd_id, species=species)
    return await _create(db, SmallRuminantGroup, farm.id, user, f"sr.{species}.group.create",
                         data.model_dump(), species=species)


async def update_group(db, farm_id, species, obj_id, data: GroupUpdate, user) -> SmallRuminantGroup:
    obj = await _get_or_404(db, SmallRuminantGroup, farm_id, obj_id, species=species)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("herd_id"):
        await _require_parent(db, SmallRuminantHerd, farm_id, fields["herd_id"], species=species)
    return await _update(db, obj, farm_id, user, f"sr.{species}.group.update", data)


async def get_group_detail(db, farm_id, species, group_id) -> tuple[SmallRuminantGroup, dict]:
    group = await _get_or_404(db, SmallRuminantGroup, farm_id, group_id, species=species)
    result = await db.execute(
        select(func.count(SmallRuminant.id)).where(
            SmallRuminant.group_id == group_id, SmallRuminant.status == "active",
            SmallRuminant.deleted_at.is_(None),
        )
    )
    occupied = result.scalar_one() or 0
    # Groups have no capacity concept; report the recorded head count only.
    return group, {"occupied": {"label": engine.RECORDED, "value": occupied,
                                "detail": "Active animals currently in this group."}}


# ── Pen (species-neutral physical housing) ─────────────────────────────────────

async def list_pens(db, farm_id, pen_type: str | None = None) -> list[SmallRuminantPen]:
    conds = [SmallRuminantPen.farm_id == farm_id, SmallRuminantPen.deleted_at.is_(None)]
    if pen_type:
        conds.append(SmallRuminantPen.pen_type == pen_type)
    result = await db.execute(select(SmallRuminantPen).where(*conds).order_by(SmallRuminantPen.name))
    return list(result.scalars().all())


async def create_pen(db, farm: Farm, data: PenCreate, user: User) -> SmallRuminantPen:
    return await _create(db, SmallRuminantPen, farm.id, user, "sr.pen.create", data.model_dump())


async def update_pen(db, farm_id, obj_id, data: PenUpdate, user) -> SmallRuminantPen:
    obj = await _get_or_404(db, SmallRuminantPen, farm_id, obj_id)
    return await _update(db, obj, farm_id, user, "sr.pen.update", data)


async def _pen_occupancy_count(db, pen_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(SmallRuminant.id)).where(
            SmallRuminant.pen_id == pen_id, SmallRuminant.status == "active",
            SmallRuminant.deleted_at.is_(None),
        )
    )
    return result.scalar_one() or 0


async def get_pen_detail(db, farm_id, pen_id) -> tuple[SmallRuminantPen, dict]:
    pen = await _get_or_404(db, SmallRuminantPen, farm_id, pen_id)
    occupied = await _pen_occupancy_count(db, pen_id)
    return pen, engine.compute_occupancy(pen.capacity, occupied).as_dict()


# ── Pasture (species-neutral grazing) ──────────────────────────────────────────

async def list_pastures(db, farm_id, status: str | None = None) -> list[SmallRuminantPasture]:
    conds = [SmallRuminantPasture.farm_id == farm_id, SmallRuminantPasture.deleted_at.is_(None)]
    if status:
        conds.append(SmallRuminantPasture.status == status)
    result = await db.execute(select(SmallRuminantPasture).where(*conds).order_by(SmallRuminantPasture.name))
    return list(result.scalars().all())


async def create_pasture(db, farm: Farm, data: PastureCreate, user: User) -> SmallRuminantPasture:
    return await _create(db, SmallRuminantPasture, farm.id, user, "sr.pasture.create", data.model_dump())


async def update_pasture(db, farm_id, obj_id, data: PastureUpdate, user) -> SmallRuminantPasture:
    obj = await _get_or_404(db, SmallRuminantPasture, farm_id, obj_id)
    return await _update(db, obj, farm_id, user, "sr.pasture.update", data)


async def _pasture_occupancy_count(db, pasture_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(SmallRuminant.id)).where(
            SmallRuminant.pasture_id == pasture_id, SmallRuminant.status == "active",
            SmallRuminant.deleted_at.is_(None),
        )
    )
    return result.scalar_one() or 0


async def get_pasture_detail(db, farm_id, pasture_id) -> tuple[SmallRuminantPasture, dict]:
    pasture = await _get_or_404(db, SmallRuminantPasture, farm_id, pasture_id)
    occupied = await _pasture_occupancy_count(db, pasture_id)
    return pasture, engine.compute_occupancy(pasture.carrying_capacity, occupied).as_dict()


# ── Farm-wide housing summary ──────────────────────────────────────────────────

async def housing_summary(db, farm_id: uuid.UUID, species: str) -> dict:
    """Deterministic farm-wide housing roll-up for a species workspace.

    Management counts (herds/groups) are species-scoped; physical pens/pastures are
    species-neutral, and their occupancy is the count of *this species'* active
    animals located there. Pen and pasture capacity are aggregated through the pure
    engine. Overcrowded locations are surfaced by id for the Housing workspace and
    Mission Control.
    """
    async def _count_species(model) -> int:
        r = await db.execute(
            select(func.count(model.id)).where(
                model.farm_id == farm_id, model.species == species, model.deleted_at.is_(None)
            )
        )
        return r.scalar_one() or 0

    async def _location_rollup(location_model, animal_fk):
        rows = await db.execute(
            select(location_model.id, location_model.name, _capacity_col(location_model)).where(
                location_model.farm_id == farm_id, location_model.deleted_at.is_(None)
            )
        )
        locs = [{"id": row[0], "name": row[1], "capacity": row[2]} for row in rows]
        occ_rows = await db.execute(
            select(animal_fk, func.count(SmallRuminant.id)).where(
                SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
                SmallRuminant.status == "active", animal_fk.is_not(None),
                SmallRuminant.deleted_at.is_(None),
            ).group_by(animal_fk)
        )
        occ = {row[0]: row[1] for row in occ_rows}
        children = [{"capacity": loc["capacity"], "occupied": occ.get(loc["id"], 0)} for loc in locs]
        overcrowded = [
            {"id": str(loc["id"]), "name": loc["name"], "capacity": loc["capacity"],
             "occupied": occ.get(loc["id"], 0)}
            for loc in locs if engine.is_overcrowded(loc["capacity"], occ.get(loc["id"], 0))
        ]
        return len(locs), engine.rollup(children), overcrowded

    pen_count, pen_rollup, pen_over = await _location_rollup(SmallRuminantPen, SmallRuminant.pen_id)
    pas_count, pas_rollup, pas_over = await _location_rollup(SmallRuminantPasture, SmallRuminant.pasture_id)

    return {
        "species": species,
        "counts": {
            "herds": await _count_species(SmallRuminantHerd),
            "groups": await _count_species(SmallRuminantGroup),
            "pens": pen_count,
            "pastures": pas_count,
        },
        "pen_capacity": pen_rollup,
        "pasture_capacity": pas_rollup,
        "overcrowded_pens": pen_over,
        "overcrowded_pastures": pas_over,
    }


def _capacity_col(model):
    """Pens expose ``capacity``; pastures expose ``carrying_capacity``."""
    return model.capacity if model is SmallRuminantPen else model.carrying_capacity
