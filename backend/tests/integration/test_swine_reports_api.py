"""
Swine Analytics & Reporting (Module 20, Milestone 9) — over HTTP.

Confirms the composition layer:

  * reports exist at every level (pig / litter / pen / farm / organization);
  * each report composes existing engine outputs and explains metrics (meaning + source);
  * the farm dashboard combines reproduction/farrowing/feed/health/growth/finance;
  * CSV exports are produced independently of any UI;
  * reporting is read-only (a GET report never mutates records);
  * RBAC holds (viewer reads; export gated to owner/manager).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sw(fid) -> str:
    return f"/api/v1/farms/{fid}/swine"


async def _pig(client, fid, h, **overrides):
    body = {"name": "P", "sex": "barrow", "production_stage": "grower", "date_of_birth": "2026-01-01"}
    body.update(overrides)
    r = await client.post(f"{_sw(fid)}/pigs", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestReportLevels:
    async def test_pig_report_composes_and_explains(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        pid = pig["id"]
        await async_client.post(f"{_sw(fid)}/growth/pigs/{pid}/weights",
                                json={"recorded_on": "2026-03-01", "weight_kg": 40}, headers=h)
        r = await async_client.get(f"{_sw(fid)}/reports/pig/{pid}", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["report_type"] == "pig"
        # Composed sections present, each carrying an explanation + source engine.
        assert data["growth"]["source"] == "growth"
        assert data["market_readiness"]["meaning"]
        assert data["financial_contribution"]["revenue"]["source"] == "finance"
        assert "health_history" in data and "movement_history" in data

    async def test_farm_dashboard_combines_domains(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        await _pig(async_client, fid, h)
        r = await async_client.get(f"{_sw(fid)}/reports/farm", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        for section in ("reproduction", "farrowing", "feed", "health", "growth", "finance"):
            assert section in data, section
            assert data[section]["source"]
        # Health section keeps the §4.4 disclaimer (analytics never diagnoses).
        assert "disclaimer" in data["health"]

    async def test_pen_and_organization_reports(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pen = await async_client.post(f"{_sw(fid)}/housing/pens",
                                      json={"name": "Grower A", "pen_type": "grower_pen", "capacity": 20}, headers=h)
        pen_id = pen.json()["data"]["id"]
        await _pig(async_client, fid, h, pen_id=pen_id)
        pr = await async_client.get(f"{_sw(fid)}/reports/pen/{pen_id}", headers=h)
        assert pr.status_code == 200
        assert pr.json()["data"]["occupancy"]["occupied"]["value"] == 1
        org = await async_client.get(f"{_sw(fid)}/reports/organization", headers=h)
        assert org.status_code == 200
        assert "executive_kpis" in org.json()["data"] and "benchmarking" in org.json()["data"]

    async def test_litter_report(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        boar = await _pig(async_client, fid, h, sex="boar")
        sow = await _pig(async_client, fid, h, sex="sow")
        b = await async_client.post(f"{_sw(fid)}/breeding",
                                    json={"dam_id": sow["id"], "sire_id": boar["id"], "service_date": "2026-01-01"},
                                    headers=h)
        chk = await async_client.post(f"{_sw(fid)}/breeding/{b.json()['data']['id']}/pregnancy-check",
                                      json={"checked_on": "2026-01-25", "result": "pregnant"}, headers=h)
        f = await async_client.post(f"{_sw(fid)}/farrowing",
                                    json={"pregnancy_id": chk.json()["data"]["pregnancy"]["id"],
                                          "farrowing_date": "2026-04-25", "born_alive": 10, "stillborn": 1},
                                    headers=h)
        litter_id = f.json()["data"]["litter"]["id"]
        r = await async_client.get(f"{_sw(fid)}/reports/litter/{litter_id}", headers=h)
        assert r.status_code == 200
        assert r.json()["data"]["birth_performance"]["source"] == "farrowing"
        assert r.json()["data"]["survival"]["meaning"]


class TestExportAndSafety:
    async def test_csv_exports(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        await _pig(async_client, fid, h, ear_tag="EX-1")
        reg = await async_client.get(f"{_sw(fid)}/reports/registry.csv", headers=h)
        assert reg.status_code == 200
        assert reg.headers["content-type"].startswith("text/csv")
        assert "internal_ref" in reg.text and "EX-1" in reg.text
        sales = await async_client.get(f"{_sw(fid)}/reports/sales.csv", headers=h)
        assert sales.status_code == 200 and "sale_type" in sales.text

    async def test_reporting_is_read_only(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        h = auth_headers_owner
        pig = await _pig(async_client, fid, h)
        before = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        await async_client.get(f"{_sw(fid)}/reports/pig/{pig['id']}", headers=h)
        await async_client.get(f"{_sw(fid)}/reports/farm", headers=h)
        after = await async_client.get(f"{_sw(fid)}/pigs/{pig['id']}", headers=h)
        # A report GET does not mutate the pig.
        assert before.json()["data"]["status"] == after.json()["data"]["status"]
        assert before.json()["data"]["updated_at"] == after.json()["data"]["updated_at"]


class TestPermissions:
    async def test_viewer_reads_worker_no_export(
        self, async_client, workspace, auth_headers_owner, auth_headers_viewer, auth_headers_worker
    ):
        fid = workspace.farm.id
        await _pig(async_client, fid, auth_headers_owner)
        v = await async_client.get(f"{_sw(fid)}/reports/farm", headers=auth_headers_viewer)
        assert v.status_code == 200
        # Worker lacks strategic report/export views.
        w = await async_client.get(f"{_sw(fid)}/reports/registry.csv", headers=auth_headers_worker)
        assert w.status_code == 403
