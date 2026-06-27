"""
AGRIOS — Audit Log Service (Sprint 7)
Provides a single append function for writing immutable audit log entries.

DB-08 (Frozen): audit_logs is append-only. Only INSERT operations exist.
No UPDATE, no DELETE, no soft-delete, no admin GET endpoint in V1.

Usage:
    from app.services.audit_service import log_action
    await log_action(db, action="flock.create", resource_type="flock", ...)
"""

import uuid
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[uuid.UUID] = None,
    farm_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """
    Append an immutable audit log entry.

    action format: "resource.verb" e.g. "flock.create", "expense.delete"
    This function never raises — log failures are caught and logged to stderr
    so they never disrupt the calling request.
    """
    try:
        entry = AuditLog(
            id=uuid.uuid4(),
            farm_id=farm_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        await db.flush()  # Write in the current transaction but don't commit independently
        return entry
    except Exception as e:
        logger.error(f"audit_service.log_action failed: {e}")
        # Never raise — audit failures must not break the request
        return None  # type: ignore[return-value]


async def log_action_safe(
    db: AsyncSession,
    action: str,
    resource_type: str,
    **kwargs: Any,
) -> None:
    """
    Fire-and-forget audit log. Commits immediately in a separate try/except.
    Use when the calling function does not manage its own commit cycle.
    """
    try:
        entry = AuditLog(
            id=uuid.uuid4(),
            action=action,
            resource_type=resource_type,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        logger.error(f"audit_service.log_action_safe failed: {e}")
