"""
Greena — Swine ARIA API (Module 20, Milestone 10)

Deterministic-first, honesty-labelled Q&A + explainable recommendations over the
platform AI router. ARIA explains/recommends; it never edits data, never diagnoses,
never invents. Reuses the platform ``AI_QUERY`` / ``AI_INSIGHT_VIEW`` permissions
(no swine-specific AI perms — ARIA is a shared layer).

Route map (prefix /farms/{farm_id}/swine/aria):
  POST /ask              ask a question (deterministic-first; grounded LLM fallback)
  GET  /context          the bounded context snapshot ARIA reasons over (AR-01)
  GET  /recommendations  explainable deterministic recommendations (reason + evidence)
"""

from fastapi import APIRouter, Depends

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import AriaAnswer, AriaAsk
from app.services import swine_aria_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/aria", tags=["Swine ARIA"])


@router.post("/ask", response_model=SuccessResponse[AriaAnswer])
async def ask(
    farm_id: str, body: AriaAsk, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.ask(db, farm, current_user, body.question))


@router.get("/context", response_model=SuccessResponse[dict])
async def context(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.compile_context(db, farm))


@router.get("/recommendations", response_model=SuccessResponse[dict])
async def recommendations(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.recommendations(db, farm))
