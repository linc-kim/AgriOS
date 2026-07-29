"""
Mission Control × Aviculture — the strategic briefing over HTTP (Module 15, Part 11).

Confirms Mission Control integrates the aviculture deterministic engines safely:
the briefing endpoint composes health/finance/valuation/breeding/incubation/
population/automation/workflow summaries, surfaces honesty-labelled insights that
cite recorded evidence, and is gated on the AI insight-view permission. Mission
Control orchestrates — the aviculture engines remain the source of truth.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


def _briefing(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/mission/aviculture/briefing"


async def _species(client, farm_id, headers) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "African Grey", "species_group": "parrot"}, headers=headers)
    return r.json()["data"]["id"]


class TestBriefing:
    async def test_empty_farm_briefing_is_grounded(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(_briefing(workspace.farm.id), headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        for key in ("headline", "summaries", "insights", "priorities", "counts"):
            assert key in d
        # Every consumed engine is represented in the summaries.
        for key in ("health", "finance", "valuation", "breeding", "incubation",
                    "population_forecast", "automation", "workflows"):
            assert key in d["summaries"]
        # An empty farm has no recorded valuation — reported as unknown, never invented.
        val_insights = [i for i in d["insights"] if i["category"] == "finance" and "valuation" in i["title"].lower()]
        assert val_insights and val_insights[0]["evidence"][0]["fact_type"] == "unknown"

    async def test_summaries_reflect_recorded_collection(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        for _ in range(3):
            await async_client.post(f"{_avi(farm)}/birds", json={"species_id": sid}, headers=auth_headers_owner)
        r = await async_client.get(_briefing(farm), headers=auth_headers_owner)
        d = r.json()["data"]
        assert d["summaries"]["collection"]["total"]["value"] == 3
        assert d["summaries"]["collection"]["total"]["label"] == "recorded"

    async def test_every_insight_cites_evidence_and_honesty_fields(self, async_client, workspace, auth_headers_owner):
        # Doc 15 §15 — every recommendation explains evidence, reasoning, confidence, limitations.
        r = await async_client.get(_briefing(workspace.farm.id), headers=auth_headers_owner)
        for ins in r.json()["data"]["insights"]:
            assert ins["evidence"], f"insight {ins['title']} has no evidence"
            assert ins["detail"].strip(), f"insight {ins['title']} has no reasoning"
            assert ins["confidence"] in ("high", "medium", "low")
            assert ins["limitations"].strip(), f"insight {ins['title']} has no limitations"
            for e in ins["evidence"]:
                assert e["fact_type"] in ("recorded", "calculated", "forecast", "unknown")

    async def test_insight_view_permission_allows_viewer(self, async_client, workspace, auth_headers_viewer):
        # A viewer holds AI_INSIGHT_VIEW and may read the strategic briefing.
        r = await async_client.get(_briefing(workspace.farm.id), headers=auth_headers_viewer)
        assert r.status_code == 200, r.text
