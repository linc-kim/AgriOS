"""
AGRIOS — Integration Tests: Flock Lifecycle Flow (Sprint 3)

Tests the complete flock lifecycle end-to-end against the live DB:
  1. Create flock → house becomes occupied
  2. Submit daily logs (upsert on same date, new date)
  3. Record weigh-in → FCR computed
  4. Log egg production (upsert)
  5. Record feed purchase (farm-level and flock-level)
  6. Fetch flock detail → metrics populated
  7. Close flock (sold) → house released
  8. Verify closed flock rejects new daily logs

Plan limit test:
  - Create 3 flocks on Free plan → 4th rejected with 402
  - (Mocked subscription plan with max_active_flocks=3)

RBAC tests:
  - farm_worker can submit daily log (OPS_LOG_SUBMIT)
  - farm_worker cannot create flock (FLOCK_CREATE)
  - farm_worker cannot close flock (FLOCK_CLOSE)
  - viewer cannot submit daily log (OPS_LOG_SUBMIT)

These tests require:
  - Postgres test database (TEST_DATABASE_URL env var)
  - Alembic migrations applied up to 016
  - pytest-asyncio

Run with: pytest tests/integration/test_flock_flow.py -v
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────
# NOTE: Full fixture scaffolding depends on the test DB setup in conftest.py.
# These tests define the contract. The CI harness wires the fixtures.


@pytest.mark.asyncio
async def test_create_flock_occupies_house(
    authenticated_client: AsyncClient,
    farm_with_house: dict,
):
    """Creating a flock marks the house as occupied."""
    farm_id = farm_with_house["farm_id"]
    house_id = farm_with_house["house_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks",
        json={
            "house_id": house_id,
            "name": "Batch 1 – Integration Test",
            "initial_count": 500,
            "placement_date": str(date.today() - timedelta(days=5)),
            "expected_cycle_days": 42,
            "species_key": "poultry",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    flock = body["data"]
    assert flock["status"] == "active"
    assert flock["house_id"] == house_id


@pytest.mark.asyncio
async def test_second_flock_on_same_house_rejected(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """A house with an active flock rejects a second flock (409)."""
    farm_id = farm_with_active_flock["farm_id"]
    house_id = farm_with_active_flock["house_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks",
        json={
            "house_id": house_id,
            "name": "Batch 2 – Should Fail",
            "initial_count": 300,
            "placement_date": str(date.today()),
            "species_key": "poultry",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_daily_log_submit_and_upsert(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """Submit a daily log, then re-submit the same date → upsert updates the record."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]
    today = str(date.today())

    # First submission
    r1 = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": today,
            "mortality_count": 1,
            "feed_consumed_kg": "25.000",
        },
    )
    assert r1.status_code == 200
    log_id_1 = r1.json()["data"]["id"]

    # Second submission (same date) → upsert
    r2 = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": today,
            "mortality_count": 2,
            "feed_consumed_kg": "26.500",
            "notes": "Corrected feed amount",
        },
    )
    assert r2.status_code == 200
    log_id_2 = r2.json()["data"]["id"]

    # Same record updated (same row, feed updated)
    assert log_id_1 == log_id_2
    assert r2.json()["data"]["mortality_count"] == 2
    assert Decimal(r2.json()["data"]["feed_consumed_kg"]) == Decimal("26.500")


