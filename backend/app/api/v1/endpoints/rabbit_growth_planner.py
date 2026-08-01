"""
Greena — Rabbit Growth Planner API (Module 17, Milestone 8)

Rabbit's permission-guarded surface over the **platform** Growth Planner
(`growth_planner_service`, module='rabbit'). The planner is cross-module; this
module only supplies the rabbit metric provider (imported here so it registers)
and the `RABBIT_GROWTH_VIEW` / `RABBIT_GROWTH_EDIT` guards. No module planner.

Route map (prefix /farms/{farm_id}/rabbit/growth):
  GET/POST  /plans                                    list / create plans
  GET       /plans/{plan_id}                          detail + progress (planned vs actual)
  PATCH     /plans/{plan_id}                           revise plan (writes a version)
  POST      /plans/{plan_id}/archive                   archive plan
  PATCH     /plans/{plan_id}/milestones/{milestone_id} update milestone status
  GET       /plans/{plan_id}/revisions                 version history
  GET       /plans/{plan_id}/compare                   diff two revisions
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.growth import (
    GoalResponse,
    MilestoneResponse,
    MilestoneStatusUpdate,
    PlanCreate,
    PlanDetailResponse,
    PlanResponse,
    PlanUpdate,
    RevisionResponse,
)
from app.services import rabbit_growth_provider  # noqa: F401 — imported to register the provider
from app.services import growth_planner_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit/growth", tags=["Rabbit Growth Planner"])

_MODULE = "rabbit"
_MANAGER_ROLES = {"farm_owner", "farm_manager", "enterprise_owner"}


def _detail(detail: dict) -> PlanDetailResponse:
    return PlanDetailResponse(
        **PlanResponse.model_validate(detail["plan"]).model_dump(),
        goals=[GoalResponse.model_validate(g) for g in detail["goals"]],
        milestones=[MilestoneResponse.model_validate(mi) for mi in detail["milestones"]],
        progress=detail["progress"],
    )


@router.get("/plans", response_model=SuccessResponse[list[PlanResponse]])
async def list_plans(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_VIEW)),
):
    rows = await svc.list_plans(db, farm_id, _MODULE)
    return SuccessResponse(data=[PlanResponse.model_validate(r) for r in rows])


@router.post("/plans", response_model=SuccessResponse[PlanResponse], status_code=status.HTTP_201_CREATED)
async def create_plan(
    farm_id: UUID, body: PlanCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_EDIT)),
):
    plan = await svc.create_plan(db, farm_id, _MODULE, body, current_user)
    return SuccessResponse(data=PlanResponse.model_validate(plan))


@router.get("/plans/{plan_id}", response_model=SuccessResponse[PlanDetailResponse])
async def get_plan(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_VIEW)),
):
    detail = await svc.get_plan_detail(db, farm_id, _MODULE, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.patch("/plans/{plan_id}", response_model=SuccessResponse[PlanDetailResponse])
async def update_plan(
    farm_id: UUID, plan_id: UUID, body: PlanUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_EDIT)),
):
    await svc.update_plan(db, farm_id, _MODULE, plan_id, body, current_user)
    detail = await svc.get_plan_detail(db, farm_id, _MODULE, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.post("/plans/{plan_id}/archive", response_model=SuccessResponse[PlanResponse])
async def archive_plan(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_EDIT)),
):
    plan = await svc.archive_plan(db, farm_id, _MODULE, plan_id, current_user)
    return SuccessResponse(data=PlanResponse.model_validate(plan))


@router.patch("/plans/{plan_id}/milestones/{milestone_id}", response_model=SuccessResponse[PlanDetailResponse])
async def update_milestone_status(
    farm_id: UUID, plan_id: UUID, milestone_id: UUID, body: MilestoneStatusUpdate,
    db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_EDIT)),
):
    await svc.update_milestone_status(db, farm_id, _MODULE, plan_id, milestone_id, body.status, body.reason, current_user)
    detail = await svc.get_plan_detail(db, farm_id, _MODULE, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.get("/plans/{plan_id}/revisions", response_model=SuccessResponse[list[RevisionResponse]])
async def list_revisions(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_VIEW)),
):
    rows = await svc.list_revisions(db, farm_id, _MODULE, plan_id)
    return SuccessResponse(data=[RevisionResponse.model_validate(r) for r in rows])


@router.get("/plans/{plan_id}/compare", response_model=SuccessResponse[dict])
async def compare_revisions(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.RABBIT_GROWTH_VIEW)),
    from_revision: int = Query(..., ge=1),
    to_revision: int = Query(..., ge=1),
):
    data = await svc.compare_revisions(db, farm_id, _MODULE, plan_id, from_revision, to_revision)
    return SuccessResponse(data=data)
