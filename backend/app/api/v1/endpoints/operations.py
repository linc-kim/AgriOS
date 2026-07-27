"""
Greena — Operations Director endpoints (Module 13 Part 7).

ARIA supervising an entire organization: aggregated organization facts,
cross-farm comparison, a unified operations dashboard, the merged timeline,
performance analytics, organization reports, and task assignment across farms.

Everything is deterministic — the endpoints wire real, permission-scoped
organization data through the pure `aria_operations` engine. No AI provider is
reachable from any of them, exactly as required.

Scope is org-first: routes live under `/organizations/{organization_id}/operations`.
Access is resolved once per request in `_access`, which enforces two boundaries —
a user who is not a member of the organization gets a 403 before any data is
read, and each tier only ever sees the sections and farms its role allows. That
is what makes "no permission leaks" and "no supervisor reaches another
organization" structural rather than hopeful.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth import User
from app.schemas.base import SuccessResponse
from app.schemas.operations import (
    OpsAggregate,
    OpsAlert,
    OpsAnalytics,
    OpsComparison,
    OpsDashboard,
    OpsFarmRank,
    OpsFarmSummary,
    OpsMetric,
    OpsNotification,
    OpsOrganizationFacts,
    OpsOrgPriority,
    OpsRanking,
    OpsReport,
    OpsReportSection,
    OpsTask,
    OpsTaskAssign,
    OpsTaskHistoryEvent,
    OpsTimelineEvent,
    OpsWorker,
    OpsWorkerPerformance,
)
from app.services import aria_operations_data as opsdata
from app.services.aria_operations import DashboardFilter
from app.services.aria_supervisor import MonitorState

router = APIRouter(prefix="/organizations/{organization_id}/operations", tags=["Operations"])


# ── Access dependency ─────────────────────────────────────────────────────────


async def _access(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> tuple[opsdata.OrgAccess, User]:
    """Resolve and enforce the user's access to this organization."""
    access = await opsdata.resolve_access(db, organization_id, current_user)
    return access, current_user


def _require_section(access: opsdata.OrgAccess, section: str) -> None:
    if section not in access.scope.sections:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "OPERATIONS_SECTION_FORBIDDEN",
                "message": f"Your role ({access.scope.tier}) cannot access '{section}'.",
            },
        )


def _severity(value: str | None) -> MonitorState | None:
    if not value:
        return None
    try:
        return MonitorState(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BAD_SEVERITY", "message": "severity must be watch|warning|critical."},
        )


# ── Serialisers ───────────────────────────────────────────────────────────────


def _agg(a) -> OpsAggregate:
    return OpsAggregate(
        key=a.key, label=a.label, value=a.value, unit=a.unit, available=a.available,
        source_farms=a.source_farms, missing_farms=a.missing_farms, method=a.method,
    )


def _priority(p) -> OpsOrgPriority:
    return OpsOrgPriority(
        rank=p.rank, label=p.label, why=p.why, farm_id=p.farm_id,
        farm_name=p.farm_name, severity=p.severity.value, source=p.source,
    )


def _org_facts(o) -> OpsOrganizationFacts:
    return OpsOrganizationFacts(
        organization_name=o.organization_name, as_of=o.as_of.isoformat(),
        farm_count=o.farm_count, farm_names=o.farm_names, overall=o.overall.value,
        health=_agg(o.health), production=_agg(o.production), mortality=_agg(o.mortality),
        feed_usage=_agg(o.feed_usage), water_usage=_agg(o.water_usage),
        inventory=_agg(o.inventory), financial=_agg(o.financial),
        priorities=[_priority(p) for p in o.priorities], silent_farms=o.silent_farms,
    )


def _rank(fr) -> OpsFarmRank:
    return OpsFarmRank(farm_id=fr.farm_id, farm_name=fr.farm_name, value=fr.value,
                       display=fr.display, available=fr.available)


def _ranking(r) -> OpsRanking:
    return OpsRanking(
        key=r.key, label=r.label, unit=r.unit, higher_is_better=r.higher_is_better,
        ranked=[_rank(x) for x in r.ranked], missing=[_rank(x) for x in r.missing],
        best=_rank(r.best) if r.best else None,
        needs_attention=_rank(r.needs_attention) if r.needs_attention else None,
        average=r.average, method=r.method,
    )


