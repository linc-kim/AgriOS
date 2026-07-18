"""
Greena — Admin Platform Endpoints (Module 10).

Platform-wide administration under /admin/platform. All endpoints require a
platform admin role (ADMIN_DASHBOARD); mutations require specific admin
permissions. Organization owners have none of these, so they cannot access it.
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi import status as http_status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession
from app.schemas.admin_platform import (
    AdminAskInput, AdminAskResponse, AdminDashboard, AdminFarmRow, AdminFarmStats,
    AdminOrgDetail, AdminOrgPage, AdminUserPage, AuditPage, AuditRow, BackgroundJobRow,
    BackgroundJobStats, FeatureFlagRow, FeatureFlagSetInput, LoginHistoryRow,
    PlatformAnalytics, RoleChangeInput, RunJobInput, SystemConfigResponse, SystemConfigUpdate,
    SystemHealth, AdminActionInput,
)
from app.schemas.base import SuccessResponse
from app.services import admin_platform_service as svc

router = APIRouter(prefix="/admin/platform", tags=["Admin Platform"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ── Dashboard / analytics / health ────────────────────────────────────────────

@router.get("/dashboard", response_model=SuccessResponse[AdminDashboard], summary="Admin dashboard")
async def dashboard(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.admin_dashboard(db))


@router.get("/analytics", response_model=SuccessResponse[PlatformAnalytics], summary="Platform analytics")
async def analytics(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.platform_analytics(db))


@router.get("/health", response_model=SuccessResponse[SystemHealth], summary="System health")
async def health(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.system_health(db))


# ── Organizations ─────────────────────────────────────────────────────────────

@router.get("/organizations", response_model=SuccessResponse[AdminOrgPage], summary="List organizations")
async def list_orgs(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
                    q: str | None = Query(default=None), status: str | None = Query(default=None),
                    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return SuccessResponse(data=await svc.list_organizations(db, q, status, page, page_size))


@router.get("/organizations/{org_id}", response_model=SuccessResponse[AdminOrgDetail], summary="Organization detail")
async def org_detail(org_id: str, db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.get_org_detail(db, UUID(org_id)))


@router.post("/organizations/{org_id}/suspend", response_model=SuccessResponse[dict], summary="Suspend organization")
async def suspend_org(org_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                      body: AdminActionInput | None = None, _p=Depends(require_permission(Permission.ADMIN_ORG_MANAGE))):
    await svc.set_org_suspended(db, current_user, UUID(org_id), True, body.reason if body else None, _ip(request))
    return SuccessResponse(data={"suspended": True})


@router.post("/organizations/{org_id}/reactivate", response_model=SuccessResponse[dict], summary="Reactivate organization")
async def reactivate_org(org_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                         body: AdminActionInput | None = None, _p=Depends(require_permission(Permission.ADMIN_ORG_MANAGE))):
    await svc.set_org_suspended(db, current_user, UUID(org_id), False, body.reason if body else None, _ip(request))
    return SuccessResponse(data={"suspended": False})


@router.delete("/organizations/{org_id}", response_model=SuccessResponse[dict], summary="Soft-delete organization")
async def delete_org(org_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                     _p=Depends(require_permission(Permission.ADMIN_ORG_MANAGE))):
    await svc.soft_delete_org(db, current_user, UUID(org_id), ip=_ip(request))
    return SuccessResponse(data={"deleted": True})


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=SuccessResponse[AdminUserPage], summary="List users")
async def list_users(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
                     q: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return SuccessResponse(data=await svc.list_users(db, q, page, page_size))


@router.post("/users/{user_id}/role", response_model=SuccessResponse[dict], summary="Change user role")
async def change_role(user_id: str, body: RoleChangeInput, request: Request, db: DBSession, current_user: CurrentUser,
                      _p=Depends(require_permission(Permission.ADMIN_USER_MANAGE))):
    await svc.change_user_role(db, current_user, UUID(user_id), body.role, _ip(request))
    return SuccessResponse(data={"role": body.role})


@router.post("/users/{user_id}/disable", response_model=SuccessResponse[dict], summary="Disable user")
async def disable_user(user_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                       body: AdminActionInput | None = None, _p=Depends(require_permission(Permission.ADMIN_USER_MANAGE))):
    await svc.set_user_active(db, current_user, UUID(user_id), False, body.reason if body else None, _ip(request))
    return SuccessResponse(data={"is_active": False})


@router.post("/users/{user_id}/reactivate", response_model=SuccessResponse[dict], summary="Reactivate user")
async def reactivate_user(user_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                          _p=Depends(require_permission(Permission.ADMIN_USER_MANAGE))):
    await svc.set_user_active(db, current_user, UUID(user_id), True, ip=_ip(request))
    return SuccessResponse(data={"is_active": True})


@router.post("/users/{user_id}/force-logout", response_model=SuccessResponse[dict], summary="Force logout")
async def force_logout(user_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                       _p=Depends(require_permission(Permission.ADMIN_USER_MANAGE))):
    n = await svc.force_logout(db, current_user, UUID(user_id), _ip(request))
    return SuccessResponse(data={"sessions_revoked": n})


@router.post("/users/{user_id}/reset-password", response_model=SuccessResponse[dict], summary="Force password reset")
async def reset_password(user_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                         _p=Depends(require_permission(Permission.ADMIN_USER_MANAGE))):
    return SuccessResponse(data=await svc.force_password_reset(db, current_user, UUID(user_id), _ip(request)))


@router.get("/users/{user_id}/login-history", response_model=SuccessResponse[list[LoginHistoryRow]], summary="Login history")
async def login_history(user_id: str, db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.user_login_history(db, UUID(user_id)))


@router.get("/users/{user_id}/audit", response_model=SuccessResponse[list[AuditRow]], summary="User audit history")
async def user_audit(user_id: str, db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.user_audit_history(db, UUID(user_id)))


# ── Farms ─────────────────────────────────────────────────────────────────────

@router.get("/farms", response_model=SuccessResponse[dict], summary="List farms")
async def list_farms(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
                     q: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return SuccessResponse(data=await svc.list_farms(db, q, page, page_size))


@router.post("/farms/{farm_id}/archive", response_model=SuccessResponse[dict], summary="Archive farm")
async def archive_farm(farm_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                       body: AdminActionInput | None = None, _p=Depends(require_permission(Permission.ADMIN_FARM_MANAGE))):
    await svc.set_farm_archived(db, current_user, UUID(farm_id), True, body.reason if body else None, _ip(request))
    return SuccessResponse(data={"archived": True})


@router.post("/farms/{farm_id}/restore", response_model=SuccessResponse[dict], summary="Restore farm")
async def restore_farm(farm_id: str, request: Request, db: DBSession, current_user: CurrentUser,
                       _p=Depends(require_permission(Permission.ADMIN_FARM_MANAGE))):
    await svc.set_farm_archived(db, current_user, UUID(farm_id), False, ip=_ip(request))
    return SuccessResponse(data={"archived": False})


@router.get("/farms/{farm_id}/stats", response_model=SuccessResponse[AdminFarmStats], summary="Farm statistics")
async def farm_stats(farm_id: str, db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.farm_stats(db, UUID(farm_id)))


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=SuccessResponse[AuditPage], summary="Audit center")
async def audit(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
                q: str | None = Query(default=None), resource_type: str | None = Query(default=None),
                action: str | None = Query(default=None), date_from: date | None = Query(default=None),
                date_to: date | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=200)):
    return SuccessResponse(data=await svc.list_audit(db, q, resource_type, action, date_from, date_to, page, page_size))


@router.get("/audit/csv", summary="Export audit CSV")
async def audit_csv(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
                    resource_type: str | None = Query(default=None), action: str | None = Query(default=None),
                    date_from: date | None = Query(default=None), date_to: date | None = Query(default=None)) -> Response:
    csv_text = await svc.export_audit_csv(db, resource_type=resource_type, action=action, date_from=date_from, date_to=date_to)
    return Response(content=csv_text, media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="audit_log.csv"'})


# ── Feature flags ─────────────────────────────────────────────────────────────

@router.get("/feature-flags", response_model=SuccessResponse[list[FeatureFlagRow]], summary="List feature flags")
async def feature_flags(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    flags = await svc.list_feature_flags(db)
    return SuccessResponse(data=[FeatureFlagRow.model_validate(f) for f in flags])


@router.post("/feature-flags", response_model=SuccessResponse[FeatureFlagRow], summary="Set feature flag")
async def set_flag(body: FeatureFlagSetInput, request: Request, db: DBSession, current_user: CurrentUser,
                   _p=Depends(require_permission(Permission.ADMIN_PLATFORM_CONFIG))):
    flag = await svc.set_feature_flag(db, current_user, body.flag_key, body.is_enabled,
                                      body.organization_id, body.name, body.description, _ip(request))
    return SuccessResponse(data=FeatureFlagRow.model_validate(flag))


# ── System config ─────────────────────────────────────────────────────────────

@router.get("/system-config", response_model=SuccessResponse[SystemConfigResponse], summary="Get system config")
async def get_config(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=SystemConfigResponse.model_validate(await svc.get_system_config(db), from_attributes=True))


@router.patch("/system-config", response_model=SuccessResponse[SystemConfigResponse], summary="Update system config / maintenance")
async def update_config(body: SystemConfigUpdate, request: Request, db: DBSession, current_user: CurrentUser,
                        _p=Depends(require_permission(Permission.ADMIN_PLATFORM_CONFIG))):
    cfg = await svc.update_system_config(db, current_user, body.model_dump(exclude_unset=True), _ip(request))
    return SuccessResponse(data=SystemConfigResponse.model_validate(cfg, from_attributes=True))


# ── Background jobs ───────────────────────────────────────────────────────────

@router.get("/jobs", response_model=SuccessResponse[BackgroundJobStats], summary="Background jobs dashboard")
async def jobs(db: DBSession, current_user: CurrentUser, _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    data = await svc.jobs_dashboard(db)
    data["recent"] = [BackgroundJobRow.model_validate(j) for j in data["recent"]]
    return SuccessResponse(data=data)


@router.post("/jobs/run", response_model=SuccessResponse[BackgroundJobRow], summary="Run a background job")
async def run_job(body: RunJobInput, request: Request, db: DBSession, current_user: CurrentUser,
                  _p=Depends(require_permission(Permission.ADMIN_PLATFORM_CONFIG))):
    job = await svc.run_job(db, current_user, body.name, _ip(request))
    return SuccessResponse(data=BackgroundJobRow.model_validate(job))


# ── Admin AI ──────────────────────────────────────────────────────────────────

@router.post("/ai/ask", response_model=SuccessResponse[AdminAskResponse], summary="Ask ARIA about the platform")
async def admin_ask(body: AdminAskInput, db: DBSession, current_user: CurrentUser,
                    _p=Depends(require_permission(Permission.ADMIN_DASHBOARD))):
    return SuccessResponse(data=await svc.admin_ask(db, body.question))
