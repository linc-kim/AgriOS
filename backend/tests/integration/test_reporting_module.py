"""
Greena — Module 7 Reporting & BI integration tests.

Covers report generation across types, role dashboards, comparisons, CSV export,
and saved/pinned reports.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


def _rep(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/reporting"


async def _seed_finance(client, farm_id, flock_id, headers):
    # A revenue + expense so finance/sales/purchases reports have data.
    cats = (await client.get(f"/api/v1/farms/{farm_id}/finance/categories", headers=headers)).json()["data"]
    labour = [c for c in cats if c["slug"] == "labour"][0]
    await client.post(f"/api/v1/farms/{farm_id}/revenue", json={
        "flock_id": str(flock_id), "revenue_type": "eggs", "revenue_date": str(date.today()),
        "amount": "6000.00", "eggs_count": 1200}, headers=headers)
    await client.post(f"/api/v1/farms/{farm_id}/expenses", json={
        "category_id": labour["id"], "expense_date": str(date.today()), "amount": "1500.00",
        "description": "wages"}, headers=headers)


async def test_generate_all_report_types(async_client, test_farm, test_flock, auth_headers_owner):
    await _seed_finance(async_client, test_farm.id, test_flock.id, auth_headers_owner)
    for rt in ["farm_summary", "production", "finance", "feed", "health", "inventory",
               "mortality", "vaccination", "sales", "purchases", "assets", "maintenance",
               "staff_activity", "ai_insights"]:
        r = await async_client.get(f"{_rep(test_farm.id)}/generate?report_type={rt}&period_type=monthly", headers=auth_headers_owner)
        assert r.status_code == 200, f"{rt}: {r.text}"
        d = r.json()["data"]
        assert d["report_type"] == rt
        assert isinstance(d["sections"], list) and len(d["sections"]) >= 1
        assert "ai_context" in d


async def test_finance_report_values(async_client, test_farm, test_flock, auth_headers_owner):
    await _seed_finance(async_client, test_farm.id, test_flock.id, auth_headers_owner)
    r = await async_client.get(f"{_rep(test_farm.id)}/generate?report_type=finance&period_type=monthly", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    kpis = {k["label"]: k["value"] for k in r.json()["data"]["sections"][0]["kpis"]}
    assert "Revenue" in kpis and "Net profit" in kpis
    assert "6,000" in kpis["Revenue"]


async def test_period_types(async_client, test_farm, auth_headers_owner):
    for p in ["daily", "weekly", "monthly", "quarterly", "annual"]:
        r = await async_client.get(f"{_rep(test_farm.id)}/generate?report_type=farm_summary&period_type={p}", headers=auth_headers_owner)
        assert r.status_code == 200, f"{p}: {r.text}"
    # Custom range.
    r = await async_client.get(
        f"{_rep(test_farm.id)}/generate?report_type=finance&period_type=custom&start=2026-01-01&end=2026-12-31",
        headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    # Custom without dates → 422.
    bad = await async_client.get(f"{_rep(test_farm.id)}/generate?report_type=finance&period_type=custom", headers=auth_headers_owner)
    assert bad.status_code == 422


async def test_dashboards(async_client, test_farm, auth_headers_owner):
    for role in ["executive", "farm_manager", "veterinary", "finance", "production", "inventory"]:
        r = await async_client.get(f"{_rep(test_farm.id)}/dashboards/{role}", headers=auth_headers_owner)
        assert r.status_code == 200, f"{role}: {r.text}"
        assert len(r.json()["data"]["sections"]) >= 1


async def test_comparisons(async_client, test_farm, test_flock, auth_headers_owner):
    for c in ["month_vs_month", "year_vs_year"]:
        r = await async_client.get(f"{_rep(test_farm.id)}/comparisons?comparison_type={c}", headers=auth_headers_owner)
        assert r.status_code == 200, f"{c}: {r.text}"
        assert r.json()["data"]["sections"][0]["kind"] == "table"


async def test_csv_export(async_client, test_farm, test_flock, auth_headers_owner):
    await _seed_finance(async_client, test_farm.id, test_flock.id, auth_headers_owner)
    r = await async_client.get(f"{_rep(test_farm.id)}/generate/csv?report_type=finance&period_type=monthly", headers=auth_headers_owner)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Financial summary" in r.text


async def test_saved_reports_crud(async_client, test_farm, auth_headers_owner):
    c = await async_client.post(f"{_rep(test_farm.id)}/saved", json={
        "name": "My monthly finance", "report_type": "finance", "config": {"period_type": "monthly"}, "is_pinned": True,
    }, headers=auth_headers_owner)
    assert c.status_code == 201, c.text
    rid = c.json()["data"]["id"]

    lst = await async_client.get(f"{_rep(test_farm.id)}/saved", headers=auth_headers_owner)
    assert any(x["id"] == rid and x["is_pinned"] for x in lst.json()["data"])

    u = await async_client.patch(f"{_rep(test_farm.id)}/saved/{rid}", json={"is_pinned": False}, headers=auth_headers_owner)
    assert u.status_code == 200 and u.json()["data"]["is_pinned"] is False

    d = await async_client.delete(f"{_rep(test_farm.id)}/saved/{rid}", headers=auth_headers_owner)
    assert d.status_code == 200


async def test_viewer_can_read_reports(async_client, test_farm, auth_headers_viewer):
    r = await async_client.get(f"{_rep(test_farm.id)}/generate?report_type=farm_summary&period_type=monthly", headers=auth_headers_viewer)
    assert r.status_code == 200, r.text
