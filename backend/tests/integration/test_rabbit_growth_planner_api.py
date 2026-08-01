"""
Rabbit Growth Planner (Module 17, Milestone 8) — over HTTP.

Confirms the module reuses the PLATFORM Growth Planner (no module planner): a plan
with a rabbit goal tracks planned-vs-actual from the registered rabbit metric
provider (recorded facts), revisions are versioned, and RBAC holds.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _g(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit/growth"


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestGrowthPlanner:
    async def test_plan_tracks_actual_from_recorded_facts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # Two active rabbits → herd_size actual = 2.
        await _register(async_client, fid, auth_headers_owner, sex="doe")
        await _register(async_client, fid, auth_headers_owner, sex="buck")

        plan = await async_client.post(
            f"{_g(fid)}/plans",
            json={"title": "Scale to 4", "is_primary": True,
                  "goals": [{"metric_key": "herd_size", "label": "Herd size",
                             "baseline_value": 0, "target_value": 4, "is_primary": True}]},
            headers=auth_headers_owner,
        )
        assert plan.status_code == 201, plan.text
        plan_id = plan.json()["data"]["id"]

        detail = await async_client.get(f"{_g(fid)}/plans/{plan_id}", headers=auth_headers_owner)
        assert detail.status_code == 200, detail.text
        data = detail.json()["data"]
        # Primary goal progress = actual 2 / target 4 = 50%.
        assert data["progress"]["overall_percent"]["value"] == 50.0
        goal = data["progress"]["goals"][0]
        assert goal["metric_key"] == "herd_size"

    async def test_unknown_metric_key_reports_unknown(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        plan = await async_client.post(
            f"{_g(fid)}/plans",
            json={"title": "Odd goal", "is_primary": True,
                  "goals": [{"metric_key": "not_a_metric", "label": "?", "target_value": 10, "is_primary": True}]},
            headers=auth_headers_owner,
        )
        plan_id = plan.json()["data"]["id"]
        detail = await async_client.get(f"{_g(fid)}/plans/{plan_id}", headers=auth_headers_owner)
        # Provider returns None for an unknown key → overall unknown, never invented.
        assert detail.json()["data"]["progress"]["overall_percent"]["label"] == "unknown"

    async def test_revision_written_on_update(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        plan = await async_client.post(f"{_g(fid)}/plans", json={"title": "V1"}, headers=auth_headers_owner)
        plan_id = plan.json()["data"]["id"]
        upd = await async_client.patch(f"{_g(fid)}/plans/{plan_id}",
                                       json={"title": "V2", "reason": "scope change"}, headers=auth_headers_owner)
        assert upd.status_code == 200
        revs = await async_client.get(f"{_g(fid)}/plans/{plan_id}/revisions", headers=auth_headers_owner)
        assert revs.status_code == 200
        assert len(revs.json()["data"]) >= 1


class TestRBAC:
    async def test_worker_cannot_view_or_edit_growth_plans(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_g(fid)}/plans", headers=auth_headers_worker)).status_code == 403
        create = await async_client.post(f"{_g(fid)}/plans", json={"title": "X"}, headers=auth_headers_worker)
        assert create.status_code == 403

    async def test_viewer_can_view_but_not_edit(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_g(fid)}/plans", headers=auth_headers_viewer)).status_code == 200
        create = await async_client.post(f"{_g(fid)}/plans", json={"title": "X"}, headers=auth_headers_viewer)
        assert create.status_code == 403
