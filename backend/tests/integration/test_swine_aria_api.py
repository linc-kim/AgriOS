"""
Swine ARIA & Mission Control briefing (Module 20, Milestone 10) — over HTTP.

Confirms the interpretation layer:

  * factual questions are answered deterministically (no LLM), honesty-labelled;
  * unavailable data is reported as unavailable, never invented;
  * health answers are patterns that recommend a vet — never a diagnosis;
  * the context snapshot composes analytics (AR-01 bounded context);
  * recommendations are explainable (recommendation + reason + supporting data + confidence);
  * ARIA is read-only (asking never mutates a record);
  * Mission Control exposes the same deterministic briefing.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


async def _pig(client, fid, h, sex="barrow"):
    r = await client.post(f"{_sw(fid)}/pigs", json={"name": "P", "sex": sex}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestDeterministicAsk:
    async def test_population_is_deterministic(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        await _pig(async_client, fid, h)
        await _pig(async_client, fid, h)
        r = await async_client.post(f"{_sw(fid)}/aria/ask", json={"question": "How many pigs do I have?"}, headers=h)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["provider"] == "deterministic" and data["engine"] == "deterministic"
        assert data["fact_type"] == "recorded" and "2" in data["answer"]
        assert data["sources"] == ["reports.population"]

    async def test_unavailable_is_not_invented(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        # No cost/sale data yet → cost per pig unavailable, not fabricated.
        r = await async_client.post(f"{_sw(fid)}/aria/ask", json={"question": "What is my cost per pig?"}, headers=h)
        data = r.json()["data"]
        assert data["fact_type"] == "unavailable"
        assert "not enough" in data["answer"].lower()

    async def test_health_answer_is_pattern_not_diagnosis(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        await async_client.post(f"{_sw(fid)}/health/disease-cases",
                                json={"pig_id": pig["id"], "disease_name": "Scours"}, headers=h)
        r = await async_client.post(f"{_sw(fid)}/aria/ask",
                                    json={"question": "Are my pigs sick / any disease?"}, headers=h)
        data = r.json()["data"]
        assert "do not diagnose" in data["answer"].lower() or "recommend a vet" in data["answer"].lower()


class TestContextAndRecommendations:
    async def test_context_is_bounded_snapshot(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        await _pig(async_client, fid, h)
        ctx = await async_client.get(f"{_sw(fid)}/aria/context", headers=h)
        assert ctx.status_code == 200
        data = ctx.json()["data"]
        assert data["active_pigs"] == 1
        for key in ("conception_rate_pct", "mortality_rate_pct", "gross_margin", "cost_per_pig"):
            assert key in data

    async def test_recommendations_are_explainable(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        # Create an overcrowded pen (capacity 1, two pigs) → a housing recommendation.
        pen = await async_client.post(f"{_sw(fid)}/housing/pens",
                                      json={"name": "Tight", "pen_type": "finisher_pen", "capacity": 1}, headers=h)
        pen_id = pen.json()["data"]["id"]
        for _ in range(2):
            await _pig(async_client, fid, h)
            # place each pig into the pen
        pigs = await async_client.get(f"{_sw(fid)}/pigs", headers=h)
        for p in pigs.json()["data"][:2]:
            await async_client.post(f"{_sw(fid)}/pigs/{p['id']}/move", json={"pen_id": pen_id}, headers=h)
        rec = await async_client.get(f"{_sw(fid)}/aria/recommendations", headers=h)
        assert rec.status_code == 200
        data = rec.json()["data"]
        housing = [r for r in data["recommendations"] if r["category"] == "housing"]
        assert housing, data["recommendations"]
        r0 = housing[0]
        for field in ("recommendation", "reason", "confidence", "supporting_data"):
            assert field in r0 and r0[field] not in (None, "", [])

    async def test_ask_is_read_only(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        before = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        await async_client.post(f"{_sw(fid)}/aria/ask", json={"question": "How is the farm doing?"}, headers=h)
        after = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        assert before.json()["data"]["updated_at"] == after.json()["data"]["updated_at"]


class TestMissionBriefing:
    async def test_mission_swine_briefing(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        await _pig(async_client, fid, h)
        b = await async_client.get(f"/api/v1/farms/{fid}/mission/swine/briefing", headers=h)
        assert b.status_code == 200, b.text
        data = b.json()["data"]
        assert "headline" in data and "insights" in data and "counts" in data
