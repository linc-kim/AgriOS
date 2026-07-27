"""
Breeding Engine — over HTTP, against a real database (Module 15, Part 4).

Confirms the endpoints wire recorded parentage through the pure engine: pairs and
programmes CRUD, compatibility returns labelled genetic figures, a real full-sib
pair is flagged high-risk, pedigrees compute inbreeding and founders, offspring
are tracked, circular ancestry is rejected at the write boundary, and permissions
hold. Genetics is never fabricated — unknown ancestry stays unknown.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "Silkie", "species_group": "ornamental_chicken"}, headers=headers)
    return r.json()["data"]["id"]


async def _bird(client, farm_id, headers, sid, sex="unknown", **extra) -> str:
    body = {"species_id": sid, "sex": sex}
    body.update(extra)
    r = await client.post(f"{_avi(farm_id)}/birds", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestPairs:
    async def test_create_and_dissolve_pair(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        m = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male")
        f = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female")
        r = await async_client.post(f"{_avi(workspace.farm.id)}/pairs",
                                    json={"male_bird_id": m, "female_bird_id": f, "name": "Pair 1"},
                                    headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        pair_id = r.json()["data"]["id"]

        detail = await async_client.get(f"{_avi(workspace.farm.id)}/pairs/{pair_id}", headers=auth_headers_owner)
        # Unrelated opposite-sex pair → compatible, minimal risk.
        comp = detail.json()["data"]["compatibility"]
        assert comp["risk_level"] == "minimal" and comp["compatible"] is True

        rd = await async_client.post(f"{_avi(workspace.farm.id)}/pairs/{pair_id}/dissolve",
                                     json={"reason": "incompatible"}, headers=auth_headers_owner)
        assert rd.status_code == 200 and rd.json()["data"]["status"] == "dissolved"

    async def test_viewer_cannot_create_pair(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/pairs", json={}, headers=auth_headers_viewer)
        assert r.status_code == 403


class TestPedigreeAndCompatibility:
    async def test_full_sibling_pair_flagged_high_risk(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        sire = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male")
        dam = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female")
        # Two full-sibling offspring sharing both parents.
        son = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male", sire_id=sire, dam_id=dam)
        daughter = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female", sire_id=sire, dam_id=dam)

        r = await async_client.post(f"{_avi(workspace.farm.id)}/compatibility",
                                    json={"male_bird_id": son, "female_bird_id": daughter}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["risk_level"] == "high"
        assert data["relationship_coefficient"]["value"] == 0.5
        assert data["relationship_coefficient"]["label"] == "calculated"
        assert data["offspring_inbreeding"]["value"] == 0.25
        assert data["offspring_inbreeding"]["label"] == "forecast"

    async def test_pedigree_and_offspring(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        sire = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male")
        dam = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female")
        chick = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sire_id=sire, dam_id=dam)

        ped = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{chick}/pedigree", headers=auth_headers_owner)
        assert ped.status_code == 200, ped.text
        pdata = ped.json()["data"]
        assert pdata["inbreeding_coefficient"]["value"] == 0.0  # parents unrelated
        assert pdata["ancestry"]["sire"]["id"] == sire

        off = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{sire}/offspring", headers=auth_headers_owner)
        assert any(o["id"] == chick for o in off.json()["data"]["offspring"])
        assert off.json()["data"]["performance"]["offspring_total"]["value"] >= 1

    async def test_relatedness_endpoint(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        sire = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male")
        dam = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female")
        child = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sire_id=sire, dam_id=dam)
        r = await async_client.get(f"{_avi(workspace.farm.id)}/relatedness",
                                   params={"bird_a": sire, "bird_b": child}, headers=auth_headers_owner)
        assert r.json()["data"]["relationship_coefficient"]["value"] == 0.5


class TestCycleSafety:
    async def test_circular_ancestry_rejected(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        grandparent = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        parent = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sire_id=grandparent)
        child = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sire_id=parent)
        # Try to make the grandparent a child of its own grandchild → cycle.
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{grandparent}/parents",
                                    json={"sire_id": child}, headers=auth_headers_owner)
        assert r.status_code == 409, r.text

    async def test_bird_cannot_be_its_own_parent(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        b = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{b}/parents",
                                    json={"sire_id": b}, headers=auth_headers_owner)
        assert r.status_code in (400, 409, 422)


class TestPrograms:
    async def test_program_with_goals_and_pair_link(self, async_client, workspace, auth_headers_owner):
        sid = await _species(async_client, workspace.farm.id, auth_headers_owner)
        rp = await async_client.post(f"{_avi(workspace.farm.id)}/breeding-programs",
                                     json={"name": "Champion Silkies", "strategy": "exhibition",
                                           "target_traits": ["white plumage", "five toes"]}, headers=auth_headers_owner)
        assert rp.status_code == 201, rp.text
        prog_id = rp.json()["data"]["id"]

        rg = await async_client.post(f"{_avi(workspace.farm.id)}/breeding-programs/{prog_id}/goals",
                                     json={"description": "Win national show", "target_metric": "awards", "target_value": "3"},
                                     headers=auth_headers_owner)
        assert rg.status_code == 201, rg.text

        m = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="male")
        f = await _bird(async_client, workspace.farm.id, auth_headers_owner, sid, sex="female")
        rpair = await async_client.post(f"{_avi(workspace.farm.id)}/pairs",
                                        json={"male_bird_id": m, "female_bird_id": f, "program_id": prog_id},
                                        headers=auth_headers_owner)
        assert rpair.status_code == 201, rpair.text

        lp = await async_client.get(f"{_avi(workspace.farm.id)}/breeding-programs", headers=auth_headers_owner)
        prog = next(p for p in lp.json()["data"] if p["id"] == prog_id)
        assert prog["pair_count"] >= 1
