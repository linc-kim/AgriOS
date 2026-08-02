"""
Small Ruminant Breeding (Modules 18/19, Milestone 3) — over HTTP.

The full shared reproduction cycle for both species over one implementation:
register a dam and sire, breed, check pregnancy, record the birth (kidding for
goats, lambing for sheep) with automatic offspring creation carrying sire/dam/
birth pedigree links, then wean. Eligibility, pedigree and permissions are
enforced identically for goats and sheep.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _animal(client, fid, species, headers, sex, name) -> str:
    r = await client.post(f"{_sr(fid, species)}/animals", json={"name": name, "sex": sex}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestBreedingCycle:
    @pytest.mark.parametrize("species,dam_sex,sire_sex", [("goat", "doe", "buck"), ("sheep", "ewe", "ram")])
    async def test_full_cycle_with_offspring(
        self, async_client, workspace, auth_headers_owner, species, dam_sex, sire_sex
    ):
        fid = workspace.farm.id
        dam = await _animal(async_client, fid, species, auth_headers_owner, dam_sex, "Dam")
        sire = await _animal(async_client, fid, species, auth_headers_owner, sire_sex, "Sire")
        base = f"{_sr(fid, species)}/breeding"

        # Create breeding with a service date → planned birth date is forecast.
        br = await async_client.post(
            base, json={"dam_id": dam, "sire_id": sire, "service_date": "2026-01-01"},
            headers=auth_headers_owner,
        )
        assert br.status_code == 201, br.text
        bid = br.json()["data"]["id"]
        assert br.json()["data"]["planned_birth_date"] is not None
        assert br.json()["data"]["status"] == "serviced"

        # Confirm pregnancy.
        pc = await async_client.post(
            f"{base}/{bid}/pregnancy-check", json={"checked_on": "2026-02-01", "result": "pregnant"},
            headers=auth_headers_owner,
        )
        assert pc.status_code == 200 and pc.json()["data"]["status"] == "pregnant"

        # Record birth with two live offspring auto-created.
        birth = await async_client.post(
            f"{base}/{bid}/birth",
            json={"birth_date": "2026-05-30", "birth_type": "twin", "total_born": 2,
                  "live_born": 2, "create_offspring": True},
            headers=auth_headers_owner,
        )
        assert birth.status_code == 201, birth.text
        payload = birth.json()["data"]
        assert len(payload["offspring_created"]) == 2
        birth_id = payload["birth"]["id"]

        # Offspring exist with sire/dam links.
        listing = await async_client.get(f"{_sr(fid, species)}/animals", headers=auth_headers_owner)
        kids = [a for a in listing.json()["data"] if a["dam_id"] == dam and a["sire_id"] == sire]
        assert len(kids) == 2
        assert all(k["lifecycle_stage"] == "newborn" for k in kids)

        # Pedigree of a kid resolves to the two parents.
        ped = await async_client.get(
            f"{base}/pedigree/{kids[0]['id']}", headers=auth_headers_owner
        )
        assert ped.status_code == 200
        assert ped.json()["data"]["inbreeding_coefficient"]["label"] == "calculated"

        # Wean both.
        wean = await async_client.post(
            f"{base}/births/{birth_id}/wean", json={"weaned": 2, "weaning_date": "2026-08-01"},
            headers=auth_headers_owner,
        )
        assert wean.status_code == 200 and wean.json()["data"]["status"] == "weaned"

        # Reproduction summary reflects the recorded facts.
        summ = await async_client.get(f"{base}/summary", headers=auth_headers_owner)
        s = summ.json()["data"]
        assert s["total_births"]["value"] >= 1 and s["total_offspring_weaned"]["value"] >= 2

    async def test_ineligible_pairing_is_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe = await _animal(async_client, fid, "goat", auth_headers_owner, "doe", "D")
        wether = await _animal(async_client, fid, "goat", auth_headers_owner, "wether", "W")
        # A wether is castrated — not a valid sire.
        r = await async_client.post(
            f"{_sr(fid, 'goat')}/breeding", json={"dam_id": doe, "sire_id": wether},
            headers=auth_headers_owner,
        )
        assert r.status_code == 409
        assert "buck" in r.text  # the eligibility reason names the required sire term

    async def test_open_cycle_blocks_second_breeding(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe = await _animal(async_client, fid, "goat", auth_headers_owner, "doe", "D")
        buck = await _animal(async_client, fid, "goat", auth_headers_owner, "buck", "B")
        base = f"{_sr(fid, 'goat')}/breeding"
        first = await async_client.post(base, json={"dam_id": doe, "sire_id": buck, "service_date": "2026-01-01"},
                                        headers=auth_headers_owner)
        assert first.status_code == 201
        second = await async_client.post(base, json={"dam_id": doe, "sire_id": buck},
                                         headers=auth_headers_owner)
        assert second.status_code == 409  # open cycle


class TestCompatibilityAndPermissions:
    async def test_compatibility_flags_full_sibs(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe = await _animal(async_client, fid, "goat", auth_headers_owner, "doe", "Dam")
        buck = await _animal(async_client, fid, "goat", auth_headers_owner, "buck", "Sire")
        base = f"{_sr(fid, 'goat')}/breeding"
        br = await async_client.post(base, json={"dam_id": doe, "sire_id": buck, "service_date": "2026-01-01"},
                                     headers=auth_headers_owner)
        bid = br.json()["data"]["id"]
        await async_client.post(f"{base}/{bid}/pregnancy-check",
                                json={"checked_on": "2026-02-01", "result": "pregnant"}, headers=auth_headers_owner)
        await async_client.post(
            f"{base}/{bid}/birth",
            json={"birth_date": "2026-05-30", "birth_type": "twin", "total_born": 2, "live_born": 2,
                  "create_offspring": True}, headers=auth_headers_owner,
        )
        # The two auto-created kids are full sibs.
        listing = await async_client.get(f"{_sr(fid, 'goat')}/animals", headers=auth_headers_owner)
        kids = [a for a in listing.json()["data"] if a["dam_id"] == doe and a["sire_id"] == buck]
        # Give them breeding sexes to check the pairing math (compatibility ignores
        # whether they'd actually be bred).
        await async_client.patch(f"{_sr(fid, 'goat')}/animals/{kids[0]['id']}",
                                 json={"sex": "buck"}, headers=auth_headers_owner)
        await async_client.patch(f"{_sr(fid, 'goat')}/animals/{kids[1]['id']}",
                                 json={"sex": "doe"}, headers=auth_headers_owner)
        compat = await async_client.get(
            f"{base}/compatibility?sire_id={kids[0]['id']}&dam_id={kids[1]['id']}", headers=auth_headers_owner
        )
        assert compat.status_code == 200
        assert compat.json()["data"]["offspring_inbreeding"]["value"] == 0.25
        assert compat.json()["data"]["risk_level"] == "high"

    async def test_worker_can_breed_viewer_cannot(
        self, async_client, workspace, auth_headers_worker, auth_headers_viewer
    ):
        fid = workspace.farm.id
        doe = await _animal(async_client, fid, "goat", auth_headers_worker, "doe", "D")
        buck = await _animal(async_client, fid, "goat", auth_headers_worker, "buck", "B")
        base = f"{_sr(fid, 'goat')}/breeding"
        ok = await async_client.post(base, json={"dam_id": doe, "sire_id": buck}, headers=auth_headers_worker)
        assert ok.status_code == 201  # worker has SR_BREEDING_MANAGE
        denied = await async_client.post(base, json={"dam_id": doe, "sire_id": buck}, headers=auth_headers_viewer)
        assert denied.status_code == 403
