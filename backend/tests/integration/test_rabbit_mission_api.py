"""
Rabbit Mission Control briefing (Module 17, Milestone 10) — over HTTP.

Confirms the strategic briefing composes the rabbit deterministic engines into
evidence-citing insights, is served under AI_INSIGHT_VIEW, and holds the same
shape as the aviculture/BSF briefings.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _mission(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/mission"


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


class TestBriefing:
    async def test_briefing_structure(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await async_client.post(f"{_rb(fid)}/rabbits", json={"sex": "doe"}, headers=auth_headers_owner)
        r = await async_client.get(f"{_mission(fid)}/rabbit/briefing", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        for key in ("headline", "summaries", "insights", "priorities", "counts"):
            assert key in data
        assert isinstance(data["insights"], list)

    async def test_viewer_can_read_briefing(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        r = await async_client.get(f"{_mission(fid)}/rabbit/briefing", headers=auth_headers_viewer)
        assert r.status_code == 200  # viewer has AI_INSIGHT_VIEW

    async def test_worker_cannot_read_briefing(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await async_client.get(f"{_mission(fid)}/rabbit/briefing", headers=auth_headers_worker)
        assert r.status_code == 403  # worker lacks AI_INSIGHT_VIEW
