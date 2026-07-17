"""
Greena — Module 9 ARIA AI Platform integration tests.

Covers the unified context builder, forecasts, explainable mortality prediction
and disease-risk scoring, the AI dashboard, and the offline-safe assistant
(caching + rate-limit fields), plus RBAC.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


def _ai(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/ai"


async def test_context_builder(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_ai(test_farm.id)}/context", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for key in ("feed", "finance", "inventory", "health", "production"):
        assert key in d and isinstance(d[key], dict)


async def test_forecasts(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_ai(test_farm.id)}/forecasts", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for key in ("feed", "financial", "inventory", "production"):
        assert d[key] is not None
        assert "projected_value" in d[key] and "confidence" in d[key] and isinstance(d[key]["factors"], list)


async def test_mortality_prediction_explainable(async_client, test_farm, test_flock, auth_headers_owner):
    # Seed some mortality so the prediction has signal.
    await async_client.post(f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/logs", json={
        "log_date": str(date.today() - timedelta(days=1)), "mortality_count": 6, "culls": 1,
        "feed_consumed_kg": "30.0"}, headers=auth_headers_owner)

    r = await async_client.get(f"{_ai(test_farm.id)}/predictions/mortality", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["predicted_next_7d"] >= 0
    assert d["trend"] in ("rising", "stable", "falling")
    assert d["confidence"] in ("low", "medium", "high")
    assert len(d["factors"]) >= 2  # explainable
    assert d["explanation"]


async def test_disease_risk_scoring(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_ai(test_farm.id)}/predictions/disease-risk", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert 0 <= d["score"] <= 100
    assert d["level"] in ("low", "moderate", "high", "critical")
    assert len(d["factors"]) >= 1
    assert d["recommendation"]


async def test_dashboard(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_ai(test_farm.id)}/dashboard", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert "forecasts" in d and "mortality" in d and "disease_risk" in d
    assert d["providers"]["offline_fallback"] is True
    assert d["headline"]


async def test_ask_offline_safe_and_cache(async_client, test_farm, test_flock, auth_headers_owner):
    # First ask → computed by offline fallback (no keys configured in tests).
    r1 = await async_client.post(f"{_ai(test_farm.id)}/ask", json={"question": "How is my feed stock?"}, headers=auth_headers_owner)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["provider"] == "offline"
    assert d1["cached"] is False
    assert "feed" in d1["sources"]
    assert d1["answer"]
    assert d1["rate_limit_remaining"] is not None

    # Same question again → served from cache.
    r2 = await async_client.post(f"{_ai(test_farm.id)}/ask", json={"question": "How is my feed stock?"}, headers=auth_headers_owner)
    assert r2.status_code == 200
    assert r2.json()["data"]["cached"] is True

    # A finance question routes to the finance context.
    r3 = await async_client.post(f"{_ai(test_farm.id)}/ask", json={"question": "What is my profit this month?"}, headers=auth_headers_owner)
    assert r3.status_code == 200
    assert "finance" in r3.json()["data"]["sources"]


async def test_ask_disease_question_uses_risk(async_client, test_farm, auth_headers_owner):
    r = await async_client.post(f"{_ai(test_farm.id)}/ask", json={"question": "What is my disease risk?"}, headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    assert "health" in r.json()["data"]["sources"]
    assert "risk" in r.json()["data"]["answer"].lower() or "/100" in r.json()["data"]["answer"]


async def test_rbac_viewer_reads_worker_denied_ask(async_client, test_farm, auth_headers_viewer, auth_headers_worker):
    # Viewer can read AI insights (dashboard).
    assert (await async_client.get(f"{_ai(test_farm.id)}/dashboard", headers=auth_headers_viewer)).status_code == 200
    # Worker lacks AI_QUERY → cannot ask.
    denied = await async_client.post(f"{_ai(test_farm.id)}/ask", json={"question": "hi"}, headers=auth_headers_worker)
    assert denied.status_code == 403
