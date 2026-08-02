"""
Greena — Small Ruminant Wool Service (Modules 18/19, Milestone 7, Sheep wool)

Shearing sessions and per-animal fleece records. Sheep-specific but on the shared
foundation: availability is gated by the species ``produces_wool`` capability, so
goats are rejected from this workspace (the mirror of the dairy gate). All wool
math is delegated to the PURE :mod:`small_ruminant_wool_engine`. Fleece records are
immutable; wool sale revenue is handled by the finance milestone.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import (
    SmallRuminantFleece,
    SmallRuminantGroup,
    SmallRuminantShearing,
)
from app.schemas.small_ruminant import FleeceCreate, ShearingCreate
from app.services import audit_service
from app.services import small_ruminant_species_config as cfg
from app.services import small_ruminant_wool_engine as eng
from app.services.small_ruminant_service import _append_event, _get_animal_or_404


def _require_wool(species: str) -> None:
    """Guard: the wool workspace applies only to wool-producing species (sheep)."""
    if not cfg.produces_wool(species):
        raise ValidationException(f"Wool / shearing is not applicable to {species} in this workspace.")


def _at(on: date) -> datetime:
    return datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc)


async def _get_shearing_or_404(db, farm_id, species, shearing_id) -> SmallRuminantShearing:
    result = await db.execute(
        select(SmallRuminantShearing).where(
            SmallRuminantShearing.id == shearing_id, SmallRuminantShearing.farm_id == farm_id,
            SmallRuminantShearing.species == species, SmallRuminantShearing.deleted_at.is_(None),
        )
    )
    sh = result.scalar_one_or_none()
    if sh is None:
        raise NotFoundException(f"Shearing {shearing_id} not found on this farm.")
    return sh


# ── Shearing sessions ──────────────────────────────────────────────────────────

async def record_shearing(db, farm: Farm, species: str, data: ShearingCreate, user: User):
    """Record a shearing session, optionally with per-animal fleece rows."""
    _require_wool(species)
    if data.group_id is not None:
        exists = await db.execute(
            select(SmallRuminantGroup.id).where(
                SmallRuminantGroup.id == data.group_id, SmallRuminantGroup.farm_id == farm.id,
                SmallRuminantGroup.species == species, SmallRuminantGroup.deleted_at.is_(None),
            )
        )
        if exists.scalar_one_or_none() is None:
            raise NotFoundException(f"Group {data.group_id} not found on this farm.")

    sh = SmallRuminantShearing(
        id=uuid.uuid4(), species=species, farm_id=farm.id, group_id=data.group_id,
        shearing_date=data.shearing_date, method=data.method, shearer=data.shearer,
        notes=data.notes, created_by=user.id,
    )
    db.add(sh)
    await db.flush()

    created_fleeces: list[str] = []
    for fl in data.fleeces or []:
        await _get_animal_or_404(db, farm.id, species, fl.animal_id)
        fleece = SmallRuminantFleece(
            id=uuid.uuid4(), species=species, farm_id=farm.id, shearing_id=sh.id, animal_id=fl.animal_id,
            shorn_on=data.shearing_date, greasy_weight_kg=fl.greasy_weight_kg,
            clean_yield_pct=fl.clean_yield_pct, staple_length_cm=fl.staple_length_cm, micron=fl.micron,
            grade=fl.grade, condition=fl.condition, notes=fl.notes, recorded_by=user.id,
        )
        db.add(fleece)
        await db.flush()
        await _append_event(db, fl.animal_id, "sheared", f"Sheared: {fl.greasy_weight_kg} kg greasy",
                            occurred_at=_at(data.shearing_date), operator_id=user.id,
                            details={"shearing_id": str(sh.id), "greasy_weight_kg": str(fl.greasy_weight_kg)})
        created_fleeces.append(str(fleece.id))

    await audit_service.log_action(
        db, action=f"sr.{species}.shearing.record", resource_type="sr_shearing",
        resource_id=sh.id, farm_id=farm.id, user_id=user.id,
        new_value={"fleeces": len(created_fleeces)},
    )
    await db.commit()
    await db.refresh(sh)
    return sh, created_fleeces


async def add_fleece(db, farm: Farm, species: str, shearing_id, data: FleeceCreate, user: User):
    """Add a single fleece record to an existing shearing session."""
    _require_wool(species)
    sh = await _get_shearing_or_404(db, farm.id, species, shearing_id)
    await _get_animal_or_404(db, farm.id, species, data.animal_id)
    fleece = SmallRuminantFleece(
        id=uuid.uuid4(), species=species, farm_id=farm.id, shearing_id=sh.id, animal_id=data.animal_id,
        shorn_on=sh.shearing_date, greasy_weight_kg=data.greasy_weight_kg,
        clean_yield_pct=data.clean_yield_pct, staple_length_cm=data.staple_length_cm, micron=data.micron,
        grade=data.grade, condition=data.condition, notes=data.notes, recorded_by=user.id,
    )
    db.add(fleece)
    await db.flush()
    await _append_event(db, data.animal_id, "sheared", f"Sheared: {data.greasy_weight_kg} kg greasy",
                        occurred_at=_at(sh.shearing_date), operator_id=user.id,
                        details={"shearing_id": str(sh.id)})
    await audit_service.log_action(
        db, action=f"sr.{species}.fleece.record", resource_type="sr_fleece",
        resource_id=fleece.id, farm_id=farm.id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(fleece)
    return fleece


# ── Reads ──────────────────────────────────────────────────────────────────────

async def list_shearings(db, farm_id, species):
    _require_wool(species)
    result = await db.execute(
        select(SmallRuminantShearing).where(
            SmallRuminantShearing.farm_id == farm_id, SmallRuminantShearing.species == species,
            SmallRuminantShearing.deleted_at.is_(None),
        ).order_by(SmallRuminantShearing.shearing_date.desc())
    )
    return list(result.scalars().all())


async def list_fleeces(db, farm_id, species, *, animal_id=None, shearing_id=None):
    _require_wool(species)
    conds = [SmallRuminantFleece.farm_id == farm_id, SmallRuminantFleece.species == species,
             SmallRuminantFleece.deleted_at.is_(None)]
    if animal_id:
        conds.append(SmallRuminantFleece.animal_id == animal_id)
    if shearing_id:
        conds.append(SmallRuminantFleece.shearing_id == shearing_id)
    result = await db.execute(
        select(SmallRuminantFleece).where(*conds).order_by(SmallRuminantFleece.shorn_on.desc())
    )
    return list(result.scalars().all())


def _fleece_dict(f) -> dict:
    return {"greasy_weight_kg": f.greasy_weight_kg, "clean_yield_pct": f.clean_yield_pct,
            "staple_length_cm": f.staple_length_cm, "micron": f.micron, "grade": f.grade}


async def fleece_analysis(db, farm_id, species, fleece_id, price_per_kg=None) -> dict:
    _require_wool(species)
    result = await db.execute(
        select(SmallRuminantFleece).where(
            SmallRuminantFleece.id == fleece_id, SmallRuminantFleece.farm_id == farm_id,
            SmallRuminantFleece.species == species, SmallRuminantFleece.deleted_at.is_(None),
        )
    )
    f = result.scalar_one_or_none()
    if f is None:
        raise NotFoundException(f"Fleece {fleece_id} not found on this farm.")
    return {"fleece_id": str(fleece_id), "animal_id": str(f.animal_id),
            "analysis": eng.fleece_analysis(_fleece_dict(f), price_per_kg)}


async def wool_summary(db, farm_id, species, price_per_kg=None) -> dict:
    _require_wool(species)
    result = await db.execute(
        select(SmallRuminantFleece).where(
            SmallRuminantFleece.farm_id == farm_id, SmallRuminantFleece.species == species,
            SmallRuminantFleece.deleted_at.is_(None),
        )
    )
    fleeces = [_fleece_dict(f) for f in result.scalars().all()]
    shearings = await db.execute(
        select(func.count(SmallRuminantShearing.id)).where(
            SmallRuminantShearing.farm_id == farm_id, SmallRuminantShearing.species == species,
            SmallRuminantShearing.deleted_at.is_(None),
        )
    )
    summary = eng.clip_summary(fleeces, price_per_kg)
    summary["shearing_sessions"] = {"label": eng.RECORDED, "value": shearings.scalar_one() or 0,
                                    "detail": "Recorded shearing sessions."}
    return summary
