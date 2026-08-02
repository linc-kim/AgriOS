"""
Greena — Swine Growth & Production Service (Module 20, Milestone 7)

Records immutable weight events and body-condition scores, owns the production-stage
transition history, and produces growth analytics + the market-readiness assessment.
No growth figure is stored — ADG, gain, curves and FCR are computed on demand by the
PURE :mod:`swine_growth_engine` (feed conversion reuses the feed engine). Market
readiness is an explainable assessment against configurable targets, integrating the
registry (breed/age), health (withdrawals, open cases, isolation) and feed data.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineBodyCondition,
    SwineBreed,
    SwineDiseaseCase,
    SwineIsolation,
    SwinePig,
    SwineStageTransition,
    SwineTreatment,
    SwineWeight,
)
from app.schemas.swine import (
    BodyConditionCreate,
    StageTransitionInput,
    WeightCreate,
)
from app.services import audit_service
from app.services import swine_config as cfg
from app.services import swine_growth_engine as eng
from app.services.swine_service import _append_event, _get_pig_or_404, record_stage_transition


# ── Weight (immutable events) ──────────────────────────────────────────────────

async def record_weight(db: AsyncSession, farm: Farm, pig_id: uuid.UUID, data: WeightCreate, user: User) -> SwineWeight:
    pig = await _get_pig_or_404(db, farm.id, pig_id)
    age_days = data.age_days
    if age_days is None and pig.date_of_birth is not None:
        age_days = (data.recorded_on - pig.date_of_birth).days
    row = SwineWeight(
        id=uuid.uuid4(), farm_id=farm.id, pig_id=pig_id, recorded_on=data.recorded_on,
        weight_kg=data.weight_kg, method=data.method, age_days=age_days, notes=data.notes,
        recorded_by=user.id,
    )
    db.add(row)
    await db.flush()
    # Mirror the latest weight onto the pig for fast display (derived, not source of truth).
    latest = await db.execute(
        select(SwineWeight.weight_kg).where(
            SwineWeight.pig_id == pig_id, SwineWeight.deleted_at.is_(None)
        ).order_by(SwineWeight.recorded_on.desc(), SwineWeight.created_at.desc()).limit(1))
    pig.current_weight_kg = latest.scalar_one()
    await _append_event(db, pig_id, "weight_recorded", f"Weighed {data.weight_kg} kg",
                        occurred_at=datetime.combine(data.recorded_on, datetime.min.time(), tzinfo=timezone.utc),
                        operator_id=user.id, details={"weight_kg": str(data.weight_kg)})
    await audit_service.log_action(
        db, action="swine.growth.weight.record", resource_type="swine_weight",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"weight_kg": str(data.weight_kg)})
    await db.commit()
    await db.refresh(row)
    return row


async def _weights(db, farm_id, pig_id) -> list[dict]:
    r = await db.execute(select(SwineWeight.recorded_on, SwineWeight.weight_kg, SwineWeight.age_days).where(
        SwineWeight.farm_id == farm_id, SwineWeight.pig_id == pig_id, SwineWeight.deleted_at.is_(None)))
    return [{"recorded_on": row[0], "weight_kg": row[1], "age_days": row[2]} for row in r]


async def list_weights(db, farm_id, pig_id, limit=200, offset=0):
    await _get_pig_or_404(db, farm_id, pig_id)
    r = await db.execute(select(SwineWeight).where(
        SwineWeight.farm_id == farm_id, SwineWeight.pig_id == pig_id, SwineWeight.deleted_at.is_(None)
    ).order_by(SwineWeight.recorded_on.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())


async def growth_analysis(db, farm_id, pig_id) -> dict:
    await _get_pig_or_404(db, farm_id, pig_id)
    analysis = eng.growth_analysis(await _weights(db, farm_id, pig_id))
    return {"pig_id": str(pig_id), **analysis}


async def weight_gain_kg(db, farm_id, pig_id) -> float | None:
    """Total recorded gain (kg) for a pig — used to wire FCR in the feed summary."""
    return eng.total_gain_kg(await _weights(db, farm_id, pig_id))


async def _adg_value(db, farm_id, pig_id) -> float | None:
    lab = eng.average_daily_gain(await _weights(db, farm_id, pig_id))
    return lab["value"] if lab["label"] == eng.CALCULATED else None


# ── Body condition (independent of weight) ─────────────────────────────────────

async def record_body_condition(db, farm: Farm, pig_id, data: BodyConditionCreate, user: User) -> SwineBodyCondition:
    await _get_pig_or_404(db, farm.id, pig_id)
    row = SwineBodyCondition(
        id=uuid.uuid4(), farm_id=farm.id, pig_id=pig_id, assessed_on=data.assessed_on,
        score=data.score, assessor=data.assessor, notes=data.notes, created_by=user.id)
    db.add(row)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.growth.body_condition.record", resource_type="swine_body_condition",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"score": str(data.score)})
    await db.commit()
    await db.refresh(row)
    return row


async def list_body_condition(db, farm_id, pig_id):
    await _get_pig_or_404(db, farm_id, pig_id)
    r = await db.execute(select(SwineBodyCondition).where(
        SwineBodyCondition.farm_id == farm_id, SwineBodyCondition.pig_id == pig_id,
        SwineBodyCondition.deleted_at.is_(None)).order_by(SwineBodyCondition.assessed_on.desc()))
    return list(r.scalars().all())


# ── Production-stage transitions (history) ─────────────────────────────────────

async def transition_stage(db, farm: Farm, pig_id, data: StageTransitionInput, user: User) -> SwinePig:
    pig = await _get_pig_or_404(db, farm.id, pig_id)
    if not cfg.is_forward_stage_transition(pig.production_stage, data.new_stage):
        from app.exceptions import ValidationException
        raise ValidationException(
            f"Invalid production-stage transition {pig.production_stage!r} → {data.new_stage!r}.")
    await record_stage_transition(db, farm.id, pig, data.new_stage,
                                  reason=data.reason, source=data.source, user=user, on=data.transition_date)
    await audit_service.log_action(
        db, action="swine.growth.stage.transition", resource_type="swine_pig",
        resource_id=pig.id, farm_id=farm.id, user_id=user.id, new_value={"new_stage": data.new_stage})
    await db.commit()
    await db.refresh(pig)
    return pig


async def list_stage_transitions(db, farm_id, pig_id):
    await _get_pig_or_404(db, farm_id, pig_id)
    r = await db.execute(select(SwineStageTransition).where(
        SwineStageTransition.farm_id == farm_id, SwineStageTransition.pig_id == pig_id,
        SwineStageTransition.deleted_at.is_(None)).order_by(SwineStageTransition.transition_date.desc()))
    return list(r.scalars().all())


# ── Market readiness (explainable assessment) ──────────────────────────────────

async def _breed_profile(db, breed_id) -> dict | None:
    if breed_id is None:
        return None
    r = await db.execute(select(SwineBreed.profile).where(SwineBreed.id == breed_id))
    return r.scalar_one_or_none()


async def market_readiness(db, farm_id, pig_id, *, target_weight_kg=None, target_age_days=None) -> dict:
    pig = await _get_pig_or_404(db, farm_id, pig_id)
    weights = await _weights(db, farm_id, pig_id)
    latest = max(weights, key=lambda w: w["recorded_on"]) if weights else None
    latest_weight = float(latest["weight_kg"]) if latest else None
    age_days = latest["age_days"] if latest else None
    if age_days is None and pig.date_of_birth is not None:
        age_days = (date.today() - pig.date_of_birth).days
    adg = await _adg_value(db, farm_id, pig_id)

    targets = cfg.market_targets(await _breed_profile(db, pig.breed_id),
                                 target_weight_kg=target_weight_kg, target_age_days=target_age_days)

    today = date.today()
    wd = await db.execute(select(func.count(SwineTreatment.id)).where(
        SwineTreatment.farm_id == farm_id, SwineTreatment.pig_id == pig_id,
        SwineTreatment.withdrawal_until >= today, SwineTreatment.deleted_at.is_(None)))
    active_withdrawal = (wd.scalar_one() or 0) > 0
    oc = await db.execute(select(func.count(SwineDiseaseCase.id)).where(
        SwineDiseaseCase.farm_id == farm_id, SwineDiseaseCase.pig_id == pig_id,
        SwineDiseaseCase.status.in_(("suspected", "confirmed", "chronic")),
        SwineDiseaseCase.deleted_at.is_(None)))
    iso = await db.execute(select(func.count(SwineIsolation.id)).where(
        SwineIsolation.farm_id == farm_id, SwineIsolation.pig_id == pig_id,
        SwineIsolation.status == "active", SwineIsolation.deleted_at.is_(None)))
    health_ok = (oc.scalar_one() or 0) == 0 and (iso.scalar_one() or 0) == 0

    assessment = eng.market_readiness(
        latest_weight_kg=latest_weight, age_days=age_days, targets=targets, adg_kg=adg,
        active_withdrawal=active_withdrawal, health_ok=health_ok,
        approaching_fraction=cfg.MARKET_APPROACHING_FRACTION)
    return {"pig_id": str(pig_id), **assessment}


# ── Cohort analytics (historical) ──────────────────────────────────────────────

async def _cohort_members(db, farm_id, *, group_id=None, litter_id=None, pen_id=None,
                          production_stage=None, breed_id=None) -> dict:
    conds = [SwinePig.farm_id == farm_id, SwinePig.status == "active", SwinePig.deleted_at.is_(None)]
    if group_id:
        conds.append(SwinePig.group_id == group_id)
    if litter_id:
        conds.append(SwinePig.litter_id == litter_id)
    if pen_id:
        conds.append(SwinePig.pen_id == pen_id)
    if production_stage:
        conds.append(SwinePig.production_stage == production_stage)
    if breed_id:
        conds.append(SwinePig.breed_id == breed_id)
    r = await db.execute(select(SwinePig.id).where(*conds))
    pig_ids = [row[0] for row in r]
    members = []
    for pid in pig_ids:
        ws = await _weights(db, farm_id, pid)
        latest = max(ws, key=lambda w: w["recorded_on"]) if ws else None
        adg = eng.average_daily_gain(ws)
        members.append({
            "latest_weight_kg": float(latest["weight_kg"]) if latest else None,
            "adg_kg": adg["value"] if adg["label"] == eng.CALCULATED else None,
        })
    return eng.cohort_summary(members)


async def cohort_growth(db, farm_id, *, group_id=None, litter_id=None, pen_id=None,
                        production_stage=None, breed_id=None) -> dict:
    scope = {"group_id": str(group_id) if group_id else None,
             "litter_id": str(litter_id) if litter_id else None,
             "pen_id": str(pen_id) if pen_id else None,
             "production_stage": production_stage, "breed_id": str(breed_id) if breed_id else None}
    summary = await _cohort_members(db, farm_id, group_id=group_id, litter_id=litter_id, pen_id=pen_id,
                                    production_stage=production_stage, breed_id=breed_id)
    return {"scope": scope, "summary": summary}


async def stage_comparison(db, farm_id) -> dict:
    """Average weight + ADG by production stage (historical comparison)."""
    out = {}
    for stage in ("weaner", "nursery", "grower", "finisher"):
        out[stage] = await _cohort_members(db, farm_id, production_stage=stage)
    return {"by_stage": out}


async def herd_growth_summary(db, farm_id) -> dict:
    total = await db.execute(select(func.count(SwineWeight.id)).where(
        SwineWeight.farm_id == farm_id, SwineWeight.deleted_at.is_(None)))
    herd = await _cohort_members(db, farm_id)
    return {"total_weighings": total.scalar_one() or 0, "herd": herd}
