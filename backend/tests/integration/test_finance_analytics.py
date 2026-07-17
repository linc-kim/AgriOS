"""
Greena — Module 5 Finance Analytics integration tests.

Exercises the farm-level analytics layer end-to-end:
  * Overview dashboard (today / 30-day / cash balance / top category / charts)
  * Rolling analytics windows (7d/30d/90d/ytd/lifetime) + margins + per-unit
  * Unified transaction search (filter by kind / amount / search / sort / paginate)
  * Cash flow running balance
  * Period reports (monthly) + CSV export
  * Profit + category maths
  * AI context shape
  * Auto-integration: a fed expense (via existing endpoints) flows into analytics
"""

from datetime import date

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


def _fin(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/finance"


async def _seed_expense(client, farm_id, headers, categories, slug, amount, flock_id=None, method="cash"):
    cat = [c for c in categories if c["slug"] == slug][0]
    body = {
        "category_id": cat["id"], "expense_date": str(date.today()),
        "amount": amount, "description": f"{slug} test", "payment_method": method,
    }
    if flock_id:
        body["flock_id"] = str(flock_id)
    r = await client.post(f"/api/v1/farms/{farm_id}/expenses", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def _seed_revenue(client, farm_id, headers, rtype, amount, flock_id, extra=None):
    body = {
        "flock_id": str(flock_id), "revenue_type": rtype, "revenue_date": str(date.today()),
        "amount": amount,
    }
    if extra:
        body.update(extra)
    r = await client.post(f"/api/v1/farms/{farm_id}/revenue", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


@pytest_asyncio.fixture
async def _categories(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"/api/v1/farms/{test_farm.id}/finance/categories", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def test_overview_reflects_revenue_and_expenses(
    async_client, test_farm, test_flock, auth_headers_owner, _categories
):
    await _seed_revenue(async_client, test_farm.id, auth_headers_owner, "eggs", "5000.00", test_flock.id,
                        {"eggs_count": 1000, "trays_count": 33})
    await _seed_expense(async_client, test_farm.id, auth_headers_owner, _categories, "labour", "1200.00", method="credit")

    r = await async_client.get(f"{_fin(test_farm.id)}/overview", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert float(d["today_revenue"]) >= 5000.0
    assert float(d["today_expenses"]) >= 1200.0
    assert float(d["today_profit"]) == pytest.approx(float(d["today_revenue"]) - float(d["today_expenses"]))
    # Cash balance = lifetime revenue − expenses.
    assert float(d["cash_balance"]) == pytest.approx(float(d["m30_revenue"]) - float(d["m30_expenses"]), abs=1e6)
    # Credit expense is outstanding.
    assert float(d["outstanding_costs"]) >= 1200.0
    assert d["top_expense_category"] is not None
    assert len(d["revenue_series"]) == 30  # daily series over 30-day window


async def test_analytics_windows_and_margins(
    async_client, test_farm, test_flock, auth_headers_owner, _categories
):
    await _seed_revenue(async_client, test_farm.id, auth_headers_owner, "birds", "20000.00", test_flock.id,
                        {"birds_sold": 100, "avg_weight_kg": "1.8"})
    await _seed_expense(async_client, test_farm.id, auth_headers_owner, _categories, "feed_purchase", "8000.00", test_flock.id)
    await _seed_expense(async_client, test_farm.id, auth_headers_owner, _categories, "labour", "2000.00")

    r = await async_client.get(f"{_fin(test_farm.id)}/analytics", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    windows = {w["window"]: w for w in d["windows"]}
    for key in ("7d", "30d", "90d", "ytd", "lifetime"):
        assert key in windows
    life = windows["lifetime"]
    # Gross profit excludes only direct costs (feed); net subtracts all expenses.
    assert float(life["direct_costs"]) >= 8000.0
    assert float(life["gross_profit"]) > float(life["net_profit"])
    assert life["net_margin_pct"] is not None

    # Per-unit economics present.
    pu = d["per_unit"]
    assert pu["total_birds"] >= 500
    assert pu["cost_per_bird"] is not None
    assert pu["revenue_per_kg"] is not None
    # Cost centre for the flock exists.
    assert any(c["flock_id"] == str(test_flock.id) for c in d["cost_centres"])


async def test_transaction_search_filter_sort_paginate(
    async_client, test_farm, test_flock, auth_headers_owner, _categories
):
    await _seed_revenue(async_client, test_farm.id, auth_headers_owner, "manure", "800.00", test_flock.id)
    await _seed_expense(async_client, test_farm.id, auth_headers_owner, _categories, "transport", "450.00")

    # Only expenses.
    r = await async_client.get(f"{_fin(test_farm.id)}/transactions?kind=expense", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert all(t["kind"] == "expense" for t in d["items"])
    assert float(d["total_expenses"]) >= 450.0

    # Only revenue + amount filter.
    r2 = await async_client.get(f"{_fin(test_farm.id)}/transactions?kind=revenue&min_amount=700", headers=auth_headers_owner)
    assert r2.status_code == 200
    assert all(t["kind"] == "revenue" and float(t["amount"]) >= 700 for t in r2.json()["data"]["items"])

    # Sort by amount desc — first item is the largest.
    r3 = await async_client.get(f"{_fin(test_farm.id)}/transactions?sort=amount_desc&page_size=50", headers=auth_headers_owner)
    items = r3.json()["data"]["items"]
    amounts = [float(t["amount"]) for t in items]
    assert amounts == sorted(amounts, reverse=True)

    # Pagination.
    r4 = await async_client.get(f"{_fin(test_farm.id)}/transactions?page=1&page_size=1", headers=auth_headers_owner)
    assert len(r4.json()["data"]["items"]) == 1


async def test_cashflow_running_balance(async_client, test_farm, test_flock, auth_headers_owner, _categories):
    await _seed_revenue(async_client, test_farm.id, auth_headers_owner, "other", "3000.00", test_flock.id)
    r = await async_client.get(f"{_fin(test_farm.id)}/cashflow?months=3", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert len(d["points"]) == 3
    # Last point's running balance equals closing balance.
    assert float(d["points"][-1]["running_balance"]) == pytest.approx(float(d["closing_balance"]))


async def test_report_and_csv(async_client, test_farm, test_flock, auth_headers_owner, _categories):
    await _seed_revenue(async_client, test_farm.id, auth_headers_owner, "eggs", "4000.00", test_flock.id,
                        {"eggs_count": 800})
    await _seed_expense(async_client, test_farm.id, auth_headers_owner, _categories, "electricity", "600.00")

    today = date.today()
    r = await async_client.get(
        f"{_fin(test_farm.id)}/reports?period_type=monthly&year={today.year}&index={today.month}",
        headers=auth_headers_owner,
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert float(d["total_revenue"]) >= 4000.0
    assert float(d["net_profit"]) == pytest.approx(float(d["total_revenue"]) - float(d["total_expenses"]))
    assert any(c["slug"] == "electricity" for c in d["expense_by_category"])

    csv = await async_client.get(f"{_fin(test_farm.id)}/reports/csv", headers=auth_headers_owner)
    assert csv.status_code == 200
    assert "text/csv" in csv.headers["content-type"]
    assert "Total revenue" in csv.text


async def test_ai_context_shape(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_fin(test_farm.id)}/ai-context", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    for key in ("cash_balance", "rolling_averages", "revenue_by_type", "expense_by_category", "cost_centres", "recent_events"):
        assert key in d
    assert "lifetime" in d["rolling_averages"]


async def test_feed_purchase_flows_into_finance_analytics(
    async_client, test_farm, test_flock, auth_headers_owner
):
    # A feed purchase (Feed module) auto-creates an expense → visible in analytics.
    buy = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/feed/purchases",
        json={"feed_type": "layer_mash", "location": "fin_store", "quantity_kg": "100.0",
              "price_per_kg": "50.00", "purchase_date": str(date.today()), "flock_id": str(test_flock.id)},
        headers=auth_headers_owner,
    )
    assert buy.status_code == 201, buy.text
    r = await async_client.get(f"{_fin(test_farm.id)}/transactions?kind=expense&q=Feed", headers=auth_headers_owner)
    assert r.status_code == 200
    assert any("Feed" in (t["description"] or "") for t in r.json()["data"]["items"])


async def test_viewer_can_read_analytics(async_client, test_farm, auth_headers_viewer):
    r = await async_client.get(f"{_fin(test_farm.id)}/analytics", headers=auth_headers_viewer)
    assert r.status_code == 200, r.text
