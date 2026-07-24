"""
ARIA farm intelligence — over HTTP, against a real database.

The pure engine is exhaustively unit-tested; these confirm the endpoints wire
the real farm data through it and that the deterministic answer path (knowledge
+ decision) works end to end with no AI provider involved.
"""

import pytest


pytestmark = pytest.mark.asyncio


class TestIntelligenceEndpoint:
    async def test_returns_the_full_operations_view(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(
            f"/api/v1/farms/{workspace.farm.id}/aria/intelligence",
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert {"briefing", "health", "insights", "checklist", "trends"} <= set(data)
        # Health score is a real 0–100 with five explained factors.
        assert 0 <= data["health"]["score"] <= 100
        assert len(data["health"]["factors"]) == 5
        for f in data["health"]["factors"]:
            assert f["explanation"]
        # Briefing has status lines and priorities.
        assert data["briefing"]["lines"]
        assert data["briefing"]["priorities"]

    async def test_every_insight_is_fully_explained(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(
            f"/api/v1/farms/{workspace.farm.id}/aria/intelligence",
            headers=auth_headers_owner,
        )
        for insight in r.json()["data"]["insights"]:
            assert insight["problem"] and insight["reason"]
            assert insight["action"] and insight["benefit"]
            assert insight["sources"]

    async def test_briefing_endpoint(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(
            f"/api/v1/farms/{workspace.farm.id}/aria/briefing",
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["greeting"]


class TestDeterministicAnswer:
    async def test_knowledge_question(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(
            f"/api/v1/farms/{workspace.farm.id}/aria/answer",
            json={"question": "what are the signs of coccidiosis?"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["type"] == "knowledge"
        assert data["knowledge"]["key"] == "coccidiosis"
        # §4.4: disease knowledge carries the see-a-vet boundary.
        assert data["knowledge"]["vet_now"] is True

    async def test_decision_question(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(
            f"/api/v1/farms/{workspace.farm.id}/aria/answer",
            json={"question": "should I vaccinate today?"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["type"] == "decision"
        # Never a bare verdict — the case is laid out.
        d = data["decision"]
        assert d["lean"] in ("consider", "caution", "hold", "need_info")

    async def test_unknown_question_returns_none(
        self, async_client, workspace, auth_headers_owner
    ):
        """The honest edge: neither knowledge nor decision, so the client falls back."""
        r = await async_client.post(
            f"/api/v1/farms/{workspace.farm.id}/aria/answer",
            json={"question": "what is the capital of France?"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["type"] == "none"

    async def test_answer_never_calls_an_ai_provider(
        self, async_client, workspace, auth_headers_owner, monkeypatch
    ):
        import app.services.ai_provider as ai_provider

        async def _explode(*a, **k):  # pragma: no cover
            raise AssertionError("deterministic answer must not consult an AI provider")

        monkeypatch.setattr(ai_provider, "complete", _explode)
        r = await async_client.post(
            f"/api/v1/farms/{workspace.farm.id}/aria/answer",
            json={"question": "how do i vaccinate for newcastle"},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["type"] == "knowledge"