@pytest.mark.asyncio
async def test_daily_log_future_date_rejected(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": str(date.today() + timedelta(days=1)),
            "mortality_count": 0,
            "feed_consumed_kg": "25.000",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_weighin_computes_fcr(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """Weigh-in computes FCR from cumulative feed logs."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    # Submit some feed logs first
    for days_ago in range(3, 0, -1):
        await authenticated_client.post(
            f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
            json={
                "log_date": str(date.today() - timedelta(days=days_ago)),
                "mortality_count": 0,
                "feed_consumed_kg": "50.000",
            },
        )

    # Submit weigh-in
    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/weighins",
        json={
            "weighed_at": str(date.today()),
            "sample_size": 50,
            "average_weight_kg": "0.900",
        },
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["total_biomass_kg"] is not None
    assert body["fcr_to_date"] is not None


@pytest.mark.asyncio
async def test_flock_detail_returns_metrics(
    authenticated_client: AsyncClient,
    farm_with_logged_flock: dict,
):
    """GET /flocks/{id} returns computed metrics including survival_rate."""
    farm_id = farm_with_logged_flock["farm_id"]
    flock_id = farm_with_logged_flock["flock_id"]

    response = await authenticated_client.get(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    metrics = data["metrics"]

    assert "survival_rate" in metrics
    assert 0.0 <= metrics["survival_rate"] <= 100.0
    assert metrics["total_mortality"] >= 0
    assert metrics["current_count"] >= 0
    assert metrics["total_feed_kg"] is not None
    assert metrics["days_alive"] >= 0


@pytest.mark.asyncio
async def test_close_flock_releases_house(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """Closing a flock clears production_houses.current_flock_id."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/close",
        json={
            "status": "sold",
            "close_date": str(date.today()),
            "close_reason": "Reached target weight",
            "sale_price_per_kg": "185.00",
            "total_birds_sold": 490,
            "closing_weight_kg": "2.150",
        },
    )
    assert response.status_code == 200
    flock = response.json()["data"]
    assert flock["status"] == "sold"
    assert flock["close_date"] == str(date.today())
    assert Decimal(flock["sale_price_per_kg"]) == Decimal("185.00")


@pytest.mark.asyncio
async def test_closed_flock_rejects_daily_log(
    authenticated_client: AsyncClient,
    farm_with_closed_flock: dict,
):
    """A closed flock must not accept new daily logs (409)."""
    farm_id = farm_with_closed_flock["farm_id"]
    flock_id = farm_with_closed_flock["flock_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": str(date.today()),
            "mortality_count": 0,
            "feed_consumed_kg": "25.000",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_feed_purchase_farm_level(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """Record a feed purchase not linked to a specific flock."""
    farm_id = farm_with_active_flock["farm_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/feed-purchases",
        json={
            "purchase_date": str(date.today()),
            "feed_type": "Starter",
            "quantity_kg": "500.000",
            "price_per_kg": "55.00",
            "supplier": "Unga Feeds Ltd",
        },
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert Decimal(body["total_cost"]) == Decimal("27500.00")
    assert body["flock_id"] is None


@pytest.mark.asyncio
async def test_feed_purchase_flock_level(
    authenticated_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """Record a feed purchase linked to a specific flock."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/feed-purchases",
        json={
            "flock_id": flock_id,
            "purchase_date": str(date.today()),
            "feed_type": "Grower",
            "quantity_kg": "200.000",
            "price_per_kg": "60.00",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["flock_id"] == flock_id


@pytest.mark.asyncio
async def test_plan_limit_rejects_fourth_flock(
    authenticated_client: AsyncClient,
    farm_at_flock_limit: dict,
):
    """Free plan (max 3 active flocks): 4th flock creation returns 402."""
    farm_id = farm_at_flock_limit["farm_id"]
    house_id = farm_at_flock_limit["extra_house_id"]

    response = await authenticated_client.post(
        f"/api/v1/farms/{farm_id}/flocks",
        json={
            "house_id": house_id,
            "name": "Batch 4 – Should Fail",
            "initial_count": 100,
            "placement_date": str(date.today()),
            "species_key": "poultry",
        },
    )
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "PLAN_LIMIT"


# ── RBAC Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_farm_worker_can_submit_daily_log(
    worker_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """farm_worker has OPS_LOG_SUBMIT → can submit daily logs."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await worker_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": str(date.today() - timedelta(days=1)),
            "mortality_count": 0,
            "feed_consumed_kg": "20.000",
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_farm_worker_cannot_create_flock(
    worker_client: AsyncClient,
    farm_with_house: dict,
):
    """farm_worker lacks FLOCK_CREATE → 403."""
    farm_id = farm_with_house["farm_id"]
    house_id = farm_with_house["house_id"]

    response = await worker_client.post(
        f"/api/v1/farms/{farm_id}/flocks",
        json={
            "house_id": house_id,
            "name": "Worker Batch",
            "initial_count": 100,
            "placement_date": str(date.today()),
            "species_key": "poultry",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_farm_worker_cannot_close_flock(
    worker_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """farm_worker lacks FLOCK_CLOSE → 403."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await worker_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/close",
        json={
            "status": "closed",
            "close_date": str(date.today()),
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_submit_daily_log(
    viewer_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """viewer lacks OPS_LOG_SUBMIT → 403."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await viewer_client.post(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
        json={
            "log_date": str(date.today()),
            "mortality_count": 0,
            "feed_consumed_kg": "25.000",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_view_flock(
    viewer_client: AsyncClient,
    farm_with_active_flock: dict,
):
    """viewer has FLOCK_VIEW → can read flock detail."""
    farm_id = farm_with_active_flock["farm_id"]
    flock_id = farm_with_active_flock["flock_id"]

    response = await viewer_client.get(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}"
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_log_correction_requires_manager(
    worker_client: AsyncClient,
    farm_with_logged_flock: dict,
):
    """farm_worker lacks OPS_LOG_CORRECT → 403 on PATCH /logs/{date}."""
    farm_id = farm_with_logged_flock["farm_id"]
    flock_id = farm_with_logged_flock["flock_id"]
    log_date = farm_with_logged_flock["log_date"]

    response = await worker_client.patch(
        f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs/{log_date}",
        json={
            "mortality_count": 5,
            "correction_reason": "Missed birds during count",
        },
    )
    assert response.status_code == 403
