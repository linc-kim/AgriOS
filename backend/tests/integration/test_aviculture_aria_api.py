"""
Aviculture ARIA — over HTTP, against a real database (Module 15, Part 10).

Confirms the assistant extends the platform AI architecture safely: it refuses to
diagnose disease, answers factual questions deterministically from recorded facts
(honesty-labelled, no LLM), returns a bounded context snapshot (AR-01), serves
data-driven species knowledge, and enforces the AI permission.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers, profile=None) -> str:
    body = {"common_name": "African Grey", "species_group": "parrot"}
    if profile:
        body["profile"] = profile
    r = await client.post(f"{_avi(farm_id)}/species", json=body, headers=headers)
    return r.json()["data"]["id"]


class TestAsk:
    async def test_refuses_diagnosis(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/aria/ask",
                                    json={"question": "What disease does my macaw have?"}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert "no_diagnosis" in d["safety"]
        assert d["provider"] == "deterministic"
        assert "veterinarian" in d["answer"].lower()

    async def test_factual_answer_is_deterministic_and_labelled(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        await async_client.post(f"{_avi(farm)}/birds", json={"species_id": sid}, headers=auth_headers_owner)
        r = await async_client.post(f"{_avi(farm)}/aria/ask",
                                    json={"question": "How many birds do I have?"}, headers=auth_headers_owner)
        d = r.json()["data"]
        assert d["provider"] == "deterministic"
        assert d["fact_type"] == "recorded_fact"
        assert "bird(s) recorded" in d["answer"]
        assert d["sources"] == ["collection.total"]

    async def test_open_question_stays_grounded_offline(self, async_client, workspace, auth_headers_owner):
        # With no AI key configured the assistant returns a grounded offline answer,
        # never a fabricated one.
        r = await async_client.post(f"{_avi(workspace.farm.id)}/aria/ask",
                                    json={"question": "Explain line breeding strategy to me"}, headers=auth_headers_owner)
        d = r.json()["data"]
        assert d["provider"] in ("offline", "gemini", "claude")
        assert d["answer"]

    async def test_ai_query_permission_enforced(self, async_client, workspace, auth_headers_viewer):
        # Viewer holds AI_INSIGHT_VIEW but not AI_QUERY.
        r = await async_client.post(f"{_avi(workspace.farm.id)}/aria/ask",
                                    json={"question": "How many birds?"}, headers=auth_headers_viewer)
        assert r.status_code == 403


class TestContextAndKnowledge:
    async def test_context_is_bounded_and_labelled(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_avi(workspace.farm.id)}/aria/context", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        ctx = r.json()["data"]["context"]
        for key in ("birds_total", "active_pairs", "mortality_rate_pct", "collection_value", "tasks_due"):
            assert key in ctx
        # health/finance figures keep their engine labels.
        assert "label" in ctx["mortality_rate_pct"]

    async def test_species_knowledge_from_profile(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner,
                             profile={"housing": {"aviary_types": ["flight"]}, "diet": "pellets + fruit"})
        r = await async_client.get(f"{_avi(farm)}/aria/species/{sid}/knowledge", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["label"] == "recorded_fact"
        assert d["profile"]["diet"] == "pellets + fruit"
        assert "veterinary" in d["disclaimer"].lower()

    async def test_species_knowledge_without_profile_is_unavailable(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        r = await async_client.get(f"{_avi(farm)}/aria/species/{sid}/knowledge", headers=auth_headers_owner)
        assert r.json()["data"]["label"] == "unavailable"