def _worker(w) -> OpsWorker:
    return OpsWorker(user_id=w.user_id, name=w.name, role=w.role.value,
                     role_label=w.role_label, farm_ids=w.farm_ids, farm_names=w.farm_names)


def _task(t) -> OpsTask:
    return OpsTask(
        task_id=t.task_id, farm_id=t.farm_id, farm_name=t.farm_name, title=t.title,
        status=t.status.value, priority=t.priority, owner_id=t.owner_id,
        owner_name=t.owner_name,
        due_at=t.due_at.isoformat() if t.due_at else None,
        created_at=t.created_at.isoformat() if t.created_at else None,
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
        history=[OpsTaskHistoryEvent(**h) for h in t.history],
    )


def _timeline_event(e) -> OpsTimelineEvent:
    return OpsTimelineEvent(
        at=e.at.isoformat(), farm_id=e.farm_id, farm_name=e.farm_name, kind=e.kind,
        title=e.title, detail=e.detail, worker=e.worker, severity=e.severity.value,
    )


def _metric(m) -> OpsMetric:
    return OpsMetric(key=m.key, label=m.label, value=m.value, unit=m.unit,
                     available=m.available, method=m.method, detail=m.detail)


# ── 1. Organization intelligence ──────────────────────────────────────────────


@router.get("/organization", response_model=SuccessResponse[OpsOrganizationFacts],
            summary="Aggregated organization facts")
async def organization_facts(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "organization")
    o = await opsdata.organization_overview(db, access, user)
    return SuccessResponse(data=_org_facts(o))


# ── 2. Cross-farm comparison ──────────────────────────────────────────────────


@router.get("/farms", response_model=SuccessResponse[OpsComparison],
            summary="Cross-farm comparison (ranked, missing data shown)")
async def compare_farms(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "comparison")
    c = await opsdata.cross_farm(db, access, user)
    return SuccessResponse(data=OpsComparison(
        farm_count=c.farm_count, rankings=[_ranking(r) for r in c.rankings],
    ))


# ── 3. Workers ────────────────────────────────────────────────────────────────


@router.get("/workers", response_model=SuccessResponse[list[OpsWorker]],
            summary="Organization team across farms")
