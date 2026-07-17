"""
Greena — Phase 3 Health Management: health events, finance integration, summary.
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


def _url(farm_id, flock_id):
    return f"/api/v1/farms/{farm_id}/flocks/{flock_id}/health-events"


async def test_log_observation_and_list(async_client, test_farm, test_flock, auth_headers_owner):
    resp = await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={
            "event_type": "symptom",
            "event_date": str(date.today()),
            "title": "Reduced feed intake",
            "symptoms": ["reduced_eating", "lethargy"],
            "observations": {"affected_house": "House 1"},
            "severity": "watch",
            "affected_count": 12,
            "follow_up_date": str(date.today() + timedelta(days=2)),
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["event_type"] == "symptom"
    assert data["symptoms"] == ["reduced_eating", "lethargy"]
    assert data["status"] == "open"

    lst = await async_client.get(_url(test_farm.id, test_flock.id), headers=auth_headers_owner)
    assert lst.status_code == 200
    assert any(e["title"] == "Reduced feed intake" for e in lst.json()["data"])


async def test_medication_event_creates_expense(async_client, test_farm, test_flock, auth_headers_owner):
    resp = await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={
            "event_type": "medication",
            "event_date": str(date.today()),
            "title": "Antibiotic course",
            "medication_name": "Oxytetracycline",
            "dosage": "10g / 100L water, 5 days",
            "cost_kes": "1500.00",
            "severity": "warning",
        },
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["expense_id"] is not None

    # The cost shows up in the farm's expenses.
    expenses = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/expenses", headers=auth_headers_owner
    )
    items = expenses.json()["data"]["items"]
    assert any("Oxytetracycline" in (e.get("description") or "") for e in items)


async def test_progress_and_resolve_event(async_client, test_farm, test_flock, auth_headers_owner):
    created = await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={"event_type": "diagnosis", "event_date": str(date.today()), "title": "Suspected coccidiosis", "severity": "warning"},
        headers=auth_headers_owner,
    )
    event_id = created.json()["data"]["id"]

    upd = await async_client.patch(
        f"{_url(test_farm.id, test_flock.id)}/{event_id}",
        json={"status": "resolved", "treatment": "Amprolium administered"},
        headers=auth_headers_owner,
    )
    assert upd.status_code == 200, upd.text
    data = upd.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolved_date"] is not None
    assert data["treatment"] == "Amprolium administered"


async def test_health_summary(async_client, test_farm, test_flock, auth_headers_owner):
    # One open critical event with follow-up.
    await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={
            "event_type": "quarantine",
            "event_date": str(date.today()),
            "title": "Isolated sick birds",
            "severity": "critical",
            "affected_count": 5,
            "follow_up_date": str(date.today() + timedelta(days=1)),
        },
        headers=auth_headers_owner,
    )
    summary = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/health/summary", headers=auth_headers_owner
    )
    assert summary.status_code == 200, summary.text
    d = summary.json()["data"]
    assert d["open_events"] >= 1
    assert d["critical_open"] >= 1
    assert d["total_affected_open"] >= 5
    assert len(d["upcoming_follow_ups"]) >= 1


async def test_rbac_viewer_can_view_not_log(async_client, test_farm, test_flock, auth_headers_viewer):
    view = await async_client.get(_url(test_farm.id, test_flock.id), headers=auth_headers_viewer)
    assert view.status_code == 200
    denied = await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={"event_type": "observation", "event_date": str(date.today()), "title": "nope"},
        headers=auth_headers_viewer,
    )
    assert denied.status_code == 403


async def test_rbac_vet_can_log(async_client, test_farm, test_flock, auth_headers_vet):
    resp = await async_client.post(
        _url(test_farm.id, test_flock.id),
        json={"event_type": "vet_visit", "event_date": str(date.today()), "title": "Routine vet check", "vet_name": "Dr. Otieno"},
        headers=auth_headers_vet,
    )
    assert resp.status_code == 201, resp.text
