"""
Greena — Mission Control data layer (Module 14).

The only part of Mission Control that touches the database. It persists missions,
assumptions, policies and the append-only revision history; gathers the farm's
current facts through the *existing* `aria_planning_data.gather` (the same rich
`FarmFacts` the planner uses); and runs the pure `mission_control` engine to
produce the roadmap, business plan, daily mission, progress, manual, reports and
dashboard.

It never re-computes a farm metric. Facts come from the planner's gatherer,
strategy from the pure engine, and the CEO advisor's prose from the shared
`ai_provider` (Gemini when available, a grounded deterministic answer otherwise).
The original plan is never overwritten: a replan writes a new `MissionRevision`.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.mission import Mission, MissionRevision
from app.services import (
    ai_provider,
    aria_planning,
    aria_planning_data,
    aviculture_automation_service,
    aviculture_intelligence,
    aviculture_reporting_service,
    bsf_intelligence,
    bsf_reporting_service,
    growth_planner_service,
    mission_control as mc,
    rabbit_intelligence,
    rabbit_reporting_service,
    small_ruminant_intelligence,
    small_ruminant_reporting_service,
    swine_intelligence,
    swine_reporting_service,
)


# ── Spec mapping ──────────────────────────────────────────────────────────────


def _to_spec(mission: Mission) -> mc.MissionSpec:
    metrics_raw = mission.success_metrics or []
    metrics: list[mc.Metric] = []
    for i, m in enumerate(metrics_raw):
        metrics.append(mc.Metric(
            kind=m.get("kind", "qualitative"), label=m.get("label", m.get("kind", "goal")),
            target=_num(m.get("target")), unit=m.get("unit", ""),
            primary=bool(m.get("primary", i == 0)),
        ))
    if metrics and not any(m.primary for m in metrics):
        metrics[0].primary = True
    return mc.MissionSpec(
        name=mission.name, description=mission.description or "",
        target_date=mission.target_date, metrics=metrics,
        constraints=list(mission.constraints or []), priorities=list(mission.priorities or []),
        assumptions=list(mission.assumptions or []), policies=list(mission.policies or []),
        baseline=dict(mission.baseline or {}), status=mission.status,
        created_on=mission.created_at.date() if mission.created_at else None,
    )


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Facts + farm count ────────────────────────────────────────────────────────


async def _facts(db: AsyncSession, farm: Farm, user: User):
    return await aria_planning_data.gather(db, farm, user)


async def _farm_count(db: AsyncSession, farm: Farm) -> int:
    if farm.organization_id is None:
        return 1
    n = (await db.execute(
        select(func.count(Farm.id)).where(
            Farm.organization_id == farm.organization_id, Farm.deleted_at.is_(None))
    )).scalar_one()
    return int(n or 1)


# ── CRUD ──────────────────────────────────────────────────────────────────────


async def create_mission(db: AsyncSession, farm: Farm, user: User, data: dict) -> Mission:
    """
    Create a mission, snapshotting the baseline so progress is measured honestly.

    The baseline is the current value of each metric *at creation*, read from the
    farm's recorded facts — that is what lets "28% complete" mean "28% of the way
    from where you started", not from zero.
    """
    facts = await _facts(db, farm, user)
    farm_count = await _farm_count(db, farm)

    metrics = data.get("success_metrics") or []
    baseline: dict = {}
    for m in metrics:
        kind = m.get("kind")
        if kind and kind not in baseline:
            val = mc.current_metric_value(kind, facts, farm_count=farm_count)
            if val is not None:
                baseline[kind] = val

    make_primary = bool(data.get("is_primary"))
    if make_primary:
        await _clear_primary(db, farm.id)

    mission = Mission(
        farm_id=farm.id, name=data["name"], description=data.get("description"),
        target_date=_parse_date(data.get("target_date")),
        status=data.get("status", "active"), is_primary=make_primary,
        success_metrics=metrics, constraints=data.get("constraints") or [],
        priorities=data.get("priorities") or [],
        assumptions=data.get("assumptions") or [], policies=data.get("policies") or [],
        baseline=baseline, created_by=user.id,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return mission


async def _clear_primary(db, farm_id) -> None:
    rows = (await db.execute(
        select(Mission).where(Mission.farm_id == farm_id, Mission.is_primary.is_(True),
                              Mission.deleted_at.is_(None))
    )).scalars().all()
    for r in rows:
        r.is_primary = False


async def list_missions(db: AsyncSession, farm: Farm) -> list[Mission]:
    rows = (await db.execute(
        select(Mission).where(Mission.farm_id == farm.id, Mission.deleted_at.is_(None))
        .order_by(Mission.is_primary.desc(), Mission.created_at.desc())
    )).scalars().all()
    return list(rows)


async def get_mission(db: AsyncSession, farm: Farm, mission_id: uuid.UUID) -> Mission:
    m = (await db.execute(
        select(Mission).where(Mission.id == mission_id, Mission.farm_id == farm.id,
                              Mission.deleted_at.is_(None))
    )).scalar_one_or_none()
    if m is None:
        raise NotFoundException("Mission")
    return m


async def primary_mission(db: AsyncSession, farm: Farm) -> Mission | None:
    m = (await db.execute(
        select(Mission).where(Mission.farm_id == farm.id, Mission.deleted_at.is_(None))
        .order_by(Mission.is_primary.desc(), Mission.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    return m


async def update_mission(db: AsyncSession, farm: Farm, mission_id: uuid.UUID, changes: dict) -> Mission:
    m = await get_mission(db, farm, mission_id)
    if changes.get("is_primary"):
        await _clear_primary(db, farm.id)
    for field in ("name", "description", "status", "is_primary", "success_metrics",
                  "constraints", "priorities", "assumptions", "policies"):
        if field in changes and changes[field] is not None:
            setattr(m, field, changes[field])
    if "target_date" in changes and changes["target_date"] is not None:
        m.target_date = _parse_date(changes["target_date"])
    m.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(m)
    return m


async def delete_mission(db: AsyncSession, farm: Farm, mission_id: uuid.UUID) -> None:
    m = await get_mission(db, farm, mission_id)
    m.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Revisions (Part 7) ────────────────────────────────────────────────────────


async def create_revision(db: AsyncSession, farm: Farm, user: User, mission_id: uuid.UUID,
                          *, reason: str, trigger: str = "manual") -> MissionRevision:
    """
    Snapshot the current assumptions and plan as a new revision.

    The original is never overwritten — this appends. The snapshot captures the
    assumptions the plan was based on, so the history is a real audit trail.
    """
    m = await get_mission(db, farm, mission_id)
    last = (await db.execute(
        select(func.max(MissionRevision.revision_number)).where(MissionRevision.mission_id == m.id)
    )).scalar_one()
    number = int(last or 0) + 1
    snapshot = {
        "assumptions": m.assumptions, "policies": m.policies,
        "success_metrics": m.success_metrics, "target_date": m.target_date.isoformat() if m.target_date else None,
        "baseline": m.baseline,
    }
    rev = MissionRevision(mission_id=m.id, revision_number=number, reason=reason,
                          trigger=trigger, snapshot=snapshot, created_by=user.id)
    db.add(rev)
    await db.commit()
    await db.refresh(rev)
    return rev


async def list_revisions(db: AsyncSession, farm: Farm, mission_id: uuid.UUID) -> list[MissionRevision]:
    await get_mission(db, farm, mission_id)  # scope check
    rows = (await db.execute(
        select(MissionRevision).where(MissionRevision.mission_id == mission_id,
                                      MissionRevision.deleted_at.is_(None))
        .order_by(MissionRevision.revision_number.desc())
    )).scalars().all()
    return list(rows)


async def replan(db: AsyncSession, farm: Farm, user: User, mission_id: uuid.UUID,
                 *, apply_changes: dict | None = None) -> dict:
    """
    Evaluate whether the plan needs revising and, optionally, apply new assumptions.

    Always snapshots the *current* plan as a revision first (so nothing is lost),
    then applies any accepted assumption changes and returns the fresh evaluation.
    """
    m = await get_mission(db, farm, mission_id)
    facts = await _facts(db, farm, user)
    spec = _to_spec(m)
    evaluation = mc.evaluate_adaptation(spec, facts, today=date.today(),
                                        farm_count=await _farm_count(db, farm))

    rev = await create_revision(db, farm, user, mission_id,
                                reason="Replan requested", trigger=evaluation.trigger)

    if apply_changes:
        if "assumptions" in apply_changes:
            m.assumptions = apply_changes["assumptions"]
        if "target_date" in apply_changes and apply_changes["target_date"]:
            m.target_date = _parse_date(apply_changes["target_date"])
        m.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(m)

    return {
        "revision_number": rev.revision_number,
        "evaluation": evaluation,
        "applied": bool(apply_changes),
    }


# ── Engine orchestration (read) ───────────────────────────────────────────────


async def _context(db, farm, user, mission_id):
    m = await get_mission(db, farm, mission_id)
    facts = await _facts(db, farm, user)
    spec = _to_spec(m)
    farm_count = await _farm_count(db, farm)
    today = date.today()
    roadmap = mc.build_roadmap(spec, facts, today=today, farm_count=farm_count)
    return m, spec, facts, roadmap, farm_count, today


async def dashboard(db, farm, user, mission_id) -> mc.MissionDashboard:
    _m, spec, facts, _rm, farm_count, today = await _context(db, farm, user, mission_id)
    return mc.build_dashboard(spec, facts, today=today, farm_count=farm_count)


async def roadmap(db, farm, user, mission_id) -> mc.Roadmap:
    _m, _spec, _facts, rm, _fc, _today = await _context(db, farm, user, mission_id)
    return rm


async def business_plan(db, farm, user, mission_id) -> mc.BusinessPlan:
    _m, spec, facts, rm, _fc, today = await _context(db, farm, user, mission_id)
    return mc.build_business_plan(spec, facts, rm, today=today)


async def progress(db, farm, user, mission_id) -> mc.Progress:
    _m, spec, facts, rm, farm_count, today = await _context(db, farm, user, mission_id)
    return mc.build_progress(spec, facts, rm, today=today, farm_count=farm_count)


async def daily(db, farm, user, mission_id) -> mc.DailyMission:
    _m, spec, facts, rm, farm_count, today = await _context(db, farm, user, mission_id)
    prog = mc.build_progress(spec, facts, rm, today=today, farm_count=farm_count)
    return mc.daily_mission(spec, facts, rm, prog, today=today)


async def manual(db, farm, user, mission_id) -> mc.OperationsManual:
    _m, spec, facts, rm, _fc, today = await _context(db, farm, user, mission_id)
    return mc.build_manual(spec, facts, rm, today=today)


async def report(db, farm, user, mission_id, *, period: str) -> mc.MissionReport:
    _m, spec, facts, rm, farm_count, today = await _context(db, farm, user, mission_id)
    prog = mc.build_progress(spec, facts, rm, today=today, farm_count=farm_count)
    return mc.build_report(spec, facts, rm, prog, period=period, today=today)


async def adaptation(db, farm, user, mission_id) -> mc.RevisionProposal:
    _m, spec, facts, _rm, farm_count, today = await _context(db, farm, user, mission_id)
    return mc.evaluate_adaptation(spec, facts, today=today, farm_count=farm_count)


def discovery_questions() -> list[mc.Question]:
    return mc.discovery_questions()


# ── 8. CEO advisor ────────────────────────────────────────────────────────────


async def ceo_advice(db, farm, user, mission_id, question: str) -> dict:
    """
    A strategic answer grounded in the deterministic engines.

    The deterministic layer builds the full context — progress, adaptation,
    cash flow, and a what-if simulation when the question implies one — and
    Gemini (if enabled) only *explains the trade-offs* in that context. Offline,
    the deterministic explanation is returned verbatim. Gemini never invents a
    number and never performs a calculation.
    """
    from app.services import ai_settings_service, aria_assistant_service

    _m, spec, facts, rm, farm_count, today = await _context(db, farm, user, mission_id)
    prog = mc.build_progress(spec, facts, rm, today=today, farm_count=farm_count)
    evaluation = mc.evaluate_adaptation(spec, facts, today=today, farm_count=farm_count)
    cashflow = aria_planning.project_cashflow(facts, days=30)

    # Deterministic simulation when the question is a what-if.
    sim_line = ""
    scenario, magnitude = aria_assistant_service._parse_scenario(question)
    if any(w in question.lower() for w in ("what if", "what happens", "if i", "should i", "vipi")):
        sim = aria_planning.simulate(facts, scenario, magnitude)
        if sim.available:
            changes = "; ".join(f"{c.label}: {c.current} → {c.projected} ({c.difference})" for c in sim.changes)
            sim_line = f" Simulated ({sim.scenario}): {changes}."

    cash_line = (f"30-day cash flow is projected at {cashflow.net} KES ({cashflow.outlook})."
                 if cashflow.net is not None
                 else "30-day cash flow can't be projected yet — not enough recorded spend.")
    deterministic = (
        f"On '{spec.name}': you are {prog.completion_pct:.0f}% complete "
        f"({prog.completion_explanation}) and currently {prog.current_phase_name}. "
        f"{cash_line} "
        + ("Assumptions still hold. " if not evaluation.needed
           else "Note: " + " ".join(evaluation.reasons[:2]) + " ")
        + sim_line
    ).strip()

    settings = await ai_settings_service.get_or_create(db, farm.id)
    if ai_settings_service.effective_ai_enabled(settings) and ai_provider.gemini_available():
        prompt = (
            "You are ARIA acting as a CEO advisor for a Kenyan poultry farmer. Using ONLY the "
            "context below, explain the trade-offs and offer alternatives. Do NOT invent numbers "
            "or perform calculations — the figures are already computed. Do not diagnose disease. "
            f"Keep under 150 words.\n\nQUESTION: {question}\n\nCONTEXT: {deterministic}"
        )
        res = await ai_provider.complete(prompt, offline_answer=deterministic)
        if res.provider in ("gemini", "claude"):
            await ai_settings_service.record_usage(
                db, farm_id=farm.id, user_id=user.id, provider=res.provider, model=res.provider,
                prompt_tokens=res.prompt_tokens, completion_tokens=res.completion_tokens,
                cost_usd=res.cost_usd, call_type="ceo_advisor")
        answer, provider = res.text, res.provider
    else:
        answer, provider = deterministic, "offline"

    return {
        "question": question, "answer": ai_provider.redact_secrets(answer),
        "provider": provider, "grounded_context": deterministic,
        "fact_type": "ai_suggestion" if provider in ("gemini", "claude") else "strategic_recommendation",
        "sources": ["mission progress", "cash flow", "adaptation check"],
    }


# ── Aviculture integration (Module 15, Part 11) ───────────────────────────────


async def aviculture_briefing(db: AsyncSession, farm: Farm) -> aviculture_intelligence.Briefing:
    """
    Mission Control's strategic briefing on the aviculture collection.

    Mission Control *orchestrates* here — it does not own the business logic. It
    gathers the aviculture domain's already-computed deterministic outputs (the
    reporting dashboard, the population forecast, the automation engine's due
    items, and the active workflows) and hands them to the pure
    ``aviculture_intelligence`` engine, which identifies risks, overdue work,
    breeding and incubation problems, financial issues and population trends —
    every insight citing the recorded/calculated/forecast evidence it rests on.
    No aviculture figure is recomputed; the deterministic engines remain the
    single source of truth.
    """
    dashboard = await aviculture_reporting_service.dashboard(db, farm)
    forecast = await aviculture_reporting_service.population_forecast(db, farm)
    due_items = await aviculture_automation_service.preview(db, farm)
    workflow_rows = await aviculture_automation_service.list_workflows(db, farm.id)
    workflows = [{"status": w.status, "workflow_type": w.workflow_type} for w in workflow_rows]

    return aviculture_intelligence.build_briefing(
        dashboard=dashboard, forecast=forecast, due_items=due_items, workflows=workflows)


async def bsf_briefing(db: AsyncSession, farm: Farm) -> bsf_intelligence.Briefing:
    """Mission Control's strategic briefing on Black Soldier Fly production.

    Mission Control *orchestrates* — it owns no BSF business logic. It gathers the
    BSF domain's already-computed deterministic outputs (the executive dashboard,
    which itself composes the production/feed/environment/health/finance/
    sustainability engines plus the forecast and bottleneck engines) and the
    Growth Planner's recorded progress, and hands them to the pure
    ``bsf_intelligence`` engine. No BSF figure is recomputed; the deterministic
    engines and the Growth Planner remain the sources of truth.
    """
    dashboard = await bsf_reporting_service.executive_dashboard(db, farm.id)
    forecast = dashboard.get("forecast", {})
    bottlenecks = dashboard.get("bottlenecks", [])

    growth = None
    plan = await growth_planner_service.get_primary_plan(db, farm.id, "bsf")
    if plan is not None:
        growth = await growth_planner_service.compute_progress(db, farm.id, "bsf", plan)

    return bsf_intelligence.build_briefing(
        dashboard=dashboard, forecast=forecast, growth=growth, bottlenecks=bottlenecks)


async def rabbit_briefing(db: AsyncSession, farm: Farm) -> rabbit_intelligence.Briefing:
    """Mission Control's strategic briefing on rabbit management.

    Mission Control *orchestrates* — it owns no rabbit business logic. It gathers
    the rabbit domain's already-computed deterministic outputs (the executive
    dashboard, which itself composes the reproduction/health/finance/housing
    summaries plus the forecast and bottleneck engines) and the Growth Planner's
    recorded progress, and hands them to the pure ``rabbit_intelligence`` engine.
    No rabbit figure is recomputed; the deterministic engines and the Growth
    Planner remain the sources of truth.
    """
    dashboard = await rabbit_reporting_service.executive_dashboard(db, farm.id)
    forecast = dashboard.get("forecast", {})
    bottlenecks = dashboard.get("bottlenecks", [])

    growth = None
    plan = await growth_planner_service.get_primary_plan(db, farm.id, "rabbit")
    if plan is not None:
        growth = await growth_planner_service.compute_progress(db, farm.id, "rabbit", plan)

    return rabbit_intelligence.build_briefing(
        dashboard=dashboard, forecast=forecast, growth=growth, bottlenecks=bottlenecks)


async def small_ruminant_briefing(db: AsyncSession, farm: Farm, species: str):
    """Mission Control's strategic briefing on a goat or sheep workspace.

    Mission Control *orchestrates* — it owns no small-ruminant business logic. It
    gathers the domain's already-computed deterministic outputs (the executive
    dashboard, which composes the reproduction/health/finance/housing/dairy/wool
    summaries plus the forecast and bottleneck engines) and the Growth Planner's
    recorded progress, and hands them to the pure ``small_ruminant_intelligence``
    engine. No figure is recomputed."""
    dashboard = await small_ruminant_reporting_service.executive_dashboard(db, farm.id, species)
    forecast = dashboard.get("forecast", {})
    bottlenecks = dashboard.get("bottlenecks", [])

    growth = None
    plan = await growth_planner_service.get_primary_plan(db, farm.id, species)
    if plan is not None:
        growth = await growth_planner_service.compute_progress(db, farm.id, species, plan)

    return small_ruminant_intelligence.build_briefing(
        species=species, dashboard=dashboard, forecast=forecast, growth=growth, bottlenecks=bottlenecks)


async def swine_briefing(db: AsyncSession, farm: Farm):
    """Mission Control's strategic briefing on the swine workspace.

    Mission Control *orchestrates* — it owns no swine business logic. It gathers the
    domain's already-computed deterministic farm dashboard (which composes the
    reproduction/farrowing/feed/health/growth/finance/housing summaries) and hands it
    to the pure ``swine_intelligence`` engine. No figure is recomputed."""
    dashboard = await swine_reporting_service.farm_dashboard(db, farm.id)
    return swine_intelligence.build_briefing(dashboard=dashboard)


# ── helpers ───────────────────────────────────────────────────────────────────


def _parse_date(v):
    if v is None or isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ValidationException("Invalid date — use YYYY-MM-DD.")
