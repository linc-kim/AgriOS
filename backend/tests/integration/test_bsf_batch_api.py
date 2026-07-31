"""
BSF Batch Backbone (Module 16, Part 2) — over HTTP, against a real database.

These confirm the endpoints wire real farm data through the services: batches get
an auto batch number and a 'created' lifecycle + timeline event, lifecycle
advances are validated (forward only, premature blocked unless acknowledged),
splits preserve lineage and cannot over-allocate, merges require aligned stages,
production metrics are honesty-labelled, permissions hold (viewer read-only,
worker cannot terminate), and one farm never reads another farm's batch.
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


async def _make_unit(client, farm_id, headers, capacity=None) -> str:
    body = {"name": "Bin 1", "unit_type": "bin"}
    if capacity is not None:
        body["capacity_grams"] = capacity
    r = await client.post(f"{_bsf(farm_id)}/production-units", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _make_batch(client, farm_id, headers, **overrides) -> dict:
    body = {"lifecycle_stage": "egg", "population_estimate": 10000, "biomass_estimate_g": 500}
    body.update(overrides)
    r = await client.post(f"{_bsf(farm_id)}/batches", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestInfrastructure:
    async def test_owner_creates_species_unit_colony(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        sid = await _make_species(async_client, fid, auth_headers_owner)
        uid = await _make_unit(async_client, fid, auth_headers_owner, capacity=20000)
        rc = await async_client.post(
            f"{_bsf(fid)}/colonies",
            json={"name": "Colony A", "species_id": sid, "production_unit_id": uid, "source": "purchased"},
            headers=auth_headers_owner,
        )
        assert rc.status_code == 201, rc.text
        assert rc.json()["data"]["status"] == "active"

    async def test_viewer_cannot_create_unit(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(
            f"{_bsf(workspace.farm.id)}/production-units",
            json={"name": "X", "unit_type": "bin"}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403

    async def test_invalid_unit_type_rejected(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(
            f"{_bsf(workspace.farm.id)}/production-units",
            json={"name": "X", "unit_type": "spaceship"}, headers=auth_headers_owner,
        )
        assert r.status_code == 422

    async def test_duplicate_unit_code_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r1 = await async_client.post(
            f"{_bsf(fid)}/production-units",
            json={"name": "A", "unit_type": "tray", "code": "DUPT"}, headers=auth_headers_owner,
        )
        assert r1.status_code == 201
        r2 = await async_client.post(
            f"{_bsf(fid)}/production-units",
            json={"name": "B", "unit_type": "tray", "code": "DUPT"}, headers=auth_headers_owner,
        )
        assert r2.status_code == 409


class TestBatchIdentity:
    async def test_create_gives_auto_number_and_history(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        assert batch["batch_number"].startswith("BSF-")
        assert batch["status"] == "active" and batch["lifecycle_stage"] == "egg"

        # Detail carries deterministic, honesty-labelled metrics.
        detail = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}", headers=auth_headers_owner)
        assert detail.status_code == 200
        metrics = detail.json()["data"]["metrics"]
        assert metrics["average_weight_mg"]["label"] == "calculated"

        # A birth lifecycle event + a 'created' timeline event exist.
        life = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}/lifecycle", headers=auth_headers_owner)
        assert life.status_code == 200 and len(life.json()["data"]) == 1
        tl = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}/timeline", headers=auth_headers_owner)
        assert any(e["event_type"] == "created" for e in tl.json()["data"])

    async def test_list_pagination_envelope(self, async_client, workspace, auth_headers_owner):
        await _make_batch(async_client, workspace.farm.id, auth_headers_owner)
        r = await async_client.get(f"{_bsf(workspace.farm.id)}/batches?limit=5", headers=auth_headers_owner)
        assert r.status_code == 200
        body = r.json()
        assert body["meta"]["limit"] == 5 and body["meta"]["total"] >= 1


class TestLifecycle:
    async def test_forward_advance_records_snapshot(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_worker)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/advance",
            json={"to_stage": "hatchling", "population_estimate": 9500}, headers=auth_headers_worker,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["lifecycle_stage"] == "hatchling"

    async def test_backward_advance_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, lifecycle_stage="prepupae")
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/advance",
            json={"to_stage": "egg"}, headers=auth_headers_owner,
        )
        assert r.status_code == 422 and "backward" in r.text.lower()

    async def test_premature_blocked_then_allowed(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # egg stage expects 4 days; advancing same-day is premature.
        sid = await _make_species(async_client, fid, auth_headers_owner, lifecycle={"egg_days": 4})
        batch = await _make_batch(async_client, fid, auth_headers_owner, species_id=sid, lifecycle_stage="egg")
        blocked = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/advance",
            json={"to_stage": "hatchling"}, headers=auth_headers_owner,
        )
        assert blocked.status_code == 422 and "premature" in blocked.text.lower()
        ok = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/advance",
            json={"to_stage": "hatchling", "allow_premature": True}, headers=auth_headers_owner,
        )
        assert ok.status_code == 200


class TestSplitMerge:
    async def test_split_preserves_lineage(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, population_estimate=10000)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/split",
            json={"parts": [{"population_estimate": 6000}, {"population_estimate": 3000}]},
            headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        children = r.json()["data"]
        assert len(children) == 2
        assert all(c["parent_batch_id"] == batch["id"] for c in children)
        # Parent is now terminal (split).
        parent = await async_client.get(f"{_bsf(fid)}/batches/{batch['id']}", headers=auth_headers_owner)
        assert parent.json()["data"]["status"] == "split"

    async def test_split_over_allocation_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner, population_estimate=1000)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/split",
            json={"parts": [{"population_estimate": 800}, {"population_estimate": 800}]},
            headers=auth_headers_owner,
        )
        assert r.status_code == 422

    async def test_merge_requires_aligned_stages(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        b1 = await _make_batch(async_client, fid, auth_headers_owner, lifecycle_stage="feeding_larvae")
        b2 = await _make_batch(async_client, fid, auth_headers_owner, lifecycle_stage="prepupae")
        r = await async_client.post(
            f"{_bsf(fid)}/batches/merge",
            json={"source_batch_ids": [b1["id"], b2["id"]]}, headers=auth_headers_owner,
        )
        assert r.status_code == 422 and "stage" in r.text.lower()

    async def test_merge_sums_and_marks_sources(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        b1 = await _make_batch(async_client, fid, auth_headers_owner,
                               lifecycle_stage="feeding_larvae", population_estimate=4000)
        b2 = await _make_batch(async_client, fid, auth_headers_owner,
                               lifecycle_stage="feeding_larvae", population_estimate=3000)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/merge",
            json={"source_batch_ids": [b1["id"], b2["id"]]}, headers=auth_headers_owner,
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["population_estimate"] == 7000
        # Sources are now merged (terminal).
        s1 = await async_client.get(f"{_bsf(fid)}/batches/{b1['id']}", headers=auth_headers_owner)
        assert s1.json()["data"]["status"] == "merged"


class TestPermissionsAndIsolation:
    async def test_worker_cannot_terminate(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_worker)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/terminate", json={}, headers=auth_headers_worker,
        )
        assert r.status_code == 403

    async def test_owner_can_terminate(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        batch = await _make_batch(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_bsf(fid)}/batches/{batch['id']}/terminate",
            json={"reason": "contamination"}, headers=auth_headers_owner,
        )
        assert r.status_code == 200 and r.json()["data"]["status"] == "terminated"

    async def test_farm_isolation(self, async_client, workspace, auth_headers_owner):
        # A batch created on farm A must never be visible under farm B.
        batch = await _make_batch(async_client, workspace.farm.id, auth_headers_owner)
        r = await async_client.get(
            f"{_bsf(workspace.farm_b.id)}/batches/{batch['id']}", headers=auth_headers_owner,
        )
        assert r.status_code == 404
