"""
Greena — ARIA AI Platform Endpoints (Module 9).

Extends the existing ARIA chat with predictions, forecasting, a unified context
builder and an offline-safe assistant. Farm-scoped under /farms/{farm_id}/ai.

  GET  /ai/context                     unified AI context
  GET  /ai/forecasts                   feed / financial / inventory / production
  GET  /ai/predictions/mortality       explainable mortality prediction
  GET  /ai/predictions/disease-risk    explainable disease-risk score
  GET  /ai/dashboard                   AI dashboard (forecasts + predictions)
  POST /ai/ask                         natural-language assistant (offline-safe)

RBAC: AI_INSIGHT_VIEW (reads) · AI_QUERY (ask).
"""

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.ai_platform import (
    AIDashboard,
    AIPlatformContext,
    AskRequest,
    AskResponse,
    DiseaseRisk,
    ForecastsResponse,
    MortalityPrediction,
)
from app.schemas.base import SuccessResponse
from app.services import ai_platform_service

router = APIRouter()


@router.get("/farms/{farm_id}/ai/context", response_model=SuccessResponse[AIPlatformContext],
            summary="Unified AI farm context", tags=["AI Platform"])
async def context(farm_id: str, db: DBSession, current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access()),
                  _p=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await ai_platform_service.build_context(db, farm))


@router.get("/farms/{farm_id}/ai/forecasts", response_model=SuccessResponse[ForecastsResponse],
            summary="Feed / financial / inventory / production forecasts", tags=["AI Platform"])
async def forecasts(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await ai_platform_service.get_forecasts(db, farm))


@router.get("/farms/{farm_id}/ai/predictions/mortality", response_model=SuccessResponse[MortalityPrediction],
            summary="Explainable mortality prediction", tags=["AI Platform"])
async def mortality(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await ai_platform_service.predict_mortality(db, farm))


@router.get("/farms/{farm_id}/ai/predictions/disease-risk", response_model=SuccessResponse[DiseaseRisk],
            summary="Explainable disease-risk score", tags=["AI Platform"])
async def disease_risk(farm_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await ai_platform_service.disease_risk(db, farm))


@router.get("/farms/{farm_id}/ai/dashboard", response_model=SuccessResponse[AIDashboard],
            summary="AI dashboard (forecasts + predictions + risk)", tags=["AI Platform"])
async def dashboard(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.AI_INSIGHT_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await ai_platform_service.get_dashboard(db, farm))


@router.post("/farms/{farm_id}/ai/ask", response_model=SuccessResponse[AskResponse],
             status_code=status.HTTP_200_OK, summary="Natural-language assistant (offline-safe)", tags=["AI Platform"])
async def ask(farm_id: str, body: AskRequest, db: DBSession, current_user: CurrentUser,
              access: tuple = Depends(require_farm_access()),
              _p=Depends(require_permission(Permission.AI_QUERY))):
    farm, _ = access
    result = await ai_platform_service.ask(db, farm, current_user, body.question, body.conversation_id)
    return SuccessResponse(data=result)