async def list_workers(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, _user = access_user
    _require_section(access, "workers")
    workers = await opsdata.list_workers(db, access)
    return SuccessResponse(data=[_worker(w) for w in workers])


# ── 4. Tasks ──────────────────────────────────────────────────────────────────


@router.get("/tasks", response_model=SuccessResponse[list[OpsTask]],
            summary="Assignable tasks across the organization")
async def list_tasks(
    organization_id: uuid.UUID,
    farm_id: str | None = Query(None),
    worker_id: str | None = Query(None),
    include_done: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "tasks")
    tasks = await opsdata.list_tasks(
        db, access, user, farm_id=farm_id, worker_id=worker_id, include_done=include_done,
    )
    return SuccessResponse(data=[_task(t) for t in tasks])


@router.post("/tasks/{task_id}/assign", response_model=SuccessResponse[OpsTask],
             summary="Assign or reassign a task to a worker")
async def assign_task(
    organization_id: uuid.UUID,
    task_id: uuid.UUID,
    body: OpsTaskAssign,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "tasks")
    rem = await opsdata.assign_task(db, access, task_id, body.owner_id, user)
    # Re-read as a TaskView for a consistent response shape.
    tasks = await opsdata.gather_tasks(db, {str(rem.farm_id): ""})
    view = next(t for t in tasks if t.task_id == str(rem.id))
    return SuccessResponse(data=_task(view))


@router.post("/tasks/{task_id}/complete", response_model=SuccessResponse[OpsTask],
             summary="Mark a task complete")
async def complete_task(
    organization_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "tasks")
    rem = await opsdata.complete_task(db, access, task_id, user)
    tasks = await opsdata.gather_tasks(db, {str(rem.farm_id): ""})
    view = next(t for t in tasks if t.task_id == str(rem.id))
    return SuccessResponse(data=_task(view))


# ── 5. Operations dashboard ───────────────────────────────────────────────────


@router.get("/dashboard", response_model=SuccessResponse[OpsDashboard],
            summary="Unified operations dashboard")
async def dashboard(
    organization_id: uuid.UUID,
    farm_id: str | None = Query(None),
    worker_id: str | None = Query(None),
    severity: str | None = Query(None, description="watch|warning|critical"),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "dashboard")
    flt = DashboardFilter(
        farm_id=farm_id, worker_id=worker_id, severity=_severity(severity),
        since=since, until=until,
    )
    d = await opsdata.operations_dashboard(db, access, user, flt=flt)
    return SuccessResponse(data=OpsDashboard(
        as_of=d.as_of.isoformat(),
        tier=access.scope.tier,
        sections=sorted(access.scope.sections),
        organization=_org_facts(d.organization),
        farms=[OpsFarmSummary(
            farm_id=f.farm_id, farm_name=f.farm_name, overall=f.overall.value,
            health_score=f.health_score, open_tasks=f.open_tasks,
            overdue_tasks=f.overdue_tasks, alert_count=f.alert_count, silent=f.silent,
        ) for f in d.farms],
        alerts=[OpsAlert(at=a.at.isoformat(), farm_id=a.farm_id, farm_name=a.farm_name,
                         kind=a.kind, title=a.title, detail=a.detail, severity=a.severity.value)
                for a in d.alerts],
        priorities=[_priority(p) for p in d.priorities],
        tasks=[_task(t) for t in d.tasks],
        workers=[_worker(w) for w in d.workers],
        notifications=[OpsNotification(at=n.at.isoformat(), farm_id=n.farm_id,
                                       farm_name=n.farm_name, title=n.title, body=n.body,
                                       severity=n.severity)
                       for n in d.notifications],
        operational_status=d.operational_status,
    ))


# ── 6. Organization timeline ──────────────────────────────────────────────────


@router.get("/timeline", response_model=SuccessResponse[list[OpsTimelineEvent]],
            summary="Merged, worker-attributed organization timeline")
async def timeline(
    organization_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=300),
    farm_id: str | None = Query(None),
    worker: str | None = Query(None),
    severity: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "timeline")
    events = await opsdata.organization_timeline(
        db, access, user, days=days, limit=limit, farm_id=farm_id,
        worker=worker, severity=_severity(severity),
    )
    return SuccessResponse(data=[_timeline_event(e) for e in events])


# ── 7. Performance analytics ──────────────────────────────────────────────────


@router.get("/analytics", response_model=SuccessResponse[OpsAnalytics],
            summary="Deterministic performance analytics")
async def analytics(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "analytics")
    a = await opsdata.analytics(db, access, user)
    return SuccessResponse(data=OpsAnalytics(
        workers=[OpsWorkerPerformance(
            user_id=w.user_id, name=w.name, assigned=w.assigned, completed=w.completed,
            overdue=w.overdue, completion_rate=w.completion_rate,
            avg_completion_hours=w.avg_completion_hours, method=w.method,
        ) for w in a.workers],
        farm_productivity=[_metric(m) for m in a.farm_productivity],
        org_metrics=[_metric(m) for m in a.org_metrics],
        trends=[_metric(m) for m in a.trends],
    ))


# ── 9. Organization reports ───────────────────────────────────────────────────


@router.get("/reports", response_model=SuccessResponse[OpsReport],
            summary="Export-ready organization report")
async def reports(
    organization_id: uuid.UUID,
    period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
    access_user: tuple = Depends(_access),
):
    access, user = access_user
    _require_section(access, "reports")
    r = await opsdata.organization_report(db, access, user, period=period)
    return SuccessResponse(data=OpsReport(
        period=r.period, label=r.label, as_of=r.as_of.isoformat(),
        organization_name=r.organization_name, farm_count=r.farm_count,
        sections=[OpsReportSection(label=s.label, value=s.value, available=s.available,
                                   method=s.method) for s in r.sections],
        risks=r.risks, priorities=r.priorities, notes=r.notes,
    ))
