"""
Greena — BSF ARIA API (Module 16, Part 8)

ARIA explains, summarises, recommends and answers questions about BSF production —
deterministic-first, honesty-labelled, source-referenced. It is read-only: there
is no path by which ARIA mutates a plan or any record (ARIA/Mission Control
Contract). Reuses the platform AI router; `AI_QUERY` guards the question route,
`AI_INSIGHT_VIEW` the read.

Route map (prefix /farms/{farm_id}/bsf/aria):
  POST /ask        ask a question (deterministic-first, grounded LLM fallback)
  GET  /context    the bounded deterministic context ARIA reasons over
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import AriaAnswer, AriaAsk
from app.services import bsf_aria_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf/aria", tags=["Black Soldier Fly"])


@router.post("/ask", response_model=SuccessResponse[AriaAnswer])
async def ask(
    farm_id: UUID, body: AriaAsk, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_QUERY)),
):
    farm, _ = access
    result = await svc.ask(db, farm, current_user, body.question)
    return SuccessResponse(data=AriaAnswer(**result))


@router.get("/context", response_model=SuccessResponse[dict])
async def context(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.compile_context(db, farm))
