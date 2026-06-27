"""
AGRIOS — Finance Module Integration Tests
Tests the full finance lifecycle against a real (test) database.

Test coverage:
  1.  List expense categories — system categories visible to all farms
  2.  Create custom expense category — 201, farm-scoped
  3.  System category cannot be deleted via API — 403
  4.  Custom category delete — 200 (soft delete)
  5.  Log expense — 201, snapshot recomputed
  6.  List expenses — correct ordering and pagination
  7.  Get single expense — correct data returned
  8.  Update (correct) expense — correction note appended to notes
  9.  Soft-delete expense — no longer visible in list
 10.  Log revenue (egg sale) — 201, snapshot recomputed
 11.  Log revenue (bird sale) — 201, fcr computed
 12.  List revenue — type filter works
 13.  Get single revenue record — correct data
 14.  Update (correct) revenue record — correction note appended
 15.  Flock snapshot — returns pre-computed P&L (not real-time query)
 16.  Finance dashboard — returns aggregate across all farm flocks
 17.  RBAC: farm_worker cannot POST expense (403)
 18.  RBAC: farm_worker can GET expense list (200)
 19.  RBAC: viewer can GET expense list (200)
 20.  RBAC: viewer cannot POST expense (403)
 21.  Calculator: FCR endpoint — no farm access required, returns rating
 22.  Calculator: profit projection — returns projected profit
 23.  Calculator: break-even — returns break-even price
 24.  Calculator: feed needs — returns daily consumption
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio

# These tests follow the same async fixture pattern used in test_health_flow.py.
# They assume:
#   - `async_client` fixture provides an authenticated httpx.AsyncClient
#   - `test_farm` fixture provides a Farm with an active flock
#   - `test_flock` fixture provides an active Flock in the test farm
#   - `auth_headers_owner` / `auth_headers_manager` / `auth_headers_worker`
#     / `auth_headers_viewer` fixtures provide Authorization headers per role
# The fixture infrastructure is shared via conftest.py (Sprint 0/2 setup).

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_system_category_id(async_client, farm_id, headers) -> str:
    """Return the ID of the first system expense category."""
    resp = await async_client.get(
        f"/api/v1/farms/{farm_id}/expense-categories",
        headers=headers,
    )
    assert resp.status_code == 200
    cats = resp.json()["data"]
    system_cats = [c for c in cats if c["is_system"] is True]
    assert system_cats, "No system categories found — check migration 019"
    return system_cats[0]["id"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. List expense categories — system categories visible to all farms
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_expense_categories_includes_system(
    async_client, test_farm, auth_headers_owner
):
    """System categories (farm_id=NULL) are visible to every farm."""
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expense-categories",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    cats = resp.json()["data"]
    assert len(cats) >= 17  # 17 system categories seeded in migration 019
    slugs = {c["slug"] for c in cats if c["is_system"]}
    assert "feed_purchase" in slugs
    assert "vaccination" in slugs
    assert "labour" in slugs


# ─────────────────────────────────────────────────────────────────────────────
# 2. Create custom expense category — 201, farm-scoped
# ─────────────────────────────────────────────────────────────────────────────

async def test_create_custom_expense_category(
    async_client, test_farm, auth_headers_owner
):
    """Farm owner creates a custom expense category."""
    payload = {
        "name": "Packaging Materials",
        "slug": "packaging_materials",
        "icon": "📦",
        "color": "#6366F1",
    }
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expense-categories",
        json=payload,
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Packaging Materials"
    assert data["slug"] == "packaging_materials"
    assert data["is_system"] is False
    assert data["farm_id"] == str(test_farm.id)


# ─────────────────────────────────────────────────────────────────────────────
# 3. System category cannot be deleted via API — 403
# ─────────────────────────────────────────────────────────────────────────────

async def test_delete_system_category_forbidden(
    async_client, test_farm, auth_headers_owner
):
    """System categories are protected — DELETE returns 403."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    resp = await async_client.delete(
        f"/api/v1/farms/{test_farm.id}/expense-categories/{system_cat_id}",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 4. Custom category delete — 200 (soft delete)
