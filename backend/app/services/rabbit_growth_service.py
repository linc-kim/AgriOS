"""
Greena — Rabbit Growth Service (Module 17, Milestone 4)

Weight recording and growth analysis. The service owns DB reads/writes; all
calculations are delegated to the PURE :mod:`rabbit_growth_engine` (GMIS §1.3).
Weight history is immutable (Spec Part 3 §9); ``rabbit.current_weight_g`` is kept
in sync with the latest measurement for fast display. Registry helpers (rabbit
lookup, event append) are reused from :mod:`rabbit_service`.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.models.rabbit import Rabbit, RabbitBreed, RabbitWeight
from app.schemas.rabbit import WeightCreate
from app.services import audit_service, rabbit_growth_engine as eng, rabbit_service


async def _weights_for(db: AsyncSession, rabbit_id: uuid.UUID) -> list[RabbitWeight]:
    result = await db.execute(
        select(RabbitWeight).where(
            RabbitWeight.rabbit_id == rabbit_id, RabbitWeight.deleted_at.is_(None)
        ).order_by(RabbitWeight.recorded_on)
    )
    return list(result.scalars().all())


async def _breed_growth_curve(db: AsyncSession, breed_id: uuid.UUID | None) -> list[dict] | None:
    if breed_id is None:
        return None
    profile = (await db.execute(select(RabbitBreed.profile).where(RabbitBreed.id == breed_id))).scalar_one_or_none()
    if profile and isinstance(profile, dict):
        curve = profile.get("growth_curve")
        if isinstance(curve, list) and curve:
            return curve
    return None


async def record_weight(db: AsyncSession, farm: Farm, rabbit_id: uuid.UUID, data: WeightCreate, user: User) -> RabbitWeight:
    r = await rabbit_service._get_rabbit_or_404(db, farm.id, rabbit_id)
    age_days = (data.recorded_on - r.date_of_birth).days if r.date_of_birth else None
    weight = RabbitWeight(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=rabbit_id, recorded_on=data.recorded_on,
        weight_g=data.weight_g, age_days=age_days, notes=data.notes, recorded_by=user.id,
    )
    db.add(weight)
    await db.flush()

    # Keep the rabbit's display weight in sync with the latest measurement.
    latest = (await db.execute(
        select(RabbitWeight.weight_g).where(
            RabbitWeight.rabbit_id == rabbit_id, RabbitWeight.deleted_at.is_(None)
        ).order_by(RabbitWeight.recorded_on.desc(), RabbitWeight.created_at.desc()).limit(1)
    )).scalar_one()
    r.current_weight_g = latest

    await rabbit_service._append_event(
        db, rabbit_id, "weight_recorded", f"Weight recorded: {data.weight_g} g",
        occurred_at=datetime.combine(data.recorded_on, datetime.min.time(), tzinfo=timezone.utc),
        operator_id=user.id, details={"weight_g": str(data.weight_g), "age_days": age_days},
    )
    await audit_service.log_action(
        db, action="rabbit.weight.record", resource_type="rabbit_weight",
        resource_id=weight.id, farm_id=farm.id, user_id=user.id, new_value={"weight_g": str(data.weight_g)},
    )
    await db.commit()
    await db.refresh(weight)
    return weight


async def list_weights(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> list[RabbitWeight]:
    await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
    result = await db.execute(
        select(RabbitWeight).where(
            RabbitWeight.rabbit_id == rabbit_id, RabbitWeight.deleted_at.is_(None)
        ).order_by(RabbitWeight.recorded_on.desc(), RabbitWeight.created_at.desc())
    )
    return list(result.scalars().all())


async def growth_analysis(db: AsyncSession, farm_id: uuid.UUID, rabbit_id: uuid.UUID) -> dict:
    r = await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
    weights = await _weights_for(db, rabbit_id)
    wdicts = [{"recorded_on": w.recorded_on, "weight_g": w.weight_g} for w in weights]
    curve = await _breed_growth_curve(db, r.breed_id)

    analysis = eng.weight_analysis(wdicts, dob=r.date_of_birth, growth_curve=curve)
    series = eng.growth_series(wdicts, dob=r.date_of_birth)

    # Herd percentile among active same-breed peers' latest recorded weight.
    peer_conds = [
        Rabbit.farm_id == farm_id, Rabbit.status == "active",
        Rabbit.id != rabbit_id, Rabbit.current_weight_g.is_not(None), Rabbit.deleted_at.is_(None),
    ]
    if r.breed_id is not None:
        peer_conds.append(Rabbit.breed_id == r.breed_id)
    peers = (await db.execute(select(Rabbit.current_weight_g).where(*peer_conds))).scalars().all()
    latest_val = analysis["latest_weight_g"]["value"]
    percentile = eng.growth_percentile(latest_val, list(peers))

    return {
        "rabbit_id": str(rabbit_id),
        "internal_ref": r.internal_ref,
        "analysis": analysis,
        "series": series,
        "herd_percentile_pct": percentile,
    }


async def latest_weight_gain_g(db: AsyncSession, rabbit_id: uuid.UUID) -> float | None:
    """Total recorded live-weight gain (last − first) in grams, or None if <2
    measurements. Used by the Feed engine for FCR."""
    rows = (await db.execute(
        select(RabbitWeight.weight_g).where(
            RabbitWeight.rabbit_id == rabbit_id, RabbitWeight.deleted_at.is_(None)
        ).order_by(RabbitWeight.recorded_on)
    )).scalars().all()
    if len(rows) < 2:
        return None
    return float(rows[-1]) - float(rows[0])
