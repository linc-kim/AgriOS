"""
Incubation Engine — over HTTP, against a real database (Module 15, Part 5).

Confirms the hatch process wires through the pure engine: eggs and batches CRUD,
species-driven schedule (hatch/lockdown dates computed from the profile), setting
eggs, candling that records fertility, a hatch that produces a real chick bird
linked to its pair as parents, honesty-labelled statistics, and permissions.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers, days=21) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "Java Sparrow", "species_group": "finch",
                                "profile": {"incubation": {"incubation_days": days, "temp_c": 37.5, "humidity_pct": 55}}},
                          headers=headers)
    return r.json()["data"]["id"]


async def _bird(client, farm_id, headers, sid, sex) -> str:
    r = await client.post(f"{_avi(farm_id)}/birds", json={"species_id": sid, "sex": sex}, headers=headers)
    return r.json()["data"]["id"]


class TestEggsAndBatches:
    async def test_egg_gets_identifier(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/eggs",
                                    json={"species_id": sid, "quality": "good"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        assert r.json()["data"]["identifier"].startswith("EGG-")
        assert r.json()["data"]["status"] == "collected"

    async def test_batch_schedule_from_species(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner, days=21)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/incubation-batches",
                                    json={"name": "Batch A", "method": "artificial", "species_id": sid,
                                          "set_on": "2026-07-01"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["expected_hatch_on"] == "2026-07-22"
        assert d["expected_lockdown_on"] == "2026-07-19"

    async def test_viewer_cannot_create_egg(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/eggs", json={}, headers=auth_headers_viewer)
        assert r.status_code == 403


class TestHatchFlow:
    async def test_full_incubation_to_chick(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        male = await _bird(async_client, farm, auth_headers_owner, sid, "male")
        female = await _bird(async_client, farm, auth_headers_owner, sid, "female")
        pair = (await async_client.post(f"{_avi(farm)}/pairs",
                json={"male_bird_id": male, "female_bird_id": female}, headers=auth_headers_owner)).json()["data"]["id"]

        # Egg from the pair (species inferred), then a batch, then set the egg.
        egg = (await async_client.post(f"{_avi(farm)}/eggs",
               json={"pair_id": pair}, headers=auth_headers_owner)).json()["data"]
        assert egg["species_id"] == sid  # inferred from the pair
        batch = (await async_client.post(f"{_avi(farm)}/incubation-batches",
                 json={"name": "Hatch run", "species_id": sid, "set_on": "2026-07-01"}, headers=auth_headers_owner)).json()["data"]["id"]
        rs = await async_client.post(f"{_avi(farm)}/incubation-batches/{batch}/set-eggs",
                                     json={"egg_ids": [egg["id"]], "set_on": "2026-07-01"}, headers=auth_headers_owner)
        assert rs.status_code == 200 and rs.json()["data"]["eggs_set"] == 1

        # Candle → fertile (records fertility on the egg).
        rc = await async_client.post(f"{_avi(farm)}/eggs/{egg['id']}/candling",
                                     json={"result": "fertile", "candled_on": "2026-07-08"}, headers=auth_headers_owner)
        assert rc.status_code == 201 and rc.json()["data"]["day_number"] == 7

        # Hatch → creates a real chick bird linked to the pair as parents.
        rh = await async_client.post(f"{_avi(farm)}/eggs/{egg['id']}/hatch",
                                     json={"outcome": "hatched", "hatched_on": "2026-07-22",
                                           "create_chick": True, "chick_name": "Pip"}, headers=auth_headers_owner)
        assert rh.status_code == 201, rh.text
        chick_id = rh.json()["data"]["chick_bird_id"]
        assert chick_id is not None

        chick = (await async_client.get(f"{_avi(farm)}/birds/{chick_id}", headers=auth_headers_owner)).json()["data"]
        assert chick["lifecycle_stage"] == "chick"
        assert chick["acquisition_type"] == "bred"
        assert chick["sire_id"] == male and chick["dam_id"] == female

        # Batch statistics reflect the hatch (honesty-labelled).
        detail = (await async_client.get(f"{_avi(farm)}/incubation-batches/{batch}", headers=auth_headers_owner)).json()["data"]
        assert detail["statistics"]["hatched"]["value"] == 1
        assert detail["statistics"]["hatch_rate_pct"]["value"] == 100.0
        assert detail["statistics"]["hatch_rate_pct"]["label"] == "calculated"

    async def test_failed_hatch_records_reason_no_chick(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        egg = (await async_client.post(f"{_avi(farm)}/eggs", json={"species_id": sid}, headers=auth_headers_owner)).json()["data"]
        r = await async_client.post(f"{_avi(farm)}/eggs/{egg['id']}/hatch",
                                    json={"outcome": "dead_in_shell", "failure_reason": "malposition"}, headers=auth_headers_owner)
        assert r.status_code == 201
        assert r.json()["data"]["chick_bird_id"] is None
        # Egg is now terminal; a second outcome is rejected.
        r2 = await async_client.post(f"{_avi(farm)}/eggs/{egg['id']}/hatch",
                                     json={"outcome": "hatched"}, headers=auth_headers_owner)
        assert r2.status_code == 409

    async def test_empty_batch_statistics_not_fabricated(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        batch = (await async_client.post(f"{_avi(workspace.farm.id)}/incubation-batches",
                 json={"name": "Empty", "species_id": sid}, headers=auth_headers_owner)).json()["data"]["id"]
        detail = (await async_client.get(f"{_avi(workspace.farm.id)}/incubation-batches/{batch}", headers=auth_headers_owner)).json()["data"]
        assert detail["statistics"]["hatch_rate_pct"]["label"] == "unknown"
