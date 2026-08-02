"""
Small Ruminant Dairy (Modules 18/19, Milestone 6, Goat dairy) — over HTTP.

The first species-specific milestone, still on the shared foundation: a lactation
cycle is started at freshening, milk sessions are recorded (immutable), metrics are
deterministic (total/avg/peak + 305-day forecast + advisory dry-off), and dry-off
closes the cycle. Availability is gated by the species produces_milk capability.
"""

import pytest

pytestmark = pytest.mark.asyncio


def _sr(farm_id, species) -> str:
    return f"/api/v1/farms/{farm_id}/sr/{species}"


async def _doe(client, fid, headers) -> str:
    r = await client.post(f"{_sr(fid, 'goat')}/animals",
                          json={"name": "Milker", "sex": "doe", "purpose": "dairy"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


class TestDairyCycle:
    async def test_lactation_milk_metrics_and_dry_off(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        aid = await _doe(async_client, fid, auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/dairy"

        lac = await async_client.post(f"{base}/animals/{aid}/lactations",
                                      json={"freshening_date": "2026-01-01"}, headers=auth_headers_owner)
        assert lac.status_code == 201 and lac.json()["data"]["lactation_number"] == 1
        assert lac.json()["data"]["expected_dry_off_date"] is not None  # forecast set
        lid = lac.json()["data"]["id"]
        # Doe is now lactating.
        detail = await async_client.get(f"{_sr(fid, 'goat')}/animals/{aid}", headers=auth_headers_owner)
        assert detail.json()["data"]["reproductive_status"] == "lactating"

        # Record two milk sessions on one day + a bigger day.
        for on, session, qty in [("2026-01-02", "am", "1.5"), ("2026-01-02", "pm", "1.2"),
                                 ("2026-01-10", "total", "3.4")]:
            r = await async_client.post(f"{base}/animals/{aid}/milk",
                                        json={"recorded_on": on, "session": session, "quantity_liters": qty},
                                        headers=auth_headers_owner)
            assert r.status_code == 201, r.text
            assert r.json()["data"]["lactation_id"] == lid  # auto-attached to active lactation

        metrics = await async_client.get(f"{base}/lactations/{lid}/metrics", headers=auth_headers_owner)
        m = metrics.json()["data"]["metrics"]
        assert m["total_yield_l"]["value"] == 6.1     # 2.7 + 3.4
        assert m["peak_daily_yield_l"]["value"] == 3.4
        assert metrics.json()["data"]["dry_off_recommendation"]["label"] == "recommendation"

        # Second active lactation is blocked until dry-off.
        dup = await async_client.post(f"{base}/animals/{aid}/lactations",
                                      json={"freshening_date": "2026-02-01"}, headers=auth_headers_owner)
        assert dup.status_code == 409

        dry = await async_client.post(f"{base}/lactations/{lid}/dry-off",
                                      json={"dry_off_date": "2026-09-01"}, headers=auth_headers_owner)
        assert dry.status_code == 200 and dry.json()["data"]["status"] == "completed"

        summary = await async_client.get(f"{base}/summary", headers=auth_headers_owner)
        assert summary.json()["data"]["total_recorded_yield_l"]["value"] == 6.1

    async def test_permissions(self, async_client, workspace, auth_headers_owner,
                               auth_headers_worker, auth_headers_viewer):
        fid = workspace.farm.id
        aid = await _doe(async_client, fid, auth_headers_owner)
        base = f"{_sr(fid, 'goat')}/dairy"
        # Worker can record milk (operational).
        lac = await async_client.post(f"{base}/animals/{aid}/lactations",
                                      json={"freshening_date": "2026-01-01"}, headers=auth_headers_worker)
        assert lac.status_code == 201
        # Viewer cannot record.
        denied = await async_client.post(f"{base}/animals/{aid}/milk",
                                         json={"recorded_on": "2026-01-02", "quantity_liters": "2.0"},
                                         headers=auth_headers_viewer)
        assert denied.status_code == 403
