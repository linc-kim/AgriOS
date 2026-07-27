"""
Greena — Mission Control endpoints (Module 14).

The strategic operating system on top of the deterministic engines. Missions are
created and edited here; the roadmap, business plan, daily mission, progress,
manual, reports and dashboard are all *computed live* from the mission plus
recorded facts, so they never go stale. The CEO advisor grounds Gemini in the
deterministic context and never lets it invent a number.

Scope is farm-first (`/farms/{farm_id}/mission`). Reads require AI_INSIGHT_VIEW;
strategic writes (create/update/replan/advisor) require AI_QUERY — the CEO's
seat, and the level that can incur model cost. Everything is deterministic where
the spec asks for it; Gemini only ever explains.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import require_farm_access
from app.exceptions import ValidationException
from app.models.auth import User
from app.schemas.base import SuccessResponse
from app.schemas.mission import (
    AdaptationOut,
    AdvisorOut,
    AdvisorRequest,
    BusinessPlanOut,
    DailyMissionOut,
    DashboardOut,
    DiscoveryQuestion,
    ManualOut,
    ManualSectionOut,
    MissionCreate,
    MissionHealthOut,
    MissionOut,
    MissionUpdate,
    MValue,
    PhaseOut,
    PlanSectionOut,
    ProgressOut,
    ReplanOut,
    ReplanRequest,
    ReportOut,
    RevisionCreate,
    RevisionOut,
    RoadmapOut,
)
from app.services import mission_control_data as mcd

router = APIRouter(prefix="/farms/{farm_id}/mission", tags=["Mission Control"])

_READ = {"farm_owner", "farm_manager", "enterprise_owner", "vet_consultant", "viewer"}
_WRITE = {"farm_owner", "farm_manager", "enterprise_owner"}


# ── Serialisers ───────────────────────────────────────────────────────────────


def _mv(v) -> MValue:
    return MValue(label=v.label, value=v.value, fact_type=v.fact_type.value,
                  detail=v.detail, unit=v.unit, available=v.available)


def _phase(p) -> PhaseOut:
    return PhaseOut(
        index=p.index, name=p.name, objectives=p.objectives, infrastructure=p.infrastructure,
        bird_target=p.bird_target, financial_target=_mv(p.financial_target),
        operational_targets=p.operational_targets,
        start_date=p.start_date.isoformat() if p.start_date else None,
        end_date=p.end_date.isoformat() if p.end_date else None,
        duration_days=p.duration_days, completion_criteria=p.completion_criteria,
        dependencies=p.dependencies, risks=p.risks, fact_type=p.fact_type.value,
    )


def _health(h) -> MissionHealthOut:
    from app.schemas.mission import HealthFactorOut
    return MissionHealthOut(
        score=h.score, grade=h.grade,
        factors=[HealthFactorOut(label=f.label, score=f.score, max_score=f.max_score,
                                 explanation=f.explanation) for f in h.factors],
    )


def _milestone(m):
    from app.schemas.mission import MilestoneOut
    return MilestoneOut(name=m.name, target=m.target, done=m.done, detail=m.detail)


def _daily(d) -> DailyMissionOut:
    return DailyMissionOut(
        on=d.on.isoformat(), headline=d.headline, phase=d.phase,
        critical_tasks=[_mv(x) for x in d.critical_tasks], risks=[_mv(x) for x in d.risks],
        opportunities=[_mv(x) for x in d.opportunities], budget=_mv(d.budget),
        purchases=[_mv(x) for x in d.purchases], records_required=[_mv(x) for x in d.records_required],
        kpis=[_mv(x) for x in d.kpis],
    )


def _mission_out(m) -> MissionOut:
    return MissionOut(
        id=str(m.id), farm_id=str(m.farm_id), name=m.name, description=m.description,
        target_date=m.target_date.isoformat() if m.target_date else None, status=m.status,
        is_primary=m.is_primary, success_metrics=m.success_metrics, constraints=m.constraints,
        priorities=m.priorities, assumptions=m.assumptions, policies=m.policies,
        baseline=m.baseline, created_at=m.created_at.isoformat(),
    )


# ── Discovery ─────────────────────────────────────────────────────────────────


@router.get("/discovery", response_model=SuccessResponse[list[DiscoveryQuestion]],
            summary="The mission discovery interview questions")
async def discovery(
    farm_id: uuid.UUID,
    access=Depends(require_farm_access(_READ)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    qs = mcd.discovery_questions()
    return SuccessResponse(data=[
        DiscoveryQuestion(key=q.key, prompt=q.prompt, kind=q.kind, unit=q.unit,
                          options=q.options, why=q.why) for q in qs
    ])


# ── Mission CRUD ──────────────────────────────────────────────────────────────


@router.get("", response_model=SuccessResponse[list[MissionOut]], summary="List missions")
async def list_missions(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    rows = await mcd.list_missions(db, farm)
    return SuccessResponse(data=[_mission_out(m) for m in rows])


@router.post("", response_model=SuccessResponse[MissionOut], summary="Create a mission")
async def create_mission(
    farm_id: uuid.UUID,
    body: MissionCreate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    data = body.model_dump()
    m = await mcd.create_mission(db, farm, current_user, data)
    return SuccessResponse(data=_mission_out(m))


@router.get("/{mission_id}", response_model=SuccessResponse[MissionOut], summary="Get a mission")
async def get_mission(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    return SuccessResponse(data=_mission_out(await mcd.get_mission(db, farm, mission_id)))


@router.put("/{mission_id}", response_model=SuccessResponse[MissionOut], summary="Update a mission")
async def update_mission(
    farm_id: uuid.UUID, mission_id: uuid.UUID, body: MissionUpdate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    m = await mcd.update_mission(db, farm, mission_id, body.model_dump(exclude_none=True))
    return SuccessResponse(data=_mission_out(m))


@router.delete("/{mission_id}", response_model=SuccessResponse[dict], summary="Archive a mission")
async def delete_mission(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    await mcd.delete_mission(db, farm, mission_id)
    return SuccessResponse(data={"deleted": True})


# ── Computed strategic views ──────────────────────────────────────────────────


@router.get("/{mission_id}/dashboard", response_model=SuccessResponse[DashboardOut],
            summary="CEO mission dashboard")
async def mission_dashboard(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    d = await mcd.dashboard(db, farm, current_user, mission_id)
    return SuccessResponse(data=DashboardOut(
        mission_name=d.mission_name, status=d.status, completion_pct=d.completion_pct,
        current_phase=d.current_phase, daily=_daily(d.daily),
        upcoming_milestones=[_milestone(m) for m in d.upcoming_milestones],
        risks=[_mv(x) for x in d.risks], cash_runway=_mv(d.cash_runway),
        budget_status=_mv(d.budget_status), population=_mv(d.population),
        revenue=_mv(d.revenue), profit=_mv(d.profit), operations_health=_mv(d.operations_health),
        health=_health(d.health), time_remaining_days=d.time_remaining_days,
    ))


@router.get("/{mission_id}/roadmap", response_model=SuccessResponse[RoadmapOut], summary="Master roadmap")
async def mission_roadmap(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    r = await mcd.roadmap(db, farm, current_user, mission_id)
    return SuccessResponse(data=RoadmapOut(
        mission_name=r.mission_name, metric_kind=r.metric_kind, baseline_value=r.baseline_value,
        target_value=r.target_value, phases=[_phase(p) for p in r.phases], method=r.method, notes=r.notes,
    ))


@router.get("/{mission_id}/phases", response_model=SuccessResponse[list[PhaseOut]], summary="Roadmap phases")
async def mission_phases(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    r = await mcd.roadmap(db, farm, current_user, mission_id)
    return SuccessResponse(data=[_phase(p) for p in r.phases])


@router.get("/{mission_id}/plan", response_model=SuccessResponse[BusinessPlanOut], summary="Living business plan")
async def mission_plan(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    p = await mcd.business_plan(db, farm, current_user, mission_id)
    return SuccessResponse(data=BusinessPlanOut(
        mission_name=p.mission_name, as_of=p.as_of.isoformat(),
        sections=[PlanSectionOut(heading=s.heading, body=[_mv(v) for v in s.body],
                                 fact_type=s.fact_type.value) for s in p.sections],
        notes=p.notes,
    ))


@router.get("/{mission_id}/progress", response_model=SuccessResponse[ProgressOut], summary="Progress tracker")
async def mission_progress(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    p = await mcd.progress(db, farm, current_user, mission_id)
    return SuccessResponse(data=ProgressOut(
        completion_pct=p.completion_pct, completion_explanation=p.completion_explanation,
        current_phase_name=p.current_phase_name, current_phase_index=p.current_phase_index,
        milestones=[_milestone(m) for m in p.milestones], financial=_mv(p.financial),
        population=_mv(p.population), infrastructure=_mv(p.infrastructure), profit=_mv(p.profit),
        cash_reserve=_mv(p.cash_reserve), time_remaining_days=p.time_remaining_days,
        time_elapsed_pct=p.time_elapsed_pct, forecasted_completion=_mv(p.forecasted_completion),
        on_track=p.on_track, metrics=[_mv(x) for x in p.metrics],
    ))


@router.get("/{mission_id}/daily", response_model=SuccessResponse[DailyMissionOut], summary="Today's mission")
async def mission_daily(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    return SuccessResponse(data=_daily(await mcd.daily(db, farm, current_user, mission_id)))


@router.get("/{mission_id}/manual", response_model=SuccessResponse[ManualOut], summary="Living operations manual")
async def mission_manual(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    man = await mcd.manual(db, farm, current_user, mission_id)
    return SuccessResponse(data=ManualOut(
        mission_name=man.mission_name, as_of=man.as_of.isoformat(),
        sections=[ManualSectionOut(heading=s.heading, items=s.items) for s in man.sections],
    ))


@router.get("/{mission_id}/reports", response_model=SuccessResponse[ReportOut], summary="CEO report")
async def mission_report(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    period: str = Query("weekly", pattern="^(weekly|monthly|quarterly|annual)$"),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    r = await mcd.report(db, farm, current_user, mission_id, period=period)
    return SuccessResponse(data=ReportOut(
        period=r.period, label=r.label, as_of=r.as_of.isoformat(), mission_name=r.mission_name,
        health=_health(r.health), progress_vs_plan=[_mv(v) for v in r.progress_vs_plan],
        budget_vs_plan=[_mv(v) for v in r.budget_vs_plan], growth_vs_plan=[_mv(v) for v in r.growth_vs_plan],
        upcoming_decisions=r.upcoming_decisions, recommended_actions=r.recommended_actions, notes=r.notes,
    ))


@router.get("/{mission_id}/adaptation", response_model=SuccessResponse[AdaptationOut], summary="Adaptive check")
async def mission_adaptation(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    current_user: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    a = await mcd.adaptation(db, farm, current_user, mission_id)
    return SuccessResponse(data=AdaptationOut(
        needed=a.needed, trigger=a.trigger, reasons=a.reasons,
        recommendations=a.recommendations, detail=[_mv(v) for v in a.detail],
    ))


# ── Revisions & replan (Part 7) ───────────────────────────────────────────────


@router.get("/{mission_id}/revisions", response_model=SuccessResponse[list[RevisionOut]],
            summary="Plan revision history")
async def list_revisions(
    farm_id: uuid.UUID, mission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_READ)),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _m = access
    rows = await mcd.list_revisions(db, farm, mission_id)
    return SuccessResponse(data=[
        RevisionOut(id=str(r.id), revision_number=r.revision_number, reason=r.reason,
                    trigger=r.trigger, snapshot=r.snapshot, created_at=r.created_at.isoformat())
        for r in rows
    ])


@router.post("/{mission_id}/revisions", response_model=SuccessResponse[RevisionOut],
             summary="Snapshot a new plan revision (never overwrites the original)")
async def create_revision(
    farm_id: uuid.UUID, mission_id: uuid.UUID, body: RevisionCreate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    r = await mcd.create_revision(db, farm, current_user, mission_id, reason=body.reason)
    return SuccessResponse(data=RevisionOut(
        id=str(r.id), revision_number=r.revision_number, reason=r.reason, trigger=r.trigger,
        snapshot=r.snapshot, created_at=r.created_at.isoformat(),
    ))


@router.post("/{mission_id}/replan", response_model=SuccessResponse[ReplanOut],
             summary="Evaluate and optionally apply a replan")
async def replan(
    farm_id: uuid.UUID, mission_id: uuid.UUID, body: ReplanRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    changes = body.model_dump(exclude_none=True)
    if changes.get("assumptions"):
        changes["assumptions"] = [a for a in changes["assumptions"]]
    result = await mcd.replan(db, farm, current_user, mission_id, apply_changes=changes or None)
    ev = result["evaluation"]
    return SuccessResponse(data=ReplanOut(
        revision_number=result["revision_number"], applied=result["applied"],
        evaluation=AdaptationOut(needed=ev.needed, trigger=ev.trigger, reasons=ev.reasons,
                                 recommendations=ev.recommendations, detail=[_mv(v) for v in ev.detail]),
    ))


# ── 8. CEO advisor ────────────────────────────────────────────────────────────


@router.post("/{mission_id}/advisor", response_model=SuccessResponse[AdvisorOut],
             summary="Ask the CEO advisor (Gemini grounded in deterministic context)")
async def advisor(
    farm_id: uuid.UUID, mission_id: uuid.UUID, body: AdvisorRequest,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access(_WRITE)),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _m = access
    if not body.question.strip():
        raise ValidationException("Ask a question.")
    result = await mcd.ceo_advice(db, farm, current_user, mission_id, body.question)
    return SuccessResponse(data=AdvisorOut(**result))
