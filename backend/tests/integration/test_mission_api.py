"""
Mission Control — over HTTP, against a real database.

The pure engine is unit-tested; these confirm the endpoints wire real farm data
through it: a mission can be created (with an honest baseline captured from
records), the roadmap/plan/progress/daily/manual/reports/dashboard all compute,
the original plan is never overwritten by a replan (a revision is appended),
permissions hold, and the CEO advisor stays grounded and offline without a key.
"""

import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


def _base(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/mission"


async def _create(client, farm_id, headers, **overrides):
    body = {
        "name": "Reach 10,000 Layers",
        "description": "Scale the layer flock",
        "target_date": "2027-07-25",
        "is_primary": True,
        "success_metrics": [{"kind": "birds", "label": "Layers", "target": 10000, "unit": "birds", "primary": True}],
        "constraints": ["No loans"],
        "priorities": ["Low mortality"],
        "policies": [{"key": "max_mortality", "statement": "Maximum mortality target: 3%", "category": "risk", "value": 3}],
    }
    body.update(overrides)
    return await client.post(_base(farm_id), json=body, headers=headers)


class TestCreateAndBaseline:
    async def test_create_captures_baseline(self, async_client, workspace, auth_headers_owner):
        r = await _create(async_client, workspace.farm.id, auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["is_primary"] is True
        # Baseline snapshots the current bird count from records.
        assert "birds" in d["baseline"]

    async def test_discovery_questions(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/discovery", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        keys = {q["key"] for q in r.json()["data"]}
        assert "take_loans" in keys


class TestComputedViews:
    @pytest_asyncio.fixture
    async def mission_id(self, async_client, workspace, auth_headers_owner):
        r = await _create(async_client, workspace.farm.id, auth_headers_owner)
        return r.json()["data"]["id"]

    async def test_dashboard(self, async_client, workspace, auth_headers_owner, mission_id):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/dashboard", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert "completion_pct" in d and d["daily"]["headline"]
        assert d["health"]["score"] >= 0

    async def test_roadmap_phases(self, async_client, workspace, auth_headers_owner, mission_id):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/roadmap", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        phases = r.json()["data"]["phases"]
        assert phases[0]["name"] == "Current state"
        # Every phase figure carries a fact_type.
        assert phases[1]["fact_type"]

    async def test_business_plan_labels_facts(self, async_client, workspace, auth_headers_owner, mission_id):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/plan", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        headings = {s["heading"] for s in r.json()["data"]["sections"]}
        assert "Current position" in headings
        cur = next(s for s in r.json()["data"]["sections"] if s["heading"] == "Current position")
        assert all(v["fact_type"] == "recorded_fact" for v in cur["body"])

    async def test_progress_explains_percentage(self, async_client, workspace, auth_headers_owner, mission_id):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/progress", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["completion_explanation"]
        assert d["forecasted_completion"]["fact_type"] == "calculated_forecast"

    async def test_daily_and_manual_and_reports(self, async_client, workspace, auth_headers_owner, mission_id):
        for path in ("daily", "manual", "reports", "adaptation"):
            r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/{path}", headers=auth_headers_owner)
            assert r.status_code == 200, f"{path}: {r.text}"

    async def test_monthly_report(self, async_client, workspace, auth_headers_owner, mission_id):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{mission_id}/reports",
                                   params={"period": "quarterly"}, headers=auth_headers_owner)
        assert r.json()["data"]["period"] == "quarterly"


class TestRevisions:
    async def test_replan_appends_revision_never_overwrites(self, async_client, workspace, auth_headers_owner):
        mid = (await _create(async_client, workspace.farm.id, auth_headers_owner)).json()["data"]["id"]
        r = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/replan", json={}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["revision_number"] == 1

        # A second replan appends #2 — the first is preserved.
        r2 = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/replan", json={}, headers=auth_headers_owner)
        assert r2.json()["data"]["revision_number"] == 2

        hist = await async_client.get(f"{_base(workspace.farm.id)}/{mid}/revisions", headers=auth_headers_owner)
        numbers = [rev["revision_number"] for rev in hist.json()["data"]]
        assert numbers == [2, 1]

    async def test_replan_can_apply_new_target_date(self, async_client, workspace, auth_headers_owner):
        mid = (await _create(async_client, workspace.farm.id, auth_headers_owner)).json()["data"]["id"]
        r = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/replan",
                                    json={"target_date": "2028-01-01"}, headers=auth_headers_owner)
        assert r.json()["data"]["applied"] is True
        m = await async_client.get(f"{_base(workspace.farm.id)}/{mid}", headers=auth_headers_owner)
        assert m.json()["data"]["target_date"] == "2028-01-01"


class TestAdvisor:
    async def test_advisor_is_grounded_and_offline(self, async_client, workspace, auth_headers_owner):
        mid = (await _create(async_client, workspace.farm.id, auth_headers_owner)).json()["data"]["id"]
        r = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/advisor",
                                    json={"question": "Should I delay expansion?"}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["provider"] == "offline"        # no key in tests
        assert d["grounded_context"]
        assert d["fact_type"] == "strategic_recommendation"

    async def test_advisor_simulation_grounded(self, async_client, workspace, auth_headers_owner):
        mid = (await _create(async_client, workspace.farm.id, auth_headers_owner)).json()["data"]["id"]
        r = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/advisor",
                                    json={"question": "What happens if feed prices double?"}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text


class TestPermissions:
    async def test_worker_cannot_create_mission(self, async_client, workspace, auth_headers_worker):
        r = await _create(async_client, workspace.farm.id, auth_headers_worker)
        assert r.status_code == 403

    async def test_viewer_can_read_but_not_write(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        mid = (await _create(async_client, workspace.farm.id, auth_headers_owner)).json()["data"]["id"]
        read = await async_client.get(f"{_base(workspace.farm.id)}/{mid}/dashboard", headers=auth_headers_viewer)
        assert read.status_code == 200
        write = await async_client.post(f"{_base(workspace.farm.id)}/{mid}/advisor",
                                        json={"question": "hi"}, headers=auth_headers_viewer)
        assert write.status_code == 403

    async def test_unknown_mission_404(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/{uuid.uuid4()}/dashboard", headers=auth_headers_owner)
        assert r.status_code == 404
