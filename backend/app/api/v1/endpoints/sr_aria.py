"""
Greena — Small Ruminant ARIA API (Modules 18/19, Milestone 10)

Deterministic-first, honesty-labelled Q&A over the platform AI router for goat and
sheep workspaces. ARIA explains/recommends; it never edits data. Reuses the
platform ``AI_QUERY`` / ``AI_INSIGHT_VIEW`` permissions (no SR-specific AI perms).

Route map (prefix /farms/{farm_id}/sr/{species}/aria):
  POST /ask       ask a question (deterministic-first; grounded LLM fallback)
  GET  /context   the bounded context snapshot ARIA reasons over (AR-01)
"""

from fastapi import APIRouter, Depends

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.small_ruminant import AriaAnswer, AriaAsk
from app.services import small_ruminant_aria_service as svc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/aria", tags=["Small Ruminant ARIA"])


@router.post("/ask", response_model=SuccessResponse[AriaAnswer])
async def ask(
    farm_id: str, body: AriaAsk, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.ask(db, farm, species, current_user, body.question))


@router.get("/context", response_model=SuccessResponse[dict])
async def context(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.compile_context(db, farm, species))
