"""
Greena — Operations Planner API (Platform Module 5).

The permission-guarded surface over the cross-module Operations Planner services.
Farm-scoped (org isolation via ``require_farm_access``); every route enforces
authentication + RBAC + farm ownership, and mutations are audit-logged in the
services. ``module`` is a query/body field (routines carry their own enterprise),
so one workspace serves every Greena module.

Route map (prefix /farms/{farm_id}/operations):
  Manual        GET/PATCH /manual · POST /manual/rebuild · GET /manual/revisions
  Routines      GET/POST /routines · GET/PATCH /routines/{id} ·
                POST /routines/{id}/{activate|deactivate|archive|duplicate} ·
                GET /routines/{id}/versions · POST /routines/{id}/versions/{n}/approve
  SOPs          GET/POST /sops · PATCH /sops/{id} · POST /sops/{id}/approve
  Checklists    GET/POST /checklists · GET /checklists/{id}
  Shifts        GET/POST /shifts
  Templates     GET /templates · POST /templates/apply · POST /templates/{id}/clone
  Scheduling    GET /schedule · POST /schedule/materialize · GET /calendar
  Assignments   GET/POST /assignments · POST /assignments/{id}/reassign
  Completions   GET/POST /completions
  Exceptions    GET/POST /exceptions · POST /exceptions/{id}/resolve
  Analytics     GET /analytics/{performance|compliance|efficiency|capacity|optimization}
  Recommends    GET /recommendations · POST /recommendations/generate · /{id}/decide
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas import ops_planner as sc
from app.schemas.base import SuccessResponse
from app.services import ops_optimization_service as opt
from app.services import ops_scheduler_service as sched
from app.services import ops_service as svc

router = APIRouter(prefix="/farms/{farm_id}/operations", tags=["Operations Planner"])

P = Permission


def _routine_detail(detail: dict) -> sc.RoutineDetailResponse:
    return sc.RoutineDetailResponse(
        **sc.RoutineResponse.model_validate(detail["routine"]).model_dump(),
        schedule=sc.ScheduleResponse.model_validate(detail["schedule"]) if detail["schedule"] else None,
        task_templates=[sc.TaskTemplateResponse.model_validate(t) for t in detail["task_templates"]],
    )


# ── Operations Manual ─────────────────────────────────────────────────────────

@router.get("/manual", response_model=SuccessResponse[sc.ManualResponse])
async def get_manual(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_VIEW)),
):
    manual = await svc.get_or_create_manual(db, farm_id, current_user)
    return SuccessResponse(data=sc.ManualResponse.model_validate(manual))


@router.patch("/manual", response_model=SuccessResponse[sc.ManualResponse])
async def update_manual(
    farm_id: UUID, body: sc.ManualUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_EDIT)),
):
    manual = await svc.update_manual(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.ManualResponse.model_validate(manual))


@router.post("/manual/rebuild", response_model=SuccessResponse[sc.ManualResponse])
async def rebuild_manual(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_EDIT)),
):
    manual = await svc.rebuild_manual(db, farm_id, current_user)
    return SuccessResponse(data=sc.ManualResponse.model_validate(manual))


@router.get("/manual/revisions", response_model=SuccessResponse[list[sc.ManualRevisionResponse]])
async def list_manual_revisions(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_VIEW)),
):
    rows = await svc.list_manual_revisions(db, farm_id)
    return SuccessResponse(data=[sc.ManualRevisionResponse.model_validate(r) for r in rows])


# ── Routines ──────────────────────────────────────────────────────────────────

@router.get("/routines", response_model=SuccessResponse[list[sc.RoutineResponse]])
async def list_routines(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    module: str | None = Query(None), category: str | None = Query(None),
    status_: str | None = Query(None, alias="status"), frequency: str | None = Query(None),
):
    rows = await svc.list_routines(db, farm_id, module, category, status_, frequency)
    return SuccessResponse(data=[sc.RoutineResponse.model_validate(r) for r in rows])


@router.post("/routines", response_model=SuccessResponse[sc.RoutineResponse],
             status_code=status.HTTP_201_CREATED)
async def create_routine(
    farm_id: UUID, body: sc.RoutineCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.create_routine(db, farm_id, body.module, body, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.get("/routines/{routine_id}", response_model=SuccessResponse[sc.RoutineDetailResponse])
async def get_routine(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
):
    detail = await svc.get_routine_detail(db, farm_id, routine_id)
    return SuccessResponse(data=_routine_detail(detail))


@router.patch("/routines/{routine_id}", response_model=SuccessResponse[sc.RoutineDetailResponse])
async def update_routine(
    farm_id: UUID, routine_id: UUID, body: sc.RoutineUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    await svc.update_routine(db, farm_id, routine_id, body, current_user)
    return SuccessResponse(data=_routine_detail(await svc.get_routine_detail(db, farm_id, routine_id)))


@router.post("/routines/{routine_id}/activate", response_model=SuccessResponse[sc.RoutineResponse])
async def activate_routine(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.set_routine_active(db, farm_id, routine_id, True, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.post("/routines/{routine_id}/deactivate", response_model=SuccessResponse[sc.RoutineResponse])
async def deactivate_routine(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.set_routine_active(db, farm_id, routine_id, False, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.post("/routines/{routine_id}/archive", response_model=SuccessResponse[sc.RoutineResponse])
async def archive_routine(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.archive_routine(db, farm_id, routine_id, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.post("/routines/{routine_id}/duplicate", response_model=SuccessResponse[sc.RoutineResponse],
             status_code=status.HTTP_201_CREATED)
async def duplicate_routine(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.duplicate_routine(db, farm_id, routine_id, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.get("/routines/{routine_id}/versions",
            response_model=SuccessResponse[list[sc.RoutineVersionResponse]])
async def list_routine_versions(
    farm_id: UUID, routine_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
):
    rows = await svc.list_routine_versions(db, farm_id, routine_id)
    return SuccessResponse(data=[sc.RoutineVersionResponse.model_validate(r) for r in rows])


@router.post("/routines/{routine_id}/versions/{version_number}/approve",
             response_model=SuccessResponse[sc.RoutineVersionResponse])
async def approve_routine_version(
    farm_id: UUID, routine_id: UUID, version_number: int, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_APPROVE)),
):
    version = await svc.approve_routine_version(db, farm_id, routine_id, version_number, current_user)
    return SuccessResponse(data=sc.RoutineVersionResponse.model_validate(version))


# ── SOPs ──────────────────────────────────────────────────────────────────────

@router.get("/sops", response_model=SuccessResponse[list[sc.SOPResponse]])
async def list_sops(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_VIEW)),
    module: str | None = Query(None),
):
    rows = await svc.list_sops(db, farm_id, module)
    return SuccessResponse(data=[sc.SOPResponse.model_validate(r) for r in rows])


@router.post("/sops", response_model=SuccessResponse[sc.SOPResponse], status_code=status.HTTP_201_CREATED)
async def create_sop(
    farm_id: UUID, body: sc.SOPInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_EDIT)),
):
    sop = await svc.create_sop(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.SOPResponse.model_validate(sop))


@router.patch("/sops/{sop_id}", response_model=SuccessResponse[sc.SOPResponse])
async def update_sop(
    farm_id: UUID, sop_id: UUID, body: sc.SOPInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_EDIT)),
):
    sop = await svc.update_sop(db, farm_id, sop_id, body, current_user)
    return SuccessResponse(data=sc.SOPResponse.model_validate(sop))


@router.post("/sops/{sop_id}/approve", response_model=SuccessResponse[sc.SOPResponse])
async def approve_sop(
    farm_id: UUID, sop_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_MANUAL_APPROVE)),
):
    sop = await svc.approve_sop(db, farm_id, sop_id, current_user)
    return SuccessResponse(data=sc.SOPResponse.model_validate(sop))


# ── Checklists ────────────────────────────────────────────────────────────────

@router.get("/checklists", response_model=SuccessResponse[list[sc.ChecklistResponse]])
async def list_checklists(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_VIEW)),
    routine_id: UUID | None = Query(None),
):
    rows = await svc.list_checklists(db, farm_id, routine_id)
    return SuccessResponse(data=[sc.ChecklistResponse.model_validate(r) for r in rows])


@router.post("/checklists", response_model=SuccessResponse[sc.ChecklistResponse],
             status_code=status.HTTP_201_CREATED)
async def create_checklist(
    farm_id: UUID, body: sc.ChecklistInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_EDIT)),
):
    checklist = await svc.create_checklist(db, farm_id, body, current_user)
    detail = await svc.get_checklist_detail(db, farm_id, checklist.id)
    return SuccessResponse(data=sc.ChecklistResponse(
        **sc.ChecklistResponse.model_validate(detail["checklist"]).model_dump(exclude={"items"}),
        items=[sc.ChecklistItemResponse.model_validate(i) for i in detail["items"]]))


@router.get("/checklists/{checklist_id}", response_model=SuccessResponse[sc.ChecklistResponse])
async def get_checklist(
    farm_id: UUID, checklist_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SOP_VIEW)),
):
    detail = await svc.get_checklist_detail(db, farm_id, checklist_id)
    return SuccessResponse(data=sc.ChecklistResponse(
        **sc.ChecklistResponse.model_validate(detail["checklist"]).model_dump(exclude={"items"}),
        items=[sc.ChecklistItemResponse.model_validate(i) for i in detail["items"]]))


# ── Shifts ────────────────────────────────────────────────────────────────────

@router.get("/shifts", response_model=SuccessResponse[list[sc.ShiftResponse]])
async def list_shifts(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
):
    rows = await svc.list_shifts(db, farm_id)
    return SuccessResponse(data=[sc.ShiftResponse.model_validate(r) for r in rows])


@router.post("/shifts", response_model=SuccessResponse[sc.ShiftResponse], status_code=status.HTTP_201_CREATED)
async def create_shift(
    farm_id: UUID, body: sc.ShiftInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ASSIGN_MANAGE)),
):
    shift = await svc.create_shift(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.ShiftResponse.model_validate(shift))


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=SuccessResponse[list[sc.TemplateResponse]])
async def list_templates(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    module: str | None = Query(None),
):
    rows = await svc.list_templates(db, farm_id, module)
    return SuccessResponse(data=[sc.TemplateResponse.model_validate(r) for r in rows])


@router.post("/templates/apply", response_model=SuccessResponse[sc.RoutineResponse],
             status_code=status.HTTP_201_CREATED)
async def apply_template(
    farm_id: UUID, body: sc.ApplyTemplateInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    routine = await svc.apply_template(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.RoutineResponse.model_validate(routine))


@router.post("/templates/{template_id}/clone", response_model=SuccessResponse[sc.TemplateResponse],
             status_code=status.HTTP_201_CREATED)
async def clone_template(
    farm_id: UUID, template_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    tpl = await svc.clone_template(db, farm_id, template_id, current_user)
    return SuccessResponse(data=sc.TemplateResponse.model_validate(tpl))


# ── Scheduling & calendar ─────────────────────────────────────────────────────

@router.get("/schedule", response_model=SuccessResponse[dict])
async def build_schedule(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    start: date = Query(...), end: date = Query(...),
    module: str | None = Query(None), daily_minutes: int = Query(480, ge=1),
):
    data = await sched.build_schedule(db, farm_id, module, start, end, daily_minutes)
    return SuccessResponse(data=data)


@router.post("/schedule/materialize", response_model=SuccessResponse[dict])
async def materialize_schedule(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_SCHEDULE_MANAGE)),
    start: date = Query(...), end: date = Query(...), module: str | None = Query(None),
):
    data = await sched.materialize_tasks(db, farm_id, module, start, end, current_user)
    return SuccessResponse(data=data)


@router.get("/calendar", response_model=SuccessResponse[dict])
async def calendar(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    start: date = Query(...), end: date = Query(...), module: str | None = Query(None),
):
    data = await sched.calendar(db, farm_id, module, start, end)
    return SuccessResponse(data=data)


# ── Assignments ───────────────────────────────────────────────────────────────

@router.get("/assignments", response_model=SuccessResponse[list[sc.AssignmentResponse]])
async def list_assignments(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    routine_id: UUID | None = Query(None),
):
    rows = await sched.list_assignments(db, farm_id, routine_id)
    return SuccessResponse(data=[sc.AssignmentResponse.model_validate(r) for r in rows])


@router.post("/assignments", response_model=SuccessResponse[sc.AssignmentResponse],
             status_code=status.HTTP_201_CREATED)
async def create_assignment(
    farm_id: UUID, body: sc.AssignmentInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ASSIGN_MANAGE)),
):
    assignment = await sched.create_assignment(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.AssignmentResponse.model_validate(assignment))


@router.post("/assignments/{assignment_id}/reassign",
             response_model=SuccessResponse[sc.AssignmentResponse])
async def reassign_assignment(
    farm_id: UUID, assignment_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ASSIGN_MANAGE)),
    worker_id: UUID | None = Query(None),
):
    assignment = await sched.reassign(db, farm_id, assignment_id, worker_id, current_user)
    return SuccessResponse(data=sc.AssignmentResponse.model_validate(assignment))


# ── Completions ───────────────────────────────────────────────────────────────

@router.get("/completions", response_model=SuccessResponse[list[sc.CompletionResponse]])
async def list_completions(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    routine_id: UUID | None = Query(None), since: date | None = Query(None),
):
    rows = await sched.list_completions(db, farm_id, routine_id, since)
    return SuccessResponse(data=[sc.CompletionResponse.model_validate(r) for r in rows])


@router.post("/completions", response_model=SuccessResponse[sc.CompletionResponse],
             status_code=status.HTTP_201_CREATED)
async def record_completion(
    farm_id: UUID, body: sc.CompletionInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ASSIGN_MANAGE)),
):
    completion = await sched.record_completion(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.CompletionResponse.model_validate(completion))


# ── Exceptions ────────────────────────────────────────────────────────────────

@router.get("/exceptions", response_model=SuccessResponse[list[sc.ExceptionResponse]])
async def list_exceptions(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_VIEW)),
    status_: str | None = Query(None, alias="status"),
):
    rows = await svc.list_exceptions(db, farm_id, status_)
    return SuccessResponse(data=[sc.ExceptionResponse.model_validate(r) for r in rows])


@router.post("/exceptions", response_model=SuccessResponse[sc.ExceptionResponse],
             status_code=status.HTTP_201_CREATED)
async def create_exception(
    farm_id: UUID, body: sc.ExceptionInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    exc = await svc.create_exception(db, farm_id, body, current_user)
    return SuccessResponse(data=sc.ExceptionResponse.model_validate(exc))


@router.post("/exceptions/{exception_id}/resolve", response_model=SuccessResponse[sc.ExceptionResponse])
async def resolve_exception(
    farm_id: UUID, exception_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
    resolution: str | None = Query(None),
):
    exc = await svc.resolve_exception(db, farm_id, exception_id, resolution, current_user)
    return SuccessResponse(data=sc.ExceptionResponse.model_validate(exc))


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics/performance", response_model=SuccessResponse[dict])
async def analytics_performance(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
    module: str | None = Query(None), since: date | None = Query(None),
):
    return SuccessResponse(data=await opt.performance(db, farm_id, module, since=since))


@router.get("/analytics/compliance", response_model=SuccessResponse[dict])
async def analytics_compliance(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
):
    return SuccessResponse(data=await opt.compliance_report(db, farm_id))


@router.get("/analytics/efficiency", response_model=SuccessResponse[dict])
async def analytics_efficiency(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
):
    return SuccessResponse(data=await opt.efficiency(db, farm_id))


@router.get("/analytics/capacity", response_model=SuccessResponse[dict])
async def analytics_capacity(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
    module: str | None = Query(None), growth_factor: float | None = Query(None, gt=0),
):
    return SuccessResponse(data=await opt.capacity_report(db, farm_id, module, growth_factor))


@router.get("/analytics/optimization", response_model=SuccessResponse[dict])
async def analytics_optimization(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
    module: str | None = Query(None), since: date | None = Query(None),
):
    return SuccessResponse(data=await opt.analyze(db, farm_id, module, since=since))


# ── Improvement recommendations ───────────────────────────────────────────────

@router.get("/recommendations", response_model=SuccessResponse[list[sc.RecommendationResponse]])
async def list_recommendations(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ANALYTICS_VIEW)),
    module: str | None = Query(None), status_: str | None = Query(None, alias="status"),
):
    rows = await opt.list_recommendations(db, farm_id, module, status_)
    return SuccessResponse(data=[sc.RecommendationResponse.model_validate(r) for r in rows])


@router.post("/recommendations/generate",
             response_model=SuccessResponse[list[sc.RecommendationResponse]])
async def generate_recommendations(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
    module: str | None = Query(None), since: date | None = Query(None),
):
    rows = await opt.generate_recommendations(db, farm_id, module, current_user, since=since)
    return SuccessResponse(data=[sc.RecommendationResponse.model_validate(r) for r in rows])


@router.post("/recommendations/{recommendation_id}/decide",
             response_model=SuccessResponse[sc.RecommendationResponse])
async def decide_recommendation(
    farm_id: UUID, recommendation_id: UUID, body: sc.RecommendationDecision,
    db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _p=Depends(require_permission(P.OPSPLAN_ROUTINE_EDIT)),
):
    rec = await opt.decide_recommendation(db, farm_id, recommendation_id, body.approval_status, current_user)
    return SuccessResponse(data=sc.RecommendationResponse.model_validate(rec))
