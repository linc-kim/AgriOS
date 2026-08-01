"""
Rabbit Analytics & Reporting (Module 17, Milestone 7) — over HTTP.

Confirms the executive dashboard composes the M3–M6 analytics + forecast +
bottlenecks (recorded facts distinct from forecasts), the forecast bundle labels
projections, the executive summary and bottlenecks endpoints, the CSV herd export,
and RBAC (workers excluded from strategic reports; export needs REPORT_EXPORT).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _rb(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit"


def _rep(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/rabbit/reports"


async def _register(client, farm_id, headers, **overrides) -> dict:
    body = {"sex": "doe"}
    body.update(overrides)
    r = await client.post(f"{_rb(farm_id)}/rabbits", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestDashboard:
    async def test_dashboard_composes_blocks_and_labels(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, sex="buck")
        await _register(async_client, fid, auth_headers_owner, sex="doe")
        r = await async_client.get(f"{_rep(fid)}/dashboard", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        # Composed blocks present.
        for block in ("recorded_facts", "reproduction", "health", "finance", "housing",
                      "forecast", "bottlenecks"):
            assert block in data
        pop = data["recorded_facts"]["population"]
        assert pop["total_rabbits"]["label"] == "recorded"
        assert pop["bucks"]["value"] >= 1 and pop["does"]["value"] >= 1
        # Forecasts are forecast-labelled or unknown — never recorded.
        assert data["forecast"]["herd_size"]["forecast"]["label"] in ("forecast", "unknown")

    async def test_bottlenecks_endpoint(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"{_rep(fid)}/bottlenecks", headers=auth_headers_owner)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)


class TestForecastAndSummary:
    async def test_forecast_bundle_labels(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"{_rep(fid)}/forecast?horizon_days=60&window_days=30", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        for key in ("herd_size", "kits_produced", "feed_requirement_kg", "revenue", "housing_capacity"):
            assert key in data
        assert data["herd_size"]["forecast"]["label"] in ("forecast", "unknown")

    async def test_executive_summary(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner)
        r = await async_client.get(f"{_rep(fid)}/executive-summary", headers=auth_headers_owner)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["herd_size"]["label"] == "recorded"
        assert "top_bottlenecks" in data and "disclaimer" in data


class TestExport:
    async def test_herd_csv_export(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await _register(async_client, fid, auth_headers_owner, name="Exporter")
        r = await async_client.get(f"{_rep(fid)}/herd.csv", headers=auth_headers_owner)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "internal_ref" in r.text and "Exporter" in r.text


class TestRBAC:
    async def test_worker_cannot_view_reports(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        r = await async_client.get(f"{_rep(fid)}/dashboard", headers=auth_headers_worker)
        assert r.status_code == 403  # workers excluded from strategic reports

    async def test_viewer_can_view_but_not_export(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        assert (await async_client.get(f"{_rep(fid)}/dashboard", headers=auth_headers_viewer)).status_code == 200
        csv_resp = await async_client.get(f"{_rep(fid)}/herd.csv", headers=auth_headers_viewer)
        assert csv_resp.status_code == 403  # export needs RABBIT_REPORT_EXPORT
