"""
BSF ARIA & Mission Control (Module 16, Part 8) — over HTTP.

Confirms ARIA answers deterministic-first from recorded facts (with sources +
honesty labels), that its context is the bounded engine snapshot, that it is
read-only (no plan mutation path), and that Mission Control's BSF briefing
orchestrates the deterministic engines + Growth Planner into evidence-citing
insights. Permissions hold.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


def _mission(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/mission"


async def _seed(client, farm_id, headers):
    batch = (await client.post(
        f"{_bsf(farm_id)}/batches",
        json={"lifecycle_stage": "prepupae", "population_estimate": 1000, "biomass_estimate_g": 60000},
        headers=headers,
    )).json()["data"]
    await client.post(f"{_bsf(farm_id)}/batches/{batch['id']}/harvests",
                      json={"harvest_type": "prepupae", "quantity_kg": 12, "revenue_amount": 4000, "currency": "KES"},
                      headers=headers)


class TestAria:
    async def test_factual_answer_is_deterministic_with_sources(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.post(f"{_bsf(fid)}/aria/ask",
                                    json={"question": "How much have I harvested in total?"},
                                    headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        # No LLM needed → deterministic engine, recorded fact, with a source reference.
        assert data["provider"] == "deterministic" and data["fact_type"] == "recorded"
        assert data["sources"] and "12" in data["answer"]

    async def test_unknown_metric_is_labelled_not_faked(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id  # fresh farm state: no growth plan
        r = await async_client.post(f"{_bsf(fid)}/aria/ask",
                                    json={"question": "How is my growth goal progressing?"},
                                    headers=auth_headers_owner)
        data = r.json()["data"]
        assert data["fact_type"] == "unavailable"  # no fabricated progress

    async def test_context_is_bounded_snapshot(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"{_bsf(fid)}/aria/context", headers=auth_headers_owner)
        assert r.status_code == 200
        ctx = r.json()["data"]
        # Bounded, engine-sourced keys — not raw rows.
        for key in ("active_batches", "total_harvest_kg", "feed_conversion_ratio", "top_bottleneck"):
            assert key in ctx

    async def test_aria_is_read_only(self, async_client, workspace, auth_headers_owner):
        # ARIA exposes only ask/context — there is no ARIA route that mutates.
        fid = workspace.farm.id
        for method in ("post", "patch", "delete"):
            r = await getattr(async_client, method)(f"{_bsf(fid)}/aria/plans", headers=auth_headers_owner)
            assert r.status_code in (404, 405)


class TestMissionBriefing:
    async def test_briefing_orchestrates_with_evidence(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_mission(fid)}/bsf/briefing", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "headline" in data and "summaries" in data and "counts" in data
        # Any insight present must cite evidence with an honesty label.
        for ins in data["insights"]:
            assert "evidence" in ins and "confidence" in ins
            for e in ins["evidence"]:
                assert e["fact_type"] in ("recorded", "calculated", "forecast", "unknown", "unavailable")

    async def test_briefing_requires_insight_view(self, async_client, workspace, auth_headers_worker):
        # Worker lacks AI_INSIGHT_VIEW → 403.
        r = await async_client.get(f"{_mission(workspace.farm.id)}/bsf/briefing", headers=auth_headers_worker)
        assert r.status_code == 403
