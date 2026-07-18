"""
Greena — Module 10 Admin Platform integration tests.

Covers RBAC (platform admin only), organization management, user management +
audit history, farm management, the audit center, platform analytics, feature
flags, system config / maintenance, system health, background jobs, and the
admin AI assistant.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _ap() -> str:
    return "/api/v1/admin/platform"


# ── RBAC ──────────────────────────────────────────────────────────────────────

async def test_rbac_owner_denied_admin_reads(async_client, auth_headers_owner):
    for path in ("/dashboard", "/analytics", "/organizations", "/users", "/health"):
        r = await async_client.get(f"{_ap()}{path}", headers=auth_headers_owner)
        assert r.status_code == 403, f"{path}: {r.status_code}"


async def test_super_admin_can_read_dashboard(async_client, auth_headers_super_admin):
    r = await async_client.get(f"{_ap()}/dashboard", headers=auth_headers_super_admin)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for key in ("organizations", "farms", "users", "ai_requests_total", "health_status", "maintenance_mode"):
        assert key in d


# ── Organizations ─────────────────────────────────────────────────────────────

async def test_organization_list_and_suspend(async_client, auth_headers_super_admin, integration_session, workspace):
    from app.models.organization import Organization
    org = Organization(name="Acme Poultry", slug="acme-poultry-admin", owner_id=workspace.users["owner"].id,
                       country="KE", timezone="Africa/Nairobi", currency="KES")
    integration_session.add(org)
    await integration_session.commit()

    lst = await async_client.get(f"{_ap()}/organizations?q=acme", headers=auth_headers_super_admin)
    assert lst.status_code == 200, lst.text
    rows = lst.json()["data"]["items"]
    assert any(o["slug"] == "acme-poultry-admin" for o in rows)
    oid = [o for o in rows if o["slug"] == "acme-poultry-admin"][0]["id"]

    sus = await async_client.post(f"{_ap()}/organizations/{oid}/suspend", json={"reason": "non-payment"}, headers=auth_headers_super_admin)
    assert sus.status_code == 200
    detail = await async_client.get(f"{_ap()}/organizations/{oid}", headers=auth_headers_super_admin)
    assert detail.json()["data"]["is_suspended"] is True

    react = await async_client.post(f"{_ap()}/organizations/{oid}/reactivate", json={}, headers=auth_headers_super_admin)
    assert react.status_code == 200

    # Suspend action was audited.
    aud = await async_client.get(f"{_ap()}/audit?action=org.suspend", headers=auth_headers_super_admin)
    assert any(a["resource_type"] == "organization" for a in aud.json()["data"]["items"])


# ── Users ─────────────────────────────────────────────────────────────────────

async def test_user_role_change_force_logout_audit(async_client, auth_headers_super_admin, workspace):
    uid = str(workspace.users["worker"].id)

    role = await async_client.post(f"{_ap()}/users/{uid}/role", json={"role": "farm_manager"}, headers=auth_headers_super_admin)
    assert role.status_code == 200, role.text
    lst = await async_client.get(f"{_ap()}/users?q=Winnie", headers=auth_headers_super_admin)
    mine = [u for u in lst.json()["data"]["items"] if u["id"] == uid]
    assert mine and "farm_manager" in mine[0]["roles"]

    fl = await async_client.post(f"{_ap()}/users/{uid}/force-logout", headers=auth_headers_super_admin)
    assert fl.status_code == 200 and fl.json()["data"]["sessions_revoked"] >= 0

    hist = await async_client.get(f"{_ap()}/users/{uid}/audit", headers=auth_headers_super_admin)
    assert hist.status_code == 200
    assert any(a["action"] == "user.role_change" for a in hist.json()["data"])

    # Disable + reactivate.
    dis = await async_client.post(f"{_ap()}/users/{uid}/disable", json={"reason": "policy"}, headers=auth_headers_super_admin)
    assert dis.status_code == 200 and dis.json()["data"]["is_active"] is False
    await async_client.post(f"{_ap()}/users/{uid}/reactivate", headers=auth_headers_super_admin)

    lh = await async_client.get(f"{_ap()}/users/{uid}/login-history", headers=auth_headers_super_admin)
    assert lh.status_code == 200


# ── Farms ─────────────────────────────────────────────────────────────────────

async def test_farm_archive_restore_and_stats(async_client, auth_headers_super_admin, test_farm):
    arc = await async_client.post(f"{_ap()}/farms/{test_farm.id}/archive", json={"reason": "dormant"}, headers=auth_headers_super_admin)
    assert arc.status_code == 200
    stats = await async_client.get(f"{_ap()}/farms/{test_farm.id}/stats", headers=auth_headers_super_admin)
    assert stats.status_code == 200
    d = stats.json()["data"]
    assert "net_profit" in d and "ai_requests" in d
    await async_client.post(f"{_ap()}/farms/{test_farm.id}/restore", headers=auth_headers_super_admin)


# ── Analytics ─────────────────────────────────────────────────────────────────

async def test_analytics(async_client, auth_headers_super_admin):
    r = await async_client.get(f"{_ap()}/analytics", headers=auth_headers_super_admin)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for key in ("total_organizations", "ai_gemini", "ai_claude", "ai_offline", "subscription_breakdown", "growth", "top_farms"):
        assert key in d
    assert len(d["growth"]) == 6


# ── Feature flags ─────────────────────────────────────────────────────────────

async def test_feature_flags(async_client, auth_headers_super_admin):
    lst = await async_client.get(f"{_ap()}/feature-flags", headers=auth_headers_super_admin)
    assert lst.status_code == 200
    keys = {f["flag_key"] for f in lst.json()["data"]}
    assert "aria" in keys and "feed" in keys

    disabled = await async_client.post(f"{_ap()}/feature-flags", json={"flag_key": "automation", "is_enabled": False}, headers=auth_headers_super_admin)
    assert disabled.status_code == 200 and disabled.json()["data"]["is_enabled"] is False


# ── System config / maintenance ───────────────────────────────────────────────

async def test_system_config_and_maintenance(async_client, auth_headers_super_admin):
    cfg = await async_client.get(f"{_ap()}/system-config", headers=auth_headers_super_admin)
    assert cfg.status_code == 200
    assert cfg.json()["data"]["maintenance_mode"] is False

    upd = await async_client.patch(f"{_ap()}/system-config", json={
        "maintenance_mode": True, "banner_message": "Scheduled maintenance tonight."}, headers=auth_headers_super_admin)
    assert upd.status_code == 200
    assert upd.json()["data"]["maintenance_mode"] is True
    assert upd.json()["data"]["banner_message"] == "Scheduled maintenance tonight."

    # Reset.
    await async_client.patch(f"{_ap()}/system-config", json={"maintenance_mode": False}, headers=auth_headers_super_admin)


# ── Health + jobs ─────────────────────────────────────────────────────────────

async def test_health_and_jobs(async_client, auth_headers_super_admin):
    h = await async_client.get(f"{_ap()}/health", headers=auth_headers_super_admin)
    assert h.status_code == 200
    d = h.json()["data"]
    assert d["status"] in ("ok", "degraded")
    assert any(c["name"] == "Database" for c in d["components"])
    assert d["uptime_seconds"] >= 0

    run = await async_client.post(f"{_ap()}/jobs/run", json={"name": "cleanup_expired_sessions"}, headers=auth_headers_super_admin)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["status"] == "success"

    jobs = await async_client.get(f"{_ap()}/jobs", headers=auth_headers_super_admin)
    assert jobs.status_code == 200
    assert jobs.json()["data"]["success"] >= 1

    # Unknown job rejected.
    bad = await async_client.post(f"{_ap()}/jobs/run", json={"name": "definitely_not_a_job"}, headers=auth_headers_super_admin)
    assert bad.status_code == 422


# ── Admin AI ──────────────────────────────────────────────────────────────────

async def test_admin_ai_ask(async_client, auth_headers_super_admin):
    r = await async_client.post(f"{_ap()}/ai/ask", json={"question": "How many AI requests this month and which farms use it most?"}, headers=auth_headers_super_admin)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["provider"] in ("offline", "gemini", "claude")
    assert "ai_usage" in d["sources"]
    assert d["answer"]
