"""
Swine Farrowing, Litters & Fostering (Module 20, Milestone 4) — over HTTP.

Confirms the offspring lifecycle on the refined architecture:

  * a farrowing resolves its pregnancy (status → farrowed) and creates a litter,
    updating the dam (lactating, parity++);
  * litter-level management works without any individual pig rows;
  * individual pigs can be created against a litter (production_stage=piglet, birth_sex);
  * pre-wean mortality is recorded on the litter;
  * cross-fostering moves individual piglets, updating nurse sow + foster counts and
    preserving birth-litter traceability;
  * weaning closes the litter, frees the dam, and advances individual piglets to weaner;
  * herd litter analytics are deterministic (live-birth rate, avg litter size).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/swine"


async def _pig(client, fid, h, sex):
    r = await client.post(f"{_sw(fid)}/pigs", json={"name": sex.title(), "sex": sex}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _pregnant_sow(client, fid, h, service_date="2026-01-01"):
    boar = await _pig(client, fid, h, "boar")
    sow = await _pig(client, fid, h, "sow")
    b = await client.post(f"{_sw(fid)}/breeding",
                          json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": service_date},
                          headers=h)
    chk = await client.post(f"{_sw(fid)}/breeding/{b.json()['data']['id']}/pregnancy-check",
                            json={"checked_on": "2026-01-25", "result": "pregnant"}, headers=h)
    return sow, b.json()["data"], chk.json()["data"]["pregnancy"]


class TestFarrowing:
    async def test_farrowing_resolves_pregnancy_and_creates_litter(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        sow, _b, preg = await _pregnant_sow(async_client, fid, h)
        f = await async_client.post(
            f"{_sw(fid)}/farrowing",
            json={"pregnancy_id": preg["id"], "farrowing_date": "2026-04-25",
                  "born_alive": 11, "stillborn": 1, "mummified": 1}, headers=h,
        )
        assert f.status_code == 201, f.text
        data = f.json()["data"]
        assert data["litter"]["total_born"] == 13 and data["litter"]["born_alive"] == 11
        # Pregnancy resolved to farrowed.
        pd = await async_client.get(f"{_sw(fid)}/pregnancy/{preg['id']}", headers=h)
        assert pd.json()["data"]["pregnancy"]["status"] == "farrowed"
        # Dam lactating with parity 1.
        dam = await async_client.get(f"{_sw(fid)}/pigs/{sow['id']}", headers=h)
        assert dam.json()["data"]["reproductive_status"] == "lactating"
        assert dam.json()["data"]["parity"] == 1

    async def test_individual_piglets_and_performance(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _pregnant_sow(async_client, fid, h)
        f = await async_client.post(
            f"{_sw(fid)}/farrowing",
            json={"pregnancy_id": preg["id"], "farrowing_date": "2026-04-25", "born_alive": 3,
                  "create_individuals": [
                      {"birth_sex": "male", "birth_weight_kg": "1.4"},
                      {"birth_sex": "female", "birth_weight_kg": "1.3"}]},
            headers=h,
        )
        assert f.status_code == 201, f.text
        assert len(f.json()["data"]["individuals_created"]) == 2
        litter_id = f.json()["data"]["litter"]["id"]
        detail = await async_client.get(f"{_sw(fid)}/farrowing/litters/{litter_id}", headers=h)
        assert detail.json()["data"]["individual_pig_count"] == 2
        # Live-birth rate is deterministic (3 alive / 3 born).
        assert detail.json()["data"]["performance"]["live_birth_rate_pct"]["value"] == 100.0
        # The piglets are pigs at production_stage=piglet with birth_sex recorded.
        pigs = await async_client.get(f"{_sw(fid)}/pigs?production_stage=piglet", headers=h)
        assert len(pigs.json()["data"]) == 2
        assert {p["birth_sex"] for p in pigs.json()["data"]} == {"male", "female"}


class TestFostering:
    async def test_cross_foster_moves_individuals_and_counts(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        # Two litters from two sows.
        _s1, _b1, p1 = await _pregnant_sow(async_client, fid, h, service_date="2026-01-01")
        _s2, _b2, p2 = await _pregnant_sow(async_client, fid, h, service_date="2026-01-03")
        f1 = await async_client.post(f"{_sw(fid)}/farrowing",
                                     json={"pregnancy_id": p1["id"], "farrowing_date": "2026-04-25",
                                           "born_alive": 2,
                                           "create_individuals": [{"birth_sex": "male"}, {"birth_sex": "male"}]},
                                     headers=h)
        f2 = await async_client.post(f"{_sw(fid)}/farrowing",
                                     json={"pregnancy_id": p2["id"], "farrowing_date": "2026-04-27",
                                           "born_alive": 6}, headers=h)
        l1, l2 = f1.json()["data"]["litter"]["id"], f2.json()["data"]["litter"]["id"]
        pigs = await async_client.get(f"{_sw(fid)}/pigs?production_stage=piglet", headers=h)
        move_pig = pigs.json()["data"][0]
        # Foster one individual piglet from litter 1 → litter 2.
        r = await async_client.post(
            f"{_sw(fid)}/farrowing/foster",
            json={"source_litter_id": l1, "dest_litter_id": l2, "pig_ids": [move_pig["id"]],
                  "transfer_date": "2026-04-28", "reason": "even out litters"}, headers=h,
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["piglet_count"] == 1
        # The moved pig keeps its birth litter but gains a nurse (foster) sow, and a
        # movement-history row exists.
        moved = await async_client.get(f"{_sw(fid)}/pigs/{move_pig['id']}", headers=h)
        assert moved.json()["data"]["litter_id"] == l1
        assert moved.json()["data"]["nurse_dam_id"] is not None
        hist = await async_client.get(f"{_sw(fid)}/pigs/{move_pig['id']}/movements", headers=h)
        assert any(m["movement_type"] == "farrowing_move" for m in hist.json()["data"])


class TestWeaningAndAnalytics:
    async def test_weaning_closes_litter_frees_dam_advances_piglets(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        sow, _b, preg = await _pregnant_sow(async_client, fid, h)
        f = await async_client.post(f"{_sw(fid)}/farrowing",
                                    json={"pregnancy_id": preg["id"], "farrowing_date": "2026-04-25",
                                          "born_alive": 4,
                                          "create_individuals": [{"birth_sex": "male"}, {"birth_sex": "female"}]},
                                    headers=h)
        litter_id = f.json()["data"]["litter"]["id"]
        # One pre-wean death.
        await async_client.post(f"{_sw(fid)}/farrowing/litters/{litter_id}/mortality",
                                json={"count": 1, "cause": "crushed"}, headers=h)
        wean = await async_client.post(f"{_sw(fid)}/farrowing/litters/{litter_id}/wean",
                                       json={"weaned": 3, "weaning_date": "2026-05-20"}, headers=h)
        assert wean.status_code == 200, wean.text
        assert wean.json()["data"]["status"] == "weaned" and wean.json()["data"]["weaned"] == 3
        # Dam freed.
        dam = await async_client.get(f"{_sw(fid)}/pigs/{sow['id']}", headers=h)
        assert dam.json()["data"]["reproductive_status"] == "weaned"
        # Individual piglets advanced to weaner.
        weaners = await async_client.get(f"{_sw(fid)}/pigs?production_stage=weaner", headers=h)
        assert len(weaners.json()["data"]) == 2

    async def test_cannot_wean_more_than_nursing(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _pregnant_sow(async_client, fid, h)
        f = await async_client.post(f"{_sw(fid)}/farrowing",
                                    json={"pregnancy_id": preg["id"], "farrowing_date": "2026-04-25",
                                          "born_alive": 3}, headers=h)
        litter_id = f.json()["data"]["litter"]["id"]
        bad = await async_client.post(f"{_sw(fid)}/farrowing/litters/{litter_id}/wean",
                                      json={"weaned": 5, "weaning_date": "2026-05-20"}, headers=h)
        assert bad.status_code == 422

    async def test_farrowing_summary_is_deterministic(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        _sow, _b, preg = await _pregnant_sow(async_client, fid, h)
        await async_client.post(f"{_sw(fid)}/farrowing",
                                json={"pregnancy_id": preg["id"], "farrowing_date": "2026-04-25",
                                      "born_alive": 10, "stillborn": 2}, headers=h)
        summary = await async_client.get(f"{_sw(fid)}/farrowing/summary", headers=h)
        data = summary.json()["data"]
        assert data["total_farrowings"]["value"] == 1
        assert data["avg_litter_size"]["value"] == 12.0   # 12 born / 1 farrowing
        assert data["live_birth_rate_pct"]["value"] == round(10 / 12 * 100, 1)
