"""
AGRIOS — Notifications Endpoints (Sprint 7)

Endpoint groups (all farm-scoped):
  GET    /farms/{farm_id}/notifications              — List notifications
  PATCH  /farms/{farm_id}/notifications/{id}/read   — Mark one read
  POST   /farms/{farm_id}/notifications/read-all    — Mark all read
  DELETE /farms/{farm_id}/notifications/{id}        — Soft-delete notification

Permission: NOTIFICATION_VIEW (all authenticated farm members).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import get_current_user, require_farm_access
from app.models.auth import User
from app.schemas.base import SuccessResponse
from app.schemas.platform import NotificationListResponse, NotificationResponse
from app.services import notification_service

router = APIRouter(prefix="/farms/{farm_id}", tags=["Notifications"])


@router.get(
    "/notifications",
    response_model=SuccessResponse[NotificationListResponse],
    summary="List notifications for the current user on this farm",
)
async def list_notifications(
    farm_id: uuid.UUID,
    unread_only: bool = Query(False, description="Return only unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_VIEW)),
):
    """
    Returns paginated notifications for the current user.
    Includes total count and unread_count for the badge.
    """
    result = await notification_service.list_notifications(
        db=db,
        user_id=current_user.id,
        farm_id=farm_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(data=result)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=SuccessResponse[NotificationResponse],
    summary="Mark a notification as read",
)
async def mark_notification_read(
    farm_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_VIEW)),
):
    result = await notification_service.mark_notification_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
        farm_id=farm_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification not found."},
        )
    return SuccessResponse(data=result)


@router.post(
    "/notifications/read-all",
    response_model=SuccessResponse[dict],
    summary="Mark all notifications as read",
)
async def mark_all_read(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_VIEW)),
):
    updated = await notification_service.mark_all_read(
        db=db,
        user_id=current_user.id,
        farm_id=farm_id,
    )
    return SuccessResponse(data={"updated": updated})


@router.delete(
    "/notifications/{notification_id}",
    response_model=SuccessResponse[dict],
    summary="Soft-delete a notification",
)
async def delete_notification(
    farm_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    access=Depends(
        require_farm_access({
            "farm_owner", "farm_manager", "enterprise_owner",
            "vet_consultant", "farm_worker", "viewer",
        })
    ),
    current_user: User = Depends(require_permission(Permission.NOTIFICATION_VIEW)),
):
    deleted = await notification_service.delete_notification(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
        farm_id=farm_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification not found."},
        )
    return SuccessResponse(data={"deleted": True})
