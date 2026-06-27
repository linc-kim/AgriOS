"""
Sprint 8 — Admin Module Unit Tests
Tests: schemas, service logic, RBAC, edge cases.
"""

import uuid
import pytest
from datetime import datetime, timezone

from app.schemas.admin import (
    PlatformStats,
    AdminUserSummary,
    AdminUserListResponse,
    AdminUserSuspend,
    AdminUserQuotaOverride,
    AdminFarmSummary,
    AdminFarmListResponse,
    AdminFarmPlanOverride,
    AdminAIUsageDay,
    AdminAIUsageResponse,
    SubscriptionPlanSummary,
)


# ── PlatformStats schema ─────────────────────────────────────────────────────

class TestPlatformStats:
    def test_valid_stats(self):
        stats = PlatformStats(
            total_users=100,
            active_users_30d=42,
            total_farms=35,
            active_farms_30d=20,
            total_flocks=80,
            active_flocks=55,
            total_ai_queries_30d=1200,
            total_ai_cost_usd_30d=3.75,
            total_notifications_sent_30d=500,
            total_disease_alerts_active=3,
            total_market_prices=120,
        )
        assert stats.total_users == 100
        assert stats.active_farms_30d == 20
        assert stats.total_ai_cost_usd_30d == 3.75

    def test_zero_values_allowed(self):
        stats = PlatformStats(
            total_users=0, active_users_30d=0, total_farms=0,
            active_farms_30d=0, total_flocks=0, active_flocks=0,
            total_ai_queries_30d=0, total_ai_cost_usd_30d=0.0,
            total_notifications_sent_30d=0, total_disease_alerts_active=0,
            total_market_prices=0,
        )
        assert stats.total_users == 0


# ── AdminUserSuspend schema ──────────────────────────────────────────────────

class TestAdminUserSuspend:
    def test_valid_reason(self):
        obj = AdminUserSuspend(reason="Violated terms of service")
        assert len(obj.reason) >= 5

    def test_reason_too_short(self):
        with pytest.raises(Exception):
            AdminUserSuspend(reason="bad")

    def test_reason_too_long(self):
        with pytest.raises(Exception):
            AdminUserSuspend(reason="x" * 501)

    def test_reason_boundary_min(self):
        obj = AdminUserSuspend(reason="12345")
        assert obj.reason == "12345"

    def test_reason_boundary_max(self):
        obj = AdminUserSuspend(reason="x" * 500)
        assert len(obj.reason) == 500


# ── AdminUserQuotaOverride schema ────────────────────────────────────────────

class TestAdminUserQuotaOverride:
    def test_valid_quota(self):
        obj = AdminUserQuotaOverride(monthly_limit=50, reason="Trial extension")
        assert obj.monthly_limit == 50

    def test_null_quota_allowed(self):
        obj = AdminUserQuotaOverride(monthly_limit=None, reason="Reset to default")
        assert obj.monthly_limit is None

    def test_zero_quota_allowed(self):
        obj = AdminUserQuotaOverride(monthly_limit=0, reason="Suspended quota")
        assert obj.monthly_limit == 0

    def test_negative_quota_rejected(self):
        with pytest.raises(Exception):
            AdminUserQuotaOverride(monthly_limit=-1, reason="Invalid quota test")


# ── AdminFarmPlanOverride schema ─────────────────────────────────────────────

class TestAdminFarmPlanOverride:
    def test_free_plan(self):
        obj = AdminFarmPlanOverride(plan_name="free", reason="Downgraded for inactivity")
        assert obj.plan_name == "free"

    def test_starter_plan(self):
        obj = AdminFarmPlanOverride(plan_name="starter", reason="Upgraded per request")
        assert obj.plan_name == "starter"

    def test_pro_plan(self):
        obj = AdminFarmPlanOverride(plan_name="pro", reason="Promotional upgrade")
        assert obj.plan_name == "pro"

    def test_reason_too_short(self):
        with pytest.raises(Exception):
            AdminFarmPlanOverride(plan_name="free", reason="bad")

    def test_reason_too_long(self):
        with pytest.raises(Exception):
            AdminFarmPlanOverride(plan_name="pro", reason="x" * 501)


# ── AdminAIUsageDay schema ────────────────────────────────────────────────────

class TestAdminAIUsageDay:
    def test_valid_day(self):
        day = AdminAIUsageDay(
            date="2025-06-01",
            query_count=45,
            total_tokens=12500,
            cost_usd=0.0125,
            unique_users=12,
        )
        assert day.date == "2025-06-01"
        assert day.cost_usd == 0.0125

    def test_zero_counts_allowed(self):
        day = AdminAIUsageDay(
            date="2025-06-02",
            query_count=0,
            total_tokens=0,
            cost_usd=0.0,
            unique_users=0,
        )
        assert day.query_count == 0


# ── AdminAIUsageResponse schema ───────────────────────────────────────────────

