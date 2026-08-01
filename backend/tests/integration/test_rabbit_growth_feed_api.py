"""
Rabbit Growth, Weight & Feed (Module 17, Milestone 4) — over HTTP.

Confirms immutable weight recording (with current-weight sync), deterministic
growth analysis incl. breed-curve deviation, feeding both manually and via the
reused platform Inventory module (a consumption movement decrements stock and
snapshots the cost with no double-count), FCR, and RBAC.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


def _inv(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/inventory"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestWeightAndGrowth:
    async def test_record_weight_syncs_current_and_lists(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner, date_of_birth="2026-01-01")
        rid = r["id"]
        w1 = await async_client.post(
            f"{_rb(fid)}/rabbits/{rid}/weights",
            json={"recorded_on": "2026-01-08", "weight_g": 200}, headers=auth_headers_owner,
        )
        assert w1.status_code == 201, w1.text
        assert w1.json()["data"]["age_days"] == 7
        # current_weight_g mirrors the latest measurement.
        detail = await async_client.get(f"{_rb(fid)}/rabbits/{rid}", headers=auth_headers_owner)
        assert float(detail.json()["data"]["current_weight_g"]) == 200.0

    async def test_growth_analysis_with_breed_curve_deviation(self, async_client, workspace, auth_headers_manager):
        fid = workspace.farm.id
        breed = await async_client.post(
            f"{_rb(fid)}/breeds",
            json={"name": "GrowthBreed", "category": "commercial_meat",
                  "profile": {"growth_curve": [{"age_days": 7, "weight_g": 150},
                                               {"age_days": 37, "weight_g": 900}]}},
            headers=auth_headers_manager,
        )
        breed_id = breed.json()["data"]["id"]
        r = await _register(async_client, fid, auth_headers_manager,
                            date_of_birth="2026-01-01", breed_id=breed_id)
        rid = r["id"]
        for day, wt in (("2026-01-08", 150), ("2026-02-07", 1000)):
            await async_client.post(f"{_rb(fid)}/rabbits/{rid}/weights",
                                    json={"recorded_on": day, "weight_g": wt}, headers=auth_headers_manager)
        g = await async_client.get(f"{_rb(fid)}/rabbits/{rid}/growth", headers=auth_headers_manager)
        assert g.status_code == 200, g.text
        analysis = g.json()["data"]["analysis"]
        assert analysis["total_gain_g"]["value"] == 850.0            # 1000 - 150
        assert analysis["average_daily_gain"]["value"] == round(850 / 30, 2)
        # age 37d → expected 900 (curve endpoint); latest 1000 → deviation +100.
        assert analysis["expected_weight_g"]["value"] == 900.0
        assert analysis["deviation_g"]["value"] == 100.0


class TestFeed:
    async def test_manual_feeding_records_cost(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        fed = await async_client.post(
            f"{_rb(fid)}/feed",
            json={"rabbit_id": r["id"], "feed_type": "pellets", "quantity_kg": 0.25,
                  "fed_on": date.today().isoformat(), "cost": 30},
            headers=auth_headers_owner,
        )
        assert fed.status_code == 201, fed.text
        data = fed.json()["data"]
        assert data["inventory_movement_id"] is None  # manual, no inventory link
        assert float(data["cost"]) == 30.0

    async def test_inventory_linked_feeding_decrements_stock(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        item = await async_client.post(
            f"{_inv(fid)}/items",
            json={"name": "Rabbit Pellets", "category": "feed", "unit": "kg",
                  "opening_quantity": 100, "opening_cost": 50},
            headers=auth_headers_owner,
        )
        assert item.status_code == 201, item.text
        item_id = item.json()["data"]["id"]

        r = await _register(async_client, fid, auth_headers_owner)
        fed = await async_client.post(
            f"{_rb(fid)}/feed",
            json={"rabbit_id": r["id"], "inventory_item_id": item_id, "quantity_kg": 10,
                  "fed_on": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        assert fed.status_code == 201, fed.text
        data = fed.json()["data"]
        assert data["inventory_movement_id"] is not None
        assert float(data["cost"]) == 500.0  # 10 kg × avg_cost 50 (snapshot, not re-expensed)

        after = await async_client.get(f"{_inv(fid)}/items/{item_id}", headers=auth_headers_owner)
        assert float(after.json()["data"]["quantity"]) == 90.0  # decremented by consumption

    async def test_feed_summary_fcr(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner, date_of_birth="2026-01-01")
        rid = r["id"]
        for day, wt in (("2026-01-08", 500), ("2026-02-07", 2500)):  # +2 kg gain
            await async_client.post(f"{_rb(fid)}/rabbits/{rid}/weights",
                                    json={"recorded_on": day, "weight_g": wt}, headers=auth_headers_owner)
        await async_client.post(f"{_rb(fid)}/feed",
                                json={"rabbit_id": rid, "quantity_kg": 6, "fed_on": "2026-02-07", "cost": 300},
                                headers=auth_headers_owner)
        s = await async_client.get(f"{_rb(fid)}/feed/summary?rabbit_id={rid}", headers=auth_headers_owner)
        assert s.status_code == 200
        summary = s.json()["data"]["summary"]
        assert summary["total_feed_kg"]["value"] == 6.0
        assert summary["feed_conversion_ratio"]["value"] == 3.0  # 6 kg feed / 2 kg gain


class TestRBAC:
    async def test_worker_can_record_weight_and_feed(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_worker)
        w = await async_client.post(f"{_rb(fid)}/rabbits/{r['id']}/weights",
                                    json={"recorded_on": date.today().isoformat(), "weight_g": 800},
                                    headers=auth_headers_worker)
        assert w.status_code == 201
        f = await async_client.post(f"{_rb(fid)}/feed",
                                    json={"rabbit_id": r["id"], "quantity_kg": 0.2, "fed_on": date.today().isoformat()},
                                    headers=auth_headers_worker)
        assert f.status_code == 201

    async def test_viewer_cannot_record_but_can_read(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        r = await _register(async_client, fid, auth_headers_owner)
        w = await async_client.post(f"{_rb(fid)}/rabbits/{r['id']}/weights",
                                    json={"recorded_on": date.today().isoformat(), "weight_g": 800},
                                    headers=auth_headers_viewer)
        assert w.status_code == 403
        assert (await async_client.get(f"{_rb(fid)}/feed", headers=auth_headers_viewer)).status_code == 200
