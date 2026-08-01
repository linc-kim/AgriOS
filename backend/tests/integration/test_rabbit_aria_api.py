"""
Rabbit ARIA (Module 17, Milestone 9) — over HTTP.

Confirms deterministic-first, honesty-labelled Q&A grounded in recorded facts: a
factual question is answered with no LLM (fact_type recorded/calculated + sources),
the bounded context snapshot is exposed, health answers are patterns not diagnoses
(§4.4), and AI permissions reuse the platform AI_QUERY / AI_INSIGHT_VIEW.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _aria(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit/aria"


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestDeterministicAnswers:
    async def test_herd_size_answered_from_recorded_facts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, sex="buck")
        await _register(async_client, fid, auth_headers_owner, sex="doe")
        r = await async_client.post(f"{_aria(fid)}/ask", json={"question": "How many rabbits do I have?"},
                                    headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["provider"] == "deterministic"        # no LLM for a factual question
        assert data["fact_type"] == "recorded"
        assert data["sources"]
        assert "2" in data["answer"]

    async def test_mortality_answer_is_pattern_not_diagnosis(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.post(f"{_aria(fid)}/ask", json={"question": "What is my mortality rate?"},
                                    headers=auth_headers_owner)
        assert r.status_code == 200
        data = r.json()["data"]
        # Either unavailable (no data) or a pattern — never a diagnosis.
        if data["fact_type"] == "calculated":
            assert "not a diagnosis" in data["answer"].lower()

    async def test_context_snapshot_exposed(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"{_aria(fid)}/context", headers=auth_headers_owner)
        assert r.status_code == 200
        ctx = r.json()["data"]
        assert "total_rabbits" in ctx and "farm" in ctx


class TestRBAC:
    async def test_worker_cannot_query_aria(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await async_client.post(f"{_aria(fid)}/ask", json={"question": "hi"}, headers=auth_headers_worker)
        assert r.status_code == 403  # worker lacks AI_QUERY

    async def test_viewer_can_read_context_but_not_ask(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_aria(fid)}/context", headers=auth_headers_viewer)).status_code == 200
        ask = await async_client.post(f"{_aria(fid)}/ask", json={"question": "hi"}, headers=auth_headers_viewer)
        assert ask.status_code == 403  # viewer has AI_INSIGHT_VIEW, not AI_QUERY
