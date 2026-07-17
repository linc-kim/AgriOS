"""
Greena — Module 8 Automation & Notifications integration tests.

Covers reminders, automation rules, the trigger/reminder/rule engine, the
Activity Center (search / archive / priority), and RBAC.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


def _a(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/automation"


async def test_reminder_crud_and_complete(async_client, test_farm, auth_headers_owner):
    due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    c = await async_client.post(f"{_a(test_farm.id)}/reminders", json={
        "title": "Order feed", "notes": "2 tonnes broiler starter", "due_at": due,
        "recurrence": "none", "priority": "high"}, headers=auth_headers_owner)
    assert c.status_code == 201, c.text
    rid = c.json()["data"]["id"]
    assert c.json()["data"]["is_overdue"] is False

    lst = await async_client.get(f"{_a(test_farm.id)}/reminders", headers=auth_headers_owner)
    assert any(r["id"] == rid for r in lst.json()["data"])

    done = await async_client.patch(f"{_a(test_farm.id)}/reminders/{rid}", json={"is_done": True}, headers=auth_headers_owner)
    assert done.status_code == 200 and done.json()["data"]["is_done"] is True


async def test_due_reminder_fires_notification(async_client, test_farm, auth_headers_owner):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await async_client.post(f"{_a(test_farm.id)}/reminders", json={
        "title": "Vaccinate flock", "due_at": past, "recurrence": "none"}, headers=auth_headers_owner)

    run = await async_client.post(f"{_a(test_farm.id)}/run", headers=auth_headers_owner)
    assert run.status_code == 200, run.text
    assert run.json()["data"]["reminders_fired"] >= 1

    act = await async_client.get(f"{_a(test_farm.id)}/activity", headers=auth_headers_owner)
    assert any("Vaccinate flock" in n["title"] for n in act.json()["data"])


async def test_recurring_reminder_advances(async_client, test_farm, auth_headers_owner):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    c = await async_client.post(f"{_a(test_farm.id)}/reminders", json={
        "title": "Daily walk-through", "due_at": past, "recurrence": "daily"}, headers=auth_headers_owner)
    rid = c.json()["data"]["id"]
    await async_client.post(f"{_a(test_farm.id)}/run", headers=auth_headers_owner)
    # Still active (not done) and due_at advanced into the future.
    lst = await async_client.get(f"{_a(test_farm.id)}/reminders", headers=auth_headers_owner)
    mine = [r for r in lst.json()["data"] if r["id"] == rid][0]
    assert mine["is_done"] is False
    assert datetime.fromisoformat(mine["due_at"]) > datetime.now(timezone.utc) - timedelta(hours=1)


async def test_automation_rule_crud(async_client, test_farm, auth_headers_owner):
    c = await async_client.post(f"{_a(test_farm.id)}/rules", json={
        "name": "Alert on low feed", "trigger_type": "low_feed",
        "conditions": {"min_count": 1},
        "actions": [{"type": "notify", "priority": "high", "message": "Feed is running low!"}],
        "priority": "high"}, headers=auth_headers_owner)
    assert c.status_code == 201, c.text
    rid = c.json()["data"]["id"]

    u = await async_client.patch(f"{_a(test_farm.id)}/rules/{rid}", json={"is_active": False}, headers=auth_headers_owner)
    assert u.status_code == 200 and u.json()["data"]["is_active"] is False

    d = await async_client.delete(f"{_a(test_farm.id)}/rules/{rid}", headers=auth_headers_owner)
    assert d.status_code == 200


async def test_rule_fires_on_trigger(async_client, test_farm, test_flock, auth_headers_owner):
    # Create a low-feed situation: buy feed then set a high reorder level.
    buy = await async_client.post(f"/api/v1/farms/{test_farm.id}/feed/purchases", json={
        "feed_type": "layer_mash", "location": "auto_store", "quantity_kg": "10.0",
        "price_per_kg": "50.00", "purchase_date": str(date.today())}, headers=auth_headers_owner)
    item_id = buy.json()["data"]["item"]["id"]
    await async_client.patch(f"/api/v1/farms/{test_farm.id}/feed/inventory/{item_id}",
                             json={"reorder_level_kg": "100.0"}, headers=auth_headers_owner)

    await async_client.post(f"{_a(test_farm.id)}/rules", json={
        "name": "Low feed watcher", "trigger_type": "low_feed",
        "actions": [{"type": "notify", "priority": "critical", "message": "Reorder feed now"}]},
        headers=auth_headers_owner)

    run = await async_client.post(f"{_a(test_farm.id)}/run", headers=auth_headers_owner)
    assert run.status_code == 200, run.text
    d = run.json()["data"]
    assert d["triggers_fired"] >= 1  # low_feed trigger fired
    assert d["rules_matched"] >= 1
    # A low-feed notification exists.
    act = await async_client.get(f"{_a(test_farm.id)}/activity", headers=auth_headers_owner)
    assert any("feed" in n["title"].lower() or "Reorder" in n["body"] for n in act.json()["data"])


async def test_activity_center_search_and_archive(async_client, test_farm, auth_headers_owner):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await async_client.post(f"{_a(test_farm.id)}/reminders", json={
        "title": "Uniquely searchable reminder", "due_at": past}, headers=auth_headers_owner)
    await async_client.post(f"{_a(test_farm.id)}/run", headers=auth_headers_owner)

    # Search.
    found = await async_client.get(f"{_a(test_farm.id)}/activity?q=Uniquely", headers=auth_headers_owner)
    assert found.status_code == 200
    rows = found.json()["data"]
    assert rows and all("Uniquely" in n["title"] for n in rows)
    nid = rows[0]["id"]

    # Archive → disappears from active, appears in archived.
    arc = await async_client.post(f"{_a(test_farm.id)}/activity/{nid}/archive?archived=true", headers=auth_headers_owner)
    assert arc.status_code == 200 and arc.json()["data"]["is_archived"] is True
    active = await async_client.get(f"{_a(test_farm.id)}/activity?status=all", headers=auth_headers_owner)
    assert not any(n["id"] == nid for n in active.json()["data"])
    archived = await async_client.get(f"{_a(test_farm.id)}/activity?status=archived", headers=auth_headers_owner)
    assert any(n["id"] == nid for n in archived.json()["data"])


async def test_triggers_list_and_rbac(async_client, test_farm, auth_headers_owner, auth_headers_worker, auth_headers_viewer):
    trg = await async_client.get(f"{_a(test_farm.id)}/triggers", headers=auth_headers_owner)
    assert trg.status_code == 200 and "low_feed" in trg.json()["data"]

    # Worker can view activity but cannot manage rules.
    assert (await async_client.get(f"{_a(test_farm.id)}/activity", headers=auth_headers_worker)).status_code == 200
    denied = await async_client.post(f"{_a(test_farm.id)}/rules", json={
        "name": "x", "trigger_type": "low_feed", "actions": []}, headers=auth_headers_worker)
    assert denied.status_code == 403

    # Viewer cannot run the engine.
    assert (await async_client.post(f"{_a(test_farm.id)}/run", headers=auth_headers_viewer)).status_code == 403
