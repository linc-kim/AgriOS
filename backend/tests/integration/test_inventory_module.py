"""
Greena — Module 6 Inventory & Asset Management integration tests.

Covers items CRUD, stock movements (valuation + finance integration), suppliers,
assets + straight-line depreciation, maintenance (completion books an expense),
alerts, analytics/valuation, and RBAC.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


def _inv(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/inventory"


async def test_item_crud_and_sku_autogen(async_client, test_farm, auth_headers_owner):
    resp = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Nitrile Gloves", "category": "ppe", "unit": "box", "location": "store_a",
        "reorder_level": "5", "opening_quantity": "10", "opening_cost": "250.00",
    }, headers=auth_headers_owner)
    assert resp.status_code == 201, resp.text
    item = resp.json()["data"]
    assert item["sku"] and item["sku"].startswith("INV-PPE-")
    assert item["quantity"] == "10.000"
    assert float(item["current_value"]) == pytest.approx(2500.0)

    upd = await async_client.patch(f"{_inv(test_farm.id)}/items/{item['id']}", json={"reorder_level": "8"}, headers=auth_headers_owner)
    assert upd.status_code == 200
    assert upd.json()["data"]["reorder_level"] == "8.000"


async def test_stock_in_updates_qty_avg_cost_and_books_expense(async_client, test_farm, auth_headers_owner):
    r = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Vaccine ND", "category": "vaccines", "unit": "vial", "opening_quantity": "0",
    }, headers=auth_headers_owner)
    item_id = r.json()["data"]["id"]

    # Stock in 100 @ 40.
    m1 = await async_client.post(f"{_inv(test_farm.id)}/movements", json={
        "item_id": item_id, "movement_type": "stock_in", "quantity": "100", "unit_cost": "40.00",
        "reference": "INV-001",
    }, headers=auth_headers_owner)
    assert m1.status_code == 201, m1.text
    d1 = m1.json()["data"]
    assert d1["item"]["quantity"] == "100.000"
    assert float(d1["item"]["avg_cost"]) == pytest.approx(40.0)
    assert d1["movement"]["qty_before"] == "0.000"
    assert d1["movement"]["qty_after"] == "100.000"
    assert d1["movement"]["expense_id"] is not None  # finance integration

    # Stock in 100 @ 60 → weighted avg 50.
    m2 = await async_client.post(f"{_inv(test_farm.id)}/movements", json={
        "item_id": item_id, "movement_type": "stock_in", "quantity": "100", "unit_cost": "60.00",
    }, headers=auth_headers_owner)
    assert float(m2.json()["data"]["item"]["avg_cost"]) == pytest.approx(50.0)

    # Finance expense exists.
    exp = await async_client.get(f"/api/v1/farms/{test_farm.id}/expenses", headers=auth_headers_owner)
    assert any("Inventory purchase: Vaccine ND" in (e.get("description") or "") for e in exp.json()["data"]["items"])


async def test_consumption_and_insufficient_stock(async_client, test_farm, auth_headers_owner):
    r = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Disinfectant", "category": "cleaning_supplies", "unit": "litre",
        "opening_quantity": "20", "opening_cost": "150.00",
    }, headers=auth_headers_owner)
    item_id = r.json()["data"]["id"]

    ok = await async_client.post(f"{_inv(test_farm.id)}/movements", json={
        "item_id": item_id, "movement_type": "consumption", "quantity": "5", "reason": "cleaning",
    }, headers=auth_headers_owner)
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["item"]["quantity"] == "15.000"
    assert float(ok.json()["data"]["movement"]["total_cost"]) == pytest.approx(750.0)  # 5 * 150

    bad = await async_client.post(f"{_inv(test_farm.id)}/movements", json={
        "item_id": item_id, "movement_type": "stock_out", "quantity": "999",
    }, headers=auth_headers_owner)
    assert bad.status_code == 422, bad.text


async def test_supplier_crud_and_spend(async_client, test_farm, auth_headers_owner):
    s = await async_client.post(f"{_inv(test_farm.id)}/suppliers", json={
        "name": "Agrovet Supplies", "phone": "+254733111222", "products_supplied": ["medication", "ppe"],
        "outstanding_balance": "1500.00",
    }, headers=auth_headers_owner)
    assert s.status_code == 201, s.text
    sid = s.json()["data"]["id"]

    lst = await async_client.get(f"{_inv(test_farm.id)}/suppliers", headers=auth_headers_owner)
    mine = [x for x in lst.json()["data"] if x["id"] == sid][0]
    assert mine["order_count"] == 0
    assert float(mine["outstanding_balance"]) == 1500.0


async def test_asset_depreciation(async_client, test_farm, auth_headers_owner):
    # Bought 2 years ago for 100,000, 10-year life, salvage 0 → ~20% depreciated.
    two_yrs_ago = date.today() - timedelta(days=730)
    r = await async_client.post(f"{_inv(test_farm.id)}/assets", json={
        "name": "Diesel Generator", "asset_type": "generator", "purchase_date": str(two_yrs_ago),
        "purchase_price": "100000.00", "useful_life_years": 10, "salvage_value": "0",
        "service_interval_days": 90, "condition": "good",
    }, headers=auth_headers_owner)
    assert r.status_code == 201, r.text
    a = r.json()["data"]
    assert a["age_days"] >= 720
    # Straight line: ~2/10 depreciated → current ~80,000.
    assert 78000 <= float(a["current_value"]) <= 82000
    assert float(a["accumulated_depreciation"]) > 15000
    assert a["next_service_date"] is not None


async def test_maintenance_completion_books_expense_and_advances_schedule(async_client, test_farm, auth_headers_owner):
    r = await async_client.post(f"{_inv(test_farm.id)}/assets", json={
        "name": "Incubator X", "asset_type": "incubator", "purchase_date": str(date.today() - timedelta(days=100)),
        "purchase_price": "50000.00", "useful_life_years": 8, "service_interval_days": 60,
    }, headers=auth_headers_owner)
    asset_id = r.json()["data"]["id"]

    m = await async_client.post(f"{_inv(test_farm.id)}/maintenance", json={
        "asset_id": asset_id, "title": "Replace heating element", "status": "completed",
        "completed_date": str(date.today()), "cost": "3500.00", "technician": "John",
        "parts_used": ["heating element", "thermostat"],
    }, headers=auth_headers_owner)
    assert m.status_code == 201, m.text
    assert m.json()["data"]["expense_id"] is not None  # completed → finance expense

    # Asset's next service advanced.
    a = await async_client.get(f"{_inv(test_farm.id)}/assets/{asset_id}", headers=auth_headers_owner)
    assert a.json()["data"]["last_service_date"] == str(date.today())

    exp = await async_client.get(f"/api/v1/farms/{test_farm.id}/expenses", headers=auth_headers_owner)
    assert any("Maintenance: Incubator X" in (e.get("description") or "") for e in exp.json()["data"]["items"])


async def test_alerts_low_stock_and_expiry(async_client, test_farm, auth_headers_owner):
    soon = date.today() + timedelta(days=10)
    await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Antibiotic Y", "category": "medication", "unit": "bottle",
        "opening_quantity": "2", "reorder_level": "5", "expiry_date": str(soon), "opening_cost": "300",
    }, headers=auth_headers_owner)
    alerts = await async_client.get(f"{_inv(test_farm.id)}/alerts", headers=auth_headers_owner)
    assert alerts.status_code == 200
    kinds = {a["kind"] for a in alerts.json()["data"]}
    assert "low_stock" in kinds
    assert "expiring_soon" in kinds


async def test_dashboard_and_analytics(async_client, test_farm, auth_headers_owner):
    r = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Feed Bags", "category": "packaging", "unit": "bag",
        "opening_quantity": "100", "opening_cost": "20",
    }, headers=auth_headers_owner)
    item_id = r.json()["data"]["id"]
    await async_client.post(f"{_inv(test_farm.id)}/movements", json={
        "item_id": item_id, "movement_type": "consumption", "quantity": "40",
    }, headers=auth_headers_owner)

    dash = await async_client.get(f"{_inv(test_farm.id)}/dashboard", headers=auth_headers_owner)
    assert dash.status_code == 200, dash.text
    d = dash.json()["data"]
    assert d["item_count"] >= 1
    assert float(d["total_inventory_value"]) > 0
    assert len(d["category_valuation"]) >= 1

    an = await async_client.get(f"{_inv(test_farm.id)}/analytics", headers=auth_headers_owner)
    assert an.status_code == 200, an.text
    a = an.json()["data"]
    assert float(a["inventory_valuation"]) > 0
    assert any(v["item_id"] == item_id for v in a["most_consumed"])
    assert len(a["movement_trend"]) == 12


async def test_ai_context_shape(async_client, test_farm, auth_headers_owner):
    r = await async_client.get(f"{_inv(test_farm.id)}/ai-context", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    for key in ("inventory_value", "asset_value", "items", "recent_movements", "alerts",
                "supplier_performance", "reorder_recommendations"):
        assert key in r.json()["data"]


async def test_rbac_worker_writes_viewer_reads_only(async_client, test_farm, auth_headers_worker, auth_headers_viewer):
    ok = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Broom", "category": "cleaning_supplies", "unit": "unit", "opening_quantity": "3",
    }, headers=auth_headers_worker)
    assert ok.status_code == 201, ok.text

    view = await async_client.get(f"{_inv(test_farm.id)}/items", headers=auth_headers_viewer)
    assert view.status_code == 200

    denied = await async_client.post(f"{_inv(test_farm.id)}/items", json={
        "name": "Mop", "category": "cleaning_supplies", "unit": "unit",
    }, headers=auth_headers_viewer)
    assert denied.status_code == 403
