"""
Greena — Phase 3 Feed Management: a feed purchase auto-creates a finance expense.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def test_feed_purchase_creates_expense_and_updates_snapshot(
    async_client, test_farm, test_flock, auth_headers_owner
):
    # Record a flock-scoped feed purchase.
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/feed-purchases",
        json={
            "flock_id": str(test_flock.id),
            "purchase_date": str(date.today()),
            "feed_type": "broiler_starter",
            "quantity_kg": "100.0",
            "price_per_kg": "60.00",
            "supplier": "Unga Feeds Ltd",
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    # total_cost = 100 * 60 = 6000
    assert resp.json()["data"]["total_cost"] == "6000.00"

    # A matching expense now exists in the farm's expense list.
    expenses = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses", headers=auth_headers_owner
    )
    assert expenses.status_code == 200
    items = expenses.json()["data"]["items"]
    feed_expenses = [e for e in items if "Feed purchase" in (e.get("description") or "")]
    assert feed_expenses, "feed purchase did not create an expense"
    assert any(e["amount"] == "6000.00" for e in feed_expenses)

    # The flock's financial snapshot reflects the feed cost.
    snap = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/finance",
        headers=auth_headers_owner,
    )
    assert snap.status_code == 200, snap.text
    data = snap.json()["data"]
    assert float(data["feed_cost_kes"]) >= 6000.0
    assert float(data["total_expenses_kes"]) >= 6000.0
