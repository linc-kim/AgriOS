"""
Aviculture Automation — over HTTP, against a real database (Module 15, Part 9).

Confirms the deterministic automation wires recorded state through the pure engine
and REUSES the platform Reminder engine: preview computes due items, generate
materialises them as reminders (idempotent — second run skips), tasks list/complete
work, permissions hold, and staged workflows advance deterministically with history.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "Lovebird", "species_group": "parrot"}, headers=headers)
    return r.json()["data"]["id"]


async def _bird(client, farm_id, headers, sid) -> str:
    r = await client.post(f"{_avi(farm_id)}/birds", json={"species_id": sid}, headers=headers)
    return r.json()["data"]["id"]


class TestRemindersGeneration:
    async def test_preview_and_generate_idempotent(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        # An overdue vaccination (health record with a past next_due_on).
        await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                json={"record_type": "vaccination", "title": "Polyomavirus",
                                      "next_due_on": str(date.today() - timedelta(days=2))}, headers=auth_headers_owner)

        pv = await async_client.get(f"{_avi(farm)}/automation/preview", headers=auth_headers_owner)
        assert pv.status_code == 200, pv.text
        assert any(i["kind"] == "health_due" and i["priority"] == "high" for i in pv.json()["data"])

        g1 = await async_client.post(f"{_avi(farm)}/automation/generate", headers=auth_headers_owner)
        assert g1.status_code == 200, g1.text
        assert g1.json()["data"]["created"] >= 1

        # Second generate is idempotent — the same item is skipped, not duplicated.
        g2 = await async_client.post(f"{_avi(farm)}/automation/generate", headers=auth_headers_owner)
        assert g2.json()["data"]["created"] == 0
        assert g2.json()["data"]["skipped"] >= 1

    async def test_tasks_list_and_complete(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                json={"record_type": "deworming", "next_due_on": str(date.today() - timedelta(days=1))},
                                headers=auth_headers_owner)
        await async_client.post(f"{_avi(farm)}/automation/generate", headers=auth_headers_owner)

        lt = await async_client.get(f"{_avi(farm)}/tasks", headers=auth_headers_owner)
        assert lt.status_code == 200
        tasks = lt.json()["data"]
        assert len(tasks) >= 1
        assert tasks[0]["metadata"]["module"] == "aviculture"

        done = await async_client.post(f"{_avi(farm)}/tasks/{tasks[0]['id']}/complete", headers=auth_headers_owner)
        assert done.status_code == 200 and done.json()["data"]["is_done"] is True

    async def test_viewer_cannot_generate(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/automation/generate", headers=auth_headers_viewer)
        assert r.status_code == 403


class TestWorkflows:
    async def test_intake_workflow_advances_to_completion(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)

        r = await async_client.post(f"{_avi(farm)}/workflows",
                                    json={"workflow_type": "intake", "bird_id": bird}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        wf = r.json()["data"]
        assert wf["current_stage"] == "received" and wf["status"] == "active"
        assert wf["stages"][0] == "received" and wf["stages"][-1] == "in_collection"
        wid = wf["id"]

        # Advance through all remaining stages → completed at the terminal stage.
        stages = wf["stages"]
        for _ in range(len(stages) - 1):
            a = await async_client.post(f"{_avi(farm)}/workflows/{wid}/advance",
                                        json={"note": "step"}, headers=auth_headers_owner)
            assert a.status_code == 200, a.text
        final = a.json()["data"]
        assert final["current_stage"] == "in_collection" and final["status"] == "completed"

        # Advancing a completed workflow is rejected.
        again = await async_client.post(f"{_avi(farm)}/workflows/{wid}/advance", json={}, headers=auth_headers_owner)
        assert again.status_code == 409

        # History records every transition.
        ev = await async_client.get(f"{_avi(farm)}/workflows/{wid}/events", headers=auth_headers_owner)
        assert len(ev.json()["data"]) == len(stages)  # start + each advance

    async def test_viewer_cannot_start_workflow(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/workflows",
                                    json={"workflow_type": "quarantine"}, headers=auth_headers_viewer)
        assert r.status_code == 403
