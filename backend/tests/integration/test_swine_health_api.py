"""
Swine Health & Biosecurity (Module 20, Milestone 6) — over HTTP.

Confirms the normalized clinical architecture:

  * each clinical type is its own independent record linked to a pig/group;
  * disease cases support group scope (pen/farm outbreaks), not just individuals;
  * vaccination, treatment (intent), procedure, observation and lab test are distinct;
  * mortality creates a cause-history event AND transitions the pig (still traceable);
  * isolation is historical (start → move to isolation pen → end/clearance);
  * biosecurity records are operational and tally by type;
  * the health summary is deterministic and carries the §4.4 disclaimer (no diagnosis);
  * permissions hold (worker logs; viewer cannot).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


async def _pig(client, fid, h, sex="barrow"):
    r = await client.post(f"{_sw(fid)}/pigs", json={"name": "P", "sex": sex}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestClinicalRecords:
    async def test_group_scope_disease_case(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pen = await async_client.post(f"{_sw(fid)}/housing/pens",
                                      json={"name": "Nursery 1", "pen_type": "nursery_pen"}, headers=h)
        pen_id = pen.json()["data"]["id"]
        r = await async_client.post(f"{_sw(fid)}/health/disease-cases",
                                    json={"scope": "pen", "pen_id": pen_id, "disease_name": "PRRS",
                                          "status": "suspected", "severity": "moderate",
                                          "affected_count": 12}, headers=h)
        assert r.status_code == 201, r.text
        assert r.json()["data"]["scope"] == "pen" and r.json()["data"]["affected_count"] == 12
        # Confirm with a recorded vet diagnosis (never inferred).
        cid = r.json()["data"]["id"]
        upd = await async_client.patch(f"{_sw(fid)}/health/disease-cases/{cid}",
                                       json={"status": "confirmed", "diagnosis": "PRRSV PCR positive (vet)"},
                                       headers=h)
        assert upd.json()["data"]["status"] == "confirmed"

    async def test_distinct_clinical_entities(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        pid = pig["id"]
        vac = await async_client.post(f"{_sw(fid)}/health/vaccinations",
                                      json={"pig_id": pid, "vaccine_name": "Mycoplasma",
                                            "administered_on": "2026-05-01", "route": "intramuscular"}, headers=h)
        assert vac.status_code == 201, vac.text
        # Treatment vs preventive medication share a table via intent.
        tx = await async_client.post(f"{_sw(fid)}/health/treatments",
                                     json={"pig_id": pid, "intent": "therapeutic", "product_name": "Amoxicillin",
                                           "started_on": "2026-05-02", "withdrawal_until": "2026-05-16"}, headers=h)
        prev = await async_client.post(f"{_sw(fid)}/health/treatments",
                                       json={"pig_id": pid, "intent": "preventive", "product_name": "Ivermectin",
                                             "started_on": "2026-05-03"}, headers=h)
        assert tx.status_code == 201 and prev.status_code == 201
        onlytx = await async_client.get(f"{_sw(fid)}/health/treatments?intent=therapeutic", headers=h)
        assert all(t["intent"] == "therapeutic" for t in onlytx.json()["data"])
        proc = await async_client.post(f"{_sw(fid)}/health/procedures",
                                       json={"pig_id": pid, "procedure_type": "castration",
                                             "performed_on": "2026-05-04", "analgesia": True}, headers=h)
        obs = await async_client.post(f"{_sw(fid)}/health/observations",
                                      json={"pig_id": pid, "observation_type": "examination",
                                            "observed_on": "2026-05-05", "temperature_c": "39.5",
                                            "findings": "bright, alert"}, headers=h)
        lab = await async_client.post(f"{_sw(fid)}/health/lab-tests",
                                      json={"pig_id": pid, "test_name": "Faecal egg count",
                                            "status": "pending"}, headers=h)
        assert proc.status_code == 201 and obs.status_code == 201 and lab.status_code == 201
        # Lab result recorded later (a fact, never inferred).
        lid = lab.json()["data"]["id"]
        res = await async_client.patch(f"{_sw(fid)}/health/lab-tests/{lid}",
                                       json={"status": "completed", "result": "negative"}, headers=h)
        assert res.json()["data"]["result"] == "negative"


class TestMortalityAndIsolation:
    async def test_mortality_preserves_cause_and_transitions_pig(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        m = await async_client.post(f"{_sw(fid)}/health/mortality",
                                    json={"pig_id": pig["id"], "died_on": "2026-05-10",
                                          "cause_category": "respiratory", "suspected_cause": "pneumonia",
                                          "disposal_method": "incineration"}, headers=h)
        assert m.status_code == 201, m.text
        # The pig is now deceased but still retrievable (traceable).
        p = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        assert p.status_code == 200 and p.json()["data"]["status"] == "deceased"
        # A second mortality on the same pig is rejected.
        again = await async_client.post(f"{_sw(fid)}/health/mortality",
                                        json={"pig_id": pig["id"], "died_on": "2026-05-11"}, headers=h)
        assert again.status_code == 409

    async def test_isolation_is_historical_with_movement(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        iso_pen = await async_client.post(f"{_sw(fid)}/housing/pens",
                                          json={"name": "Iso", "pen_type": "isolation"}, headers=h)
        iso_pen_id = iso_pen.json()["data"]["id"]
        pig = await _pig(async_client, fid, h)
        start = await async_client.post(f"{_sw(fid)}/health/isolations",
                                        json={"pig_id": pig["id"], "pen_id": iso_pen_id, "reason": "disease",
                                              "started_on": "2026-05-06"}, headers=h)
        assert start.status_code == 201, start.text
        iso_id = start.json()["data"]["id"]
        # The pig was moved to the isolation pen with a recorded movement.
        hist = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}/movements", headers=h)
        assert any(mv["movement_type"] == "isolation" for mv in hist.json()["data"])
        end = await async_client.post(f"{_sw(fid)}/health/isolations/{iso_id}/end",
                                      json={"ended_on": "2026-05-20", "cleared": True,
                                            "cleared_by": "Vet A"}, headers=h)
        assert end.status_code == 200 and end.json()["data"]["status"] == "cleared"


class TestBiosecurityAndSummary:
    async def test_biosecurity_records_and_summary(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        for rt in ("visitor_log", "pen_cleaning", "rodent_control"):
            r = await async_client.post(f"{_sw(fid)}/biosecurity",
                                        json={"record_type": rt, "occurred_on": "2026-05-01",
                                              "performed_by": "Staff"}, headers=h)
            assert r.status_code == 201, r.text
        s = await async_client.get(f"{_sw(fid)}/biosecurity/summary", headers=h)
        assert s.json()["data"]["total"] == 3
        assert set(s.json()["data"]["by_type"]) == {"visitor_log", "pen_cleaning", "rodent_control"}

    async def test_health_summary_has_disclaimer(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        await async_client.post(f"{_sw(fid)}/health/disease-cases",
                                json={"pig_id": pig["id"], "disease_name": "Scours"}, headers=h)
        s = await async_client.get(f"{_sw(fid)}/health/summary", headers=h)
        data = s.json()["data"]
        assert "disclaimer" in data and "diagnosis" not in data
        assert data["total_disease_cases"]["value"] >= 1


class TestPermissions:
    async def test_worker_logs_viewer_cannot(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        pig = await _pig(async_client, fid, auth_headers_owner)
        body = {"pig_id": pig["id"], "observation_type": "routine_check", "observed_on": "2026-05-01"}
        w = await async_client.post(f"{_sw(fid)}/health/observations", json=body, headers=auth_headers_worker)
        assert w.status_code == 201, w.text
        v = await async_client.post(f"{_sw(fid)}/health/observations", json=body, headers=auth_headers_viewer)
        assert v.status_code == 403
