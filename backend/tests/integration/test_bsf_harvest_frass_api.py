"""
BSF Harvest, Frass & Inventory reuse (Module 16, Part 4) — over HTTP.

Confirms harvests and frass are recorded with revenue as a fact, that harvested
output flows into the PLATFORM Inventory module via an inbound ``adjustment``
movement (never ``stock_in`` — so no purchase expense is double-booked), that a
complete harvest closes the batch, over-harvest is rejected, permissions hold,
and farm isolation is preserved.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


def _inv(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/inventory"


async def _make_batch(client, farm_id, headers, **overrides) -> dict:
    body = {"lifecycle_stage": "mature_larvae", "population_estimate": 10000, "biomass_estimate_g": 10000}
    body.update(overrides)
    r = await client.post(f"{_bsf(farm_id)}/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _make_inventory_item(client, farm_id, headers) -> str:
    r = await client.post(
        f"{_inv(farm_id)}/items",
        json={"name": "BSF Larvae", "category": "miscellaneous", "unit": "kg"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestHarvest:
    async def test_harvest_records_revenue_fact(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "larvae", "quantity_kg": 4, "revenue_amount": 200,
                  "currency": "KES", "buyer_name": "Acme Feeds", "destination": "sale"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert float(data["revenue_amount"]) == 200.0 and data["buyer_name"] == "Acme Feeds"
        # No inventory item supplied → no movement linked.
        assert data["inventory_movement_id"] is None

    async def test_harvest_routes_into_inventory_as_adjustment(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        item_id = await _make_inventory_item(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "larvae", "quantity_kg": 4, "inventory_item_id": item_id},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["inventory_movement_id"] is not None

        # The platform Inventory item now holds the harvested stock…
        item = await async_client.get(f"{_inv(fid)}/items/{item_id}", headers=auth_headers_owner)
        assert float(item.json()["data"]["quantity"]) == 4.0
        # …via an inbound ADJUSTMENT movement (never stock_in → no expense booked).
        moves = await async_client.get(f"{_inv(fid)}/movements?item_id={item_id}", headers=auth_headers_owner)
        rows = moves.json()["data"]
        assert len(rows) == 1
        assert rows[0]["movement_type"] == "adjustment"
        assert rows[0]["direction"] == 1

    async def test_complete_harvest_closes_batch(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "larvae", "quantity_kg": 8, "is_complete": True},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201
        after = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}", headers=auth_headers_owner)
        assert after.json()["data"]["status"] == "harvested"

    async def test_partial_over_biomass_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, biomass_estimate_g=5000)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "larvae", "quantity_kg": 9}, headers=auth_headers_owner,
        )
        assert r.status_code == 422 and "exceeds" in r.text.lower()

    async def test_readiness_signal(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, lifecycle_stage="prepupae")
        r = await async_client.get(
            f"{_bsf(fid)}/batches/{batch['id']}/harvest-readiness", headers=auth_headers_owner,
        )
        assert r.status_code == 200
        assert r.json()["data"]["readiness"]["value"] == "ready"

    async def test_viewer_cannot_harvest(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/harvests",
            json={"harvest_type": "larvae", "quantity_kg": 1}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403


class TestFrass:
    async def test_frass_recorded_and_routed_to_inventory(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        item_id = await _make_inventory_item(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/frass",
            json={"weight_kg": 12, "moisture_pct": 40, "inventory_item_id": item_id},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["inventory_movement_id"] is not None
        item = await async_client.get(f"{_inv(fid)}/items/{item_id}", headers=auth_headers_owner)
        assert float(item.json()["data"]["quantity"]) == 12.0

    async def test_frass_history_and_isolation(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/frass",
            json={"weight_kg": 5}, headers=auth_headers_owner,
        )
        hist = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}/frass", headers=auth_headers_owner)
        assert hist.status_code == 200 and len(hist.json()["data"]) == 1
        # Batch on farm A is invisible under farm B.
        cross = await async_client.get(
            f"{_bsf(workspace.farm_b.id)}/batches/{batch['id']}/frass", headers=auth_headers_owner,
        )
        assert cross.status_code == 404
