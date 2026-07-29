"""
Greena — Aviculture ARIA API (Module 15, Part 10)

The aviculture assistant: deterministic-first Q&A, a bounded context snapshot, and
data-driven species knowledge. Reuses the platform AI provider and settings;
preserves AR-01 (bounded context), the disease-diagnosis ban, honesty labelling
and the offline fallback. Farm-scoped, permission-guarded (reuses the existing
AI_QUERY / AI_INSIGHT_VIEW permissions).

Prefix: /farms/{farm_id}/aviculture/aria
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.aviculture_aria import (
    AskRequest, AskResponse, ContextResponse, SpeciesKnowledgeResponse,
)
from app.services import aviculture_aria_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture/aria", tags=["Aviculture — ARIA"])


@router.post("/ask", response_model=SuccessResponse[AskResponse])
async def ask(farm_id: str, body: AskRequest, db: DBSession, current_user: CurrentUser,
              access: tuple = Depends(require_farm_access()),
              _perm=Depends(require_permission(Permission.AI_QUERY))):
    farm, _ = access
    return SuccessResponse(data=AskResponse.model_validate(await svc.ask(db, farm, current_user, body.question)))


@router.get("/context", response_model=SuccessResponse[ContextResponse])
async def context(farm_id: str, db: DBSession, current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access()),
                  _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=ContextResponse(context=await svc.compile_context(db, farm)))


@router.get("/species/{species_id}/knowledge", response_model=SuccessResponse[SpeciesKnowledgeResponse])
async def species_knowledge(farm_id: str, species_id: UUID, db: DBSession, current_user: CurrentUser,
                            access: tuple = Depends(require_farm_access()),
                            _perm=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=SpeciesKnowledgeResponse.model_validate(
        await svc.species_knowledge(db, farm, species_id)))
