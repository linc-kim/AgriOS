"""
BSF Feedstock, Feeding & Environment (Module 16, Part 3) — over HTTP.

Confirms feedstock lots track remaining quantity as feeding consumes them,
over-feeding a lot is rejected, feed-conversion is deterministic and honesty-
labelled, environmental readings are recorded with a live threshold assessment
against the species profile, permissions hold, and farm isolation is preserved.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


async def _make_species(client, farm_id, headers, **profile) -> str:
    body = {"common_name": "Hermetia illucens", "production_type": "larvae"}
    if profile:
        body["profile"] = profile
    r = await client.post(f"{_bsf(farm_id)}/species", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _make_batch(client, farm_id, headers, **overrides) -> dict:
    body = {"lifecycle_stage": "feeding_larvae", "population_estimate": 10000, "biomass_estimate_g": 500}
    body.update(overrides)
    r = await client.post(f"{_bsf(farm_id)}/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _make_lot(client, farm_id, headers, weight=100) -> dict:
    r = await client.post(
        f"{_bsf(farm_id)}/feedstock-lots",
        json={"name": "Market waste", "category": "market_waste", "weight_kg": weight},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestFeedstock:
    async def test_lot_created_with_full_remaining(self, async_client, workspace, auth_headers_owner):
        lot = await _make_lot(async_client, workspace.farm.id, auth_headers_owner, weight=250)
        assert float(lot["remaining_kg"]) == 250.0 and lot["status"] == "available"

    async def test_viewer_cannot_create_lot(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(
            f"{_bsf(workspace.farm.id)}/feedstock-lots",
            json={"name": "X", "category": "market_waste", "weight_kg": 10}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403

    async def test_invalid_category_rejected(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(
            f"{_bsf(workspace.farm.id)}/feedstock-lots",
            json={"name": "X", "category": "gold", "weight_kg": 10}, headers=auth_headers_owner,
        )
        assert r.status_code == 422


class TestFeeding:
    async def test_feeding_consumes_lot(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        lot = await _make_lot(async_client, fid, auth_headers_owner, weight=100)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/feedings",
            json={"feedstock_lot_id": lot["id"], "quantity_kg": 30}, headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        # Lot remaining decremented and status moved to in_use.
        after = await async_client.get(f"{_bsf(fid)}/feedstock-lots/{lot['id']}", headers=auth_headers_owner)
        assert float(after.json()["data"]["remaining_kg"]) == 70.0
        assert after.json()["data"]["status"] == "in_use"

    async def test_overfeeding_lot_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        lot = await _make_lot(async_client, fid, auth_headers_owner, weight=10)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/feedings",
            json={"feedstock_lot_id": lot["id"], "quantity_kg": 25}, headers=auth_headers_owner,
        )
        assert r.status_code == 422 and "remaining" in r.text.lower()

    async def test_feed_conversion_is_deterministic(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # Start at 500 g biomass, grow to 5500 g (= 5 kg gain); feed 20 kg → FCR 4.0.
        batch = await _make_batch(async_client, fid, auth_headers_owner, biomass_estimate_g=500)
        lot = await _make_lot(async_client, fid, auth_headers_owner, weight=100)
        await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/feedings",
            json={"feedstock_lot_id": lot["id"], "quantity_kg": 20}, headers=auth_headers_owner,
        )
        await async_client.patch(
            f"{_bsf(fid)}/batches/{batch['id']}",
            json={"biomass_estimate_g": 5500}, headers=auth_headers_owner,
        )
        r = await async_client.get(
            f"{_bsf(fid)}/batches/{batch['id']}/feed-conversion", headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["feed_conversion_ratio"]["value"] == 4.0
        assert data["feed_conversion_ratio"]["label"] == "calculated"
        assert data["feed_consumed_kg"]["value"] == 20.0


class TestEnvironment:
    async def test_reading_flags_threshold_violation(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        sid = await _make_species(async_client, fid, auth_headers_owner,
                                  environment={"temp_min_c": 27, "temp_max_c": 35})
        batch = await _make_batch(async_client, fid, auth_headers_owner, species_id=sid)
        r = await async_client.post(
            f"{_bsf(fid)}/environment/readings",
            json={"batch_id": batch["id"], "temperature_c": 45, "humidity_pct": 60},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        assessment = r.json()["data"]["assessment"]
        assert assessment["overall"] == "critical"
        assert any(v["parameter"] == "temperature" for v in assessment["violations"])

    async def test_worker_records_reading_within_range(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker,
    ):
        fid = workspace.farm.id
        # Catalog + batch set up by the owner; the worker records the reading.
        sid = await _make_species(async_client, fid, auth_headers_owner,
                                  environment={"temp_min_c": 27, "temp_max_c": 35})
        batch = await _make_batch(async_client, fid, auth_headers_owner, species_id=sid)
        r = await async_client.post(
            f"{_bsf(fid)}/environment/readings",
            json={"batch_id": batch["id"], "temperature_c": 30}, headers=auth_headers_worker,
        )
        assert r.status_code == 201
        assert r.json()["data"]["assessment"]["overall"] == "ok"

    async def test_viewer_cannot_record_reading(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(
            f"{_bsf(workspace.farm.id)}/environment/readings",
            json={"temperature_c": 30}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403

    async def test_unit_assessment_and_isolation(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_bsf(fid)}/production-units",
            json={"name": "Env Bin", "unit_type": "bin"}, headers=auth_headers_owner,
        )
        unit_id = r.json()["data"]["id"]
        await async_client.post(
            f"{_bsf(fid)}/environment/readings",
            json={"production_unit_id": unit_id, "temperature_c": 31}, headers=auth_headers_owner,
        )
        assess = await async_client.get(
            f"{_bsf(fid)}/environment/units/{unit_id}/assessment", headers=auth_headers_owner,
        )
        assert assess.status_code == 200
        assert assess.json()["data"]["reading_count"] == 1
        # A unit on farm A is invisible under farm B.
        cross = await async_client.get(
            f"{_bsf(workspace.farm_b.id)}/environment/units/{unit_id}/assessment",
            headers=auth_headers_owner,
        )
        assert cross.status_code == 404
