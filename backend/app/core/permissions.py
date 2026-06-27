"""
AGRIOS — RBAC Permission System
Implements the permission matrix from the Engineering Constitution.
8 roles × ~30 permissions.

Usage:
    @router.post("/farms/{farm_id}/flocks")
    async def create_flock(
        farm_id: UUID,
        current_user: User = Depends(require_permission(Permission.FLOCK_CREATE)),
    ):
        ...
"""

from enum import StrEnum
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.auth import User


# ── Permission Definitions ────────────────────────────────────────────────────

class Permission(StrEnum):
    # Farm Management
    FARM_CREATE = "farm:create"
    FARM_EDIT = "farm:edit"
    FARM_DELETE = "farm:delete"
    FARM_MEMBER_INVITE = "farm:member:invite"
    FARM_MEMBER_REMOVE = "farm:member:remove"
    FARM_MEMBER_ROLE_CHANGE = "farm:member:role_change"
    FARM_UNIT_MANAGE = "farm:unit:manage"

    # Flock Management
    FLOCK_CREATE = "flock:create"
    FLOCK_CLOSE = "flock:close"
    FLOCK_VIEW = "flock:view"

    # Daily Operations
    OPS_LOG_SUBMIT = "ops:log:submit"
    OPS_LOG_CORRECT = "ops:log:correct"
    OPS_FEED_LOG = "ops:feed:log"
    OPS_WEIGHIN_LOG = "ops:weighin:log"
    OPS_PRODUCTION_LOG = "ops:production:log"
    OPS_LOG_VIEW = "ops:log:view"

    # Health Management
    HEALTH_VACCINATION_LOG = "health:vaccination:log"
    HEALTH_VACCINATION_VIEW = "health:vaccination:view"
    HEALTH_ALERT_VIEW = "health:alert:view"

    # Finance
    FINANCE_EXPENSE_LOG = "finance:expense:log"
    FINANCE_EXPENSE_EDIT = "finance:expense:edit"
    FINANCE_REVENUE_LOG = "finance:revenue:log"
    FINANCE_RECORD = "finance:record"   # Write: expenses + revenue + custom categories
    FINANCE_VIEW = "finance:view"

    # AI / ARIA
    AI_QUERY = "ai:query"
    AI_INSIGHT_VIEW = "ai:insight:view"

    # Notifications (Sprint 7)
    NOTIFICATION_VIEW = "notification:view"

    # Market Prices (Sprint 7)
    MARKET_VIEW = "market:view"

    # Admin (super_admin only)
    ADMIN_DASHBOARD = "admin:dashboard"
    ADMIN_ALERT_PUBLISH = "admin:alert:publish"
    ADMIN_MARKET_MANAGE = "admin:market:manage"
    ADMIN_USER_MANAGE = "admin:user:manage"
    ADMIN_FARM_MANAGE = "admin:farm:manage"
    ADMIN_AI_USAGE_VIEW = "admin:ai:usage:view"


# ── Role → Permission Mapping ─────────────────────────────────────────────────
# Derived from Engineering Constitution Section 5 RBAC matrix.

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "super_admin": set(Permission),  # All permissions

    "platform_admin": {
        Permission.ADMIN_DASHBOARD,
        Permission.ADMIN_ALERT_PUBLISH,
        Permission.ADMIN_MARKET_MANAGE,
        Permission.ADMIN_USER_MANAGE,
        Permission.ADMIN_FARM_MANAGE,
        Permission.ADMIN_AI_USAGE_VIEW,
        Permission.FARM_VIEW if hasattr(Permission, "FARM_VIEW") else Permission.FLOCK_VIEW,
    },

    "enterprise_owner": {
        # V1: seeded but no user-facing flows. Same as farm_owner for now.
        Permission.FARM_CREATE,
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_MEMBER_REMOVE,
        Permission.FARM_MEMBER_ROLE_CHANGE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_owner": {
        Permission.FARM_CREATE,
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_MEMBER_REMOVE,
        Permission.FARM_MEMBER_ROLE_CHANGE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_manager": {
        Permission.FARM_EDIT,
        Permission.FARM_MEMBER_INVITE,
        Permission.FARM_UNIT_MANAGE,
        Permission.FLOCK_CREATE,
        Permission.FLOCK_CLOSE,
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_LOG_CORRECT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_EXPENSE_LOG,
        Permission.FINANCE_EXPENSE_EDIT,
        Permission.FINANCE_REVENUE_LOG,
        Permission.FINANCE_RECORD,
        Permission.FINANCE_VIEW,
        Permission.AI_QUERY,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "vet_consultant": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_LOG,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "farm_worker": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_SUBMIT,
        Permission.OPS_FEED_LOG,
        Permission.OPS_WEIGHIN_LOG,
        Permission.OPS_PRODUCTION_LOG,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },

    "viewer": {
        Permission.FLOCK_VIEW,
        Permission.OPS_LOG_VIEW,
        Permission.HEALTH_VACCINATION_VIEW,
        Permission.HEALTH_ALERT_VIEW,
        Permission.FINANCE_VIEW,
        Permission.AI_INSIGHT_VIEW,
        Permission.NOTIFICATION_VIEW,
        Permission.MARKET_VIEW,
    },
}


def get_user_permissions(role_name: str) -> set[Permission]:
    """Return the set of permissions for a given role key."""
    return ROLE_PERMISSIONS.get(role_name, set())


def has_permission(role_name: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_user_permissions(role_name)


# ── FastAPI Dependencies ───────────────────────────────────────────────────────

def require_permission(permission: Permission):
    """
    FastAPI dependency factory.
    Usage: Depends(require_permission(Permission.FLOCK_CREATE))
    Checks the user's role for the requested permission.
    Farm-scoped permission validation happens in the service layer.
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        # Collect all role names for this user
        user_role_names = {ur.role.name for ur in current_user.user_roles}

        for role_name in user_role_names:
            if has_permission(role_name, permission):
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": f"Your role does not have permission: {permission}",
            },
        )

    return _check


def require_admin():
    """Shortcut dependency for super_admin-only endpoints."""
    return require_permission(Permission.ADMIN_DASHBOARD)
