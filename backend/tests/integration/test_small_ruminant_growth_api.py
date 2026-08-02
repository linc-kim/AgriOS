"""
Small Ruminant Growth & Feed (Modules 18/19, Milestone 4) — over HTTP.

Weights are immutable and sync the animal's current weight; growth analysis is
deterministic (ADG from two dated weights); the feeding log records facts and
computes FCR from the recorded weight gain. Permissions hold.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _animal(client, fid, species, headers, sex="doe") -> str:
    r = await client.post(f"{_sr(fid, species)}/animals",
                          json={"name": "Grower", "sex": sex, "date_of_birth": "2026-01-01"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestGrowth:
    async def test_weights_are_immutable_and_sync_current_weight(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}"
        for on, kg in [("2026-01-01", "3.5"), ("2026-01-31", "9.5")]:
            r = await async_client.post(f"{base}/animals/{aid}/weights",
                                        json={"recorded_on": on, "weight_kg": kg}, headers=auth_headers_owner)
            assert r.status_code == 201, r.text
        # Two immutable records exist.
        hist = await async_client.get(f"{base}/animals/{aid}/weights", headers=auth_headers_owner)
        assert len(hist.json()["data"]) == 2
        # Animal's current weight mirrors the latest record.
        detail = await async_client.get(f"{base}/animals/{aid}", headers=auth_headers_owner)
        assert detail.json()["data"]["current_weight_kg"] == "9.500"
        # Growth analysis computes ADG deterministically (6kg / 30d = 0.2).
        growth = await async_client.get(f"{base}/animals/{aid}/growth", headers=auth_headers_owner)
        adg = growth.json()["data"]["analysis"]["average_daily_gain"]
        assert adg["label"] == "calculated" and adg["value"] == 0.2

    async def test_growth_unknown_without_two_weights(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "sheep", auth_headers_owner, sex="ewe")
        g = await async_client.get(f"{_sr(fid, 'sheep')}/animals/{aid}/growth", headers=auth_headers_owner)
        assert g.json()["data"]["analysis"]["average_daily_gain"]["label"] == "unknown"


class TestFeed:
    async def test_manual_feeding_and_fcr(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_owner)
        base = f"{_sr(fid, 'goat')}"
        # Two weights → 4kg gain.
        await async_client.post(f"{base}/animals/{aid}/weights",
                                json={"recorded_on": "2026-01-01", "weight_kg": "4.0"}, headers=auth_headers_owner)
        await async_client.post(f"{base}/animals/{aid}/weights",
                                json={"recorded_on": "2026-02-01", "weight_kg": "8.0"}, headers=auth_headers_owner)
        # Manual feeding (no Inventory item) — allowed for hobby scale.
        fr = await async_client.post(f"{base}/feed",
                                     json={"animal_id": aid, "quantity_kg": "10.0", "fed_on": "2026-01-15",
                                           "feed_type": "hay", "cost": "20.0"}, headers=auth_headers_owner)
        assert fr.status_code == 201 and fr.json()["data"]["inventory_movement_id"] is None
        summary = await async_client.get(f"{base}/feed/summary?animal_id={aid}", headers=auth_headers_owner)
        s = summary.json()["data"]["summary"]
        assert s["total_feed_kg"]["value"] == 10.0
        assert s["feed_conversion_ratio"]["value"] == 2.5  # 10kg feed / 4kg gain

    async def test_permissions(self, async_client, workspace, auth_headers_worker, auth_headers_viewer):
        fid = workspace.farm.id
        aid = await _animal(async_client, fid, "goat", auth_headers_worker)
        base = f"{_sr(fid, 'goat')}"
        # Worker can log weights and feed (operational).
        w = await async_client.post(f"{base}/animals/{aid}/weights",
                                    json={"recorded_on": "2026-01-01", "weight_kg": "5.0"}, headers=auth_headers_worker)
        assert w.status_code == 201
        f_ = await async_client.post(f"{base}/feed",
                                     json={"animal_id": aid, "quantity_kg": "2.0", "fed_on": "2026-01-02"},
                                     headers=auth_headers_worker)
        assert f_.status_code == 201
        # Viewer cannot write.
        denied = await async_client.post(f"{base}/animals/{aid}/weights",
                                         json={"recorded_on": "2026-01-03", "weight_kg": "6.0"},
                                         headers=auth_headers_viewer)
        assert denied.status_code == 403
