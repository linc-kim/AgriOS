"""
Small Ruminant Growth Planner + ARIA + Mission Control (Modules 18/19, Milestone 10)
— over HTTP.

These confirm the three platform integrations are wired for both species and stay
deterministic-first: ARIA answers facts with no LLM and labels honesty; mortality
is a pattern with a disclaimer (§4.4); Mission Control composes the deterministic
engines into a briefing; the Growth Planner surface is reused (module = species).
Permissions reuse the platform AI perms.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _register(client, fid, species, headers, sex):
    r = await client.post(f"{_sr(fid, species)}/animals", json={"name": "A", "sex": sex}, headers=headers)
    assert r.status_code == 201, r.text


class TestAria:
    async def test_deterministic_herd_answer(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, "goat", auth_headers_owner, "doe")
        await _register(async_client, fid, "goat", auth_headers_owner, "buck")
        r = await async_client.post(f"{_sr(fid, 'goat')}/aria/ask",
                                    json={"question": "How many goats do I have?"}, headers=auth_headers_owner)
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["provider"] == "deterministic" and d["fact_type"] == "recorded"
        assert "2 active goats" in d["answer"]

    async def test_mortality_is_a_pattern_not_a_diagnosis(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, "sheep", auth_headers_owner, "ewe")
        r = await async_client.post(f"{_sr(fid, 'sheep')}/aria/ask",
                                    json={"question": "What is my mortality rate?"}, headers=auth_headers_owner)
        assert r.status_code == 200
        # §4.4 — either a labelled pattern with the disclaimer, or an honest "not enough data".
        assert r.json()["data"]["fact_type"] in ("calculated", "unavailable")
        if r.json()["data"]["fact_type"] == "calculated":
            assert "not a diagnosis" in r.json()["data"]["answer"]

    async def test_context_snapshot(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        ctx = await async_client.get(f"{_sr(fid, 'goat')}/aria/context", headers=auth_headers_owner)
        assert ctx.status_code == 200
        d = ctx.json()["data"]
        assert d["species"] == "goat" and "active_animals" in d and "milk_total_recorded_l" in d


class TestMissionAndGrowth:
    async def test_mission_briefing_structure(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, "goat", auth_headers_owner, "doe")
        r = await async_client.get(f"/api/v1/farms/{fid}/mission/small-ruminant/goat/briefing",
                                   headers=auth_headers_owner)
        assert r.status_code == 200
        d = r.json()["data"]
        assert "headline" in d and "insights" in d and "counts" in d
        assert "active goat" in d["headline"]

    async def test_growth_plans_surface_reused(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # The platform planner surface is reused (module = species); empty list is fine.
        r = await async_client.get(f"{_sr(fid, 'goat')}/growth/plans", headers=auth_headers_owner)
        assert r.status_code == 200 and isinstance(r.json()["data"], list)

    async def test_unknown_species_briefing_404(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"/api/v1/farms/{fid}/mission/small-ruminant/rabbit/briefing",
                                   headers=auth_headers_owner)
        assert r.status_code == 404


class TestPermissions:
    async def test_worker_no_ai_viewer_insight_only(self, async_client, workspace,
                                                    auth_headers_worker, auth_headers_viewer):
        fid = workspace.farm.id
        # Worker lacks AI_QUERY.
        w = await async_client.post(f"{_sr(fid, 'goat')}/aria/ask", json={"question": "hi"},
                                    headers=auth_headers_worker)
        assert w.status_code == 403
        # Viewer has AI_INSIGHT_VIEW (context) but not AI_QUERY (ask).
        v_ctx = await async_client.get(f"{_sr(fid, 'goat')}/aria/context", headers=auth_headers_viewer)
        assert v_ctx.status_code == 200
        v_ask = await async_client.post(f"{_sr(fid, 'goat')}/aria/ask", json={"question": "hi"},
                                        headers=auth_headers_viewer)
        assert v_ask.status_code == 403
