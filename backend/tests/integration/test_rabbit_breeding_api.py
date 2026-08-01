"""
Rabbit Breeding, Pedigree & Genetics (Module 17, Milestone 3) — over HTTP.

Exercises the full cycle (service → pregnancy check → prepare kindling → kindling
with kit creation → weaning), eligibility validation, litter performance, the
reused pedigree engine (ancestry + inbreeding), pairing compatibility, the herd
reproduction dashboard, advisory genetics, and RBAC.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _pair(client, fid, headers) -> tuple[dict, dict]:
    doe = await _register(client, fid, headers, sex="doe", name="Dam")
    buck = await _register(client, fid, headers, sex="buck", name="Sire")
    return doe, buck


class TestBreedingCycle:
    async def test_full_cycle_service_to_weaning(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        svc_date = date.today().isoformat()

        created = await async_client.post(
            f"{_rb(fid)}/breedings",
            json={"doe_id": doe["id"], "buck_id": buck["id"], "service_date": svc_date},
            headers=auth_headers_owner,
        )
        assert created.status_code == 201, created.text
        bid = created.json()["data"]["id"]
        assert created.json()["data"]["status"] == "serviced"
        assert created.json()["data"]["planned_kindling_date"] is not None  # forecast set

        pc = await async_client.post(
            f"{_rb(fid)}/breedings/{bid}/pregnancy-check",
            json={"result": "pregnant"}, headers=auth_headers_owner,
        )
        assert pc.status_code == 200 and pc.json()["data"]["status"] == "pregnant"

        await async_client.post(f"{_rb(fid)}/breedings/{bid}/prepare-kindling", json={}, headers=auth_headers_owner)

        kindle = await async_client.post(
            f"{_rb(fid)}/breedings/{bid}/kindling",
            json={"kindling_date": svc_date, "total_kits": 8, "live_kits": 7,
                  "stillbirths": 1, "create_kits": True},
            headers=auth_headers_owner,
        )
        assert kindle.status_code == 201, kindle.text
        litter = kindle.json()["data"]
        assert litter["total_kits"] == 8 and litter["live_kits"] == 7

        # 7 kit rabbits were created, linked to the litter.
        kits = await async_client.get(f"{_rb(fid)}/rabbits?limit=200", headers=auth_headers_owner)
        kit_rows = [r for r in kits.json()["data"] if r.get("litter_id") == litter["id"]]
        assert len(kit_rows) == 7
        assert all(k["lifecycle_stage"] == "kit" and k["dam_id"] == doe["id"] for k in kit_rows)

        wean = await async_client.post(
            f"{_rb(fid)}/litters/{litter['id']}/weaning",
            json={"weaned_kits": 6}, headers=auth_headers_owner,
        )
        assert wean.status_code == 200 and wean.json()["data"]["status"] == "weaned"

        detail = await async_client.get(f"{_rb(fid)}/litters/{litter['id']}", headers=auth_headers_owner)
        perf = detail.json()["data"]["performance"]
        assert perf["weaning_survival_pct"]["value"] == round(6 / 7 * 100, 1)

    async def test_ineligible_pair_rejected(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        buck1 = await _register(async_client, fid, auth_headers_owner, sex="buck")
        buck2 = await _register(async_client, fid, auth_headers_owner, sex="buck")
        r = await async_client.post(
            f"{_rb(fid)}/breedings", json={"doe_id": buck1["id"], "buck_id": buck2["id"]},
            headers=auth_headers_owner,
        )
        assert r.status_code == 422  # doe must be a doe

    async def test_open_cycle_blocks_second_breeding(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        first = await async_client.post(
            f"{_rb(fid)}/breedings",
            json={"doe_id": doe["id"], "buck_id": buck["id"], "service_date": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        assert first.status_code == 201
        second = await async_client.post(
            f"{_rb(fid)}/breedings", json={"doe_id": doe["id"], "buck_id": buck["id"]},
            headers=auth_headers_owner,
        )
        assert second.status_code == 422  # doe already has an open cycle


class TestPedigreeAndGenetics:
    async def test_pedigree_returns_ancestry_and_inbreeding(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        kit = await _register(async_client, fid, auth_headers_owner, sex="unknown",
                              sire_id=buck["id"], dam_id=doe["id"])
        ped = await async_client.get(f"{_rb(fid)}/rabbits/{kit['id']}/pedigree", headers=auth_headers_owner)
        assert ped.status_code == 200
        data = ped.json()["data"]
        assert data["inbreeding_coefficient"]["value"] == 0.0  # unrelated parents
        assert data["ancestry"]["sire"]["id"] == buck["id"]

    async def test_compatibility_labels_offspring_inbreeding_forecast(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_rb(fid)}/breeding/compatibility",
            json={"buck_id": buck["id"], "doe_id": doe["id"]}, headers=auth_headers_owner,
        )
        assert r.status_code == 200
        assert r.json()["data"]["offspring_inbreeding"]["label"] == "forecast"

    async def test_reproduction_summary_and_genetics(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        created = await async_client.post(
            f"{_rb(fid)}/breedings",
            json={"doe_id": doe["id"], "buck_id": buck["id"], "service_date": date.today().isoformat()},
            headers=auth_headers_owner,
        )
        bid = created.json()["data"]["id"]
        await async_client.post(f"{_rb(fid)}/breedings/{bid}/pregnancy-check",
                                json={"result": "pregnant"}, headers=auth_headers_owner)
        await async_client.post(
            f"{_rb(fid)}/breedings/{bid}/kindling",
            json={"kindling_date": date.today().isoformat(), "total_kits": 6, "live_kits": 6},
            headers=auth_headers_owner,
        )
        summary = await async_client.get(f"{_rb(fid)}/breeding/reproduction-summary", headers=auth_headers_owner)
        assert summary.status_code == 200
        assert summary.json()["data"]["total_litters"]["value"] >= 1

        genetics = await async_client.get(f"{_rb(fid)}/breeding/genetics", headers=auth_headers_owner)
        assert genetics.status_code == 200
        assert "breeding_value_ranking" in genetics.json()["data"]


class TestRBAC:
    async def test_worker_can_manage_breeding(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_worker)
        r = await async_client.post(
            f"{_rb(fid)}/breedings", json={"doe_id": doe["id"], "buck_id": buck["id"]},
            headers=auth_headers_worker,
        )
        assert r.status_code == 201

    async def test_viewer_cannot_create_breeding(self, async_client, workspace, auth_headers_owner, auth_headers_viewer):
        fid = workspace.farm.id
        doe, buck = await _pair(async_client, fid, auth_headers_owner)
        r = await async_client.post(
            f"{_rb(fid)}/breedings", json={"doe_id": doe["id"], "buck_id": buck["id"]},
            headers=auth_headers_viewer,
        )
        assert r.status_code == 403

    async def test_viewer_can_read_reproduction_summary(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        r = await async_client.get(f"{_rb(fid)}/breeding/reproduction-summary", headers=auth_headers_viewer)
        assert r.status_code == 200
