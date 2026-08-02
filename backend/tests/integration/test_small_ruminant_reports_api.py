"""
Small Ruminant Reports (Modules 18/19, Milestone 9) — over HTTP.

The reporting layer COMPOSES the milestone summaries into an executive dashboard,
a short-range forecast and ranked bottlenecks, and exports the registry as CSV. It
adds no new recorded data — only composition. Dairy appears for goats, wool for
sheep. Reads need SR_REPORT_VIEW; CSV export needs SR_REPORT_EXPORT (workers
excluded).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


class TestReports:
    async def test_dashboard_composes_species_summaries(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        # Register a couple of animals so the population roll-up is non-trivial.
        for sex in ("doe", "buck"):
            await async_client.post(f"{_sr(fid, 'goat')}/animals", json={"name": sex, "sex": sex},
                                    headers=auth_headers_owner)

        dash = await async_client.get(f"{_sr(fid, 'goat')}/reports/dashboard", headers=auth_headers_owner)
        assert dash.status_code == 200
        d = dash.json()["data"]
        # Composed blocks are present.
        for block in ("population", "reproduction", "health", "housing", "finance", "forecast", "bottlenecks"):
            assert block in d, f"dashboard missing {block}"
        # Goat dashboard includes dairy (produces_milk) but not wool.
        assert "dairy" in d and "wool" not in d
        assert d["population"]["active"]["value"] == 2
        assert d["forecast"]["projected_head"]["label"] in ("forecast", "unknown")

    async def test_sheep_dashboard_includes_wool_not_dairy_shape(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        dash = await async_client.get(f"{_sr(fid, 'sheep')}/reports/dashboard", headers=auth_headers_owner)
        d = dash.json()["data"]
        assert "wool" in d          # sheep produce wool
        assert "dairy" in d         # dairy sheep supported (produces_milk True)

    async def test_registry_csv_export(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        await async_client.post(f"{_sr(fid, 'goat')}/animals", json={"name": "Nim", "sex": "doe"},
                                headers=auth_headers_owner)
        r = await async_client.get(f"{_sr(fid, 'goat')}/reports/registry.csv", headers=auth_headers_owner)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "internal_ref" in r.text and "GT-" in r.text

    async def test_permissions(self, async_client, workspace, auth_headers_worker, auth_headers_viewer):
        fid = workspace.farm.id
        # Worker is excluded from strategic report views.
        w = await async_client.get(f"{_sr(fid, 'goat')}/reports/dashboard", headers=auth_headers_worker)
        assert w.status_code == 403
        # Viewer can read but not export.
        v = await async_client.get(f"{_sr(fid, 'goat')}/reports/dashboard", headers=auth_headers_viewer)
        assert v.status_code == 200
        vx = await async_client.get(f"{_sr(fid, 'goat')}/reports/registry.csv", headers=auth_headers_viewer)
        assert vx.status_code == 403
