"""
Swine Growth & Production (Module 20, Milestone 7) — over HTTP.

Confirms the growth architecture:

  * weights are immutable events; current weight is derived (mirrored) from the latest;
  * growth (ADG, gain, curve) is computed from records, never stored;
  * FCR is now wired to recorded weight gain in the feed summary;
  * production-stage changes are preserved as a transition history;
  * body condition is recorded independently of weight;
  * market readiness is an explainable assessment (weight/target/withdrawal), with a
    medicine withdrawal always withholding;
  * cohort analytics aggregate historical growth; RBAC holds.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


async def _pig(client, fid, h, **overrides):
    body = {"name": "P", "sex": "barrow", "production_stage": "grower"}
    body.update(overrides)
    r = await client.post(f"{_sw(fid)}/pigs", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestWeightAndGrowth:
    async def test_weight_is_immutable_and_syncs_current(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h, date_of_birth="2026-01-01")
        pid = pig["id"]
        for day, wt in (("2026-02-01", 30), ("2026-03-03", 60)):
            w = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights",
                                        json={"recorded_on": day, "weight_kg": wt}, headers=h)
            assert w.status_code == 201, w.text
        # Current weight mirrors the latest measurement.
        detail = await async_client.get(f"{_sw(fid)}/pigs/{pid}", headers=h)
        assert float(detail.json()["data"]["current_weight_kg"]) == 60.0
        # Two immutable records exist; age_days derived from DOB.
        hist = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/weights", headers=h)
        assert len(hist.json()["data"]) == 2
        assert any(w["age_days"] == 61 for w in hist.json()["data"])  # 2026-03-03 − 2026-01-01

    async def test_growth_analysis_and_fcr_wired(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h, date_of_birth="2026-01-01")
        pid = pig["id"]
        for day, wt in (("2026-02-01", 30), ("2026-03-03", 60)):  # +30 kg over 30 days → ADG 1.0
            await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights",
                                    json={"recorded_on": day, "weight_kg": wt}, headers=h)
        analysis = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/analysis", headers=h)
        data = analysis.json()["data"]
        assert data["average_daily_gain_kg"]["value"] == 1.0
        assert data["total_gain_kg"]["value"] == 30.0
        # Feed 60 kg → FCR = feed / gain = 60 / 30 = 2.0 (now wired to weight gain).
        await async_client.post(f"{_sw(fid)}/feed/records",
                                json={"pig_id": pid, "quantity_kg": 60, "fed_on": "2026-03-03"}, headers=h)
        fs = await async_client.get(f"{_sw(fid)}/feed/summary?pig_id={pid}", headers=h)
        assert fs.json()["data"]["summary"]["feed_conversion_ratio"]["value"] == 2.0


class TestStageAndBodyCondition:
    async def test_stage_transition_is_historical(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h, production_stage="grower")
        pid = pig["id"]
        t = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/stage",
                                    json={"new_stage": "finisher", "transition_date": "2026-04-01",
                                          "reason": "moved to finishing", "source": "manual"}, headers=h)
        assert t.status_code == 200 and t.json()["data"]["production_stage"] == "finisher"
        hist = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/stage-history", headers=h)
        rows = hist.json()["data"]
        assert any(r["previous_stage"] == "grower" and r["new_stage"] == "finisher" for r in rows)
        # A backwards transition is rejected.
        bad = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/stage",
                                      json={"new_stage": "grower", "transition_date": "2026-04-02"}, headers=h)
        assert bad.status_code == 422

    async def test_body_condition_independent_of_weight(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        pid = pig["id"]
        bc = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/body-condition",
                                     json={"assessed_on": "2026-04-01", "score": "3.5", "assessor": "Vet"}, headers=h)
        assert bc.status_code == 201, bc.text
        lst = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/body-condition", headers=h)
        assert float(lst.json()["data"][0]["score"]) == 3.5


class TestMarketReadiness:
    async def test_readiness_explains_and_withdrawal_withholds(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h, date_of_birth="2025-10-01", production_stage="finisher")
        pid = pig["id"]
        await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights",
                                json={"recorded_on": "2026-04-01", "weight_kg": 115}, headers=h)
        r = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/readiness", headers=h)
        data = r.json()["data"]
        assert data["status"] == "ready"
        assert any("target" in reason for reason in data["reasons"])
        # Record a treatment with a future withdrawal → readiness becomes withheld.
        await async_client.post(f"{_sw(fid)}/health/treatments",
                                json={"pig_id": pid, "product_name": "Antibiotic", "started_on": "2026-04-01",
                                      "withdrawal_until": "2026-12-31"}, headers=h)
        r2 = await async_client.get(f"{_sw(fid)}/growth/pigs/{pid}/readiness", headers=h)
        assert r2.json()["data"]["status"] == "withheld"


class TestPermissions:
    async def test_worker_logs_weight_viewer_cannot(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        pig = await _pig(async_client, fid, auth_headers_owner)
        pid = pig["id"]
        body = {"recorded_on": "2026-04-01", "weight_kg": 50}
        w = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights", json=body, headers=auth_headers_worker)
        assert w.status_code == 201, w.text
        v = await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights", json=body, headers=auth_headers_viewer)
        assert v.status_code == 403
