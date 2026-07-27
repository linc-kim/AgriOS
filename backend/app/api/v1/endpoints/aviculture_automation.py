"""
Greena — Aviculture Automation API (Module 15, Part 9)

Deterministic operational reminders/tasks and staged workflows. Reminders
materialise into the shared platform Reminder engine (fired by the scheduler);
notifications reuse the platform Notification engine. Workflows advance through
deterministic stage templates. Farm-scoped, permission-guarded, audited.

Prefix: /farms/{farm_id}/aviculture
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.aviculture_automation import (
    GenerateResult, OperationalItem, TaskResponse, WorkflowAdvance, WorkflowEventResponse,
    WorkflowResponse, WorkflowStart, _task_response,
)
from app.services import aviculture_automation_service as svc
from app.services import aviculture_automation_engine as engine

router = APIRouter(prefix="/farms/{farm_id}/aviculture", tags=["Aviculture — Automation"])

_MANAGE = {"farm_owner", "farm_manager", "farm_worker"}


def _workflow_response(wf) -> WorkflowResponse:
    r = WorkflowResponse.model_validate(wf)
    r.stages = engine.workflow_stages(wf.workflow_type)
    return r


# ── Deterministic reminders / tasks ───────────────────────────────────────────

@router.get("/automation/preview", response_model=SuccessResponse[list[OperationalItem]])
async def preview(farm_id: str, db: DBSession, current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access()),
                  _perm=Depends(require_permission(Permission.AVI_AUTOMATION_VIEW)),
                  horizon_days: int = Query(30, ge=1, le=365)):
    farm, _ = access
    items = await svc.preview(db, farm, horizon_days=horizon_days)
    return SuccessResponse(data=[OperationalItem.model_validate(i) for i in items])


@router.post("/automation/generate", response_model=SuccessResponse[GenerateResult])
async def generate(farm_id: str, db: DBSession, current_user: CurrentUser,
                   access: tuple = Depends(require_farm_access(_MANAGE)),
                   _perm=Depends(require_permission(Permission.AVI_AUTOMATION_MANAGE)),
                   horizon_days: int = Query(30, ge=1, le=365)):
    farm, _ = access
    return SuccessResponse(data=GenerateResult.model_validate(
        await svc.generate(db, farm, current_user, horizon_days=horizon_days)))


@router.get("/tasks", response_model=SuccessResponse[list[TaskResponse]])
async def list_tasks(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _perm=Depends(require_permission(Permission.AVI_AUTOMATION_VIEW)),
                     include_done: bool = Query(False)):
    farm, _ = access
    rows = await svc.list_tasks(db, farm.id, include_done=include_done)
    return SuccessResponse(data=[_task_response(r) for r in rows])


@router.post("/tasks/{reminder_id}/complete", response_model=SuccessResponse[TaskResponse])
async def complete_task(farm_id: str, reminder_id: UUID, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access(_MANAGE)),
                        _perm=Depends(require_permission(Permission.AVI_AUTOMATION_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=_task_response(
        await svc.complete_task(db, farm.id, reminder_id, current_user)))


# ── Workflows ─────────────────────────────────────────────────────────────────

@router.post("/workflows", response_model=SuccessResponse[WorkflowResponse], status_code=status.HTTP_201_CREATED)
async def start_workflow(farm_id: str, body: WorkflowStart, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access(_MANAGE)),
                         _perm=Depends(require_permission(Permission.AVI_AUTOMATION_MANAGE))):
    farm, _ = access
    wf = await svc.start_workflow(db, farm, workflow_type=body.workflow_type, bird_id=body.bird_id,
                                  notes=body.notes, user=current_user)
    return SuccessResponse(data=_workflow_response(wf))


@router.get("/workflows", response_model=SuccessResponse[list[WorkflowResponse]])
async def list_workflows(farm_id: str, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access()),
                         _perm=Depends(require_permission(Permission.AVI_AUTOMATION_VIEW)),
                         status_filter: str | None = Query(None, alias="status"),
                         bird_id: UUID | None = Query(None)):
    farm, _ = access
    rows = await svc.list_workflows(db, farm.id, status=status_filter, bird_id=bird_id)
    return SuccessResponse(data=[_workflow_response(w) for w in rows])


@router.post("/workflows/{workflow_id}/advance", response_model=SuccessResponse[WorkflowResponse])
async def advance_workflow(farm_id: str, workflow_id: UUID, body: WorkflowAdvance, db: DBSession, current_user: CurrentUser,
                           access: tuple = Depends(require_farm_access(_MANAGE)),
                           _perm=Depends(require_permission(Permission.AVI_AUTOMATION_MANAGE))):
    farm, _ = access
    wf = await svc.advance_workflow(db, farm.id, workflow_id, note=body.note, user=current_user)
    return SuccessResponse(data=_workflow_response(wf))


@router.get("/workflows/{workflow_id}/events", response_model=SuccessResponse[list[WorkflowEventResponse]])
async def workflow_events(farm_id: str, workflow_id: UUID, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _perm=Depends(require_permission(Permission.AVI_AUTOMATION_VIEW))):
    farm, _ = access
    rows = await svc.get_workflow_events(db, farm.id, workflow_id)
    return SuccessResponse(data=[WorkflowEventResponse.model_validate(e) for e in rows])
