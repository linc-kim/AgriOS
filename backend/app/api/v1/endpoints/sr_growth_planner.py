"""
Greena — Small Ruminant Growth Planner API (Modules 18/19, Milestone 10)

A permission-guarded surface over the **platform** Growth Planner
(``growth_planner_service``, module = species). The planner is cross-module; this
module only supplies the goat/sheep metric providers (imported here so they
register) and the ``SR_GROWTH_VIEW`` / ``SR_GROWTH_EDIT`` guards. No module planner.

Route map (prefix /farms/{farm_id}/sr/{species}/growth):
  GET/POST  /plans                                    list / create plans
  GET       /plans/{plan_id}                          detail + progress (planned vs actual)
  PATCH     /plans/{plan_id}                          revise plan (writes a version)
  POST      /plans/{plan_id}/archive                  archive plan
  PATCH     /plans/{plan_id}/milestones/{milestone_id} update milestone status
  GET       /plans/{plan_id}/revisions               version history
  GET       /plans/{plan_id}/compare                  diff two revisions
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
from app.services import small_ruminant_growth_provider  # noqa: F401 — registers goat/sheep providers
from app.services import growth_planner_service as svc
from app.api.v1.endpoints.sr_animals import SpeciesParam, _MANAGER_ROLES

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/growth", tags=["Small Ruminant Growth Planner"])

_VIEW = Depends(require_permission(Permission.SR_GROWTH_VIEW))
_EDIT = Depends(require_permission(Permission.SR_GROWTH_EDIT))


def _detail(detail: dict) -> PlanDetailResponse:
    return PlanDetailResponse(
        **PlanResponse.model_validate(detail["plan"]).model_dump(),
        goals=[GoalResponse.model_validate(g) for g in detail["goals"]],
        milestones=[MilestoneResponse.model_validate(mi) for mi in detail["milestones"]],
        progress=detail["progress"],
    )


@router.get("/plans", response_model=SuccessResponse[list[PlanResponse]])
async def list_plans(
    farm_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    rows = await svc.list_plans(db, farm_id, species)
    return SuccessResponse(data=[PlanResponse.model_validate(r) for r in rows])


@router.post("/plans", response_model=SuccessResponse[PlanResponse], status_code=status.HTTP_201_CREATED)
async def create_plan(
    farm_id: UUID, body: PlanCreate, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_EDIT,
):
    plan = await svc.create_plan(db, farm_id, species, body, current_user)
    return SuccessResponse(data=PlanResponse.model_validate(plan))


@router.get("/plans/{plan_id}", response_model=SuccessResponse[PlanDetailResponse])
async def get_plan(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    detail = await svc.get_plan_detail(db, farm_id, species, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.patch("/plans/{plan_id}", response_model=SuccessResponse[PlanDetailResponse])
async def update_plan(
    farm_id: UUID, plan_id: UUID, body: PlanUpdate, db: DBSession, current_user: CurrentUser,
    species: str = SpeciesParam, access: tuple = Depends(require_farm_access()), _perm=_EDIT,
):
    await svc.update_plan(db, farm_id, species, plan_id, body, current_user)
    detail = await svc.get_plan_detail(db, farm_id, species, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.post("/plans/{plan_id}/archive", response_model=SuccessResponse[PlanResponse])
async def archive_plan(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access(_MANAGER_ROLES)), _perm=_EDIT,
):
    plan = await svc.archive_plan(db, farm_id, species, plan_id, current_user)
    return SuccessResponse(data=PlanResponse.model_validate(plan))


@router.patch("/plans/{plan_id}/milestones/{milestone_id}", response_model=SuccessResponse[PlanDetailResponse])
async def update_milestone_status(
    farm_id: UUID, plan_id: UUID, milestone_id: UUID, body: MilestoneStatusUpdate,
    db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_EDIT,
):
    await svc.update_milestone_status(db, farm_id, species, plan_id, milestone_id, body.status,
                                      body.reason, current_user)
    detail = await svc.get_plan_detail(db, farm_id, species, plan_id)
    return SuccessResponse(data=_detail(detail))


@router.get("/plans/{plan_id}/revisions", response_model=SuccessResponse[list[RevisionResponse]])
async def list_revisions(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    rows = await svc.list_revisions(db, farm_id, species, plan_id)
    return SuccessResponse(data=[RevisionResponse.model_validate(r) for r in rows])


@router.get("/plans/{plan_id}/compare", response_model=SuccessResponse[dict])
async def compare_revisions(
    farm_id: UUID, plan_id: UUID, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    from_revision: int = Query(..., ge=1), to_revision: int = Query(..., ge=1),
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    data = await svc.compare_revisions(db, farm_id, species, plan_id, from_revision, to_revision)
    return SuccessResponse(data=data)
