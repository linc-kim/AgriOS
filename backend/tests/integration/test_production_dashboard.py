"""
Greena — Phase 3 Production Dashboard: real farm-wide metrics.
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def test_production_dashboard_aggregates_real_data(
    async_client, test_farm, test_flock, auth_headers_owner
):
    today = str(date.today())

    # Log today's feed + losses.
    await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/logs",
        json={"log_date": today, "mortality_count": 4, "culls": 1, "feed_consumed_kg": "55.5"},
        headers=auth_headers_owner,
    )
    # Log today's egg production.
    await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/production",
        json={"record_date": today, "eggs_collected": 320, "broken_eggs": 5},
        headers=auth_headers_owner,
    )

    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/production-dashboard",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200, resp.text
    d = resp.json()["data"]
    assert d["active_flock_count"] == 1
    assert d["eggs_today"] == 320
    assert d["eggs_this_week"] >= 320
    assert float(d["feed_today_kg"]) == 55.5
    assert d["mortality_this_week"] >= 4
    assert d["culls_this_week"] >= 1
    # 500 initial - 4 mortality - 1 cull = 495
    assert d["total_birds"] == 495
    assert d["avg_bird_age_days"] is not None


async def test_production_dashboard_requires_view_permission(
    async_client, test_farm, auth_headers_owner
):
    resp = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/production-dashboard",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200
