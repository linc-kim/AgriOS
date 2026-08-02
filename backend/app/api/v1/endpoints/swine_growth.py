"""
Greena — Swine Growth & Production API (Module 20, Milestone 7).

Immutable weight events, production-stage transition history, independent body-
condition scoring, computed growth analytics, and the explainable market-readiness
assessment. Growth figures are never stored — always computed from records. Weight /
body-condition / stage writes require SWINE_WEIGHT_LOG; growth reads SWINE_GROWTH_VIEW.

Route map (prefix /farms/{farm_id}/swine/growth):
    POST /pigs/{pig_id}/weights            record an (immutable) weight
    GET  /pigs/{pig_id}/weights            weight history
    GET  /pigs/{pig_id}/analysis           computed growth analysis (ADG, gain, curve)
    GET  /pigs/{pig_id}/readiness          explainable market-readiness assessment
    POST /pigs/{pig_id}/body-condition     record a BCS assessment
    GET  /pigs/{pig_id}/body-condition     BCS history
    POST /pigs/{pig_id}/stage              transition production stage (history)
    GET  /pigs/{pig_id}/stage-history      stage transition history
    GET  /cohort                           cohort growth (group/litter/stage/breed)
    GET  /stage-comparison                 avg weight + ADG by stage
    GET  /summary                          herd growth summary
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    BodyConditionCreate,
    BodyConditionResponse,
    PigResponse,
    StageTransitionInput,
    StageTransitionResponse,
    WeightCreate,
    WeightResponse,
)
from app.services import swine_growth_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/growth", tags=["Swine Growth"])

_LOG = Depends(require_permission(Permission.SWINE_WEIGHT_LOG))
_VIEW = Depends(require_permission(Permission.SWINE_GROWTH_VIEW))


@router.post("/pigs/{pig_id}/weights", response_model=SuccessResponse[WeightResponse],
             status_code=status.HTTP_201_CREATED)
async def record_weight(
    farm_id: str, pig_id: UUID, body: WeightCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.record_weight(db, farm, pig_id, body, current_user)
    return SuccessResponse(data=WeightResponse.model_validate(row))


@router.get("/pigs/{pig_id}/weights", response_model=SuccessResponse[list[WeightResponse]])
async def list_weights(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_weights(db, farm.id, pig_id)
    return SuccessResponse(data=[WeightResponse.model_validate(r) for r in rows])


@router.get("/pigs/{pig_id}/analysis", response_model=SuccessResponse[dict])
async def growth_analysis(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.growth_analysis(db, farm.id, pig_id))


@router.get("/pigs/{pig_id}/readiness", response_model=SuccessResponse[dict])
async def market_readiness(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    target_weight_kg: float | None = None, target_age_days: int | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.market_readiness(
        db, farm.id, pig_id, target_weight_kg=target_weight_kg, target_age_days=target_age_days))


@router.post("/pigs/{pig_id}/body-condition", response_model=SuccessResponse[BodyConditionResponse],
             status_code=status.HTTP_201_CREATED)
async def record_body_condition(
    farm_id: str, pig_id: UUID, body: BodyConditionCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    row = await svc.record_body_condition(db, farm, pig_id, body, current_user)
    return SuccessResponse(data=BodyConditionResponse.model_validate(row))


@router.get("/pigs/{pig_id}/body-condition", response_model=SuccessResponse[list[BodyConditionResponse]])
async def list_body_condition(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_body_condition(db, farm.id, pig_id)
    return SuccessResponse(data=[BodyConditionResponse.model_validate(r) for r in rows])


@router.post("/pigs/{pig_id}/stage", response_model=SuccessResponse[PigResponse])
async def transition_stage(
    farm_id: str, pig_id: UUID, body: StageTransitionInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_LOG,
):
    farm, _ = access
    pig = await svc.transition_stage(db, farm, pig_id, body, current_user)
    return SuccessResponse(data=PigResponse.model_validate(pig))


@router.get("/pigs/{pig_id}/stage-history", response_model=SuccessResponse[list[StageTransitionResponse]])
async def stage_history(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    rows = await svc.list_stage_transitions(db, farm.id, pig_id)
    return SuccessResponse(data=[StageTransitionResponse.model_validate(r) for r in rows])


@router.get("/cohort", response_model=SuccessResponse[dict])
async def cohort_growth(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    group_id: UUID | None = None, litter_id: UUID | None = None,
    production_stage: str | None = None, breed_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.cohort_growth(
        db, farm.id, group_id=group_id, litter_id=litter_id,
        production_stage=production_stage, breed_id=breed_id))


@router.get("/stage-comparison", response_model=SuccessResponse[dict])
async def stage_comparison(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.stage_comparison(db, farm.id))


@router.get("/summary", response_model=SuccessResponse[dict])
async def herd_growth_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await svc.herd_growth_summary(db, farm.id))
