"""
Greena — Phase 3 Daily Operations: culling reduces the live count.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def test_daily_log_records_culls_and_reduces_count(
    async_client, test_farm, test_flock, auth_headers_owner
):
    # Baseline live count from flock detail.
    detail = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}",
        headers=auth_headers_owner,
    )
    assert detail.status_code == 200, detail.text
    base = detail.json()["data"]["metrics"]["current_count"]

    # Log a day with mortality + culls.
    log = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/logs",
        json={
            "log_date": str(date.today() - timedelta(days=1)),
            "mortality_count": 2,
            "culls": 3,
            "feed_consumed_kg": "40.0",
        },
        headers=auth_headers_owner,
    )
    assert log.status_code == 200, log.text
    assert log.json()["data"]["culls"] == 3

    # Live count drops by mortality + culls (2 + 3 = 5).
    detail2 = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}",
        headers=auth_headers_owner,
    )
    metrics = detail2.json()["data"]["metrics"]
    assert metrics["total_culls"] == 3
    assert metrics["total_mortality"] == 2
    assert metrics["current_count"] == base - 5


async def test_log_egg_production_and_weighin(
    async_client, test_farm, test_flock, auth_headers_owner
):
    today = str(date.today())
    eggs = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/production",
        json={"record_date": today, "eggs_collected": 280, "broken_eggs": 4},
        headers=auth_headers_owner,
    )
    assert eggs.status_code in (200, 201), eggs.text
    assert eggs.json()["data"]["eggs_collected"] == 280

    weigh = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/weighins",
        json={"weighed_at": today, "sample_size": 30, "average_weight_kg": "1.85"},
        headers=auth_headers_owner,
    )
    assert weigh.status_code in (200, 201), weigh.text
    assert weigh.json()["data"]["sample_size"] == 30

    # Flock detail now reflects the weigh-in (avg weight populated).
    detail = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}", headers=auth_headers_owner
    )
    assert detail.json()["data"]["metrics"]["latest_avg_weight_kg"] is not None


async def test_worker_can_submit_log_viewer_cannot(
    async_client, test_farm, test_flock, auth_headers_worker, auth_headers_viewer
):
    ok = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/logs",
        json={"log_date": str(date.today()), "mortality_count": 0, "feed_consumed_kg": "38.0", "culls": 1},
        headers=auth_headers_worker,
    )
    assert ok.status_code == 200, ok.text

    denied = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/logs",
        json={"log_date": str(date.today()), "mortality_count": 0, "feed_consumed_kg": "1.0"},
        headers=auth_headers_viewer,
    )
    assert denied.status_code == 403
