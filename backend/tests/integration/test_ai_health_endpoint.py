"""AI Provider Manager health endpoint (Gate 4)."""

import pytest

pytestmark = pytest.mark.asyncio

_URL = "/api/v1/admin/ai/health"


async def test_ai_health_readable_by_super_admin(async_client, workspace, auth_headers_super_admin):
    r = await async_client.get(_URL, headers=auth_headers_super_admin)
    assert r.status_code == 200
    data = r.json()["data"]
    # Provider configuration block.
    mgr = data["manager"]
    assert mgr["version"]
    assert "registered_providers" in mgr
    assert "routing_policy" in mgr
    assert set(mgr["cache"]) == {"enabled", "ttl_seconds", "entries"}
    # Operational diagnostics.
    assert "providers" in data
    assert "usage" in data
    assert "prompt_safety" in data


async def test_ai_health_never_exposes_secrets(async_client, workspace, auth_headers_super_admin):
    """No key value, env secret, or user content may appear in the diagnostics."""
    import os

    r = await async_client.get(_URL, headers=auth_headers_super_admin)
    body = r.text.lower()
    for needle in ("api_key", "secret", "bearer", "password", "gemini_api_key"):
        assert needle not in body
    for env_key in ("JWT_SECRET", "SECRET_KEY", "DATABASE_URL"):
        val = os.environ.get(env_key, "")
        if len(val) >= 8:
            assert val not in r.text


async def test_ai_health_denied_to_non_admin(async_client, workspace, auth_headers_owner):
    r = await async_client.get(_URL, headers=auth_headers_owner)
    assert r.status_code == 403


async def test_ai_health_requires_auth(async_client, workspace):
    r = await async_client.get(_URL)
    assert r.status_code == 401