class TestAdminAIUsageResponse:
    def test_full_response(self):
        resp = AdminAIUsageResponse(
            period_days=30,
            total_queries=1500,
            total_tokens=450000,
            total_cost_usd=4.50,
            unique_users=35,
            daily_breakdown=[],
            top_model="gemini",
            fallback_rate_pct=12.5,
        )
        assert resp.period_days == 30
        assert resp.fallback_rate_pct == 12.5

    def test_optional_top_model_null(self):
        resp = AdminAIUsageResponse(
            period_days=7,
            total_queries=0,
            total_tokens=0,
            total_cost_usd=0.0,
            unique_users=0,
            daily_breakdown=[],
            top_model=None,
            fallback_rate_pct=0.0,
        )
        assert resp.top_model is None

    def test_fallback_rate_zero(self):
        resp = AdminAIUsageResponse(
            period_days=14,
            total_queries=100,
            total_tokens=30000,
            total_cost_usd=0.30,
            unique_users=10,
            daily_breakdown=[],
            top_model="gemini",
            fallback_rate_pct=0.0,
        )
        assert resp.fallback_rate_pct == 0.0

    def test_daily_breakdown_populated(self):
        day = AdminAIUsageDay(date="2025-06-01", query_count=10, total_tokens=3000, cost_usd=0.03, unique_users=5)
        resp = AdminAIUsageResponse(
            period_days=1,
            total_queries=10,
            total_tokens=3000,
            total_cost_usd=0.03,
            unique_users=5,
            daily_breakdown=[day],
            top_model="gemini",
            fallback_rate_pct=0.0,
        )
        assert len(resp.daily_breakdown) == 1
        assert resp.daily_breakdown[0].query_count == 10


# ── AdminUserSummary schema ───────────────────────────────────────────────────

class TestAdminUserSummary:
    def test_valid_summary(self):
        summary = AdminUserSummary(
            id=uuid.uuid4(),
            phone_number="+254700000001",
            name="Jane Farmer",
            is_active=True,
            is_verified=True,
            farm_count=2,
            ai_queries_this_month=15,
            created_at=datetime.now(timezone.utc),
        )
        assert summary.is_active is True
        assert summary.farm_count == 2

    def test_name_optional(self):
        summary = AdminUserSummary(
            id=uuid.uuid4(),
            phone_number="+254700000002",
            name=None,
            is_active=False,
            is_verified=False,
            farm_count=0,
            ai_queries_this_month=0,
            created_at=datetime.now(timezone.utc),
        )
        assert summary.name is None

    def test_suspended_user(self):
        summary = AdminUserSummary(
            id=uuid.uuid4(),
            phone_number="+254700000003",
            name="Suspended User",
            is_active=False,
            is_verified=True,
            farm_count=1,
            ai_queries_this_month=0,
            created_at=datetime.now(timezone.utc),
        )
        assert summary.is_active is False
        assert summary.is_verified is True


# ── AdminUserListResponse schema ──────────────────────────────────────────────

class TestAdminUserListResponse:
    def test_empty_list(self):
        resp = AdminUserListResponse(items=[], total=0)
        assert resp.total == 0
        assert len(resp.items) == 0

    def test_with_items(self):
        user = AdminUserSummary(
            id=uuid.uuid4(),
            phone_number="+254700000001",
            name="Test",
            is_active=True,
            is_verified=True,
            farm_count=1,
            ai_queries_this_month=5,
            created_at=datetime.now(timezone.utc),
        )
        resp = AdminUserListResponse(items=[user], total=1)
        assert resp.total == 1
        assert resp.items[0].phone_number == "+254700000001"


# ── AdminFarmSummary schema ───────────────────────────────────────────────────

class TestAdminFarmSummary:
    def test_valid_summary(self):
        summary = AdminFarmSummary(
            id=uuid.uuid4(),
            name="Green Valley Farm",
            owner_phone="+254700000003",
            owner_name="John Farmer",
            subscription_plan="pro",
            member_count=3,
            active_flock_count=2,
            last_log_date="2025-06-01",
            created_at=datetime.now(timezone.utc),
        )
        assert summary.subscription_plan == "pro"
        assert summary.member_count == 3

    def test_optional_fields_null(self):
        summary = AdminFarmSummary(
            id=uuid.uuid4(),
            name="Orphan Farm",
            owner_phone=None,
            owner_name=None,
            subscription_plan="free",
            member_count=1,
            active_flock_count=0,
            last_log_date=None,
            created_at=datetime.now(timezone.utc),
        )
        assert summary.owner_phone is None
        assert summary.last_log_date is None


# ── AdminFarmListResponse schema ──────────────────────────────────────────────

class TestAdminFarmListResponse:
    def test_empty_list(self):
        resp = AdminFarmListResponse(items=[], total=0)
        assert resp.total == 0

    def test_with_farms(self):
        farm = AdminFarmSummary(
            id=uuid.uuid4(),
            name="Test Farm",
            owner_phone="+254700000099",
            owner_name="Owner",
            subscription_plan="starter",
            member_count=2,
            active_flock_count=1,
            last_log_date=None,
            created_at=datetime.now(timezone.utc),
        )
        resp = AdminFarmListResponse(items=[farm], total=1)
        assert resp.items[0].name == "Test Farm"


# ── SubscriptionPlanSummary schema ────────────────────────────────────────────

class TestSubscriptionPlanSummary:
    def test_valid_plan(self):
        plan = SubscriptionPlanSummary(
            id=uuid.uuid4(),
            name="pro",
            display_name="Pro Plan",
            price_kes="2999.00",
            farm_count=18,
        )
        assert plan.name == "pro"
        assert plan.farm_count == 18

    def test_free_plan_zero_farms(self):
        plan = SubscriptionPlanSummary(
            id=uuid.uuid4(),
            name="free",
            display_name="Free Plan",
            price_kes="0.00",
            farm_count=0,
        )
        assert plan.farm_count == 0

    def test_starter_plan(self):
        plan = SubscriptionPlanSummary(
            id=uuid.uuid4(),
            name="starter",
            display_name="Starter Plan",
            price_kes="999.00",
            farm_count=45,
        )
        assert plan.price_kes == "999.00"
