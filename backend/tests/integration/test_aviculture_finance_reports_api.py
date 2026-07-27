"""
Aviculture Finance & Reports — over HTTP, against a real database (Parts 7 & 8).

Confirms Part 7 reuses the shared finance ledger (no aviculture expense table) and
computes valuation/P&L from recorded facts, and Part 8 composes the existing
engines into an honesty-labelled dashboard, forecast and CSV export. Permissions
hold (owner manages finance, viewer reads only).
"""

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _species(client, farm_id, headers) -> str:
    r = await client.post(f"{_avi(farm_id)}/species",
                          json={"common_name": "Peafowl", "species_group": "peafowl"}, headers=headers)
    return r.json()["data"]["id"]


async def _bird(client, farm_id, headers, sid) -> str:
    r = await client.post(f"{_avi(farm_id)}/birds", json={"species_id": sid}, headers=headers)
    return r.json()["data"]["id"]


class TestValuationAndFinance:
    async def test_valuation_lifts_collection_value(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        rv = await async_client.post(f"{_avi(farm)}/valuations",
                                     json={"bird_id": bird, "amount": "75000", "method": "appraised"},
                                     headers=auth_headers_owner)
        assert rv.status_code == 201, rv.text
        cv = await async_client.get(f"{_avi(farm)}/finance/valuation", headers=auth_headers_owner)
        d = cv.json()["data"]
        assert d["total_value"]["label"] == "calculated"
        assert d["total_value"]["value"] >= 75000

    async def test_collection_level_appraisal_is_authoritative(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        # A top-down collection appraisal (no bird_id) becomes the recorded total.
        r = await async_client.post(f"{_avi(farm)}/valuations",
                                    json={"amount": "500000", "method": "insured"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        cv = await async_client.get(f"{_avi(farm)}/finance/valuation", headers=auth_headers_owner)
        d = cv.json()["data"]
        assert d["total_value"]["value"] == 500000.0
        assert d["total_value"]["label"] == "recorded"

    async def test_viewer_cannot_record_valuation(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(f"{_avi(workspace.farm.id)}/valuations",
                                    json={"amount": "1000", "method": "appraised"}, headers=auth_headers_viewer)
        assert r.status_code == 403

    async def test_expense_posts_to_shared_ledger_and_summary(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        r = await async_client.post(f"{_avi(farm)}/expenses",
                                    json={"amount": "3000", "category_slug": "feed_purchase",
                                          "description": "Peafowl pellets"}, headers=auth_headers_owner)
        assert r.status_code == 201, r.text
        assert r.json()["data"]["expense_id"]
        summ = await async_client.get(f"{_avi(farm)}/finance/summary", headers=auth_headers_owner)
        s = summ.json()["data"]
        assert s["operational_expenses"]["value"] >= 3000
        assert s["net"]["label"] == "calculated"

    async def test_sale_income_flows_into_summary(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        bird = await _bird(async_client, farm, auth_headers_owner, sid)
        rs = await async_client.post(f"{_avi(farm)}/birds/{bird}/sell",
                                     json={"buyer_name": "Collector", "price": "60000"}, headers=auth_headers_owner)
        assert rs.status_code == 200, rs.text
        summ = await async_client.get(f"{_avi(farm)}/finance/summary", headers=auth_headers_owner)
        assert summ.json()["data"]["sale_income"]["value"] >= 60000


class TestReports:
    async def test_dashboard_composes_engines(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        r = await async_client.get(f"{_avi(farm)}/reports/dashboard", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        for section in ("collection", "infrastructure", "breeding", "incubation", "health", "finance"):
            assert section in d
        assert d["collection"]["total"]["label"] == "recorded"
        assert "statistics" in d["incubation"]

    async def test_population_forecast_is_labelled(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_avi(workspace.farm.id)}/reports/forecast?horizon_days=60",
                                   headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["forecast"]["label"] in ("forecast", "unknown")
        assert d["current"]["label"] == "recorded"

    async def test_collection_csv_export(self, async_client, workspace, auth_headers_owner):
        farm = workspace.farm.id
        sid = await _species(async_client, farm, auth_headers_owner)
        await _bird(async_client, farm, auth_headers_owner, sid)
        r = await async_client.get(f"{_avi(farm)}/reports/collection.csv", headers=auth_headers_owner)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "reference,name,species,sex,lifecycle_stage,status" in r.text
