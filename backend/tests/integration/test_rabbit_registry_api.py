"""
Rabbit Registry & Catalog (Module 17, Milestone 2) — over HTTP.

Confirms rabbit registration (auto internal_ref, duplicate-ear-tag guard),
listing/filtering/pagination, edit, the movement + lifecycle transitions
(archive/restore/transfer/sell/death) with terminal guards and timeline events,
plus RBAC grading and farm isolation. Catalog: breeds (org-level) and bloodlines
(farm-level).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"name": "Thumper", "sex": "doe", "purpose": "breeding"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestRegistry:
    async def test_register_auto_generates_internal_ref(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        data = await _register(async_client, fid, auth_headers_owner)
        assert data["internal_ref"].startswith("RB-")
        assert data["status"] == "active"
        assert data["sex"] == "doe"

    async def test_duplicate_ear_tag_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, ear_tag="EAR-001")
        r = await async_client.post(
            f"{_rb(fid)}/rabbits", json={"ear_tag": "EAR-001"}, headers=auth_headers_owner
        )
        assert r.status_code == 409, r.text

    async def test_invalid_sex_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.post(f"{_rb(fid)}/rabbits", json={"sex": "male"}, headers=auth_headers_owner)
        assert r.status_code == 422  # rabbit domain uses buck/doe/unknown

    async def test_list_filters_and_pagination(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, sex="buck", name="Bucky")
        await _register(async_client, fid, auth_headers_owner, sex="doe", name="Flopsy")
        r = await async_client.get(f"{_rb(fid)}/rabbits?sex=buck&limit=10", headers=auth_headers_owner)
        assert r.status_code == 200
        body = r.json()
        assert all(x["sex"] == "buck" for x in body["data"])
        assert body["meta"]["total"] >= 1

    async def test_detail_and_edit(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        upd = await async_client.patch(
            f"{_rb(fid)}/rabbits/{rid}", json={"color": "chestnut", "lifecycle_stage": "grower"},
            headers=auth_headers_owner,
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["data"]["color"] == "chestnut"
        detail = await async_client.get(f"{_rb(fid)}/rabbits/{rid}", headers=auth_headers_owner)
        assert detail.json()["data"]["lifecycle_stage"] == "grower"

    async def test_cannot_be_own_parent(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        bad = await async_client.patch(
            f"{_rb(fid)}/rabbits/{rid}", json={"sire_id": rid}, headers=auth_headers_owner
        )
        assert bad.status_code == 422


class TestLifecycle:
    async def test_archive_restore_cycle(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        arch = await async_client.post(f"{_rb(fid)}/rabbits/{rid}/archive", json={"reason": "off-site"}, headers=auth_headers_owner)
        assert arch.status_code == 200 and arch.json()["data"]["status"] == "archived"
        rest = await async_client.post(f"{_rb(fid)}/rabbits/{rid}/restore", headers=auth_headers_owner)
        assert rest.status_code == 200 and rest.json()["data"]["status"] == "active"

    async def test_sale_is_terminal(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        sold = await async_client.post(
            f"{_rb(fid)}/rabbits/{rid}/sell", json={"buyer_name": "Market Co", "price": 1500, "currency": "KES"},
            headers=auth_headers_owner,
        )
        assert sold.status_code == 200 and sold.json()["data"]["status"] == "sold"
        # Terminal — further transitions are rejected.
        again = await async_client.post(
            f"{_rb(fid)}/rabbits/{rid}/death", json={"cause": "unknown"}, headers=auth_headers_owner
        )
        assert again.status_code == 409

    async def test_timeline_accumulates_events(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        await async_client.patch(f"{_rb(fid)}/rabbits/{rid}", json={"notes": "healthy"}, headers=auth_headers_owner)
        tl = await async_client.get(f"{_rb(fid)}/rabbits/{rid}/timeline", headers=auth_headers_owner)
        assert tl.status_code == 200
        types = {e["event_type"] for e in tl.json()["data"]}
        assert "created" in types and "updated" in types


class TestRBAC:
    async def test_worker_can_register_but_not_archive_or_transact(
        self, async_client, workspace, auth_headers_worker
    ):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_worker)
        rid = r["id"]
        arch = await async_client.post(f"{_rb(fid)}/rabbits/{rid}/archive", json={}, headers=auth_headers_worker)
        assert arch.status_code == 403
        sell = await async_client.post(
            f"{_rb(fid)}/rabbits/{rid}/sell", json={"buyer_name": "X"}, headers=auth_headers_worker
        )
        assert sell.status_code == 403

    async def test_viewer_cannot_register(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        r = await async_client.post(f"{_rb(fid)}/rabbits", json={}, headers=auth_headers_viewer)
        assert r.status_code == 403


class TestIsolation:
    async def test_rabbit_not_visible_from_other_farm(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        other = workspace.farm_b.id
        r = await _register(async_client, fid, auth_headers_owner)
        rid = r["id"]
        cross = await async_client.get(f"{_rb(other)}/rabbits/{rid}", headers=auth_headers_owner)
        assert cross.status_code == 404


class TestCatalog:
    async def test_create_and_list_breed(self, async_client, workspace, auth_headers_manager):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_rb(fid)}/breeds",
            json={"name": "New Zealand White", "category": "commercial_meat", "production_purpose": "meat"},
            headers=auth_headers_manager,
        )
        assert r.status_code == 201, r.text
        lst = await async_client.get(f"{_rb(fid)}/breeds", headers=auth_headers_manager)
        assert any(b["name"] == "New Zealand White" for b in lst.json()["data"])

    async def test_worker_cannot_create_breed(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_rb(fid)}/breeds", json={"name": "X", "category": "pet"}, headers=auth_headers_worker
        )
        assert r.status_code == 403

    async def test_bloodline_create_and_list(self, async_client, workspace, auth_headers_manager):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_rb(fid)}/bloodlines", json={"name": "Champion Line", "code": "CL-1"},
            headers=auth_headers_manager,
        )
        assert r.status_code == 201, r.text
        lst = await async_client.get(f"{_rb(fid)}/bloodlines", headers=auth_headers_manager)
        assert any(b["code"] == "CL-1" for b in lst.json()["data"])
