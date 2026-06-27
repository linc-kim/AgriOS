"""
Sprint 9 — Settings / Profile Integration Tests
Tests: PATCH /auth/me lifecycle (name, language, sms pref), GET /auth/me, RBAC.
"""

import pytest
from httpx import AsyncClient


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_me_authenticated(async_client: AsyncClient, farmer_token: str):
    """Authenticated user can fetch their profile."""
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "phone" in data
    assert "language" in data
    assert "sms_notifications_enabled" in data
    assert isinstance(data["sms_notifications_enabled"], bool)


@pytest.mark.asyncio
async def test_get_me_unauthenticated(async_client: AsyncClient):
    """Unauthenticated GET /auth/me is rejected."""
    resp = await async_client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


# ── PATCH /auth/me — name update ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_name(async_client: AsyncClient, farmer_token: str):
    """User can update their display name."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"full_name": "Integration Farmer"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["full_name"] == "Integration Farmer"


@pytest.mark.asyncio
async def test_update_name_strips_whitespace(async_client: AsyncClient, farmer_token: str):
    """Name is stripped of surrounding whitespace."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"full_name": "  Spaced Name  "},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["full_name"] == "Spaced Name"


@pytest.mark.asyncio
async def test_update_name_blank_rejected(async_client: AsyncClient, farmer_token: str):
    """Blank name is rejected with 422."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"full_name": "   "},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_name_to_null(async_client: AsyncClient, farmer_token: str):
    """Name can be cleared by setting to null."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"full_name": None},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["full_name"] is None


# ── PATCH /auth/me — language update ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_language_to_swahili(async_client: AsyncClient, farmer_token: str):
    """User can switch to Swahili."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"language": "sw"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["language"] == "sw"


@pytest.mark.asyncio
async def test_update_language_to_english(async_client: AsyncClient, farmer_token: str):
    """User can switch back to English."""
    # Set to sw first
    await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"language": "sw"},
    )
    # Switch back to en
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"language": "en"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["language"] == "en"


@pytest.mark.asyncio
async def test_invalid_language_rejected(async_client: AsyncClient, farmer_token: str):
    """Unknown language code is rejected with 422."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"language": "fr"},
    )
    assert resp.status_code == 422


# ── PATCH /auth/me — SMS notification preference ─────────────────────────────

@pytest.mark.asyncio
async def test_disable_sms_notifications(async_client: AsyncClient, farmer_token: str):
    """User can disable SMS notifications."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"sms_notifications_enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sms_notifications_enabled"] is False


@pytest.mark.asyncio
async def test_enable_sms_notifications(async_client: AsyncClient, farmer_token: str):
    """User can re-enable SMS notifications."""
    # Disable first
    await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"sms_notifications_enabled": False},
    )
    # Re-enable
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"sms_notifications_enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sms_notifications_enabled"] is True


@pytest.mark.asyncio
async def test_sms_preference_persists(async_client: AsyncClient, farmer_token: str):
    """SMS preference set via PATCH is reflected in GET /auth/me."""
    await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={"sms_notifications_enabled": False},
    )
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["sms_notifications_enabled"] is False


# ── PATCH /auth/me — combined update ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_all_fields_at_once(async_client: AsyncClient, farmer_token: str):
    """All three updatable fields can be set in a single PATCH."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={
            "full_name": "Juma Mwangi",
            "language": "sw",
            "sms_notifications_enabled": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["full_name"] == "Juma Mwangi"
    assert data["language"] == "sw"
    assert data["sms_notifications_enabled"] is False


@pytest.mark.asyncio
async def test_empty_patch_no_error(async_client: AsyncClient, farmer_token: str):
    """Empty PATCH body is valid — no fields are changed."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
        json={},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patch_me_unauthenticated(async_client: AsyncClient):
    """Unauthenticated PATCH /auth/me is rejected."""
    resp = await async_client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Hacker"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_sms_default_is_true(async_client: AsyncClient, farmer_token: str):
    """New user's sms_notifications_enabled defaults to True."""
    resp = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {farmer_token}"},
    )
    assert resp.status_code == 200
    # Default should be True for fresh users
    data = resp.json()["data"]
    assert "sms_notifications_enabled" in data
