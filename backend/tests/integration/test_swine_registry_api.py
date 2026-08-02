"""
Swine Registry & Housing (Module 20, Milestone 2) — over HTTP.

These confirm the endpoints wire real farm data through the services:

  * pigs register with SW-##### refs and a 'created' timeline event;
  * swine sex/class tokens are enforced (boar/sow/gilt/barrow), invalid rejected;
  * duplicate ear tags within a farm are rejected;
  * production-stage transitions may not regress along the market path;
  * housing occupancy is derived (never stored), overcrowding + biosecurity surfaced;
  * lifecycle transitions preserve history and guard terminal records;
  * permissions hold (viewer read-only; worker operates but cannot manage housing
    or transact; owner/manager full).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/swine"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"name": "Babe", "sex": "gilt", "purpose": "breeding"}
    body.update(overrides)
    r = await client.post(f"{_sw(farm_id)}/pigs", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestRegistry:
    async def test_register_generates_ref_and_timeline(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pig = await _register(async_client, fid, auth_headers_owner)
        assert pig["internal_ref"].startswith("SW-")
        assert pig["sex"] == "gilt" and pig["status"] == "active"
        tl = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}/timeline", headers=auth_headers_owner)
        assert any(e["event_type"] == "created" for e in tl.json()["data"])

    async def test_invalid_sex_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_sw(fid)}/pigs", json={"name": "X", "sex": "ram"}, headers=auth_headers_owner
        )
        assert r.status_code == 422
        # Valid swine classes are accepted.
        for sex in ("boar", "sow", "gilt", "barrow"):
            ok = await async_client.post(
                f"{_sw(fid)}/pigs", json={"name": sex.title(), "sex": sex}, headers=auth_headers_owner
            )
            assert ok.status_code == 201, ok.text

    async def test_duplicate_ear_tag_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, ear_tag="TAG-1")
        r = await async_client.post(
            f"{_sw(fid)}/pigs", json={"name": "Dup", "sex": "sow", "ear_tag": "TAG-1"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 409

    async def test_production_stage_cannot_regress(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pig = await _register(async_client, fid, auth_headers_owner, sex="barrow", production_stage="finisher")
        # finisher → grower is a backwards jump on the market path.
        bad = await async_client.patch(
            f"{_sw(fid)}/pigs/{pig['id']}", json={"production_stage": "grower"}, headers=auth_headers_owner
        )
        assert bad.status_code == 422
        # finisher → cull (a branch) is allowed.
        ok = await async_client.patch(
            f"{_sw(fid)}/pigs/{pig['id']}", json={"production_stage": "cull"}, headers=auth_headers_owner
        )
        assert ok.status_code == 200 and ok.json()["data"]["production_stage"] == "cull"

    async def test_parent_must_exist_and_not_self(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pig = await _register(async_client, fid, auth_headers_owner)
        # A pig cannot be its own dam.
        r = await async_client.patch(
            f"{_sw(fid)}/pigs/{pig['id']}", json={"dam_id": pig["id"]}, headers=auth_headers_owner
        )
        assert r.status_code == 422
        # Unknown parent → 404.
        r2 = await async_client.patch(
            f"{_sw(fid)}/pigs/{pig['id']}",
            json={"sire_id": "00000000-0000-0000-0000-0000000000ff"}, headers=auth_headers_owner
        )
        assert r2.status_code == 404


class TestLifecycle:
    async def test_sell_makes_terminal_and_guards_further_edits(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pig = await _register(async_client, fid, auth_headers_owner)
        sold = await async_client.post(
            f"{_sw(fid)}/pigs/{pig['id']}/sell",
            json={"buyer_name": "Market", "price": "180.00"}, headers=auth_headers_owner,
        )
        assert sold.status_code == 200 and sold.json()["data"]["status"] == "sold"
        again = await async_client.patch(
            f"{_sw(fid)}/pigs/{pig['id']}", json={"name": "New"}, headers=auth_headers_owner
        )
        assert again.status_code == 409

    async def test_archive_then_restore(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pig = await _register(async_client, fid, auth_headers_owner)
        arch = await async_client.post(
            f"{_sw(fid)}/pigs/{pig['id']}/archive", json={"reason": "test"}, headers=auth_headers_owner
        )
        assert arch.status_code == 200 and arch.json()["data"]["status"] == "archived"
        rest = await async_client.post(
            f"{_sw(fid)}/pigs/{pig['id']}/restore", json={}, headers=auth_headers_owner
        )
        assert rest.status_code == 200 and rest.json()["data"]["status"] == "active"


class TestHousing:
    async def test_pen_occupancy_derived_and_overcrowding_surfaced(
        self, async_client, workspace, auth_headers_owner
    ):
        fid = workspace.farm.id
        pen = await async_client.post(
            f"{_sw(fid)}/housing/pens",
            json={"name": "Finisher 1", "pen_type": "finisher_pen", "capacity": 1,
                  "biosecurity_status": "secure"},
            headers=auth_headers_owner,
        )
        assert pen.status_code == 201, pen.text
        pen_id = pen.json()["data"]["id"]
        # Empty pen: occupancy 0.
        detail = await async_client.get(f"{_sw(fid)}/housing/pens/{pen_id}", headers=auth_headers_owner)
        assert detail.json()["data"]["occupancy"]["occupied"]["value"] == 0
        # Place two pigs into a capacity-1 pen → overcrowded.
        for _ in range(2):
            await _register(async_client, fid, auth_headers_owner, sex="barrow", pen_id=pen_id)
        detail2 = await async_client.get(f"{_sw(fid)}/housing/pens/{pen_id}", headers=auth_headers_owner)
        occ = detail2.json()["data"]["occupancy"]
        assert occ["occupied"]["value"] == 2 and occ["over_capacity"] is True
        summary = await async_client.get(f"{_sw(fid)}/housing/summary", headers=auth_headers_owner)
        over = summary.json()["data"]["overcrowded_pens"]
        assert any(o["id"] == pen_id for o in over)

    async def test_biosecurity_rollup_counts_flagged(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await async_client.post(
            f"{_sw(fid)}/housing/pens",
            json={"name": "Q", "pen_type": "quarantine", "biosecurity_status": "quarantine"},
            headers=auth_headers_owner,
        )
        summary = await async_client.get(f"{_sw(fid)}/housing/summary", headers=auth_headers_owner)
        bio = summary.json()["data"]["biosecurity"]
        assert bio["flagged"]["value"] >= 1


class TestPermissions:
    async def test_viewer_is_read_only(self, async_client, workspace, auth_headers_viewer, auth_headers_owner):
        fid = workspace.farm.id
        # Viewer can list.
        lst = await async_client.get(f"{_sw(fid)}/pigs", headers=auth_headers_viewer)
        assert lst.status_code == 200
        # Viewer cannot register.
        r = await async_client.post(
            f"{_sw(fid)}/pigs", json={"name": "X", "sex": "sow"}, headers=auth_headers_viewer
        )
        assert r.status_code == 403

    async def test_worker_operates_but_cannot_transact_or_manage_housing(
        self, async_client, workspace, auth_headers_worker, auth_headers_owner
    ):
        fid = workspace.farm.id
        # Worker can register a pig.
        pig = await _register(async_client, fid, auth_headers_worker)
        # Worker cannot create a pen (housing management).
        pen = await async_client.post(
            f"{_sw(fid)}/housing/pens", json={"name": "P", "pen_type": "pen"}, headers=auth_headers_worker
        )
        assert pen.status_code == 403
        # Worker cannot sell (transact).
        sell = await async_client.post(
            f"{_sw(fid)}/pigs/{pig['id']}/sell", json={"buyer_name": "M"}, headers=auth_headers_worker
        )
        assert sell.status_code == 403
