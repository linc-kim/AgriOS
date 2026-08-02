"""
Small Ruminant Registry & Housing (Modules 18/19, Milestone 2) — over HTTP.

These confirm the shared endpoints wire real farm data through the services for
BOTH species over one implementation:

  * the same code registers goats and sheep, distinguished only by the species
    path segment; refs are GT-##### / SH-#####;
  * species-appropriate sex is enforced (a goat may be a buck, never a ram);
  * the two workspaces are isolated — a goat never appears in the sheep list;
  * housing occupancy is derived (never stored) and overcrowding is surfaced;
  * lifecycle transitions preserve history and guard terminal records;
  * permissions hold (viewer read-only; worker operates but cannot manage housing
    or transact; owner/manager full);
  * an unknown species path is a 404 (no such workspace).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _register(client, farm_id, species, headers, **overrides) -> dict:
    sex = "doe" if species == "goat" else "ewe"
    body = {"name": "Daisy", "sex": sex, "purpose": "breeding"}
    body.update(overrides)
    r = await client.post(f"{_sr(farm_id, species)}/animals", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestSharedRegistry:
    async def test_goat_and_sheep_share_one_implementation(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        goat = await _register(async_client, fid, "goat", auth_headers_owner)
        sheep = await _register(async_client, fid, "sheep", auth_headers_owner, name="Woolly", sex="ewe")
        assert goat["internal_ref"].startswith("GT-")
        assert sheep["internal_ref"].startswith("SH-")
        assert goat["species"] == "goat" and sheep["species"] == "sheep"
        # A 'created' timeline event exists.
        tl = await async_client.get(
            f"{_sr(fid, 'goat')}/animals/{goat['id']}/timeline", headers=auth_headers_owner
        )
        assert any(e["event_type"] == "created" for e in tl.json()["data"])

    async def test_species_workspaces_are_isolated(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, "goat", auth_headers_owner)
        await _register(async_client, fid, "sheep", auth_headers_owner, sex="ewe")
        goats = await async_client.get(f"{_sr(fid, 'goat')}/animals", headers=auth_headers_owner)
        sheep = await async_client.get(f"{_sr(fid, 'sheep')}/animals", headers=auth_headers_owner)
        assert all(a["species"] == "goat" for a in goats.json()["data"])
        assert all(a["species"] == "sheep" for a in sheep.json()["data"])

    async def test_species_specific_sex_is_enforced(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # A goat is never a ram.
        r = await async_client.post(
            f"{_sr(fid, 'goat')}/animals", json={"name": "X", "sex": "ram"}, headers=auth_headers_owner
        )
        assert r.status_code == 422
        # A sheep is never a doe.
        r2 = await async_client.post(
            f"{_sr(fid, 'sheep')}/animals", json={"name": "Y", "sex": "doe"}, headers=auth_headers_owner
        )
        assert r2.status_code == 422
        # But a wether is valid for both.
        r3 = await async_client.post(
            f"{_sr(fid, 'sheep')}/animals", json={"name": "Z", "sex": "wether"}, headers=auth_headers_owner
        )
        assert r3.status_code == 201

    async def test_unknown_species_is_404(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_sr(workspace.farm.id, 'rabbit')}/animals", headers=auth_headers_owner)
        assert r.status_code == 404

    async def test_duplicate_ear_tag_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, "goat", auth_headers_owner, ear_tag="TAG-1")
        r = await async_client.post(
            f"{_sr(fid, 'goat')}/animals", json={"name": "Dup", "sex": "doe", "ear_tag": "TAG-1"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 409


class TestLifecycle:
    async def test_sell_makes_terminal_and_guards_further_edits(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        goat = await _register(async_client, fid, "goat", auth_headers_owner)
        sold = await async_client.post(
            f"{_sr(fid, 'goat')}/animals/{goat['id']}/sell",
            json={"buyer_name": "Market", "price": "120.00"}, headers=auth_headers_owner,
        )
        assert sold.status_code == 200 and sold.json()["data"]["status"] == "sold"
        # A sold animal cannot be edited further.
        again = await async_client.patch(
            f"{_sr(fid, 'goat')}/animals/{goat['id']}", json={"name": "New"}, headers=auth_headers_owner
        )
        assert again.status_code == 409

    async def test_archive_then_restore(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        goat = await _register(async_client, fid, "goat", auth_headers_owner)
        arch = await async_client.post(
            f"{_sr(fid, 'goat')}/animals/{goat['id']}/archive", json={"reason": "test"},
            headers=auth_headers_owner,
        )
        assert arch.status_code == 200 and arch.json()["data"]["status"] == "archived"
        rest = await async_client.post(
            f"{_sr(fid, 'goat')}/animals/{goat['id']}/restore", json={}, headers=auth_headers_owner
        )
        assert rest.status_code == 200 and rest.json()["data"]["status"] == "active"


class TestHousingOccupancy:
    async def test_pen_occupancy_is_derived_and_overcrowding_surfaced(
        self, async_client, workspace, auth_headers_owner
    ):
        fid = workspace.farm.id
        pen = await async_client.post(
            f"{_sr(fid, 'goat')}/housing/pens",
            json={"name": "Barn A", "pen_type": "barn", "capacity": 1}, headers=auth_headers_owner,
        )
        assert pen.status_code == 201
        pen_id = pen.json()["data"]["id"]

        # Two goats into a capacity-1 pen → overcrowded, occupancy derived.
        for i in range(2):
            a = await _register(async_client, fid, "goat", auth_headers_owner, name=f"G{i}")
            mv = await async_client.post(
                f"{_sr(fid, 'goat')}/animals/{a['id']}/move", json={"pen_id": pen_id},
                headers=auth_headers_owner,
            )
            assert mv.status_code == 200

        detail = await async_client.get(f"{_sr(fid, 'goat')}/housing/pens/{pen_id}", headers=auth_headers_owner)
        occ = detail.json()["data"]["occupancy"]
        assert occ["occupied"]["value"] == 2 and occ["occupied"]["label"] == "recorded"
        assert occ["over_capacity"] is True

        summary = await async_client.get(f"{_sr(fid, 'goat')}/housing/summary", headers=auth_headers_owner)
        s = summary.json()["data"]
        assert s["counts"]["pens"] >= 1
        assert any(p["id"] == pen_id for p in s["overcrowded_pens"])

    async def test_pen_capacity_unknown_is_not_overcrowded(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        pen = await async_client.post(
            f"{_sr(fid, 'sheep')}/housing/pens", json={"name": "Open shed", "pen_type": "shed"},
            headers=auth_headers_owner,
        )
        pen_id = pen.json()["data"]["id"]
        a = await _register(async_client, fid, "sheep", auth_headers_owner, sex="ewe")
        await async_client.post(
            f"{_sr(fid, 'sheep')}/animals/{a['id']}/move", json={"pen_id": pen_id}, headers=auth_headers_owner
        )
        detail = await async_client.get(f"{_sr(fid, 'sheep')}/housing/pens/{pen_id}", headers=auth_headers_owner)
        occ = detail.json()["data"]["occupancy"]
        assert occ["capacity"]["label"] == "unknown"  # never fabricated
        assert occ["over_capacity"] is False


class TestPermissions:
    async def test_viewer_is_read_only(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_sr(fid, 'goat')}/animals", headers=auth_headers_viewer)).status_code == 200
        r = await async_client.post(
            f"{_sr(fid, 'goat')}/animals", json={"name": "X", "sex": "doe"}, headers=auth_headers_viewer
        )
        assert r.status_code == 403

    async def test_worker_operates_but_cannot_manage_housing_or_transact(
        self, async_client, workspace, auth_headers_worker, auth_headers_owner
    ):
        fid = workspace.farm.id
        # Worker can register an animal.
        created = await async_client.post(
            f"{_sr(fid, 'goat')}/animals", json={"name": "W", "sex": "doe"}, headers=auth_headers_worker
        )
        assert created.status_code == 201
        animal_id = created.json()["data"]["id"]
        # Worker cannot create housing (manager concern).
        pen = await async_client.post(
            f"{_sr(fid, 'goat')}/housing/pens", json={"name": "P", "pen_type": "pen"},
            headers=auth_headers_worker,
        )
        assert pen.status_code == 403
        # Worker cannot transact (sell).
        sell = await async_client.post(
            f"{_sr(fid, 'goat')}/animals/{animal_id}/sell", json={"buyer_name": "B"},
            headers=auth_headers_worker,
        )
        assert sell.status_code == 403

    async def test_vet_can_read(self, async_client, workspace, auth_headers_vet):
        r = await async_client.get(f"{_sr(workspace.farm.id, 'goat')}/animals", headers=auth_headers_vet)
        assert r.status_code == 200
