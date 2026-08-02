"""
Greena — Small Ruminant Growth Service (Modules 18/19, Milestone 4)

Weight history is immutable (Goat Doc 2 §11) and in kilograms; ``current_weight_kg``
on the animal mirrors the latest record for fast display. All growth math is
delegated to the PURE :mod:`small_ruminant_growth_engine`. Expected-weight curves
come from the animal's breed ``profile['growth_curve']`` when present.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.models.small_ruminant import SmallRuminant, SmallRuminantBreed, SmallRuminantWeight
from app.schemas.small_ruminant import WeightCreate
from app.services import audit_service
from app.services import small_ruminant_growth_engine as eng
from app.services.small_ruminant_service import _append_event, _get_animal_or_404


async def _breed_growth_curve(db, breed_id) -> list[dict] | None:
    if not breed_id:
        return None
    row = await db.execute(select(SmallRuminantBreed.profile).where(SmallRuminantBreed.id == breed_id))
    profile = row.scalar_one_or_none()
    if profile and isinstance(profile.get("growth_curve"), list):
        return profile["growth_curve"]
    return None


async def record_weight(db: AsyncSession, farm: Farm, species: str, animal_id, data: WeightCreate, user: User):
    """Record an immutable weight; sync the animal's current weight for display."""
    animal = await _get_animal_or_404(db, farm.id, species, animal_id)
    age = (data.recorded_on - animal.date_of_birth).days if animal.date_of_birth else None
    w = SmallRuminantWeight(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=animal_id,
        recorded_on=data.recorded_on, weight_kg=data.weight_kg, method=data.method,
        body_condition_score=data.body_condition_score, heart_girth_cm=data.heart_girth_cm,
        height_cm=data.height_cm, body_length_cm=data.body_length_cm, age_days=age,
        notes=data.notes, recorded_by=user.id,
    )
    db.add(w)
    await db.flush()

    # Mirror the latest recorded weight onto the animal (display only; the table is
    # authoritative). Only advance if this is the most recent measurement.
    latest = await db.execute(
        select(func.max(SmallRuminantWeight.recorded_on)).where(
            SmallRuminantWeight.animal_id == animal_id, SmallRuminantWeight.deleted_at.is_(None)
        )
    )
    if latest.scalar_one() == data.recorded_on:
        animal.current_weight_kg = data.weight_kg

    await _append_event(
        db, animal_id, "weight_recorded", f"Weight {data.weight_kg} kg",
        occurred_at=datetime.combine(data.recorded_on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"weight_kg": str(data.weight_kg)},
    )
    await audit_service.log_action(
        db, action=f"sr.{species}.weight.record", resource_type="sr_weight",
        resource_id=w.id, farm_id=farm.id, user_id=user.id, new_value={"weight_kg": str(data.weight_kg)},
    )
    await db.commit()
    await db.refresh(w)
    return w


async def list_weights(db, farm_id, species, animal_id):
    await _get_animal_or_404(db, farm_id, species, animal_id)
    result = await db.execute(
        select(SmallRuminantWeight).where(
            SmallRuminantWeight.animal_id == animal_id, SmallRuminantWeight.deleted_at.is_(None)
        ).order_by(SmallRuminantWeight.recorded_on.desc())
    )
    return list(result.scalars().all())


async def _weight_dicts(db, animal_id) -> list[dict]:
    rows = await db.execute(
        select(SmallRuminantWeight.recorded_on, SmallRuminantWeight.weight_kg).where(
            SmallRuminantWeight.animal_id == animal_id, SmallRuminantWeight.deleted_at.is_(None)
        )
    )
    return [{"recorded_on": r[0], "weight_kg": r[1]} for r in rows]


async def growth_analysis(db, farm_id, species, animal_id) -> dict:
    animal = await _get_animal_or_404(db, farm_id, species, animal_id)
    weights = await _weight_dicts(db, animal_id)
    curve = await _breed_growth_curve(db, animal.breed_id)
    analysis = eng.weight_analysis(weights, dob=animal.date_of_birth, growth_curve=curve)
    series = eng.growth_series(weights, dob=animal.date_of_birth)

    # Peer percentile: latest weight vs same-species active peers' current weight.
    percentile = eng._lab(eng.UNKNOWN, None, "No latest weight recorded.")
    latest = analysis["latest_weight_kg"]["value"]
    if latest is not None:
        peers = await db.execute(
            select(SmallRuminant.current_weight_kg).where(
                SmallRuminant.farm_id == farm_id, SmallRuminant.species == species,
                SmallRuminant.status == "active", SmallRuminant.id != animal_id,
                SmallRuminant.current_weight_kg.is_not(None), SmallRuminant.deleted_at.is_(None),
            )
        )
        percentile = eng.growth_percentile(latest, [row[0] for row in peers])

    return {"animal_id": str(animal_id), "analysis": analysis, "series": series,
            "peer_percentile": percentile}


async def latest_weight_gain_kg(db, animal_id) -> float | None:
    """Total live-weight gain (kg) between the earliest and latest recorded weights."""
    if animal_id is None:
        return None
    weights = await _weight_dicts(db, animal_id)
    ws = eng._sorted(weights)
    if len(ws) < 2:
        return None
    gain = eng._f(ws[-1]["weight_kg"]) - eng._f(ws[0]["weight_kg"])
    return gain
