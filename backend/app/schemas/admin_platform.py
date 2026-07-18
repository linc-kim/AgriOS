"""
Greena — Admin Platform Schemas (Module 10).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import AGRIOSSchema, TimestampedSchema


# ── Organizations ─────────────────────────────────────────────────────────────

class AdminOrgRow(AGRIOSSchema):
    id: UUID
    name: str
    slug: str
    owner_name: str | None
    country: str | None
    currency: str
    is_suspended: bool
    is_deleted: bool
    farm_count: int
    member_count: int
    plan_name: str | None
    created_at: datetime


class AdminOrgPage(AGRIOSSchema):
    items: list[AdminOrgRow]
    total: int
    page: int
    page_size: int


class AdminOrgDetail(AdminOrgRow):
    flock_count: int
    active_flock_count: int
    ai_requests: int
    total_revenue: Decimal
    total_expenses: Decimal


# ── Users ─────────────────────────────────────────────────────────────────────

class AdminUserRow(AGRIOSSchema):
    id: UUID
    full_name: str | None
    email: str | None
    phone: str | None
    roles: list[str]
    is_active: bool
    is_suspended: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminUserPage(AGRIOSSchema):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int


class RoleChangeInput(AGRIOSSchema):
    role: str = Field(..., description="Platform role to assign")


class AdminActionInput(AGRIOSSchema):
    reason: str | None = Field(default=None, max_length=500)


class LoginHistoryRow(AGRIOSSchema):
    session_id: UUID
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    revoked: bool
    ip_address: str | None
    device: str | None


class AuditRow(AGRIOSSchema):
    id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    user_id: UUID | None
    actor_name: str | None
    farm_id: UUID | None
    ip_address: str | None
    old_value: dict | None
    new_value: dict | None
    created_at: datetime


class AuditPage(AGRIOSSchema):
    items: list[AuditRow]
    total: int
    page: int
    page_size: int


# ── Farms ─────────────────────────────────────────────────────────────────────

class AdminFarmRow(AGRIOSSchema):
    id: UUID
    name: str
    county: str | None
    owner_name: str | None
    is_active: bool
    is_archived: bool
    flock_count: int
    member_count: int
    created_at: datetime


class AdminFarmStats(AGRIOSSchema):
    id: UUID
    name: str
    owner_name: str | None
    active_flocks: int
    total_birds: int
    inventory_value: Decimal
    total_revenue: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    ai_requests: int


# ── Analytics ─────────────────────────────────────────────────────────────────

class GrowthPoint(AGRIOSSchema):
    period: str
    organizations: int
    farms: int
    users: int


class SubscriptionBreakdown(AGRIOSSchema):
    plan: str
    farm_count: int
    monthly_revenue: Decimal


class TopFarm(AGRIOSSchema):
    farm_id: UUID
    name: str
    ai_requests: int


class PlatformAnalytics(AGRIOSSchema):
    total_organizations: int
    total_farms: int
    total_users: int
    active_users_today: int
    api_requests_estimate: int
    storage_mb_estimate: Decimal
    ai_requests_total: int
    ai_gemini: int
    ai_claude: int
    ai_offline: int
    monthly_revenue_estimate: Decimal
    subscription_breakdown: list[SubscriptionBreakdown]
    growth: list[GrowthPoint]
    top_farms: list[TopFarm]


# ── Feature flags ─────────────────────────────────────────────────────────────

class FeatureFlagRow(TimestampedSchema):
    flag_key: str
    name: str
    description: str | None
    is_enabled: bool
    organization_id: UUID | None


class FeatureFlagSetInput(AGRIOSSchema):
    flag_key: str = Field(..., max_length=60)
    is_enabled: bool
    organization_id: UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None


# ── System config / maintenance ───────────────────────────────────────────────

class SystemConfigResponse(AGRIOSSchema):
    maintenance_mode: bool
    read_only_mode: bool
    banner_message: str | None
    maintenance_scheduled_at: datetime | None
    ai_provider_priority: list[str]
    email_sender: str
    sms_sender: str
    default_currency: str
    default_timezone: str
    data_retention_days: int
    limits: dict
    updated_at: datetime


class SystemConfigUpdate(AGRIOSSchema):
    maintenance_mode: bool | None = None
    read_only_mode: bool | None = None
    banner_message: str | None = None
    maintenance_scheduled_at: datetime | None = None
    ai_provider_priority: list[str] | None = None
    email_sender: str | None = Field(default=None, max_length=200)
    sms_sender: str | None = Field(default=None, max_length=50)
    default_currency: str | None = Field(default=None, max_length=3)
    default_timezone: str | None = Field(default=None, max_length=50)
    data_retention_days: int | None = Field(default=None, ge=1, le=36500)
    limits: dict | None = None


# ── System health ─────────────────────────────────────────────────────────────

class HealthComponent(AGRIOSSchema):
    name: str
    status: str            # ok | degraded | down | not_configured
    detail: str | None = None


class SystemHealth(AGRIOSSchema):
    status: str
    version: str
    environment: str
    uptime_seconds: int
    components: list[HealthComponent]
    checked_at: datetime


# ── Background jobs ───────────────────────────────────────────────────────────

class BackgroundJobRow(TimestampedSchema):
    name: str
    status: str
    queue: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    attempts: int
    error: str | None
    result: dict


class BackgroundJobStats(AGRIOSSchema):
    total: int
    success: int
    failed: int
    running: int
    queued: int
    queue_depth: int
    avg_duration_ms: int | None
    recent: list[BackgroundJobRow]


class RunJobInput(AGRIOSSchema):
    name: str = Field(..., description="Job to run, e.g. 'cleanup_expired_sessions'")


# ── Dashboard ─────────────────────────────────────────────────────────────────

class AdminDashboard(AGRIOSSchema):
    organizations: int
    farms: int
    users: int
    active_users_today: int
    monthly_revenue_estimate: Decimal
    ai_requests_total: int
    suspended_orgs: int
    suspended_users: int
    maintenance_mode: bool
    health_status: str
    jobs_failed_24h: int


# ── Admin AI ──────────────────────────────────────────────────────────────────

class AdminAskInput(AGRIOSSchema):
    question: str = Field(..., min_length=2, max_length=1000)


class AdminAskResponse(AGRIOSSchema):
    answer: str
    provider: str
    sources: list[str]
