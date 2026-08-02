"""
Small Ruminant Wool (Modules 18/19, Milestone 7, Sheep wool) — over HTTP.

The sheep-specific milestone, still on the shared foundation. A shearing session
records per-animal fleece; analysis computes clean weight / micron grade / value
deterministically; the clip summary rolls up the flock. Crucially, the workspace is
gated by the produces_wool capability — goats are rejected (the mirror of dairy).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _ewe(client, fid, headers, name="Fluffy") -> str:
    r = await client.post(f"{_sr(fid, 'sheep')}/animals",
                          json={"name": name, "sex": "ewe", "purpose": "wool"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestWoolCapabilityGate:
    async def test_goats_are_rejected_from_wool(self, async_client, workspace, auth_headers_owner):
        # Goats do not produce wool → the workspace guard rejects the operation.
        fid = workspace.farm.id
        r = await async_client.post(f"{_sr(fid, 'goat')}/wool/shearings",
                                    json={"shearing_date": "2026-01-01"}, headers=auth_headers_owner)
        assert r.status_code == 422
        gs = await async_client.get(f"{_sr(fid, 'goat')}/wool/summary", headers=auth_headers_owner)
        assert gs.status_code == 422


class TestShearingAndFleece:
    async def test_shearing_with_fleeces_analysis_and_summary(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        e1 = await _ewe(async_client, fid, auth_headers_owner, "E1")
        e2 = await _ewe(async_client, fid, auth_headers_owner, "E2")
        base = f"{_sr(fid, 'sheep')}/wool"

        sh = await async_client.post(
            f"{base}/shearings",
            json={"shearing_date": "2026-01-01", "method": "machine", "shearer": "Sam",
                  "fleeces": [
                      {"animal_id": e1, "greasy_weight_kg": "4.0", "clean_yield_pct": "65", "micron": "19.0",
                       "grade": "fine"},
                      {"animal_id": e2, "greasy_weight_kg": "3.0", "clean_yield_pct": "60", "micron": "21.0",
                       "grade": "medium"},
                  ]},
            headers=auth_headers_owner,
        )
        assert sh.status_code == 201, sh.text
        assert len(sh.json()["data"]["fleeces_created"]) == 2

        # A 'sheared' timeline event exists for the animal.
        tl = await async_client.get(f"{_sr(fid, 'sheep')}/animals/{e1}/timeline", headers=auth_headers_owner)
        assert any(ev["event_type"] == "sheared" for ev in tl.json()["data"])

        # Per-fleece analysis computes clean weight / grade / value.
        fleeces = await async_client.get(f"{base}/fleeces?animal_id={e1}", headers=auth_headers_owner)
        fid1 = fleeces.json()["data"][0]["id"]
        an = await async_client.get(f"{base}/fleeces/{fid1}/analysis?price_per_kg=10", headers=auth_headers_owner)
        a = an.json()["data"]["analysis"]
        assert a["clean_weight_kg"]["value"] == 2.6
        assert a["micron_grade"]["value"] == "fine"
        assert a["estimated_value"]["value"] == 26.0

        # Flock clip summary rolls up recorded facts.
        summary = await async_client.get(f"{base}/summary?price_per_kg=10", headers=auth_headers_owner)
        s = summary.json()["data"]
        assert s["total_greasy_kg"]["value"] == 7.0
        assert s["avg_micron"]["value"] == 20.0
        assert s["shearing_sessions"]["value"] == 1

    async def test_permissions(self, async_client, workspace, auth_headers_owner, auth_headers_worker,
                               auth_headers_viewer):
        fid = workspace.farm.id
        base = f"{_sr(fid, 'sheep')}/wool"
        # Worker can shear (operational).
        ok = await async_client.post(f"{base}/shearings", json={"shearing_date": "2026-01-01"},
                                     headers=auth_headers_worker)
        assert ok.status_code == 201
        # Viewer cannot.
        denied = await async_client.post(f"{base}/shearings", json={"shearing_date": "2026-01-02"},
                                         headers=auth_headers_viewer)
        assert denied.status_code == 403
