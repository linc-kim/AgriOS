"""
Write-path IDOR + cross-organization isolation (Gate 3 — Security §10, Doc 4 §17).

The read sweep (test_tenant_isolation_sweep.py) proves non-members cannot *read*
another farm's data. This module proves the write and cross-org halves:

  * no farm-scoped POST route accepts a non-member (all 116 runtime-discovered),
  * a denied write leaves **no state behind** (owner-verified before/after),
  * a user who owns a farm in a *different organization* is isolated both ways.

Pure integration assertions on the rolled-back connection; no migrations.
"""

import re

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.auth import Role, User, UserRole
from app.models.farm import Farm, FarmMember, SubscriptionPlan
from app.models.organization import Organization

pytestmark = pytest.mark.asyncio


async def _roles(session) -> dict[str, Role]:
    return {r.name: r for r in (await session.execute(select(Role))).scalars().all()}


async def _make_outsider(integration_session, phone: str) -> User:
    """A valid, active user with a platform role but no membership of any workspace farm."""
    roles = await _roles(integration_session)
    user = User(phone=phone, full_name="Owen Outsider", is_phone_verified=True, is_active=True)
    integration_session.add(user)
    await integration_session.flush()
    integration_session.add(UserRole(user_id=user.id, role_id=roles["farm_owner"].id, farm_id=None))
    await integration_session.commit()
    return user


def _iter_api_routes(routes):
    """Yield every leaf route (with ``methods``/``path``), recursing into
    included/mounted routers.

    FastAPI 0.141 no longer flattens ``include_router`` routes into
    ``app.routes``; it inserts an opaque ``_IncludedRouter`` node (whose
    sub-routes live on ``.original_router``), and nests further includes.
    Walking only the top level would find 0 farm-scoped routes, silently
    turning this IDOR sweep into a no-op — so recurse the tree.
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


def _farm_scoped_post_routes() -> list[str]:
    from app.main import app

    out: set[str] = set()
    for route in _iter_api_routes(app.routes):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if re.findall(r"{([^}]+)}", path) == ["farm_id"] and "POST" in methods:
            out.add(path)
    return sorted(out)


async def test_all_farm_scoped_posts_deny_outsider(async_client, workspace, integration_session):
    """No farm-scoped POST route accepts a non-member (runtime-discovered)."""
    user = await _make_outsider(integration_session, "+254790000201")
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    fid = str(workspace.farm.id)

    routes = _farm_scoped_post_routes()
    assert len(routes) > 80, f"route discovery looks wrong: {len(routes)}"

    accepted = []
    for template in routes:
        path = template.replace("{farm_id}", fid)
        resp = await async_client.post(path, json={}, headers=headers)
        if 200 <= resp.status_code < 300:
            accepted.append((template, resp.status_code))
    assert not accepted, f"{len(accepted)} write route(s) accepted a non-member: {accepted[:20]}"


async def test_outsider_write_produces_no_state_change(
    async_client, workspace, integration_session, auth_headers_owner
):
    """A denied outsider create writes nothing — owner sees an unchanged list."""
    fid = str(workspace.farm.id)
    cats = f"/api/v1/farms/{fid}/finance/categories"

    before = await async_client.get(cats, headers=auth_headers_owner)
    assert before.status_code == 200
    baseline = before.json()["data"]

    user = await _make_outsider(integration_session, "+254790000202")
    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
    resp = await async_client.post(
        cats, json={"name": "Outsider Injected", "kind": "expense"}, headers=headers
    )
    assert not (200 <= resp.status_code < 300), f"outsider create succeeded: {resp.status_code}"

    after = await async_client.get(cats, headers=auth_headers_owner)
    assert after.status_code == 200
    names = [c.get("name") for c in after.json()["data"]]
    assert "Outsider Injected" not in names
    assert len(after.json()["data"]) == len(baseline)


async def test_cross_org_farm_isolation(
    async_client, workspace, integration_session, auth_headers_owner
):
    """A user who owns a farm in a different organization is isolated in both directions."""
    roles = await _roles(integration_session)
    free = (
        await integration_session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
        )
    ).scalar_one()

    rival = User(phone="+254790000203", full_name="Rival Owner", is_phone_verified=True, is_active=True)
    integration_session.add(rival)
    await integration_session.flush()
    integration_session.add(UserRole(user_id=rival.id, role_id=roles["farm_owner"].id, farm_id=None))

    org_b = Organization(name="Rival Org", slug=f"rival-{rival.id.hex[:8]}", owner_id=rival.id)
    integration_session.add(org_b)
    await integration_session.flush()

    farm_b = Farm(
        name="Rival Farm", county="Nairobi", location="Elsewhere", owner_id=rival.id,
        plan_id=free.id, is_active=True, timezone="Africa/Nairobi", organization_id=org_b.id,
    )
    integration_session.add(farm_b)
    await integration_session.flush()
    integration_session.add(
        FarmMember(
            farm_id=farm_b.id, user_id=rival.id, role_id=roles["farm_owner"].id,
            phone=rival.phone, status="active", invited_by=rival.id,
        )
    )
    await integration_session.commit()

    rival_headers = {"Authorization": f"Bearer {create_access_token(str(rival.id))}"}

    # (a) rival (org B) cannot read the workspace org's farm (org A)
    a = await async_client.get(f"/api/v1/farms/{workspace.farm.id}", headers=rival_headers)
    assert a.status_code == 403, f"cross-org read into workspace farm: {a.status_code}"

    # (b) workspace owner (org A) cannot read the rival org's farm (org B)
    b = await async_client.get(f"/api/v1/farms/{farm_b.id}", headers=auth_headers_owner)
    assert b.status_code == 403, f"cross-org read into rival farm: {b.status_code}"
