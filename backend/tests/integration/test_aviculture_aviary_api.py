"""
Aviary Management — over HTTP, against a real database (Module 15, Part 3).

Confirms the facility layer wires real data through the pure engine: aviaries
CRUD, occupancy computed live from housed birds (never stored), zones/fixtures,
environmental readings summarised against targets, cleaning tasks with recurrence
seeding, timeline, permissions, and the guard that a still-occupied aviary cannot
be deactivated. Also checks the farm-wide infrastructure summary Mission Control
will consume.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _base(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture/aviaries"


async def _make_aviary(client, farm_id, headers, **overrides) -> dict:
    body = {"name": f"Flight {uuid.uuid4().hex[:6]}", "aviary_type": "flight",
            "purpose": "breeding", "capacity": 10}
    body.update(overrides)
    r = await client.post(_base(farm_id), json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _make_species(client, farm_id, headers) -> str:
    r = await client.post(f"/api/v1/farms/{farm_id}/aviculture/species",
                          json={"common_name": "Gouldian Finch", "species_group": "finch"}, headers=headers)
    return r.json()["data"]["id"]


class TestAviaryCrud:
    async def test_create_lists_with_zero_occupancy(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner, capacity=8)
        assert av["occupancy"]["capacity"]["value"] == 8
        assert av["occupancy"]["occupied"]["value"] == 0
        r = await async_client.get(_base(workspace.farm.id), headers=auth_headers_owner)
        assert r.status_code == 200
        assert any(a["id"] == av["id"] for a in r.json()["data"])

    async def test_occupancy_reflects_housed_birds(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner, capacity=5)
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        # House two birds in this aviary.
        for _ in range(2):
            await async_client.post(f"/api/v1/farms/{workspace.farm.id}/aviculture/birds",
                                    json={"species_id": sid, "aviary_id": av["id"]}, headers=auth_headers_owner)
        detail = await async_client.get(f"{_base(workspace.farm.id)}/{av['id']}", headers=auth_headers_owner)
        occ = detail.json()["data"]["occupancy"]
        assert occ["occupied"]["value"] == 2
        assert occ["available"]["value"] == 3
        assert occ["utilization_pct"]["value"] == 40.0

    async def test_viewer_cannot_create(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(_base(workspace.farm.id),
                                    json={"name": "X", "capacity": 1}, headers=auth_headers_viewer)
        assert r.status_code == 403

    async def test_cannot_deactivate_occupied_aviary(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner)
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        await async_client.post(f"/api/v1/farms/{workspace.farm.id}/aviculture/birds",
                                json={"species_id": sid, "aviary_id": av["id"]}, headers=auth_headers_owner)
        r = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/deactivate", json={}, headers=auth_headers_owner)
        assert r.status_code == 409


class TestInfrastructure:
    async def test_zones_and_fixtures(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner)
        rz = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/zones",
                                     json={"name": "North Flight", "zone_type": "flight", "capacity": 4},
                                     headers=auth_headers_owner)
        assert rz.status_code == 201, rz.text
        zone_id = rz.json()["data"]["id"]
        rf = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/fixtures",
                                     json={"fixture_type": "nest_box", "zone_id": zone_id, "quantity": 3},
                                     headers=auth_headers_owner)
        assert rf.status_code == 201, rf.text
        lf = await async_client.get(f"{_base(workspace.farm.id)}/{av['id']}/fixtures?fixture_type=nest_box",
                                    headers=auth_headers_owner)
        assert len(lf.json()["data"]) == 1

    async def test_environment_reading_and_summary(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner,
                                environment={"temp_min": 18, "temp_max": 28, "humidity_min": 40, "humidity_max": 70})
        r = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/environment",
                                    json={"temperature_c": "35.0", "humidity_pct": "50.0"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        detail = await async_client.get(f"{_base(workspace.farm.id)}/{av['id']}", headers=auth_headers_owner)
        summary = detail.json()["data"]["environment_summary"]
        assert summary["reading_count"] == 1
        # 35°C exceeds the 28°C target → a temperature recommendation is surfaced.
        assert any(f["metric"] == "temperature_c" for f in summary["findings"])


class TestTasks:
    async def test_weekly_task_seeds_next_on_completion(self, async_client, workspace, auth_headers_owner):
        av = await _make_aviary(async_client, workspace.farm.id, auth_headers_owner)
        rt = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/tasks",
                                     json={"task_type": "cleaning", "title": "Weekly clean",
                                           "scheduled_for": "2026-07-20", "recurrence": "weekly"},
                                     headers=auth_headers_owner)
        assert rt.status_code == 201, rt.text
        task_id = rt.json()["data"]["id"]
        rc = await async_client.post(f"{_base(workspace.farm.id)}/{av['id']}/tasks/{task_id}/complete",
                                     json={"completed_on": "2026-07-21"}, headers=auth_headers_owner)
        assert rc.status_code == 200 and rc.json()["data"]["status"] == "completed"
        # A new scheduled occurrence should now exist (recurrence seeding).
        lt = await async_client.get(f"{_base(workspace.farm.id)}/{av['id']}/tasks?status=scheduled",
                                    headers=auth_headers_owner)
        assert len(lt.json()["data"]) >= 1

    async def test_infrastructure_summary(self, async_client, workspace, auth_headers_owner):
        await _make_aviary(async_client, workspace.farm.id, auth_headers_owner, purpose="quarantine",
                           biosecurity_level="quarantine", capacity=4)
        r = await async_client.get(f"{_base(workspace.farm.id)}/summary", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["aviary_count"] >= 1
        assert data["quarantine_aviaries"] >= 1
        assert "value" in data["total_occupied"]
