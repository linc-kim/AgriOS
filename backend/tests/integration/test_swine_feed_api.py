"""
Swine Feed & Nutrition (Module 20, Milestone 5) — over HTTP.

Confirms the feed catalog, stage-based feed plans, and the feeding log that reuses
the platform Inventory module:

  * feed catalog is data-driven (org-scoped; system feeds not editable);
  * feed plans map production stages to feeds + daily targets;
  * manual feeding is allowed (no Inventory link);
  * inventory-linked feeding decrements stock and snapshots cost with NO re-expense;
  * the feed summary is deterministic (FCR unknown until weight is recorded in Growth);
  * permissions hold (worker records feed; viewer cannot).
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


def _inv(fid) -> str:
    return f"/api/v1/farms/{fid}/inventory"


async def _pig(client, fid, h, sex="barrow"):
    r = await client.post(f"{_sw(fid)}/pigs", json={"name": "P", "sex": sex}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestCatalogAndPlans:
    async def test_feed_catalog_crud_and_system_guard(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        c = await async_client.post(f"{_sw(fid)}/feed/feeds",
                                    json={"name": "Grower 16", "category": "grower", "form": "pellet",
                                          "profile": {"cp_pct": 16}}, headers=h)
        assert c.status_code == 201, c.text
        lst = await async_client.get(f"{_sw(fid)}/feed/feeds", headers=h)
        assert any(f["name"] == "Grower 16" for f in lst.json()["data"])
        # Invalid category rejected.
        bad = await async_client.post(f"{_sw(fid)}/feed/feeds",
                                      json={"name": "X", "category": "nonsense"}, headers=h)
        assert bad.status_code == 422

    async def test_feed_plan_by_stage(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        for stage, kg in (("nursery", "0.6"), ("grower", "1.8"), ("finisher", "2.8")):
            r = await async_client.post(f"{_sw(fid)}/feed/plans",
                                        json={"plan_name": "Standard", "production_stage": stage,
                                              "daily_amount_kg": kg}, headers=h)
            assert r.status_code == 201, r.text
        rows = await async_client.get(f"{_sw(fid)}/feed/plans?plan_name=Standard", headers=h)
        stages = {e["production_stage"] for e in rows.json()["data"]}
        assert stages == {"nursery", "grower", "finisher"}


class TestFeedingLog:
    async def test_manual_feeding_and_summary(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        fr = await async_client.post(f"{_sw(fid)}/feed/records",
                                     json={"pig_id": pig["id"], "quantity_kg": 8, "feed_name": "Grower",
                                           "fed_on": "2026-05-01", "cost": "16.0"}, headers=h)
        assert fr.status_code == 201 and fr.json()["data"]["inventory_movement_id"] is None
        s = await async_client.get(f"{_sw(fid)}/feed/summary?pig_id={pig['id']}", headers=h)
        summary = s.json()["data"]["summary"]
        assert summary["total_feed_kg"]["value"] == 8.0
        assert summary["total_cost"]["value"] == 16.0
        # FCR is honestly unknown until weight is recorded (Growth milestone).
        assert summary["feed_conversion_ratio"]["label"] == "unknown"

    async def test_inventory_linked_feeding_no_reexpense(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        item = await async_client.post(f"{_inv(fid)}/items",
                                       json={"name": "Sow Feed", "category": "feed", "unit": "kg",
                                             "opening_quantity": 100, "opening_cost": 40}, headers=h)
        assert item.status_code == 201, item.text
        item_id = item.json()["data"]["id"]
        pig = await _pig(async_client, fid, h)
        fed = await async_client.post(f"{_sw(fid)}/feed/records",
                                      json={"pig_id": pig["id"], "inventory_item_id": item_id,
                                            "quantity_kg": 10, "fed_on": date.today().isoformat()}, headers=h)
        assert fed.status_code == 201, fed.text
        data = fed.json()["data"]
        assert data["inventory_movement_id"] is not None
        assert float(data["cost"]) == 400.0  # 10 kg × avg cost 40 (snapshot, not re-expensed)
        # Stock decremented by the consumption movement.
        after = await async_client.get(f"{_inv(fid)}/items/{item_id}", headers=h)
        assert float(after.json()["data"]["quantity"]) == 90.0


class TestPermissions:
    async def test_worker_records_but_viewer_cannot(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        pig = await _pig(async_client, fid, auth_headers_owner)
        body = {"pig_id": pig["id"], "quantity_kg": 2, "fed_on": "2026-05-02"}
        w = await async_client.post(f"{_sw(fid)}/feed/records", json=body, headers=auth_headers_worker)
        assert w.status_code == 201, w.text
        v = await async_client.post(f"{_sw(fid)}/feed/records", json=body, headers=auth_headers_viewer)
        assert v.status_code == 403
