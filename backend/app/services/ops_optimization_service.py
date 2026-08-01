"""
Greena — Operations Planner Analytics & Optimization Service (Platform Module 5).

Runs the deterministic analytics engines (optimization, compliance, capacity,
workload) over recorded ``OpsFacts`` and persists advisory improvement
recommendations (spec Doc 4 §12, §18 Analytics). Recommendations are never
auto-applied — a user approves them, mirroring the Growth Planner's advisory-only
discipline. Every surfaced value keeps its honesty label from the engines.
"""

import uuid
from datetime import date

from sqlalchemy import select

from app.exceptions import NotFoundException
from app.models import ops_planner as m
from app.models.auth import User
from app.services import audit_service
from app.services import ops_capacity_engine as capacity_engine
from app.services import ops_compliance_engine as compliance_engine
from app.services import ops_data
from app.services import ops_optimization_engine as optimization_engine
from app.services import ops_workload_engine as workload_engine


async def performance(db, farm_id, module=None, since: date | None = None) -> dict:
    """Routine performance analytics (completion rate + status mix) from records."""
    return await ops_data.completion_metrics(db, farm_id, module, since=since)


async def compliance_report(db, farm_id, as_of: date | None = None) -> dict:
    """Recurring-compliance status derived from compliance-category routines."""
    reqs = await ops_data.compliance_requirements(db, farm_id)
    return compliance_engine.evaluate(reqs, as_of=as_of or date.today())


async def efficiency(db, farm_id) -> dict:
    """Worker workload balance / fairness (Workload Balancing Engine)."""
    wl = await ops_data.workload(db, farm_id)
    return workload_engine.balance(wl["assignments"], wl["capacities"])


async def capacity_report(db, farm_id, module=None, growth_factor: float | None = None) -> dict:
    """Labour/time capacity vs current demand, with an optional Growth-Planner
    growth projection (Capacity Planning Engine)."""
    wl = await ops_data.workload(db, farm_id)
    demand_minutes = sum(a["minutes"] for a in wl["assignments"])
    capacity_minutes = sum(wl["capacities"].values())
    return capacity_engine.analyze(
        {"labor_minutes": demand_minutes},
        {"labor_minutes": capacity_minutes},
        growth_factor=growth_factor)


async def analyze(db, farm_id, module=None, since: date | None = None) -> dict:
    """Full optimisation pass: threshold-based advisory recommendations from
    recorded completion metrics (not persisted; call ``generate_recommendations``
    to store)."""
    metrics = await ops_data.completion_metrics(db, farm_id, module, since=since)
    return optimization_engine.analyze(metrics)


async def generate_recommendations(db, farm_id, module=None, user: User = None,
                                   since: date | None = None) -> list[m.OpsRecommendation]:
    """Persist newly-surfaced optimisation recommendations (idempotent by title
    within the farm/module — a recommendation already open is not duplicated)."""
    result = await analyze(db, farm_id, module, since=since)
    existing_titles = {t for (t,) in (await db.execute(select(m.OpsRecommendation.title).where(
        m.OpsRecommendation.farm_id == farm_id,
        m.OpsRecommendation.approval_status == "pending",
        m.OpsRecommendation.deleted_at.is_(None)))).all()}
    created = []
    for rec in result["recommendations"]:
        title = rec["value"][:200]
        if title in existing_titles:
            continue
        row = m.OpsRecommendation(
            id=uuid.uuid4(), farm_id=farm_id, module=module, title=title,
            recommendation=rec["detail"], evidence=rec.get("evidence") or {},
            supporting_metrics=rec.get("evidence") or {},
            expected_benefit=rec.get("reasoning"), confidence=rec.get("confidence", "medium"),
            priority="normal", approval_status="pending", implementation_status="not_started",
            created_by=user.id if user else None)
        db.add(row)
        created.append(row)
    if created:
        await db.flush()
        await audit_service.log_action(
            db, action="ops.recommendation.generate", resource_type="ops_recommendation",
            farm_id=farm_id, user_id=user.id if user else None,
            new_value={"count": len(created)})
        await db.commit()
        for row in created:
            await db.refresh(row)
    return created


async def list_recommendations(db, farm_id, module=None, status=None) -> list[m.OpsRecommendation]:
    q = select(m.OpsRecommendation).where(
        m.OpsRecommendation.farm_id == farm_id, m.OpsRecommendation.deleted_at.is_(None))
    if module:
        q = q.where(m.OpsRecommendation.module == module)
    if status:
        q = q.where(m.OpsRecommendation.approval_status == status)
    return list((await db.execute(q.order_by(m.OpsRecommendation.created_at.desc()))).scalars().all())


async def decide_recommendation(db, farm_id, recommendation_id, approval_status, user: User) -> m.OpsRecommendation:
    rec = (await db.execute(select(m.OpsRecommendation).where(
        m.OpsRecommendation.id == recommendation_id, m.OpsRecommendation.farm_id == farm_id,
        m.OpsRecommendation.deleted_at.is_(None)))).scalar_one_or_none()
    if rec is None:
        raise NotFoundException(f"Recommendation {recommendation_id} not found for this farm.")
    rec.approval_status = approval_status
    if approval_status == "implemented":
        rec.implementation_status = "done"
    await db.flush()
    await audit_service.log_action(
        db, action="ops.recommendation.decide", resource_type="ops_recommendation",
        resource_id=rec.id, farm_id=farm_id, user_id=user.id,
        new_value={"approval_status": approval_status})
    await db.commit()
    await db.refresh(rec)
    return rec
