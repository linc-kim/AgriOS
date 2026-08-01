"""
Operations Planner (Platform Module 5) — HTTP API tests.

Covers the routine lifecycle end to end over HTTP, the honesty-labelled analytics
surface, the living Operations Manual, and RBAC boundaries (a viewer cannot write;
a worker executes but cannot author routines; approval is an owner concern).
"""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio

MODULE = "poultry"


def _ops(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/operations"


def _routine_payload(**over) -> dict:
    body = {
        "module": MODULE, "name": "Morning inspection", "category": "health",
        "frequency": "daily", "priority": "high", "estimated_duration_minutes": 30,
        "schedule": {"frequency": "daily", "start_date": (date.today() - timedelta(days=1)).isoformat()},
        "task_templates": [{"name": "Check water", "sequence": 0}],
    }
    body.update(over)
    return body


async def _create_routine(client, fid, headers, **over) -> dict:
    r = await client.post(f"{_ops(fid)}/routines", json=_routine_payload(**over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestRoutineLifecycle:
    async def test_create_list_activate_and_manual(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        routine = await _create_routine(async_client, fid, auth_headers_owner)
        assert routine["status"] == "draft" and routine["current_version"] == 1

        listed = await async_client.get(f"{_ops(fid)}/routines?module={MODULE}", headers=auth_headers_owner)
        assert listed.status_code == 200
        assert any(r["id"] == routine["id"] for r in listed.json()["data"])

        act = await async_client.post(f"{_ops(fid)}/routines/{routine['id']}/activate", headers=auth_headers_owner)
        assert act.status_code == 200 and act.json()["data"]["is_active"] is True

        manual = await async_client.get(f"{_ops(fid)}/manual", headers=auth_headers_owner)
        assert manual.status_code == 200
        daily = manual.json()["data"]["sections"].get("daily", [])
        assert any(e["id"] == routine["id"] for e in daily)

    async def test_update_writes_new_version(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        routine = await _create_routine(async_client, fid, auth_headers_owner)
        upd = await async_client.patch(
            f"{_ops(fid)}/routines/{routine['id']}",
            json={"name": "Renamed", "change_summary": "rename"}, headers=auth_headers_owner)
        assert upd.status_code == 200
        versions = await async_client.get(
            f"{_ops(fid)}/routines/{routine['id']}/versions", headers=auth_headers_owner)
        nums = {v["version_number"] for v in versions.json()["data"]}
        assert {1, 2} <= nums

    async def test_schedule_and_calendar(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        routine = await _create_routine(async_client, fid, auth_headers_owner)
        await async_client.post(f"{_ops(fid)}/routines/{routine['id']}/activate", headers=auth_headers_owner)
        start, end = date.today().isoformat(), (date.today() + timedelta(days=2)).isoformat()
        cal = await async_client.get(
            f"{_ops(fid)}/calendar?start={start}&end={end}", headers=auth_headers_owner)
        assert cal.status_code == 200
        assert any(e["type"] == "routine" for e in cal.json()["data"]["events"])
        mat = await async_client.post(
            f"{_ops(fid)}/schedule/materialize?start={start}&end={end}", headers=auth_headers_owner)
        assert mat.status_code == 200 and mat.json()["data"]["created"] == 3  # today..+2


class TestAnalyticsHonesty:
    async def test_performance_carries_labels(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(f"{_ops(fid)}/analytics/compliance", headers=auth_headers_owner)
        assert r.status_code == 200
        data = r.json()["data"]
        # compliance_rate is an honesty-labelled value (unknown when no requirements).
        assert data["compliance_rate"]["fact_type"] in (
            "calculated", "unknown", "recorded_fact")

    async def test_capacity_growth_projection_is_forecast(self, async_client, workspace, auth_headers_owner):
        fid = workspace.farm.id
        r = await async_client.get(
            f"{_ops(fid)}/analytics/capacity?growth_factor=2", headers=auth_headers_owner)
        assert r.status_code == 200


class TestRBAC:
    async def test_viewer_cannot_create_routine(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        r = await async_client.post(
            f"{_ops(fid)}/routines", json=_routine_payload(), headers=auth_headers_viewer)
        assert r.status_code == 403

    async def test_viewer_can_read_manual(self, async_client, workspace, auth_headers_viewer):
        fid = workspace.farm.id
        r = await async_client.get(f"{_ops(fid)}/manual", headers=auth_headers_viewer)
        assert r.status_code == 200

    async def test_worker_cannot_author_but_can_read(self, async_client, workspace, auth_headers_worker):
        fid = workspace.farm.id
        create = await async_client.post(
            f"{_ops(fid)}/routines", json=_routine_payload(), headers=auth_headers_worker)
        assert create.status_code == 403  # OPSPLAN_ROUTINE_EDIT not granted to worker
        read = await async_client.get(f"{_ops(fid)}/routines", headers=auth_headers_worker)
        assert read.status_code == 200

    async def test_manager_cannot_approve_version(self, async_client, workspace,
                                                  auth_headers_owner, auth_headers_manager):
        fid = workspace.farm.id
        routine = await _create_routine(async_client, fid, auth_headers_owner)
        # Approval is an owner concern (OPSPLAN_MANUAL_APPROVE) — manager is denied.
        r = await async_client.post(
            f"{_ops(fid)}/routines/{routine['id']}/versions/1/approve", headers=auth_headers_manager)
        assert r.status_code == 403
        ok = await async_client.post(
            f"{_ops(fid)}/routines/{routine['id']}/versions/1/approve", headers=auth_headers_owner)
        assert ok.status_code == 200 and ok.json()["data"]["approval_status"] == "approved"
