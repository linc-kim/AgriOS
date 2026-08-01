"""
Rabbit Housing (Module 17, Milestone 2) — over HTTP.

Confirms the 5-level hierarchy (rabbitry→building→room→row→cage) with parent
validation, deterministic cage occupancy derived from active rabbits (never
stored), overcrowding detection in the farm summary, and RBAC (workers view but
cannot manage housing; viewers are read-only).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _h(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit/housing"


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _build_hierarchy(client, fid, headers) -> dict:
    rby = (await client.post(f"{_h(fid)}/rabbitries", json={"name": "Main Rabbitry"}, headers=headers)).json()["data"]
    bld = (await client.post(f"{_h(fid)}/buildings", json={"name": "Barn 1", "rabbitry_id": rby["id"]}, headers=headers)).json()["data"]
    room = (await client.post(f"{_h(fid)}/rooms", json={"name": "Room A", "building_id": bld["id"]}, headers=headers)).json()["data"]
    row = (await client.post(f"{_h(fid)}/rows", json={"name": "Row 1", "room_id": room["id"]}, headers=headers)).json()["data"]
    return {"rabbitry": rby, "building": bld, "room": room, "row": row}


class TestHierarchy:
    async def test_full_hierarchy_creates(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = await _build_hierarchy(async_client, fid, auth_headers_owner)
        cage = await async_client.post(
            f"{_h(fid)}/cages", json={"name": "Cage 1", "row_id": h["row"]["id"], "capacity": 3},
            headers=auth_headers_owner,
        )
        assert cage.status_code == 201, cage.text
        assert cage.json()["data"]["cage_type"] == "cage"

    async def test_building_requires_valid_rabbitry(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        import uuid
        r = await async_client.post(
            f"{_h(fid)}/buildings", json={"name": "Orphan", "rabbitry_id": str(uuid.uuid4())},
            headers=auth_headers_owner,
        )
        assert r.status_code == 404


class TestOccupancy:
    async def test_cage_occupancy_derived_from_active_rabbits(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        cage = (await async_client.post(
            f"{_h(fid)}/cages", json={"name": "Cage Occ", "capacity": 5}, headers=auth_headers_owner
        )).json()["data"]
        for i in range(2):
            await async_client.post(
                f"{_rb(fid)}/rabbits", json={"name": f"R{i}", "cage_id": cage["id"]}, headers=auth_headers_owner
            )
        detail = await async_client.get(f"{_h(fid)}/cages/{cage['id']}", headers=auth_headers_owner)
        assert detail.status_code == 200
        occ = detail.json()["data"]["occupancy"]
        assert occ["occupied"]["value"] == 2
        assert occ["available"]["value"] == 3
        assert occ["over_capacity"] is False

    async def test_unknown_capacity_reports_unknown(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        cage = (await async_client.post(
            f"{_h(fid)}/cages", json={"name": "No Cap"}, headers=auth_headers_owner
        )).json()["data"]
        detail = await async_client.get(f"{_h(fid)}/cages/{cage['id']}", headers=auth_headers_owner)
        assert detail.json()["data"]["occupancy"]["capacity"]["label"] == "unknown"

    async def test_summary_flags_overcrowded_cage(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        cage = (await async_client.post(
            f"{_h(fid)}/cages", json={"name": "Tight", "code": "TIGHT", "capacity": 1}, headers=auth_headers_owner
        )).json()["data"]
        for i in range(2):
            await async_client.post(
                f"{_rb(fid)}/rabbits", json={"name": f"C{i}", "cage_id": cage["id"]}, headers=auth_headers_owner
            )
        summary = await async_client.get(f"{_h(fid)}/summary", headers=auth_headers_owner)
        assert summary.status_code == 200
        data = summary.json()["data"]
        assert data["counts"]["cages"] >= 1
        assert any(c["cage_id"] == cage["id"] for c in data["overcrowded_cages"])


class TestRBAC:
    async def test_worker_can_view_but_not_manage_housing(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        view = await async_client.get(f"{_h(fid)}/cages", headers=auth_headers_worker)
        assert view.status_code == 200
        create = await async_client.post(
            f"{_h(fid)}/cages", json={"name": "Nope"}, headers=auth_headers_worker
        )
        assert create.status_code == 403

    async def test_viewer_read_only(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_h(fid)}/rabbitries", headers=auth_headers_viewer)).status_code == 200
        create = await async_client.post(
            f"{_h(fid)}/rabbitries", json={"name": "Nope"}, headers=auth_headers_viewer
        )
        assert create.status_code == 403
