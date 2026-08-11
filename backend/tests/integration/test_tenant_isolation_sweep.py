"""
Tenant-isolation / cross-farm IDOR regression sweep (Gate 2 — Security Hardening).

The standards make cross-tenant isolation the single most important security
property (Master Index §27–31; Gap-Matrix Doc 2 §25–26; Execution Doc 4 §17, §81,
§104 — "a test suite with no tenant-isolation tests is inadequate"). The existing
integration harness makes every workspace user a member of *both* farms, so it
cannot express the one case that matters most: a valid, authenticated user who is
**not** a member of the target farm.

This module adds that case. It provisions an *outsider* — a real, active user with
a platform role but no membership of ``workspace.farm`` — and proves that:

  * a curated cross-section of farm-scoped GET endpoints denies them (403/404),
  * **every** ``/farms/{farm_id}/…`` GET route (discovered at runtime) denies them
    — no route leaks another farm's data (no 2xx),
  * ARIA/AI context inherits the caller's permissions (AI is not a way around
    authorization — Master Index §29, Doc 4 §52–54),
  * the same routes reject unauthenticated requests (401).

These are pure read assertions against the rolled-back integration connection; they
add no migrations and mutate no state.
"""

import re

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.auth import Role, User, UserRole

pytestmark = pytest.mark.asyncio


# ── Outsider provisioning ─────────────────────────────────────────────────────

async def _make_outsider_token(integration_session, phone: str) -> str:
    """
    A valid, active user holding a platform ``farm_owner`` role but **no**
    FarmMember row for any workspace farm. Committed on the shared per-test
    connection so ``async_client`` (same connection) resolves the token.
    """
    roles = {
        r.name: r
        for r in (await integration_session.execute(select(Role))).scalars().all()
    }
    user = User(
        phone=phone,
        full_name="Owen Outsider",
        is_phone_verified=True,
        is_active=True,
    )
    integration_session.add(user)
    await integration_session.flush()
    integration_session.add(
        UserRole(user_id=user.id, role_id=roles["farm_owner"].id, farm_id=None)
    )
    await integration_session.commit()
    return create_access_token(str(user.id))


def _iter_api_routes(routes):
    """Yield every leaf route (with ``methods``/``path``), recursing into
    included/mounted routers.

    FastAPI 0.141 no longer flattens ``include_router`` routes into
    ``app.routes``; it inserts an opaque ``_IncludedRouter`` node (whose
    sub-routes live on ``.original_router``), and nests further includes.
    Walking only the top level would find 0 farm-scoped routes, silently
    turning this isolation sweep into a no-op — so recurse the tree.
    """
    for route in routes:
        sub = None
        if type(route).__name__ == "_IncludedRouter":
            sub = getattr(getattr(route, "original_router", None), "routes", None)
        elif hasattr(route, "routes"):
            sub = route.routes
        if sub:
            yield from _iter_api_routes(sub)
        if getattr(route, "path", None) and hasattr(route, "methods"):
            yield route


def _farm_scoped_get_routes() -> list[str]:
    """Every GET route whose only path parameter is ``farm_id`` (runtime-discovered)."""
    from app.main import app

    routes: set[str] = set()
    for route in _iter_api_routes(app.routes):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if re.findall(r"{([^}]+)}", path) == ["farm_id"] and "GET" in methods:
            routes.add(path)
    return sorted(routes)


# A readable cross-section spanning every launch-module family. Each is a
# farm-scoped GET that runs through the farm-access chokepoint.
_CURATED = [
    "/api/v1/farms/{fid}",
    "/api/v1/farms/{fid}/flocks",
    "/api/v1/farms/{fid}/finance",
    "/api/v1/farms/{fid}/health/summary",
    "/api/v1/farms/{fid}/automation/reminders",
    "/api/v1/farms/{fid}/aviculture/birds",
    "/api/v1/farms/{fid}/bsf/batches",
    "/api/v1/farms/{fid}/rabbit/breeds",
    "/api/v1/farms/{fid}/operations/routines",
    "/api/v1/farms/{fid}/data/exports",
]

# Deny codes that all represent "you are not allowed to see this farm's data".
# 403 (FarmAccessException), 404 (scoped-out resource), 422 (a required query
# param rejected before the body ran — still no data returned).
_DENY = {401, 403, 404, 422}


async def test_curated_farm_endpoints_deny_outsider(async_client, workspace, integration_session):
    """A non-member is refused on a representative endpoint from every module family."""
    token = await _make_outsider_token(integration_session, "+254790000101")
    headers = {"Authorization": f"Bearer {token}"}
    fid = str(workspace.farm.id)

    leaked = []
    for template in _CURATED:
        path = template.replace("{fid}", fid)
        resp = await async_client.get(path, headers=headers)
        if 200 <= resp.status_code < 300:
            leaked.append((path, resp.status_code))
        else:
            assert resp.status_code in _DENY, f"{path} -> unexpected {resp.status_code}"
    assert not leaked, f"Cross-farm data leaked to a non-member: {leaked}"


async def test_all_farm_scoped_gets_deny_outsider(async_client, workspace, integration_session):
    """
    The comprehensive guarantee: NO ``/farms/{farm_id}/…`` GET route returns 2xx to a
    user who is not a member of that farm. Runtime-discovered so new modules are
    covered automatically.
    """
    token = await _make_outsider_token(integration_session, "+254790000102")
    headers = {"Authorization": f"Bearer {token}"}
    fid = str(workspace.farm.id)

    routes = _farm_scoped_get_routes()
    assert len(routes) > 150, f"Route discovery looks wrong: only {len(routes)} routes"

    leaked = []
    server_errors = []
    for template in routes:
        path = template.replace("{farm_id}", fid)
        resp = await async_client.get(path, headers=headers)
        if 200 <= resp.status_code < 300:
            leaked.append((template, resp.status_code))
        elif resp.status_code >= 500:
            server_errors.append((template, resp.status_code))

    # The hard security property: nothing leaks to a non-member.
    assert not leaked, f"{len(leaked)} farm-scoped GET(s) leaked to a non-member: {leaked[:20]}"
    # 5xx to an unauthorized caller is not a data leak, but it means the access
    # check ran after handler work — surface it rather than hide it.
    assert not server_errors, f"{len(server_errors)} route(s) 5xx'd for an outsider: {server_errors[:20]}"


async def test_aria_context_denied_to_outsider(async_client, workspace, integration_session):
    """
    AI context must inherit the caller's permissions — ARIA is not a shortcut around
    authorization (Master Index §29; Doc 4 §52–54). A non-member cannot read another
    farm's AI/ARIA context.
    """
    token = await _make_outsider_token(integration_session, "+254790000103")
    headers = {"Authorization": f"Bearer {token}"}
    fid = str(workspace.farm.id)

    for path in (
        f"/api/v1/farms/{fid}/ai/context",
        f"/api/v1/farms/{fid}/aria/insights",
        f"/api/v1/farms/{fid}/aria/briefing",
    ):
        resp = await async_client.get(path, headers=headers)
        assert resp.status_code in _DENY, f"{path} -> {resp.status_code} (expected deny)"
        assert not (200 <= resp.status_code < 300)


async def test_farm_scoped_gets_require_authentication(async_client, workspace):
    """No token at all → 401 on farm-scoped endpoints."""
    fid = str(workspace.farm.id)
    for path in (
        f"/api/v1/farms/{fid}",
        f"/api/v1/farms/{fid}/finance",
        f"/api/v1/farms/{fid}/ai/context",
    ):
        resp = await async_client.get(path)
        assert resp.status_code == 401, f"{path} -> {resp.status_code} (expected 401)"
