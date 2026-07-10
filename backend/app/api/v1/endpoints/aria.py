"""
Greena — ARIA / AI Endpoints
Sprint 6: AI module endpoints.

Endpoint groups:
  POST   /farms/{farm_id}/aria/chat                            — Send message to ARIA
  GET    /farms/{farm_id}/aria/conversations                   — List conversations
  GET    /farms/{farm_id}/aria/conversations/{conv_id}         — Get conversation detail
  DELETE /farms/{farm_id}/aria/conversations/{conv_id}         — Delete conversation
  GET    /farms/{farm_id}/aria/insights                        — List insights
  PATCH  /farms/{farm_id}/aria/insights/{insight_id}/dismiss   — Dismiss insight
  GET    /farms/{farm_id}/aria/recommendations                 — List recommendations
  PATCH  /farms/{farm_id}/aria/recommendations/{rec_id}/action — Act/dismiss recommendation
  GET    /farms/{farm_id}/aria/usage                           — Quota + usage status

Permission matrix (Engineering Constitution Section 5):
  AI_QUERY:         farm_owner, farm_manager (send messages)
  AI_INSIGHT_VIEW:  farm_owner, farm_manager, vet_consultant, farm_worker, viewer
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import get_current_user, require_farm_access
from app.models.auth import User
from app.schemas.ai import (
    AIConversationDetail,
    AIInsightListResponse,
    AIInsightResponse,
    AIRecommendationListResponse,
    AIRecommendationResponse,
    AIUsageResponse,
    ARIAMessageCreate,
    ARIAResponse,
    RecommendationAction,
)
from app.schemas.base import SuccessResponse
from app.services import aria_service

router = APIRouter(prefix="/farms/{farm_id}", tags=["ARIA"])


# ── Conversation: Send Message ────────────────────────────────────────────────

@router.post(
    "/aria/chat",
    response_model=SuccessResponse[ARIAResponse],
    status_code=status.HTTP_200_OK,
    summary="Send a message to ARIA",
)
async def send_aria_message(
    farm_id: uuid.UUID,
    body: ARIAMessageCreate,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """
    Send a message to ARIA. Creates or continues a conversation.
    Returns the assistant's reply and updated quota remaining.
    Respects quota limits per subscription plan.
    """
    farm, _ = access
    result = await aria_service.send_message(
        db=db,
        farm=farm,
        current_user=current_user,
        content=body.content,
        conversation_id=body.conversation_id,
        flock_id=body.flock_id,
    )
    return SuccessResponse(data=result)


# ── Conversation: List ────────────────────────────────────────────────────────

@router.get(
    "/aria/conversations",
    response_model=SuccessResponse[list],
    summary="List ARIA conversations for this farm",
)
async def list_conversations(
    farm_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """List conversations for the current user on this farm, newest first."""
    conversations = await aria_service.list_conversations(
        db=db,
        farm_id=farm_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=conversations)


# ── Conversation: Detail ──────────────────────────────────────────────────────

@router.get(
    "/aria/conversations/{conversation_id}",
    response_model=SuccessResponse[AIConversationDetail],
    summary="Get a conversation with full message history",
)
async def get_conversation(
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    detail = await aria_service.get_conversation_detail(db, farm_id, conversation_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
        )
    return SuccessResponse(data=detail)


# ── Conversation: Delete ──────────────────────────────────────────────────────

@router.delete(
    "/aria/conversations/{conversation_id}",
    response_model=SuccessResponse[dict],
    summary="Delete (soft-delete) a conversation",
)
async def delete_conversation(
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    deleted = await aria_service.delete_conversation(db, farm_id, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
        )
    return SuccessResponse(data={"deleted": True})


# ── Insights: List ────────────────────────────────────────────────────────────

@router.get(
    "/aria/insights",
    response_model=SuccessResponse[AIInsightListResponse],
    summary="List ARIA insights for this farm",
)
async def list_insights(
    farm_id: uuid.UUID,
    include_dismissed: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    """
    Returns active, non-expired insights.
    Severity counts included for badge rendering.
    Available to all 6 farm roles (AI_INSIGHT_VIEW covers all except vet_consultant exclusions).
    """
    result = await aria_service.list_insights(
        db=db,
        farm_id=farm_id,
        include_dismissed=include_dismissed,
    )
    return SuccessResponse(data=result)


# ── Insights: Dismiss ─────────────────────────────────────────────────────────

@router.patch(
    "/aria/insights/{insight_id}/dismiss",
    response_model=SuccessResponse[AIInsightResponse],
    summary="Dismiss an insight",
)
async def dismiss_insight(
    farm_id: uuid.UUID,
    insight_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    result = await aria_service.dismiss_insight(db, farm_id, insight_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INSIGHT_NOT_FOUND", "message": "Insight not found."},
        )
    return SuccessResponse(data=result)


# ── Recommendations: List ─────────────────────────────────────────────────────

@router.get(
    "/aria/recommendations",
    response_model=SuccessResponse[AIRecommendationListResponse],
    summary="List ARIA recommendations for this farm",
)
async def list_recommendations(
    farm_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_INSIGHT_VIEW)),
):
    result = await aria_service.list_recommendations(
        db=db,
        farm_id=farm_id,
        status_filter=status_filter,
    )
    return SuccessResponse(data=result)


# ── Recommendations: Act / Dismiss ───────────────────────────────────────────

@router.patch(
    "/aria/recommendations/{recommendation_id}/action",
    response_model=SuccessResponse[AIRecommendationResponse],
    summary="Act on or dismiss a recommendation",
)
async def action_recommendation(
    farm_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    body: RecommendationAction,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    _: User = Depends(require_permission(Permission.AI_QUERY)),
):
    result = await aria_service.action_recommendation(
        db=db,
        farm_id=farm_id,
        recommendation_id=recommendation_id,
        action=body.action,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RECOMMENDATION_NOT_FOUND",
                "message": "Recommendation not found.",
            },
        )
    return SuccessResponse(data=result)


# ── Usage / Quota ─────────────────────────────────────────────────────────────

@router.get(
    "/aria/usage",
    response_model=SuccessResponse[AIUsageResponse],
    summary="Get ARIA quota and usage status for this farm",
)
async def get_usage(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(require_farm_access({"farm_owner", "farm_manager", "enterprise_owner"})),
    current_user: User = Depends(require_permission(Permission.AI_QUERY)),
):
    """
    Returns monthly query usage, quota remaining, and cost for the current month.
    Used by AI-04 (ARIASettingsScreen) to render the quota progress bar.
    """
    farm, _ = access
    result = await aria_service.get_usage_status(db, farm, current_user.id)
    return SuccessResponse(data=result)
