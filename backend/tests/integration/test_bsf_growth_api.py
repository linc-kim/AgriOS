"""
BSF Growth Planner (Platform planner, Module 16) — over HTTP.

Confirms plans/goals/milestones are recorded domain objects, that every revision
preserves version history and is comparable, that planned-vs-actual is computed
from recorded operational data via the BSF metric provider, that advisors don't
auto-mutate (only explicit calls revise), permissions hold, and the executive
dashboard's growth score is unlocked once a plan with a recorded actual exists.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


async def _make_plan(client, farm_id, headers, target=100) -> dict:
    body = {
        "title": "Scale to commercial", "is_primary": True,
        "goals": [{"metric_key": "total_harvest_kg", "label": "Total harvest",
                   "unit": "kg", "baseline_value": 0, "target_value": target, "is_primary": True}],
        "milestones": [
            {"title": "Expand bins", "sequence": 1},
            {"title": "Add breeder colony", "sequence": 2},
        ],
    }
    r = await client.post(f"{_bsf(farm_id)}/growth/plans", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _harvest(client, farm_id, headers, kg):
    # Biomass must comfortably exceed the harvested mass (grams vs kg).
    batch = (await client.post(
        f"{_bsf(farm_id)}/batches",
        json={"lifecycle_stage": "prepupae", "population_estimate": 100000,
              "biomass_estimate_g": int(kg * 1000 * 3)},
        headers=headers,
    )).json()["data"]
    await client.post(f"{_bsf(farm_id)}/batches/{batch['id']}/harvests",
                      json={"harvest_type": "prepupae", "quantity_kg": kg}, headers=headers)


class TestPlanLifecycle:
    async def test_create_plan_starts_at_revision_one(self, async_client, workspace, auth_headers_owner):
        plan = await _make_plan(async_client, workspace.farm.id, auth_headers_owner)
        assert plan["current_revision"] == 1 and plan["is_primary"] is True

    async def test_progress_uses_recorded_actuals(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        plan = await _make_plan(async_client, fid, auth_headers_owner, target=100)
        await _harvest(async_client, fid, auth_headers_owner, 40)  # recorded actual = 40 kg
        detail = await async_client.get(f"{_bsf(fid)}/growth/plans/{plan['id']}", headers=auth_headers_owner)
        assert detail.status_code == 200, detail.text
        data = detail.json()["data"]
        # 40 of 100 → 40% overall, computed from recorded harvest facts.
        assert data["progress"]["overall_percent"]["label"] == "calculated"
        assert data["progress"]["overall_percent"]["value"] == 40.0
        assert data["progress"]["goals"][0]["progress"]["actual"]["value"] == 40.0

    async def test_revision_preserves_history_and_compares(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        plan = await _make_plan(async_client, fid, auth_headers_owner, target=100)
        # Revise the goal target → new revision, old one preserved.
        upd = await async_client.patch(
            f"{_bsf(fid)}/growth/plans/{plan['id']}",
            json={"reason": "Raised ambition",
                  "goals": [{"metric_key": "total_harvest_kg", "label": "Total harvest",
                             "unit": "kg", "baseline_value": 0, "target_value": 250, "is_primary": True}]},
            headers=auth_headers_owner,
        )
        assert upd.status_code == 200 and upd.json()["data"]["current_revision"] == 2

        revs = await async_client.get(f"{_bsf(fid)}/growth/plans/{plan['id']}/revisions", headers=auth_headers_owner)
        assert len(revs.json()["data"]) == 2  # both revisions retained

        cmp = await async_client.get(
            f"{_bsf(fid)}/growth/plans/{plan['id']}/compare?from_revision=1&to_revision=2",
            headers=auth_headers_owner,
        )
        assert cmp.status_code == 200
        changed = cmp.json()["data"]["diff"]["goals"]["changed"]
        assert changed and changed[0]["changes"]["target_value"] == {"from": 100.0, "to": 250.0}

    async def test_milestone_status_update_writes_revision(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        plan = await _make_plan(async_client, fid, auth_headers_owner)
        detail = await async_client.get(f"{_bsf(fid)}/growth/plans/{plan['id']}", headers=auth_headers_owner)
        m_id = detail.json()["data"]["milestones"][0]["id"]
        r = await async_client.patch(
            f"{_bsf(fid)}/growth/plans/{plan['id']}/milestones/{m_id}",
            json={"status": "achieved"}, headers=auth_headers_owner,
        )
        assert r.status_code == 200 and r.json()["data"]["current_revision"] == 2
        rollup = r.json()["data"]["progress"]["milestones"]
        assert rollup["by_status"].get("achieved") == 1


class TestPermissionsAndDashboard:
    async def test_worker_cannot_view_or_edit_growth(self, async_client, workspace, auth_headers_worker):
        r = await async_client.get(f"{_bsf(workspace.farm.id)}/growth/plans", headers=auth_headers_worker)
        assert r.status_code == 403

    async def test_viewer_can_view_but_not_create(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        await _make_plan(async_client, fid, auth_headers_owner)
        view = await async_client.get(f"{_bsf(fid)}/growth/plans", headers=auth_headers_viewer)
        assert view.status_code == 200
        create = await async_client.post(
            f"{_bsf(fid)}/growth/plans", json={"title": "x"}, headers=auth_headers_viewer)
        assert create.status_code == 403

    async def test_dashboard_growth_score_unlocked_by_plan(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _make_plan(async_client, fid, auth_headers_owner, target=100)
        await _harvest(async_client, fid, auth_headers_owner, 50)
        dash = await async_client.get(f"{_bsf(fid)}/reports/dashboard", headers=auth_headers_owner)
        growth = dash.json()["data"]["scores"]["growth"]
        assert growth["label"] == "calculated" and growth["value"] == 50.0
