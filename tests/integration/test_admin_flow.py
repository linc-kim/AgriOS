"""
Sprint 8 — Admin Module Integration Tests
Tests: full lifecycle — RBAC, stats, user management, farm oversight, AI usage.
All tests use TestClient with in-memory SQLite via conftest fixtures.
"""

import uuid
import pytest
from httpx import AsyncClient


# ── A-00 RBAC: non-admin blocked ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_requires_super_admin(async_client: AsyncClient, farmer_token: str):
    """Regular farmer cannot access /admin/stats."""
    resp = await async_client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_users_list_requires_super_admin(async_client: AsyncClient, farmer_token: str):
    """Regular farmer cannot list users."""
    resp = await async_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_farms_list_requires_super_admin(async_client: AsyncClient, farmer_token: str):
    """Regular farmer cannot list admin farms."""
    resp = await async_client.get(
        "/api/v1/admin/farms",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_usage_requires_super_admin(async_client: AsyncClient, farmer_token: str):
    """Regular farmer cannot view AI usage dashboard."""
    resp = await async_client.get(
        "/api/v1/admin/ai/usage",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_unauthenticated_blocked(async_client: AsyncClient):
    """Unauthenticated requests to all admin endpoints are rejected."""
    for path in ["/api/v1/admin/stats", "/api/v1/admin/users", "/api/v1/admin/farms"]:
        resp = await async_client.get(path)
        assert resp.status_code in (401, 403), f"{path} should require auth"


# ── A-01 Platform Stats ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_platform_stats_success(async_client: AsyncClient, admin_token: str):
    """super_admin can retrieve platform stats with correct shape."""
    resp = await async_client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    required_keys = [
        "total_users", "active_users_30d", "total_farms", "active_farms_30d",
        "total_flocks", "active_flocks", "total_ai_queries_30d",
        "total_ai_cost_usd_30d", "total_notifications_sent_30d",
        "total_disease_alerts_active", "total_market_prices",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"


@pytest.mark.asyncio
async def test_platform_stats_numeric_fields(async_client: AsyncClient, admin_token: str):
    """All stats fields are non-negative numbers."""
    resp = await async_client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key, value in data.items():
        assert isinstance(value, (int, float)), f"{key} should be numeric"
        assert value >= 0, f"{key} should be non-negative"


# ── A-02 User Management ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_returns_paginated(async_client: AsyncClient, admin_token: str):
    """User list returns items + total."""
    resp = await async_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_list_users_search_no_match(async_client: AsyncClient, admin_token: str):
    """Search with no match returns empty list."""
    resp = await async_client.get(
        "/api/v1/admin/users?search=nonexistent_xyz_12345",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_suspend_user_lifecycle(
    async_client: AsyncClient, admin_token: str, test_user_id: str
):
    """Suspend a user — endpoint returns 200."""
    resp = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Test suspension from integration test"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_restore_user_lifecycle(
    async_client: AsyncClient, admin_token: str, test_user_id: str
):
    """Suspend then restore a user — both return 200."""
    await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Suspension before restore test case"},
    )
    resp = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/restore",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_suspend_nonexistent_user(async_client: AsyncClient, admin_token: str):
    """Suspending a nonexistent user returns 404."""
    resp = await async_client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "Reason for nonexistent user"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suspend_requires_reason(async_client: AsyncClient, admin_token: str, test_user_id: str):
    """Suspend endpoint rejects too-short reason."""
    resp = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/suspend",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"reason": "bad"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_quota_override_valid(
    async_client: AsyncClient, admin_token: str, test_user_id: str
):
    """Quota override sets a monthly limit."""
    resp = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/quota",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"monthly_limit": 100, "reason": "Extended trial period grant"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_quota_override_null_resets(
    async_client: AsyncClient, admin_token: str, test_user_id: str
):
    """Quota override with null resets to default."""
    resp = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/quota",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"monthly_limit": None, "reason": "Resetting quota to plan default"},
    )
    assert resp.status_code == 200


# ── A-03 Farm Management ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_farms_returns_paginated(async_client: AsyncClient, admin_token: str):
    """Farm list returns items + total."""
    resp = await async_client.get(
        "/api/v1/admin/farms",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_list_farms_plan_filter(async_client: AsyncClient, admin_token: str):
    """Farm list with plan_name=free only returns free-plan farms."""
    resp = await async_client.get(
        "/api/v1/admin/farms?plan_name=free",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for farm in data["items"]:
        assert farm["subscription_plan"] == "free"


@pytest.mark.asyncio
async def test_override_farm_plan(
    async_client: AsyncClient, admin_token: str, test_farm_id: str
):
    """Admin can override a farm's subscription plan."""
    resp = await async_client.patch(
        f"/api/v1/admin/farms/{test_farm_id}/plan",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan_name": "pro", "reason": "Promotional upgrade integration test"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_override_plan_nonexistent_farm(async_client: AsyncClient, admin_token: str):
    """Overriding plan on nonexistent farm returns 404."""
    resp = await async_client.patch(
        f"/api/v1/admin/farms/{uuid.uuid4()}/plan",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"plan_name": "pro", "reason": "This farm does not exist at all"},
    )
    assert resp.status_code == 404


# ── A-04 Subscription Plans ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plans(async_client: AsyncClient, admin_token: str):
    """Admin can list subscription plans with required fields."""
    resp = await async_client.get(
        "/api/v1/admin/plans",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for plan in data:
        assert "name" in plan
        assert "price_kes" in plan
        assert "farm_count" in plan


# ── A-07 AI Usage ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_ai_usage_default_period(async_client: AsyncClient, admin_token: str):
    """AI usage endpoint returns correct shape."""
    resp = await async_client.get(
        "/api/v1/admin/ai/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "period_days" in data
    assert "total_queries" in data
    assert "total_cost_usd" in data
    assert "daily_breakdown" in data
    assert "fallback_rate_pct" in data
    assert isinstance(data["daily_breakdown"], list)


@pytest.mark.asyncio
async def test_get_ai_usage_custom_period(async_client: AsyncClient, admin_token: str):
    """AI usage endpoint respects period_days query param."""
    resp = await async_client.get(
        "/api/v1/admin/ai/usage?period_days=7",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["period_days"] == 7


@pytest.mark.asyncio
async def test_ai_usage_fallback_rate_range(async_client: AsyncClient, admin_token: str):
    """Fallback rate is between 0 and 100."""
    resp = await async_client.get(
        "/api/v1/admin/ai/usage",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    rate = resp.json()["fallback_rate_pct"]
    assert 0.0 <= rate <= 100.0
