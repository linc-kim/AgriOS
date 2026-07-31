"""
Greena — Growth Planner Service (Platform, introduced by Module 16)

Canonical, cross-module long-term-growth orchestration (see the Growth Planner
Contract in docs/MODULE_16_BSF_LEDGER.md). Generic over ``module``; callers pass
their module key and their own permission-guarded endpoints.

Guarantees:
  * Goals/milestones are recorded domain objects (structured rows), never AI text.
  * **Every mutation appends an immutable revision snapshot** — full version
    history; any two revisions are comparable.
  * Planned-vs-actual is computed by the pure engine from a **per-module metric
    provider** that reads recorded operational data only; a missing actual is
    ``unknown`` — never invented.
  * Deterministic; advisors recommend but only explicit user calls mutate a plan.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.growth import GrowthGoal, GrowthMilestone, GrowthPlan, GrowthPlanRevision
from app.services import audit_service
from app.services import growth_planner_engine as engine

# ── Per-module metric providers (recorded-data actual sources) ────────────────

MetricProvider = Callable[[AsyncSession, uuid.UUID, str], Awaitable[float | None]]
_METRIC_PROVIDERS: dict[str, MetricProvider] = {}


def register_metric_provider(module: str, fn: MetricProvider) -> None:
    """Register a module's 'actual value' provider. The provider reads recorded
    operational facts only and returns ``None`` for unknown metrics."""
    _METRIC_PROVIDERS[module] = fn


async def _actual(db: AsyncSession, farm_id: uuid.UUID, module: str, metric_key: str) -> float | None:
    fn = _METRIC_PROVIDERS.get(module)
    if fn is None:
        return None
    return await fn(db, farm_id, metric_key)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_plan_or_404(db, farm_id, module, plan_id) -> GrowthPlan:
    plan = (await db.execute(select(GrowthPlan).where(
        GrowthPlan.id == plan_id, GrowthPlan.farm_id == farm_id, GrowthPlan.module == module,
        GrowthPlan.deleted_at.is_(None)))).scalar_one_or_none()
    if plan is None:
        raise NotFoundException(f"Growth plan {plan_id} not found for this farm/module.")
    return plan


async def _goals(db, plan_id) -> list[GrowthGoal]:
    return list((await db.execute(select(GrowthGoal).where(
        GrowthGoal.plan_id == plan_id, GrowthGoal.deleted_at.is_(None)))).scalars().all())


async def _milestones(db, plan_id) -> list[GrowthMilestone]:
    result = await db.execute(
        select(GrowthMilestone)
        .where(GrowthMilestone.plan_id == plan_id, GrowthMilestone.deleted_at.is_(None))
        .order_by(GrowthMilestone.sequence))
    return list(result.scalars().all())


def _snapshot(plan: GrowthPlan, goals: list[GrowthGoal], milestones: list[GrowthMilestone]) -> dict:
    return {
        "title": plan.title, "description": plan.description, "status": plan.status,
        "goals": [{
            "id": str(g.id), "metric_key": g.metric_key, "label": g.label, "unit": g.unit,
            "baseline_value": float(g.baseline_value) if g.baseline_value is not None else None,
            "target_value": float(g.target_value),
            "target_date": g.target_date.isoformat() if g.target_date else None,
            "status": g.status, "is_primary": g.is_primary,
        } for g in goals],
        "milestones": [{
            "id": str(m.id), "title": m.title, "sequence": m.sequence,
            "target_date": m.target_date.isoformat() if m.target_date else None,
            "status": m.status, "target_metric_key": m.target_metric_key,
            "target_metric_value": float(m.target_metric_value) if m.target_metric_value is not None else None,
            "expected_impact": m.expected_impact,
        } for m in milestones],
    }


async def _write_revision(db, plan: GrowthPlan, reason: str | None, trigger: str, user: User) -> None:
    goals = await _goals(db, plan.id)
    milestones = await _milestones(db, plan.id)
    db.add(GrowthPlanRevision(
        id=uuid.uuid4(), plan_id=plan.id, revision_number=plan.current_revision,
        reason=reason, trigger=trigger, snapshot=_snapshot(plan, goals, milestones), created_by=user.id,
    ))


def _add_goals(db, plan_id, goals_data, user) -> None:
    for gd in goals_data:
        db.add(GrowthGoal(
            id=uuid.uuid4(), plan_id=plan_id, metric_key=gd.metric_key, label=gd.label, unit=gd.unit,
            baseline_value=gd.baseline_value, target_value=gd.target_value, target_date=gd.target_date,
            is_primary=gd.is_primary, created_by=user.id,
        ))


def _add_milestones(db, plan_id, milestones_data, user) -> None:
    for md in milestones_data:
        db.add(GrowthMilestone(
            id=uuid.uuid4(), plan_id=plan_id, title=md.title, description=md.description,
            sequence=md.sequence, target_date=md.target_date, target_metric_key=md.target_metric_key,
            target_metric_value=md.target_metric_value, expected_impact=md.expected_impact,
            dependencies=md.dependencies or [], created_by=user.id,
        ))


# ── Plan lifecycle ────────────────────────────────────────────────────────────

async def create_plan(db, farm_id, module, data, user: User) -> GrowthPlan:
    if data.is_primary:
        # Demote any existing primary plan for this farm/module (one primary).
        existing = (await db.execute(select(GrowthPlan).where(
            GrowthPlan.farm_id == farm_id, GrowthPlan.module == module, GrowthPlan.is_primary.is_(True),
            GrowthPlan.deleted_at.is_(None)))).scalars().all()
        for p in existing:
            p.is_primary = False
    plan = GrowthPlan(
        id=uuid.uuid4(), farm_id=farm_id, module=module, title=data.title, description=data.description,
        is_primary=data.is_primary, status="active", current_revision=1, created_by=user.id,
    )
    db.add(plan)
    await db.flush()
    _add_goals(db, plan.id, data.goals, user)
    _add_milestones(db, plan.id, data.milestones, user)
    await db.flush()
    await _write_revision(db, plan, reason="Plan created.", trigger="manual", user=user)
    await audit_service.log_action(
        db, action="growth.plan.create", resource_type="growth_plan", resource_id=plan.id,
        farm_id=farm_id, user_id=user.id, new_value={"title": plan.title, "module": module})
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_plans(db, farm_id, module) -> list[GrowthPlan]:
    result = await db.execute(
        select(GrowthPlan)
        .where(GrowthPlan.farm_id == farm_id, GrowthPlan.module == module, GrowthPlan.deleted_at.is_(None))
        .order_by(GrowthPlan.is_primary.desc(), GrowthPlan.created_at.desc()))
    return list(result.scalars().all())


async def get_primary_plan(db, farm_id, module) -> GrowthPlan | None:
    return (await db.execute(select(GrowthPlan).where(
        GrowthPlan.farm_id == farm_id, GrowthPlan.module == module, GrowthPlan.is_primary.is_(True),
        GrowthPlan.status == "active", GrowthPlan.deleted_at.is_(None))
        .order_by(GrowthPlan.created_at.desc()).limit(1))).scalar_one_or_none()


async def update_plan(db, farm_id, module, plan_id, data, user: User) -> GrowthPlan:
    plan = await _get_plan_or_404(db, farm_id, module, plan_id)
    if plan.status == "archived":
        raise ConflictException("Archived plans cannot be edited; create a new plan.")
    trigger = "manual"
    if data.title is not None:
        plan.title = data.title
    if data.description is not None:
        plan.description = data.description
    if data.status is not None:
        plan.status = data.status
    # Replace goals/milestones when supplied — the prior state is preserved in the
    # immutable revision snapshot written below (version history).
    if data.goals is not None:
        for g in await _goals(db, plan.id):
            g.soft_delete()
        _add_goals(db, plan.id, data.goals, user)
        trigger = "goal_change"
    if data.milestones is not None:
        for m in await _milestones(db, plan.id):
            m.soft_delete()
        _add_milestones(db, plan.id, data.milestones, user)
    plan.current_revision += 1
    await db.flush()
    await _write_revision(db, plan, reason=data.reason, trigger=trigger, user=user)
    await audit_service.log_action(
        db, action="growth.plan.update", resource_type="growth_plan", resource_id=plan.id,
        farm_id=farm_id, user_id=user.id, new_value={"revision": plan.current_revision})
    await db.commit()
    await db.refresh(plan)
    return plan


async def update_milestone_status(db, farm_id, module, plan_id, milestone_id, status, reason, user: User) -> GrowthPlan:
    from app.models.growth import GROWTH_MILESTONE_STATUS_VALUES
    if status not in GROWTH_MILESTONE_STATUS_VALUES:
        raise ValidationException(f"Invalid milestone status {status!r}.")
    plan = await _get_plan_or_404(db, farm_id, module, plan_id)
    milestone = (await db.execute(select(GrowthMilestone).where(
        GrowthMilestone.id == milestone_id, GrowthMilestone.plan_id == plan_id,
        GrowthMilestone.deleted_at.is_(None)))).scalar_one_or_none()
    if milestone is None:
        raise NotFoundException(f"Milestone {milestone_id} not found on this plan.")
    milestone.status = status
    plan.current_revision += 1
    await db.flush()
    await _write_revision(db, plan, reason=reason or f"Milestone → {status}.", trigger="milestone_update", user=user)
    await audit_service.log_action(
        db, action="growth.milestone.status", resource_type="growth_milestone", resource_id=milestone.id,
        farm_id=farm_id, user_id=user.id, new_value={"status": status})
    await db.commit()
    await db.refresh(plan)
    return plan


async def archive_plan(db, farm_id, module, plan_id, user: User) -> GrowthPlan:
    plan = await _get_plan_or_404(db, farm_id, module, plan_id)
    plan.status = "archived"
    plan.is_primary = False
    plan.current_revision += 1
    await db.flush()
    await _write_revision(db, plan, reason="Plan archived.", trigger="manual", user=user)
    await db.commit()
    await db.refresh(plan)
    return plan


# ── Revisions ─────────────────────────────────────────────────────────────────

async def list_revisions(db, farm_id, module, plan_id) -> list[GrowthPlanRevision]:
    await _get_plan_or_404(db, farm_id, module, plan_id)
    result = await db.execute(
        select(GrowthPlanRevision)
        .where(GrowthPlanRevision.plan_id == plan_id, GrowthPlanRevision.deleted_at.is_(None))
        .order_by(GrowthPlanRevision.revision_number.desc()))
    return list(result.scalars().all())


async def compare_revisions(db, farm_id, module, plan_id, rev_a: int, rev_b: int) -> dict:
    await _get_plan_or_404(db, farm_id, module, plan_id)
    rows = {r.revision_number: r for r in (await db.execute(select(GrowthPlanRevision).where(
        GrowthPlanRevision.plan_id == plan_id, GrowthPlanRevision.revision_number.in_((rev_a, rev_b)),
        GrowthPlanRevision.deleted_at.is_(None)))).scalars().all()}
    if rev_a not in rows or rev_b not in rows:
        raise NotFoundException("One or both revisions were not found for this plan.")
    return {"from_revision": rev_a, "to_revision": rev_b,
            "diff": engine.diff_revisions(rows[rev_a].snapshot, rows[rev_b].snapshot)}


# ── Progress (planned vs actual, from recorded data) ──────────────────────────

async def compute_progress(db, farm_id, module, plan: GrowthPlan) -> dict:
    goals = await _goals(db, plan.id)
    milestones = await _milestones(db, plan.id)
    as_of = date.today()

    goal_reports = []
    overall_values = []
    for g in goals:
        actual = await _actual(db, farm_id, module, g.metric_key)
        progress = engine.goal_progress(g.baseline_value, g.target_value, actual)
        run_rate = engine.required_run_rate(g.baseline_value, g.target_value, actual, g.target_date, as_of)
        goal_reports.append({
            "goal_id": str(g.id), "metric_key": g.metric_key, "label": g.label, "unit": g.unit,
            "is_primary": g.is_primary, "progress": progress, "run_rate": run_rate,
        })
        pct = progress.get("percent", {}).get("value")
        if pct is not None:
            overall_values.append((g.is_primary, pct))

    # Overall = primary goal's progress if present, else the mean of known goals.
    primary = [v for is_p, v in overall_values if is_p]
    if primary:
        overall = primary[0]
    elif overall_values:
        overall = round(sum(v for _, v in overall_values) / len(overall_values), 1)
    else:
        overall = None

    rollup = engine.milestone_rollup(_snapshot(plan, goals, milestones)["milestones"])
    return {
        "overall_percent": {"label": "calculated" if overall is not None else "unknown", "value": overall,
                            "detail": "Primary goal progress, else mean of goals with recorded actuals."},
        "goals": goal_reports,
        "milestones": rollup,
    }


async def get_plan_detail(db, farm_id, module, plan_id) -> dict:
    plan = await _get_plan_or_404(db, farm_id, module, plan_id)
    goals = await _goals(db, plan.id)
    milestones = await _milestones(db, plan.id)
    progress = await compute_progress(db, farm_id, module, plan)
    return {"plan": plan, "goals": goals, "milestones": milestones, "progress": progress}


async def primary_overall_progress(db, farm_id, module) -> float | None:
    """Convenience for dashboards: the primary plan's overall progress %, or None."""
    plan = await get_primary_plan(db, farm_id, module)
    if plan is None:
        return None
    progress = await compute_progress(db, farm_id, module, plan)
    return progress["overall_percent"]["value"]
