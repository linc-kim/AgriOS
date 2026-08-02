"""
Swine Pregnancy lifecycle (Module 20, Milestone 3) — over HTTP.

Pregnancy is its own table + workspace, confirmed from a breeding service:

  * a positive pregnancy check creates a confirmed pregnancy and resolves the breeding;
  * a negative check resolves the breeding as not-pregnant with no pregnancy row;
  * a dam cannot hold two active pregnancies at once;
  * a pregnancy can be rechecked (risk updated), and resolved as loss / false;
  * pregnancy detail exposes deterministic gestation progress;
  * a resolved pregnancy frees the dam (reproductive_status → open).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/swine"


async def _pig(client, farm_id, headers, sex):
    r = await client.post(f"{_sw(farm_id)}/pigs", json={"name": sex.title(), "sex": sex}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _breed_and_confirm(client, fid, h, service_date="2026-01-01", check_date="2026-01-25"):
    boar = await _pig(client, fid, h, "boar")
    sow = await _pig(client, fid, h, "sow")
    b = await client.post(
        f"{_sw(fid)}/breeding",
        json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": service_date}, headers=h,
    )
    assert b.status_code == 201, b.text
    chk = await client.post(
        f"{_sw(fid)}/breeding/{b.json()['data']['id']}/pregnancy-check",
        json={"checked_on": check_date, "result": "pregnant", "method": "ultrasound"}, headers=h,
    )
    assert chk.status_code == 200, chk.text
    return sow, b.json()["data"], chk.json()["data"]["pregnancy"]


class TestPregnancyLifecycle:
    async def test_confirm_lists_and_progress(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _breed_and_confirm(async_client, fid, h)
        assert preg["status"] == "confirmed"
        # Detail exposes gestation progress (deterministic).
        detail = await async_client.get(f"{_sw(fid)}/pregnancy/{preg['id']}", headers=h)
        assert detail.status_code == 200
        prog = detail.json()["data"]["gestation_progress"]
        assert "days_elapsed" in prog and "expected_farrowing_date" in prog

    async def test_negative_check_creates_no_pregnancy(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, "boar")
        sow = await _pig(async_client, fid, h, "sow")
        b = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-01-01"}, headers=h,
        )
        chk = await async_client.post(
            f"{_sw(fid)}/breeding/{b.json()['data']['id']}/pregnancy-check",
            json={"checked_on": "2026-01-25", "result": "not_pregnant"}, headers=h,
        )
        assert chk.status_code == 200
        assert chk.json()["data"]["breeding"]["outcome"] == "not_pregnant"
        assert chk.json()["data"]["pregnancy"] is None
        # No active pregnancies listed.
        preg = await async_client.get(f"{_sw(fid)}/pregnancy", headers=h)
        assert preg.json()["data"] == []

    async def test_dam_cannot_hold_two_active_pregnancies(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        sow, _b, _preg = await _breed_and_confirm(async_client, fid, h)
        boar2 = await _pig(async_client, fid, h, "boar")
        # A fresh service for the same (now pregnant) sow is blocked at breeding time
        # (open-cycle), so free her cycle is already closed — re-serviceable check is
        # on the pregnancy: force a second breeding + check and expect the active
        # pregnancy guard.
        b2 = await async_client.post(
            f"{_sw(fid)}/breeding",
            json={"dam_id": sow["id"], "sire_id": boar2["id"], "service_date": "2026-02-01"}, headers=h,
        )
        assert b2.status_code == 201, b2.text  # breeding.status closed after first check, so allowed
        chk2 = await async_client.post(
            f"{_sw(fid)}/breeding/{b2.json()['data']['id']}/pregnancy-check",
            json={"checked_on": "2026-02-20", "result": "pregnant"}, headers=h,
        )
        assert chk2.status_code == 409 and "active pregnancy" in chk2.text

    async def test_recheck_updates_risk(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _breed_and_confirm(async_client, fid, h)
        r = await async_client.post(
            f"{_sw(fid)}/pregnancy/{preg['id']}/recheck", json={"risk_level": "high"}, headers=h
        )
        assert r.status_code == 200 and r.json()["data"]["risk_level"] == "high"

    async def test_loss_resolves_and_frees_dam(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        sow, _b, preg = await _breed_and_confirm(async_client, fid, h)
        loss = await async_client.post(
            f"{_sw(fid)}/pregnancy/{preg['id']}/loss",
            json={"loss_reason": "abortion", "loss_date": "2026-02-10"}, headers=h,
        )
        assert loss.status_code == 200 and loss.json()["data"]["status"] == "lost"
        # Dam is freed.
        dam = await async_client.get(f"{_sw(fid)}/pigs/{sow['id']}", headers=h)
        assert dam.json()["data"]["reproductive_status"] == "open"
        # No longer in the active pregnancy list.
        active = await async_client.get(f"{_sw(fid)}/pregnancy", headers=h)
        assert all(p["id"] != preg["id"] for p in active.json()["data"])

    async def test_false_pregnancy(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _breed_and_confirm(async_client, fid, h)
        r = await async_client.post(
            f"{_sw(fid)}/pregnancy/{preg['id']}/loss", json={"false_pregnancy": True}, headers=h
        )
        assert r.status_code == 200 and r.json()["data"]["status"] == "false_pregnancy"