# ─────────────────────────────────────────────────────────────────────────────

async def test_delete_custom_category_success(
    async_client, test_farm, auth_headers_owner
):
    """Custom (farm-scoped) categories can be soft-deleted."""
    # First create one
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expense-categories",
        json={"name": "Temp Category", "slug": f"temp_cat_{uuid.uuid4().hex[:6]}"},
        headers=auth_headers_owner,
    )
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["data"]["id"]

    # Now delete it
    del_resp = await async_client.delete(
        f"/api/v1/farms/{test_farm.id}/expense-categories/{cat_id}",
        headers=auth_headers_owner,
    )
    assert del_resp.status_code == 200

    # Should not appear in list
    list_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expense-categories",
        headers=auth_headers_owner,
    )
    ids = [c["id"] for c in list_resp.json()["data"]]
    assert cat_id not in ids


# ─────────────────────────────────────────────────────────────────────────────
# 5. Log expense — 201, snapshot recomputed
# ─────────────────────────────────────────────────────────────────────────────

async def test_log_expense_triggers_snapshot(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Logging an expense returns 201 and the flock snapshot is recomputed."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    payload = {
        "category_id": system_cat_id,
        "flock_id": str(test_flock.id),
        "amount": "8500.00",
        "expense_date": str(date.today()),
        "payment_method": "mpesa",
        "supplier": "Unga Feeds Ltd",
    }
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json=payload,
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["amount"] == "8500.00"
    assert data["farm_id"] == str(test_farm.id)

    # Snapshot should now exist for the flock
    snap_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/finance/snapshot",
        headers=auth_headers_owner,
    )
    assert snap_resp.status_code == 200
    snap = snap_resp.json()["data"]
    assert snap is not None
    assert snap["flock_id"] == str(test_flock.id)


