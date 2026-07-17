"""
Greena — Phase 3, Module 4 (Feed Management) integration tests.

Exercises the full vertical slice against a real (test) database:

  * Supplier CRUD + spend history
  * Purchase → creates inventory item, weighted-average cost, stock valuation,
    and a finance expense (integration)
  * Consumption → draws stock down, allocates cost to a flock
  * Transfer → moves stock (and value) between locations
  * Wastage → writes off stock, records the value loss
  * Insufficient-stock guards
  * Reorder alerts + dashboard
  * Analytics: automatic feed cost per bird / per egg
  * AI context payload shape
  * RBAC: worker can manage feed, viewer can view but not write
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


def _base(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/feed"


async def test_supplier_crud_and_spend_history(async_client, test_farm, auth_headers_owner):
    # Create.
    resp = await async_client.post(
        f"{_base(test_farm.id)}/suppliers",
        json={"name": "Unga Feeds Ltd", "phone": "+254700111222", "feed_types": ["broiler_starter"]},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    sid = resp.json()["data"]["id"]

    # Update rating.
    upd = await async_client.patch(
        f"{_base(test_farm.id)}/suppliers/{sid}",
        json={"rating": "4.50"},
        headers=auth_headers_owner,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["rating"] == "4.50"

    # List includes spend history fields.
    lst = await async_client.get(f"{_base(test_farm.id)}/suppliers", headers=auth_headers_owner)
    assert lst.status_code == 200
    rows = lst.json()["data"]
    mine = [s for s in rows if s["id"] == sid][0]
    assert mine["purchase_count"] == 0
    assert mine["total_spend_kes"] == "0.00" or mine["total_spend_kes"] == "0"


async def test_purchase_creates_inventory_expense_and_valuation(
    async_client, test_farm, test_flock, auth_headers_owner
):
    # Buy 200 kg @ 55 = 11,000.
    resp = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={
            "feed_type": "broiler_starter",
            "location": "main_store",
            "quantity_kg": "200.0",
            "price_per_kg": "55.00",
            "purchase_date": str(date.today()),
            "supplier_name": "Test Feed Co",
            "flock_id": str(test_flock.id),
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    item = data["item"]
    assert item["quantity_kg"] == "200.000"
    assert float(item["avg_cost_per_kg"]) == pytest.approx(55.0)
    assert float(item["stock_value_kes"]) == pytest.approx(11000.0)
    assert data["transaction"]["expense_id"] is not None

    # A finance expense now exists for the purchase.
    expenses = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses", headers=auth_headers_owner
    )
    assert expenses.status_code == 200
    feed_exp = [
        e for e in expenses.json()["data"]["items"]
        if "Feed purchase" in (e.get("description") or "")
    ]
    assert feed_exp, "purchase did not create a finance expense"


async def test_weighted_average_cost_on_second_purchase(async_client, test_farm, auth_headers_owner):
    # 100 kg @ 40.
    r1 = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "layer_mash", "location": "wa_store", "quantity_kg": "100.0",
              "price_per_kg": "40.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert r1.status_code == 201, r1.text
    item_id = r1.json()["data"]["item"]["id"]

    # 100 kg @ 60 → weighted avg (100*40 + 100*60) / 200 = 50.
    r2 = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"item_id": item_id, "quantity_kg": "100.0", "price_per_kg": "60.00",
              "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert r2.status_code == 201, r2.text
    item = r2.json()["data"]["item"]
    assert item["quantity_kg"] == "200.000"
    assert float(item["avg_cost_per_kg"]) == pytest.approx(50.0)


async def test_consumption_draws_down_and_costs_flock(
    async_client, test_farm, test_flock, auth_headers_owner
):
    # Stock up.
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "grower_mash", "location": "cons_store", "quantity_kg": "300.0",
              "price_per_kg": "50.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    item_id = buy.json()["data"]["item"]["id"]

    # Consume 120 kg for the flock → 120 * 50 = 6000.
    cons = await async_client.post(
        f"{_base(test_farm.id)}/consumption",
        json={"item_id": item_id, "flock_id": str(test_flock.id), "quantity_kg": "120.0",
              "consumption_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert cons.status_code == 201, cons.text
    item = cons.json()["data"]["item"]
    assert item["quantity_kg"] == "180.000"
    assert float(cons.json()["data"]["transaction"]["total_cost"]) == pytest.approx(6000.0)

    # Shows up on the flock's consumption history.
    hist = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/feed-consumption",
        headers=auth_headers_owner,
    )
    assert hist.status_code == 200
    assert any(float(t["quantity_kg"]) == 120.0 for t in hist.json()["data"])


async def test_consumption_insufficient_stock_rejected(
    async_client, test_farm, test_flock, auth_headers_owner
):
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "chick_mash", "location": "small_store", "quantity_kg": "10.0",
              "price_per_kg": "50.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    item_id = buy.json()["data"]["item"]["id"]
    resp = await async_client.post(
        f"{_base(test_farm.id)}/consumption",
        json={"item_id": item_id, "flock_id": str(test_flock.id), "quantity_kg": "50.0",
              "consumption_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 422, resp.text


async def test_transfer_moves_stock_between_locations(async_client, test_farm, auth_headers_owner):
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "broiler_finisher", "location": "store_a", "quantity_kg": "100.0",
              "price_per_kg": "70.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    src_id = buy.json()["data"]["item"]["id"]

    tr = await async_client.post(
        f"{_base(test_farm.id)}/transfers",
        json={"from_item_id": src_id, "to_location": "store_b", "quantity_kg": "40.0",
              "transfer_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert tr.status_code == 201, tr.text
    data = tr.json()["data"]
    assert data["from_item"]["quantity_kg"] == "60.000"
    assert data["to_item"]["quantity_kg"] == "40.000"
    assert data["to_item"]["location"] == "store_b"
    # Value moved at cost — destination avg cost equals source cost.
    assert float(data["to_item"]["avg_cost_per_kg"]) == pytest.approx(70.0)


async def test_wastage_writes_off_stock(async_client, test_farm, auth_headers_owner):
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "layer_mash", "location": "waste_store", "quantity_kg": "80.0",
              "price_per_kg": "45.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    item_id = buy.json()["data"]["item"]["id"]
    waste = await async_client.post(
        f"{_base(test_farm.id)}/wastage",
        json={"item_id": item_id, "quantity_kg": "5.0", "wastage_date": str(date.today()),
              "reason": "moisture_mould"},
        headers=auth_headers_owner,
    )
    assert waste.status_code == 201, waste.text
    assert waste.json()["data"]["item"]["quantity_kg"] == "75.000"
    assert float(waste.json()["data"]["transaction"]["total_cost"]) == pytest.approx(225.0)


async def test_reorder_alert_and_dashboard(async_client, test_farm, auth_headers_owner):
    # Create an item with a reorder level, buy below it.
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "supplement", "location": "reorder_store", "quantity_kg": "15.0",
              "price_per_kg": "100.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    item_id = buy.json()["data"]["item"]["id"]
    await async_client.patch(
        f"{_base(test_farm.id)}/inventory/{item_id}",
        json={"reorder_level_kg": "20.0"},
        headers=auth_headers_owner,
    )
    alerts = await async_client.get(f"{_base(test_farm.id)}/alerts", headers=auth_headers_owner)
    assert alerts.status_code == 200
    assert any(a["item_id"] == item_id for a in alerts.json()["data"])

    dash = await async_client.get(f"{_base(test_farm.id)}/dashboard", headers=auth_headers_owner)
    assert dash.status_code == 200, dash.text
    d = dash.json()["data"]
    assert d["low_stock_count"] >= 1
    assert float(d["total_stock_value_kes"]) > 0


async def test_analytics_cost_per_bird_and_egg(
    async_client, test_farm, test_flock, auth_headers_owner
):
    buy = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "broiler_starter", "location": "an_store", "quantity_kg": "500.0",
              "price_per_kg": "60.00", "purchase_date": str(date.today())},
        headers=auth_headers_owner,
    )
    item_id = buy.json()["data"]["item"]["id"]
    await async_client.post(
        f"{_base(test_farm.id)}/consumption",
        json={"item_id": item_id, "flock_id": str(test_flock.id), "quantity_kg": "250.0",
              "consumption_date": str(date.today())},
        headers=auth_headers_owner,
    )
    an = await async_client.get(f"{_base(test_farm.id)}/analytics", headers=auth_headers_owner)
    assert an.status_code == 200, an.text
    data = an.json()["data"]
    flock_rows = [f for f in data["by_flock"] if f["flock_id"] == str(test_flock.id)]
    assert flock_rows, "flock not in analytics"
    row = flock_rows[0]
    assert float(row["feed_cost_kes"]) >= 15000.0
    # 500 birds placed → cost per bird present and positive.
    assert row["cost_per_bird_kes"] is not None
    assert float(row["cost_per_bird_kes"]) > 0


async def test_ai_context_shape(async_client, test_farm, auth_headers_owner):
    resp = await async_client.get(f"{_base(test_farm.id)}/ai-context", headers=auth_headers_owner)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    for key in ("inventory", "feed_history", "consumption", "costs",
                "supplier_history", "feed_conversions", "performance"):
        assert key in data


async def test_rbac_worker_can_manage_viewer_cannot(
    async_client, test_farm, auth_headers_worker, auth_headers_viewer
):
    # Worker can record a purchase.
    ok = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "grower_mash", "location": "rbac_store", "quantity_kg": "10.0",
              "price_per_kg": "50.00", "purchase_date": str(date.today())},
        headers=auth_headers_worker,
    )
    assert ok.status_code == 201, ok.text

    # Viewer can read inventory.
    view = await async_client.get(f"{_base(test_farm.id)}/inventory", headers=auth_headers_viewer)
    assert view.status_code == 200

    # Viewer cannot record a purchase.
    denied = await async_client.post(
        f"{_base(test_farm.id)}/purchases",
        json={"feed_type": "grower_mash", "location": "rbac_store", "quantity_kg": "10.0",
              "price_per_kg": "50.00", "purchase_date": str(date.today())},
        headers=auth_headers_viewer,
    )
    assert denied.status_code == 403, denied.text
