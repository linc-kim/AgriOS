"""
BSF Reports & Executive Dashboard (Module 16, Part 6) — over HTTP.

Confirms the executive dashboard exposes BOTH recorded facts and derived analytics
(traceability), that forecasts are labelled ``forecast`` (never confirmed), scores
are calculated/bounded with growth unavailable, bottlenecks are evidenced, CSV
export works, and reporting permissions hold (worker cannot view reports; export
needs manager/owner).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _bsf(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/bsf"


async def _seed(client, farm_id, headers) -> dict:
    """A batch with feed + a revenue harvest + mortality, so analytics are non-trivial."""
    batch = (await client.post(
        f"{_bsf(farm_id)}/batches",
        json={"lifecycle_stage": "mature_larvae", "population_estimate": 1000, "biomass_estimate_g": 10000},
        headers=headers,
    )).json()["data"]
    lot = (await client.post(
        f"{_bsf(farm_id)}/feedstock-lots",
        json={"name": "Waste", "category": "market_waste", "weight_kg": 100, "cost": 1000},
        headers=headers,
    )).json()["data"]
    await client.post(f"{_bsf(farm_id)}/batches/{batch['id']}/feedings",
                      json={"feedstock_lot_id": lot["id"], "quantity_kg": 40}, headers=headers)
    await client.post(f"{_bsf(farm_id)}/feedstock-lots/{lot['id']}/post-expense", headers=headers)
    await client.post(f"{_bsf(farm_id)}/batches/{batch['id']}/harvests",
                      json={"harvest_type": "larvae", "quantity_kg": 6, "revenue_amount": 3000, "currency": "KES"},
                      headers=headers)
    await client.post(f"{_bsf(farm_id)}/batches/{batch['id']}/mortality",
                      json={"estimated_loss": 100, "cause": "handling"}, headers=headers)
    return batch


class TestDashboard:
    async def test_dashboard_exposes_facts_and_analytics(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_bsf(fid)}/reports/dashboard", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]

        # Both blocks present → every conclusion traces to a recorded fact.
        assert "recorded_facts" in data and "analytics" in data
        assert data["recorded_facts"]["total_revenue"]["label"] == "recorded"
        assert data["recorded_facts"]["total_revenue"]["value"] >= 3000
        # A derived figure is calculated, not recorded.
        assert data["analytics"]["finance"]["gross_profit"]["label"] == "calculated"
        # Scores calculated; growth unavailable (no Growth Planner yet).
        assert data["scores"]["financial"]["label"] in ("calculated", "unknown")
        assert data["scores"]["growth"]["label"] == "unavailable"

    async def test_dashboard_forecast_is_labelled_forecast(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_bsf(fid)}/reports/dashboard", headers=auth_headers_owner)
        fc = r.json()["data"]["forecast"]["harvest_kg"]["forecast"]
        assert fc["label"] == "forecast"  # never "recorded"/"calculated"

    async def test_forecast_endpoint_carries_assumptions(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_bsf(fid)}/reports/forecast?horizon_days=60", headers=auth_headers_owner)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["horizon_days"] == 60
        assert data["revenue"]["method"] and data["revenue"]["assumptions"]


class TestBottlenecks:
    async def test_bottlenecks_evidenced(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # Batch with very low biomass but big feed → poor FCR bottleneck.
        batch = (await async_client.post(
            f"{_bsf(fid)}/batches",
            json={"lifecycle_stage": "feeding_larvae", "population_estimate": 1000, "biomass_estimate_g": 200},
            headers=auth_headers_owner,
        )).json()["data"]
        await async_client.post(f"{_bsf(fid)}/batches/{batch['id']}/harvests",
                                json={"harvest_type": "larvae", "quantity_kg": 1}, headers=auth_headers_owner)
        r = await async_client.get(f"{_bsf(fid)}/reports/bottlenecks", headers=auth_headers_owner)
        assert r.status_code == 200
        for b in r.json()["data"]:
            assert b["evidence"] and b["recommended_action"] and b["severity"]


class TestPermissionsAndExport:
    async def test_worker_cannot_view_reports(self, async_client, workspace, auth_headers_worker):
        r = await async_client.get(f"{_bsf(workspace.farm.id)}/reports/dashboard", headers=auth_headers_worker)
        assert r.status_code == 403

    async def test_viewer_can_view_but_not_export(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        view = await async_client.get(f"{_bsf(fid)}/reports/dashboard", headers=auth_headers_viewer)
        assert view.status_code == 200
        export = await async_client.get(f"{_bsf(fid)}/reports/production.csv", headers=auth_headers_viewer)
        assert export.status_code == 403

    async def test_owner_exports_csv(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _seed(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_bsf(fid)}/reports/production.csv", headers=auth_headers_owner)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "batch_number" in r.text