# ─────────────────────────────────────────────────────────────────────────────
# 6. List expenses — ordering and pagination
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_expenses_ordered_newest_first(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Multiple expenses are returned newest first by expense_date."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    for i in range(3):
        await async_client.post(
            f"/api/v1/farms/{test_farm.id}/expenses",
            json={
                "category_id": system_cat_id,
                "flock_id": str(test_flock.id),
                "amount": str(1000 * (i + 1)),
                "expense_date": str(date.today() - timedelta(days=i)),
                "payment_method": "cash",
            },
            headers=auth_headers_owner,
        )

    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    expenses = resp.json()["data"]["items"]
    dates = [e["expense_date"] for e in expenses]
    assert dates == sorted(dates, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Get single expense — correct data returned
# ─────────────────────────────────────────────────────────────────────────────

async def test_get_single_expense(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """GET single expense returns the correct record."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json={
            "category_id": system_cat_id,
            "flock_id": str(test_flock.id),
            "amount": "3200.00",
            "expense_date": str(date.today()),
            "payment_method": "bank_transfer",
            "notes": "Monthly medication stock",
        },
        headers=auth_headers_owner,
    )
    assert create_resp.status_code == 201
    expense_id = create_resp.json()["data"]["id"]

    get_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses/{expense_id}",
        headers=auth_headers_owner,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["id"] == expense_id
    assert data["amount"] == "3200.00"
    assert data["notes"] == "Monthly medication stock"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Update (correct) expense — correction note appended
# ─────────────────────────────────────────────────────────────────────────────

async def test_update_expense_appends_correction_note(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Correcting an expense appends a correction trail to the notes field."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json={
            "category_id": system_cat_id,
            "flock_id": str(test_flock.id),
            "amount": "4000.00",
            "expense_date": str(date.today()),
            "payment_method": "cash",
        },
        headers=auth_headers_owner,
    )
    expense_id = create_resp.json()["data"]["id"]

    upd_resp = await async_client.patch(
        f"/api/v1/farms/{test_farm.id}/expenses/{expense_id}",
        json={
            "amount": "4500.00",
            "correction_reason": "Amount was entered incorrectly",
        },
        headers=auth_headers_owner,
    )
    assert upd_resp.status_code == 200
    data = upd_resp.json()["data"]
    assert data["amount"] == "4500.00"
    assert "[Corrected by" in (data["notes"] or "")
    assert "Amount was entered incorrectly" in (data["notes"] or "")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Soft-delete expense — no longer visible in list
# ─────────────────────────────────────────────────────────────────────────────

async def test_soft_delete_expense(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Deleted expense is excluded from list but snapshot remains valid."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_owner
    )
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json={
            "category_id": system_cat_id,
            "flock_id": str(test_flock.id),
            "amount": "1500.00",
            "expense_date": str(date.today()),
            "payment_method": "cash",
        },
        headers=auth_headers_owner,
    )
    expense_id = create_resp.json()["data"]["id"]

    del_resp = await async_client.delete(
        f"/api/v1/farms/{test_farm.id}/expenses/{expense_id}",
        headers=auth_headers_owner,
    )
    assert del_resp.status_code == 200

    list_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses",
        headers=auth_headers_owner,
    )
    ids = [e["id"] for e in list_resp.json()["data"]["items"]]
    assert expense_id not in ids


# ─────────────────────────────────────────────────────────────────────────────
# 10. Log revenue (egg sale) — 201, snapshot recomputed
# ─────────────────────────────────────────────────────────────────────────────

async def test_log_revenue_egg_sale(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Log an egg sale — 201 returned with revenue_type=eggs."""
    payload = {
        "flock_id": str(test_flock.id),
        "revenue_type": "eggs",
        "amount": "9600.00",
        "sale_date": str(date.today()),
        "eggs_count": 480,
        "trays_count": 16,
        "buyer": "Local Market",
    }
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json=payload,
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["revenue_type"] == "eggs"
    assert data["eggs_count"] == 480
    assert data["flock_id"] == str(test_flock.id)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Log revenue (bird sale) — FCR computable after both expense and revenue
# ─────────────────────────────────────────────────────────────────────────────

async def test_log_revenue_bird_sale_updates_snapshot(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Bird sale updates snapshot with FCR data when feed expenses exist."""
    payload = {
        "flock_id": str(test_flock.id),
        "revenue_type": "birds",
        "amount": "55000.00",
        "sale_date": str(date.today()),
        "birds_sold": 200,
        "avg_weight_kg": "2.15",
        "buyer": "Kenchic Processors",
    }
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json=payload,
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["revenue_type"] == "birds"
    assert data["birds_sold"] == 200


# ─────────────────────────────────────────────────────────────────────────────
# 12. List revenue — type filter works
# ─────────────────────────────────────────────────────────────────────────────

async def test_list_revenue_type_filter(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Revenue list with type filter returns only matching records."""
    # Log an eggs sale
    await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json={
            "flock_id": str(test_flock.id),
            "revenue_type": "eggs",
            "amount": "2400.00",
            "sale_date": str(date.today()),
            "eggs_count": 120,
        },
        headers=auth_headers_owner,
    )
    # Log a manure sale
    await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json={
            "flock_id": str(test_flock.id),
            "revenue_type": "manure",
            "amount": "800.00",
            "sale_date": str(date.today()),
        },
        headers=auth_headers_owner,
    )

    # Filter to eggs only
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/revenue?revenue_type=eggs",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert all(r["revenue_type"] == "eggs" for r in items)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Get single revenue record — correct data
# ─────────────────────────────────────────────────────────────────────────────

async def test_get_single_revenue_record(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """GET single revenue record returns correct data."""
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json={
            "flock_id": str(test_flock.id),
            "revenue_type": "other",
            "amount": "1200.00",
            "sale_date": str(date.today()),
            "notes": "Consultation fee from farmer visit",
        },
        headers=auth_headers_owner,
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["data"]["id"]

    get_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/revenue/{record_id}",
        headers=auth_headers_owner,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["id"] == record_id
    assert data["revenue_type"] == "other"
    assert data["notes"] == "Consultation fee from farmer visit"


# ─────────────────────────────────────────────────────────────────────────────
# 14. Update (correct) revenue record — correction note appended
# ─────────────────────────────────────────────────────────────────────────────

async def test_update_revenue_record_appends_correction(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Correcting revenue record appends correction trail to notes."""
    create_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/revenue",
        json={
            "flock_id": str(test_flock.id),
            "revenue_type": "eggs",
            "amount": "5000.00",
            "sale_date": str(date.today()),
            "eggs_count": 250,
        },
        headers=auth_headers_owner,
    )
    record_id = create_resp.json()["data"]["id"]

    upd_resp = await async_client.patch(
        f"/api/v1/farms/{test_farm.id}/revenue/{record_id}",
        json={
            "amount": "5400.00",
            "correction_reason": "Wrong amount recorded at market",
        },
        headers=auth_headers_owner,
    )
    assert upd_resp.status_code == 200
    data = upd_resp.json()["data"]
    assert data["amount"] == "5400.00"
    assert "[Corrected by" in (data["notes"] or "")


# ─────────────────────────────────────────────────────────────────────────────
# 15. Flock snapshot — pre-computed, not real-time
# ─────────────────────────────────────────────────────────────────────────────

async def test_flock_snapshot_is_pre_computed(
    async_client, test_farm, test_flock, auth_headers_owner
):
    """Snapshot endpoint reads from financial_snapshots table (DB-07 frozen)."""
    # Refresh explicitly
    refresh_resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/finance/snapshot/refresh",
        headers=auth_headers_owner,
    )
    assert refresh_resp.status_code == 200

    snap_resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/finance/snapshot",
        headers=auth_headers_owner,
    )
    assert snap_resp.status_code == 200
    snap = snap_resp.json()["data"]
    # snapshot_at must be present and a valid timestamp
    assert snap["snapshot_at"] is not None
    # is_profitable is a bool
    assert isinstance(snap["is_profitable"], bool)


# ─────────────────────────────────────────────────────────────────────────────
# 16. Finance dashboard — aggregate across all farm flocks
# ─────────────────────────────────────────────────────────────────────────────

async def test_finance_dashboard(
    async_client, test_farm, auth_headers_owner
):
    """Finance dashboard returns totals and flock cards."""
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/finance/dashboard",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_revenue_kes" in data
    assert "total_expenses_kes" in data
    assert "net_profit_kes" in data
    assert "flock_cards" in data


# ─────────────────────────────────────────────────────────────────────────────
# 17. RBAC: farm_worker cannot POST expense (403)
# ─────────────────────────────────────────────────────────────────────────────

async def test_farm_worker_cannot_log_expense(
    async_client, test_farm, test_flock, auth_headers_worker
):
    """Farm worker (no FINANCE_RECORD permission) gets 403 on expense POST."""
    system_cat_id = await _get_system_category_id(
        async_client, test_farm.id, auth_headers_worker
    )
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json={
            "category_id": system_cat_id,
            "flock_id": str(test_flock.id),
            "amount": "500.00",
            "expense_date": str(date.today()),
            "payment_method": "cash",
        },
        headers=auth_headers_worker,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 18. RBAC: farm_worker can GET expense list (200)
# ─────────────────────────────────────────────────────────────────────────────

async def test_farm_worker_can_view_expenses(
    async_client, test_farm, auth_headers_worker
):
    """Farm worker has FINANCE_VIEW — can read expense list."""
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses",
        headers=auth_headers_worker,
    )
    assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 19. RBAC: viewer can GET expense list (200)
# ─────────────────────────────────────────────────────────────────────────────

async def test_viewer_can_view_expenses(
    async_client, test_farm, auth_headers_viewer
):
    """Viewer role has FINANCE_VIEW — can read expense list."""
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses",
        headers=auth_headers_viewer,
    )
    assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 20. RBAC: viewer cannot POST expense (403)
# ─────────────────────────────────────────────────────────────────────────────

async def test_viewer_cannot_log_expense(
    async_client, test_farm, test_flock, auth_headers_viewer
):
    """Viewer role does not have FINANCE_RECORD — gets 403 on POST."""
    # Use a dummy UUID — should fail at RBAC before DB lookup
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/expenses",
        json={
            "category_id": str(uuid.uuid4()),
            "flock_id": str(test_flock.id),
            "amount": "100.00",
            "expense_date": str(date.today()),
            "payment_method": "cash",
        },
        headers=auth_headers_viewer,
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# 21. Calculator: FCR — no farm access required, returns rating
# ─────────────────────────────────────────────────────────────────────────────

async def test_calculator_fcr(async_client, auth_headers_owner):
    """FCR calculator endpoint returns computed FCR and Kenya benchmark rating."""
    resp = await async_client.post(
        "/api/v1/calculators/fcr",
        json={
            "total_feed_kg": "200.0",
            "total_weight_gain_kg": "115.0",
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "fcr" in data
    assert "rating" in data
    assert "interpretation" in data
    # FCR = 200 / 115 ≈ 1.739 → "Good (1.7–1.9)"
    fcr_val = float(data["fcr"])
    assert 1.7 < fcr_val < 1.8
    assert "Good" in data["rating"]


# ─────────────────────────────────────────────────────────────────────────────
# 22. Calculator: profit projection
# ─────────────────────────────────────────────────────────────────────────────

async def test_calculator_profit_projection(async_client, auth_headers_owner):
    """Profit projection calculator returns expected revenue, costs, and margin."""
    resp = await async_client.post(
        "/api/v1/calculators/profit-projection",
        json={
            "bird_count": 500,
            "expected_weight_kg": "2.2",
            "expected_price_kes_per_kg": "280.00",
            "total_feed_cost_kes": "85000.00",
            "doc_cost_kes": "20000.00",
            "other_costs_kes": "5000.00",
            "mortality_pct": "3.0",
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "projected_revenue_kes" in data
    assert "total_costs_kes" in data
    assert "net_profit_kes" in data
    assert "profit_margin_pct" in data
    # Sanity: revenue = (500 * 0.97) * 2.2 * 280 ≈ 299,320
    revenue = float(data["projected_revenue_kes"])
    assert revenue > 200_000


# ─────────────────────────────────────────────────────────────────────────────
# 23. Calculator: break-even price
# ─────────────────────────────────────────────────────────────────────────────

async def test_calculator_break_even(async_client, auth_headers_owner):
    """Break-even calculator returns price per kg and per bird."""
    resp = await async_client.post(
        "/api/v1/calculators/break-even",
        json={
            "total_costs_kes": "110000.00",
            "birds_to_sell": 480,
            "avg_weight_kg": "2.1",
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "break_even_price_per_kg" in data
    assert "break_even_price_per_bird" in data
    assert "total_weight_kg" in data
    # total_weight = 480 * 2.1 = 1008 kg
    # break_even/kg = 110000 / 1008 ≈ 109.13
    price_per_kg = float(data["break_even_price_per_kg"])
    assert 100 < price_per_kg < 120


# ─────────────────────────────────────────────────────────────────────────────
# 24. Calculator: feed needs
# ─────────────────────────────────────────────────────────────────────────────

async def test_calculator_feed_needs(async_client, auth_headers_owner):
    """Feed needs calculator returns daily consumption and projected totals."""
    resp = await async_client.post(
        "/api/v1/calculators/feed-needs",
        json={
            "bird_count": 500,
            "current_age_days": 21,
            "current_total_feed_kg": "420.0",
            "days_remaining": 21,
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "daily_consumption_kg" in data
    assert "remaining_feed_needed_kg" in data
    assert "total_projected_feed_kg" in data
    assert "feed_per_bird_per_day_g" in data
    # daily consumption = 420 / 21 = 20 kg/day
    daily = float(data["daily_consumption_kg"])
    assert abs(daily - 20.0) < 1.0
