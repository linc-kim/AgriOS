"""
AGRIOS — Admin API Endpoints (Sprint 8)
Platform administration: stats, user management, farm oversight, AI usage.

All endpoints require super_admin or platform_admin role via ADMIN_* permissions.

Routes (all under /admin prefix):
  GET    /admin/stats                         → A-01 platform KPIs
  GET    /admin/users                         → A-02 user list (search, filter)
  GET    /admin/users/{user_id}               → A-02 user detail
  PATCH  /admin/users/{user_id}/suspend       → A-02 suspend user
  PATCH  /admin/users/{user_id}/restore       → A-02 restore user
  PATCH  /admin/users/{user_id}/quota         → A-02 quota override
  GET    /admin/farms                         → A-03 farm list
  PATCH  /admin/farms/{farm_id}/plan          → A-03/A-04 plan override
  GET    /admin/plans                         → A-04 subscription plan list
  GET    /admin/ai/usage                      → A-07 AI usage + cost

Note: Disease alert management (A-05) is in health.py (/health/alerts).
      Market price management (A-06) is in market.py (/market/prices).

RBAC:
  ADMIN_DASHBOARD       → all admin endpoints (super_admin + platform_admin)
  ADMIN_USER_MANAGE     → user suspend/restore/quota endpoints
  ADMIN_FARM_MANAGE     → farm plan override endpoints
  ADMIN_AI_USAGE_VIEW   → AI usage endpoint
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, require_permission
from app.database import get_db
from app.dependencies import get_current_user
from app.models.auth import User
from app.schemas.admin import (
    AdminAIUsageResponse,
    AdminFarmListResponse,
    AdminFarmPlanOverride,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserQuotaOverride,
    AdminUserSuspend,
    PlatformStats,
    SubscriptionPlanSummary,
)
from app.schemas.base import SuccessResponse
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])

# Type aliases
DBSession = Depends(get_db)
CurrentUser = Depends(get_current_user)


# ── A-01 Platform Stats ───────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=SuccessResponse[PlatformStats],
    summary="Platform KPI overview (A-01)",
)
async def get_platform_stats(
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
):
    stats = await admin_service.get_platform_stats(db)
    return SuccessResponse(data=stats)


# ── A-02 User Management ──────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=SuccessResponse[AdminUserListResponse],
    summary="List all platform users (A-02)",
)
async def list_users(
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_USER_MANAGE)),
    search: Optional[str] = Query(None, description="Search by phone or name"),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await admin_service.list_users(
        db, search=search, is_active=is_active, limit=limit, offset=offset
    )
    return SuccessResponse(data=result)


@router.get(
    "/users/{user_id}",
    response_model=SuccessResponse[AdminUserDetail],
    summary="Get user detail (A-02)",
)
async def get_user_detail(
    user_id: UUID,
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_USER_MANAGE)),
):
    detail = await admin_service.get_user_detail(db, user_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return SuccessResponse(data=detail)


@router.patch(
    "/users/{user_id}/suspend",
    response_model=SuccessResponse[dict],
    summary="Suspend a user account (A-02)",
)
async def suspend_user(
    user_id: UUID,
    body: AdminUserSuspend,
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_USER_MANAGE)),
):
    user = await admin_service.suspend_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return SuccessResponse(data={"id": str(user.id), "is_active": user.is_active})


@router.patch(
    "/users/{user_id}/restore",
    response_model=SuccessResponse[dict],
    summary="Restore a suspended user account (A-02)",
)
async def restore_user(
    user_id: UUID,
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_USER_MANAGE)),
):
    user = await admin_service.restore_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return SuccessResponse(data={"id": str(user.id), "is_active": user.is_active})


@router.patch(
    "/users/{user_id}/quota",
    response_model=SuccessResponse[dict],
    summary="Override AI query quota for a user (A-02)",
)
async def override_user_quota(
    user_id: UUID,
    body: AdminUserQuotaOverride,
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_USER_MANAGE)),
):
    user = await admin_service.override_user_quota(db, user_id, body.monthly_limit)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    quota = (user.metadata_ or {}).get("quota_override", "plan_default")
    return SuccessResponse(data={"id": str(user.id), "quota_override": quota})


# ── A-03/A-04 Farm Management & Subscriptions ────────────────────────────────

@router.get(
    "/farms",
    response_model=SuccessResponse[AdminFarmListResponse],
    summary="List all farms (A-03)",
)
async def list_farms(
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_FARM_MANAGE)),
    search: Optional[str] = Query(None),
    plan_name: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await admin_service.list_farms(
        db, search=search, plan_name=plan_name, limit=limit, offset=offset
    )
    return SuccessResponse(data=result)


@router.patch(
    "/farms/{farm_id}/plan",
    response_model=SuccessResponse[dict],
    summary="Override subscription plan for a farm (A-03/A-04)",
)
async def override_farm_plan(
    farm_id: UUID,
    body: AdminFarmPlanOverride,
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_FARM_MANAGE)),
):
    farm = await admin_service.override_farm_plan(db, farm_id, body)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found or plan name invalid",
        )
    return SuccessResponse(data={"id": str(farm.id), "plan_applied": body.plan_name})


@router.get(
    "/plans",
    response_model=SuccessResponse[list[SubscriptionPlanSummary]],
    summary="List subscription plans with farm counts (A-04)",
)
async def list_plans(
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
):
    plans = await admin_service.list_subscription_plans(db)
    return SuccessResponse(data=plans)


# ── A-07 AI Usage ─────────────────────────────────────────────────────────────

@router.get(
    "/ai/usage",
    response_model=SuccessResponse[AdminAIUsageResponse],
    summary="AI usage and cost report (A-07)",
)
async def get_ai_usage(
    db: AsyncSession = DBSession,
    current_user: User = CurrentUser,
    _perm=Depends(require_permission(Permission.ADMIN_AI_USAGE_VIEW)),
    period_days: int = Query(30, ge=1, le=365, description="Lookback period in days"),
):
    result = await admin_service.get_ai_usage(db, period_days=period_days)
    return SuccessResponse(data=result)
