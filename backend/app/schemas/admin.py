"""
Greena — Admin Module Schemas (Sprint 8)
Input/output schemas for platform administration endpoints.
All access restricted to super_admin (ADMIN_* permissions).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Platform Stats (A-01 Overview) ───────────────────────────────────────────

class PlatformStats(BaseModel):
    """Platform-wide KPIs for A-01 Admin Overview."""
    total_users: int
    active_users_30d: int
    total_farms: int
    active_farms_30d: int
    total_flocks: int
    active_flocks: int
    total_ai_queries_30d: int
    total_ai_cost_usd_30d: float
    total_notifications_sent_30d: int
    total_disease_alerts_active: int
    total_market_prices: int

    model_config = {"from_attributes": True}


# ── User Management (A-02) ───────────────────────────────────────────────────

class AdminUserSummary(BaseModel):
    """User summary for admin list view."""
    id: uuid.UUID
    phone_number: str
    name: Optional[str]
    is_active: bool
    is_verified: bool
    farm_count: int
    ai_queries_this_month: int
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: list[AdminUserSummary]
    total: int


class AdminUserSuspend(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class AdminUserQuotaOverride(BaseModel):
    """Override monthly AI query quota for a specific user."""
    monthly_limit: Optional[int] = Field(
        None,
        ge=0,
        description="Override monthly AI query limit. None = use plan default.",
    )
    reason: str = Field(..., min_length=5, max_length=500)


class AdminUserDetail(BaseModel):
    """Full user detail for admin inspection."""
    id: uuid.UUID
    phone_number: str
    name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    farms: list[dict]  # Brief farm summaries
    roles: list[str]
    ai_queries_this_month: int
    ai_queries_all_time: int

    model_config = {"from_attributes": True}


# ── Farm Management (A-03/A-04) ──────────────────────────────────────────────

class AdminFarmSummary(BaseModel):
    """Farm summary for admin list view."""
    id: uuid.UUID
    name: str
    owner_phone: Optional[str]
    owner_name: Optional[str]
    subscription_plan: str
    member_count: int
    active_flock_count: int
    last_log_date: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminFarmListResponse(BaseModel):
    items: list[AdminFarmSummary]
    total: int


class AdminFarmPlanOverride(BaseModel):
    """Override subscription plan for a farm."""
    plan_name: str = Field(..., description="New subscription plan name")
    reason: str = Field(..., min_length=5, max_length=500)

    @field_validator("plan_name")
    @classmethod
    def valid_plan(cls, v: str) -> str:
        allowed = {"free", "starter", "pro"}
        if v not in allowed:
            raise ValueError(f"plan_name must be one of {allowed}")
        return v


class AdminFarmDetail(BaseModel):
    """Full farm detail for admin inspection."""
    id: uuid.UUID
    name: str
    county: Optional[str]
    subscription_plan: str
    member_count: int
    flock_count: int
    active_flock_count: int
    total_expenses_kes: str
    total_revenue_kes: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AI Usage (A-07) ──────────────────────────────────────────────────────────

class AdminAIUsageDay(BaseModel):
    """AI usage summary for one calendar day."""
    date: str           # YYYY-MM-DD
    query_count: int
    total_tokens: int
    cost_usd: float
    unique_users: int


class AdminAIUsageResponse(BaseModel):
    """AI usage and cost summary for the admin dashboard."""
    period_days: int
    total_queries: int
    total_tokens: int
    total_cost_usd: float
    unique_users: int
    daily_breakdown: list[AdminAIUsageDay]
    top_model: Optional[str]
    fallback_rate_pct: float    # % of calls that used fallback provider


# ── Subscription Plans (A-04) ────────────────────────────────────────────────

class SubscriptionPlanSummary(BaseModel):
    """Brief subscription plan info for admin overview."""
    id: uuid.UUID
    name: str
    display_name: str
    price_kes: str
    farm_count: int

    model_config = {"from_attributes": True}
