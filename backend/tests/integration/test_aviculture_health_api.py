"""
Health Engine — over HTTP, against a real database (Module 15, Part 6).

Confirms individual-bird health wires through the pure engine: medical records on
the extended foundation table, weight trend, quarantine lifecycle, disease events,
the veterinary-guidance disclaimer on diagnostic records, the farm health summary
Mission Control reads, and permissions (vet can write clinical records; viewer
cannot).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "Canary", "species_group": "canary"}, headers=headers)
    return r.json()["data"]["id"]


async def _bird(client, farm_id, headers, sid) -> str:
    r = await client.post(f"{_avi(farm_id)}/birds", json={"species_id": sid}, headers=headers)
    return r.json()["data"]["id"]


class TestRecords:
    async def test_add_record_appends_timeline(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                    json={"record_type": "vaccination", "title": "Polyomavirus",
                                          "next_due_on": "2027-01-01"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        # It shows on the bird timeline (reused Part 2 event stream).
        tl = await async_client.get(f"{_avi(farm)}/birds/{bird}/timeline", headers=auth_headers_owner)
        assert any(e["event_type"] == "health_recorded" for e in tl.json()["data"])

    async def test_diagnostic_record_carries_disclaimer(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                    json={"record_type": "exam", "title": "Lethargy check",
                                          "details": {"differential_diagnoses": ["giardia", "PBFD"]}},
                                    headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        assert "_disclaimer" in r.json()["data"]["details"]

    async def test_vet_can_write_viewer_cannot(self, async_client, workspace, auth_headers_owner, auth_headers_vet, auth_headers_viewer):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        rv = await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                     json={"record_type": "vet_visit", "title": "Checkup"}, headers=auth_headers_vet)
        assert rv.status_code == 201, rv.text
        rn = await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                     json={"record_type": "observation"}, headers=auth_headers_viewer)
        assert rn.status_code == 403

    async def test_weight_trend(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        for d, w in (("2026-07-01", "20.0"), ("2026-07-20", "26.0")):
            await async_client.post(f"{_avi(farm)}/birds/{bird}/health",
                                    json={"record_type": "weight", "recorded_on": d, "weight_grams": w},
                                    headers=auth_headers_owner)
        r = await async_client.get(f"{_avi(farm)}/birds/{bird}/weight-trend", headers=auth_headers_owner)
        t = r.json()["data"]["trend"]
        assert t["direction"]["value"] == "up"
        assert t["change_grams"]["value"] == 6.0
        assert t["change_grams"]["label"] == "calculated"


class TestQuarantineAndDisease:
    async def test_quarantine_lifecycle(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        rs = await async_client.post(f"{_avi(farm)}/birds/{bird}/quarantine",
                                     json={"reason": "new arrival", "started_on": "2026-07-01"}, headers=auth_headers_owner)
        assert rs.status_code == 201, rs.text
        qid = rs.json()["data"]["id"]
        # Second active quarantine is rejected.
        rs2 = await async_client.post(f"{_avi(farm)}/birds/{bird}/quarantine", json={}, headers=auth_headers_owner)
        assert rs2.status_code == 409
        # Release it.
        rr = await async_client.post(f"{_avi(farm)}/quarantine/{qid}/release",
                                     json={"outcome": "cleared"}, headers=auth_headers_owner)
        assert rr.status_code == 200 and rr.json()["data"]["status"] == "released"

    async def test_disease_event_resolution(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        rc = await async_client.post(f"{_avi(farm)}/disease-events",
                                     json={"disease_name": "Coccidiosis", "status": "confirmed",
                                           "affected_count": 3, "is_notifiable": False}, headers=auth_headers_owner)
        assert rc.status_code == 201, rc.text
        eid = rc.json()["data"]["id"]
        ru = await async_client.patch(f"{_avi(farm)}/disease-events/{eid}",
                                      json={"status": "resolved"}, headers=auth_headers_owner)
        assert ru.status_code == 200 and ru.json()["data"]["resolved_on"] is not None


class TestSummary:
    async def test_health_summary_is_labelled(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        r = await async_client.get(f"{_avi(farm)}/health/summary", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert "label" in d["mortality_rate_pct"]
        assert "label" in d["vaccination_coverage_pct"]
        assert "preventive_due" in d
