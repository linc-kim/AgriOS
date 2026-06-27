"""
AGRIOS — Notification Service (Sprint 7)
Manages in-app notifications: creation, listing, read-marking, deletion.

All public functions are async and accept a db session as first argument.
Notifications are farm + user scoped. Soft-deletable.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Notification
from app.schemas.platform import NotificationCreate, NotificationListResponse, NotificationResponse


# ── Internal helpers ──────────────────────────────────────────────────────────

def _active_q(user_id: uuid.UUID, farm_id: uuid.UUID):
    """Base query filter: non-deleted notifications for this user+farm."""
    return and_(
        Notification.user_id == user_id,
        Notification.farm_id == farm_id,
        Notification.deleted_at.is_(None),
    )


# ── Create ────────────────────────────────────────────────────────────────────

async def create_notification(
    db: AsyncSession,
    payload: NotificationCreate,
) -> Notification:
    """
    Create a single in-app notification.
    Called by scheduler jobs and event hooks (e.g. disease alert publish).
    """
    notification = Notification(
        farm_id=payload.farm_id,
        user_id=payload.user_id,
        notification_type=payload.notification_type,
        title=payload.title,
        body=payload.body,
        action_route=payload.action_route,
        source=payload.source,
        is_read=False,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


async def create_notifications_bulk(
    db: AsyncSession,
    payloads: list[NotificationCreate],
) -> int:
    """Create multiple notifications in one transaction. Returns count created."""
    notifications = [
        Notification(
            farm_id=p.farm_id,
            user_id=p.user_id,
            notification_type=p.notification_type,
            title=p.title,
            body=p.body,
            action_route=p.action_route,
            source=p.source,
            is_read=False,
        )
        for p in payloads
    ]
    db.add_all(notifications)
    await db.commit()
    return len(notifications)


# ── List ──────────────────────────────────────────────────────────────────────

async def list_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    farm_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    """
    List notifications for a user on a farm, newest first.
    Optionally filter to unread only.
    Returns paginated list + total count + unread count.
    """
    base_filter = _active_q(user_id, farm_id)

    # Total and unread counts
    total_q = await db.execute(
        select(func.count()).where(base_filter)
    )
    total = total_q.scalar_one()

    unread_q = await db.execute(
        select(func.count()).where(
            and_(base_filter, Notification.is_read == False)
        )
    )
    unread_count = unread_q.scalar_one()

    # Paginated query
    filter_cond = base_filter
    if unread_only:
        filter_cond = and_(base_filter, Notification.is_read == False)

    rows = await db.execute(
        select(Notification)
        .where(filter_cond)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    notifications = rows.scalars().all()

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


# ── Mark Read ─────────────────────────────────────────────────────────────────

async def mark_notification_read(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> Optional[NotificationResponse]:
    """Mark a single notification as read. Returns updated notification or None if not found."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                _active_q(user_id, farm_id),
            )
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return None

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        await db.commit()
        await db.refresh(notif)

    return NotificationResponse.model_validate(notif)


async def mark_all_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> int:
    """Mark all unread notifications as read. Returns count updated."""
    from sqlalchemy import update

    now = datetime.utcnow()
    result = await db.execute(
        update(Notification)
        .where(
            and_(
                _active_q(user_id, farm_id),
                Notification.is_read == False,
            )
        )
        .values(is_read=True, read_at=now)
    )
    await db.commit()
    return result.rowcount


# ── Delete ────────────────────────────────────────────────────────────────────

async def delete_notification(
    db: AsyncSession,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> bool:
    """Soft-delete a notification. Returns True if deleted, False if not found."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                _active_q(user_id, farm_id),
            )
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return False

    notif.soft_delete()
    await db.commit()
    return True


# ── Unread count (for header badge) ──────────────────────────────────────────

async def get_unread_count(
    db: AsyncSession,
    user_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> int:
    """Return unread notification count for the notification badge."""
    result = await db.execute(
        select(func.count()).where(
            and_(
                _active_q(user_id, farm_id),
                Notification.is_read == False,
            )
        )
    )
    return result.scalar_one()
