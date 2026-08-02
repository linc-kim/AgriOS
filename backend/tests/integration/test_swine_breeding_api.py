"""
Swine Breeding, AI & Pregnancy (Module 20, Milestone 3) — over HTTP.

Confirms the reproduction cycle wires real data through the deterministic engine:

  * natural mating requires an intact boar sire and a sow/gilt dam;
  * a barrow is never a valid sire (the wether rule) — eligibility rejects it;
  * artificial insemination may omit an on-farm sire but must record a semen source;
  * a pregnancy check confirms pregnancy, forecasts farrowing, updates the dam;
  * a dam with an open cycle cannot be re-serviced;
  * the pregnancies view lists confirmed pregnancies;
  * compatibility flags a barrow sire and reuses the shared genetics engine;
  * the reproduction summary reports conception/pregnancy rates deterministically.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/swine"


async def _pig(client, farm_id, headers, sex, **overrides) -> dict:
    body = {"name": sex.title(), "sex": sex}
    body.update(overrides)
    r = await client.post(f"{_sw(farm_id)}/pigs", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestBreeding:
    async def test_natural_breeding_and_pregnancy_flow(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, "boar")
        sow = await _pig(async_client, fid, h, "sow")
        r = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar["id"], "method": "natural",
                  "service_date": "2026-01-01"},
            headers=h,
        )
        assert r.status_code == 201, r.text
        b = r.json()["data"]
        assert b["status"] == "serviced"
        # Planned farrowing = service + ~114d gestation (forecast).
        assert b["planned_farrowing_date"] == "2026-04-25"
        # Pregnancy check confirms and forecasts.
        chk = await async_client.post(
            f"{_sw(fid)}/breeding/{b['id']}/pregnancy-check",
            json={"checked_on": "2026-01-25", "result": "pregnant", "method": "ultrasound"},
            headers=h,
        )
        assert chk.status_code == 200 and chk.json()["data"]["status"] == "pregnant"
        # Dam now reads as pregnant.
        dam = await async_client.get(f"{_sw(fid)}/pigs/{sow['id']}", headers=h)
        assert dam.json()["data"]["reproductive_status"] == "pregnant"
        # Pregnancy workspace lists it.
        preg = await async_client.get(f"{_sw(fid)}/breeding/pregnancies", headers=h)
        assert any(p["id"] == b["id"] for p in preg.json()["data"])

    async def test_barrow_is_never_a_valid_sire(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        barrow = await _pig(async_client, fid, h, "barrow")
        sow = await _pig(async_client, fid, h, "sow")
        r = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": barrow["id"], "method": "natural"},
            headers=h,
        )
        assert r.status_code == 409
        assert "barrow" in r.text.lower()

    async def test_gilt_is_a_valid_dam(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, "boar")
        gilt = await _pig(async_client, fid, h, "gilt")
        r = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": gilt["id"], "sire_id": boar["id"], "method": "natural"},
            headers=h,
        )
        assert r.status_code == 201, r.text

    async def test_ai_requires_semen_source_when_no_sire(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        sow = await _pig(async_client, fid, h, "sow")
        # AI without a sire and without a semen source is rejected.
        bad = await async_client.post(
            f"{_sw(fid)}/breeding", json={"dam_id": sow["id"], "method": "artificial"}, headers=h
        )
        assert bad.status_code == 422
        # With a recorded semen source it succeeds and logs an insemination event.
        ok = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "method": "artificial", "service_date": "2026-02-01",
                  "semen_source": "AI Stud Co", "semen_batch": "B-42", "technician": "Tech A"},
            headers=h,
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["data"]["method"] == "artificial"
        tl = await async_client.get(f"{_sw(fid)}/pigs/{sow['id']}/timeline", headers=h)
        assert any(e["event_type"] == "inseminated" for e in tl.json()["data"])

    async def test_dam_with_open_cycle_cannot_be_reserviced(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, "boar")
        sow = await _pig(async_client, fid, h, "sow")
        first = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-01-01"}, headers=h,
        )
        assert first.status_code == 201
        second = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-01-02"}, headers=h,
        )
        assert second.status_code == 409 and "open breeding cycle" in second.text


class TestGeneticsAndSummary:
    async def test_compatibility_flags_barrow_sire(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        barrow = await _pig(async_client, fid, h, "barrow")
        sow = await _pig(async_client, fid, h, "sow")
        r = await async_client.get(
            f"{_sw(fid)}/breeding/compatibility",
            params={"sire_id": barrow["id"], "dam_id": sow["id"]}, headers=h,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["blocking"] is True
        assert any(w["code"] == "sex_mismatch" for w in data["warnings"])

    async def test_reproduction_summary_is_deterministic(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, "boar")
        sow = await _pig(async_client, fid, h, "sow")
        b = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-01-01"}, headers=h,
        )
        await async_client.post(
            f"{_sw(fid)}/breeding/{b.json()['data']['id']}/pregnancy-check",
            json={"checked_on": "2026-01-25", "result": "pregnant"}, headers=h,
        )
        summary = await async_client.get(f"{_sw(fid)}/breeding/summary", headers=h)
        data = summary.json()["data"]
        assert data["total_services"]["value"] == 1
        assert data["total_pregnancies"]["value"] == 1
        assert data["conception_rate_pct"]["value"] == 100.0


class TestPermissions:
    async def test_worker_can_breed_but_viewer_cannot(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        boar = await _pig(async_client, fid, auth_headers_owner, "boar")
        sow = await _pig(async_client, fid, auth_headers_owner, "sow")
        body = {"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-03-01"}
        # Worker holds SWINE_BREEDING_MANAGE.
        w = await async_client.post(f"{_sw(fid)}/breeding", json=body, headers=auth_headers_worker)
        assert w.status_code == 201, w.text
        # Viewer cannot write.
        v = await async_client.post(f"{_sw(fid)}/breeding", json=body, headers=auth_headers_viewer)
        assert v.status_code == 403
