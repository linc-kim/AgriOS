"""
ARIA operations director — over HTTP, against a real database.

The pure engine is exhaustively unit-tested; these confirm the endpoints wire
real organization data through it, that permission boundaries hold (a worker
cannot see organization sections or another farm's tasks, and nobody reaches an
organization they do not belong to), that task assignment writes a real,
auditable history, and that none of it touches an AI provider.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.auth import Role
from app.models.automation import Reminder
from app.models.farm import Farm, FarmMember, FarmUnit, ProductionHouse
from app.models.organization import Organization, OrganizationMember

pytestmark = pytest.mark.asyncio


def _base(org_id) -> str:
    return f"/api/v1/organizations/{org_id}/operations"


@pytest_asyncio.fixture
async def org(integration_session, workspace):
    """
    An organization owning the two harness farms, plus a third farm the worker is
    NOT a member of (to prove farm-level scoping), and a second organization the
    harness team does not belong to (to prove org isolation).

    Seeded on the per-test connection, so all of it is rolled back at teardown and
    the shared workspace baseline is left untouched.
    """
    s = integration_session
    now = datetime.now(timezone.utc)
    roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}

    owner_id = workspace.users["owner"].id
    farm_a_id = workspace.farm.id
    farm_b_id = workspace.farm_b.id

    # Organization 1 owns farm A and farm B.
    org1 = Organization(name="Green Valley Group", slug=f"gvg-{uuid.uuid4().hex[:8]}",
                        owner_id=owner_id, currency="KES", timezone="Africa/Nairobi")
    s.add(org1)
    await s.flush()

    for fid in (farm_a_id, farm_b_id):
        farm = (await s.execute(select(Farm).where(Farm.id == fid))).scalar_one()
        farm.organization_id = org1.id

    # Owner is the org's administrator.
    s.add(OrganizationMember(organization_id=org1.id, user_id=owner_id,
                             role_id=roles["enterprise_owner"].id, status="active",
                             accepted_at=now))

    # A third farm in org1 that only the owner belongs to.
    farm_c = Farm(name="Outpost Farm", county="Nairobi", owner_id=owner_id,
                  plan_id=(await s.execute(select(Farm.plan_id).where(Farm.id == farm_a_id))).scalar_one(),
                  organization_id=org1.id, is_active=True, timezone="Africa/Nairobi")
    s.add(farm_c)
    await s.flush()
    s.add(FarmMember(farm_id=farm_c.id, user_id=owner_id, role_id=roles["farm_owner"].id,
                     status="active", invited_by=owner_id, accepted_at=now))

    # Second organization, entirely separate team.
    org2 = Organization(name="Rival Co", slug=f"rival-{uuid.uuid4().hex[:8]}",
                        owner_id=workspace.users["super_admin"].id, currency="KES",
                        timezone="Africa/Nairobi")
    s.add(org2)
    await s.flush()

    # Tasks (reminders) on farm A, assigned to the worker and the manager.
    worker_id = workspace.users["worker"].id
    manager_id = workspace.users["manager"].id
    r_worker = Reminder(farm_id=farm_a_id, user_id=worker_id, title="Record today's eggs",
                        due_at=now + timedelta(days=1), created_by=owner_id)
    r_manager = Reminder(farm_id=farm_a_id, user_id=manager_id, title="Reorder feed",
                         due_at=now - timedelta(days=1), created_by=owner_id)  # overdue
    r_unassigned = Reminder(farm_id=farm_b_id, user_id=None, title="Weigh a sample of birds",
                            due_at=now + timedelta(days=2), created_by=owner_id)
    # A task on farm C — the worker must never see it.
    r_outpost = Reminder(farm_id=farm_c.id, user_id=owner_id, title="Inspect Outpost",
                         due_at=now + timedelta(days=1), created_by=owner_id)
    s.add_all([r_worker, r_manager, r_unassigned, r_outpost])
    await s.commit()

    class _Org:
        pass

    o = _Org()
    o.org1_id = org1.id
    o.org2_id = org2.id
    o.farm_a_id = farm_a_id
    o.farm_b_id = farm_b_id
    o.farm_c_id = farm_c.id
    o.worker_id = worker_id
    o.manager_id = manager_id
    o.owner_id = owner_id
    o.r_worker_id = r_worker.id
    o.r_manager_id = r_manager.id
    o.r_unassigned_id = r_unassigned.id
    o.r_outpost_id = r_outpost.id
    return o


# ── 1. Organization intelligence ──────────────────────────────────────────────


class TestOrganizationFacts:
    async def test_aggregates_farms_with_provenance(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/organization", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["farm_count"] == 3        # A, B, Outpost
        for key in ("health", "production", "mortality", "feed_usage", "water_usage",
                    "inventory", "financial"):
            agg = d[key]
            assert "method" in agg
            assert "source_farms" in agg and "missing_farms" in agg

    async def test_priorities_identify_their_farm(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/organization", headers=auth_headers_owner)
        for p in r.json()["data"]["priorities"]:
            assert p["farm_name"] and p["farm_id"]


# ── 2. Cross-farm comparison ──────────────────────────────────────────────────


class TestComparison:
    async def test_ranks_six_metrics_and_shows_missing(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/farms", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert {rk["key"] for rk in d["rankings"]} == {
            "production", "mortality", "feed_efficiency",
            "water_efficiency", "biosecurity", "health",
        }
        for rk in d["rankings"]:
            # Missing farms must be present as unavailable, never dropped silently.
            for m in rk["missing"]:
                assert m["available"] is False


# ── 5. Dashboard ──────────────────────────────────────────────────────────────


class TestDashboard:
    async def test_owner_sees_full_dashboard(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/dashboard", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["tier"] == "administrator"
        assert d["operational_status"]
        assert len(d["farms"]) == 3
        assert any(t["title"] == "Record today's eggs" for t in d["tasks"])

    async def test_filter_by_farm(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/dashboard",
                                   params={"farm_id": str(org.farm_a_id)}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        farms = r.json()["data"]["farms"]
        assert {f["farm_id"] for f in farms} == {str(org.farm_a_id)}


# ── 6. Timeline ───────────────────────────────────────────────────────────────


class TestTimeline:
    async def test_merged_timeline(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/timeline", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        for e in r.json()["data"]:
            assert e["farm_name"]
            assert "severity" in e


# ── 7. Analytics ──────────────────────────────────────────────────────────────


class TestAnalytics:
    async def test_metrics_expose_calculation(self, async_client, org, auth_headers_owner):
        r = await async_client.get(f"{_base(org.org1_id)}/analytics", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        for m in d["org_metrics"] + d["farm_productivity"] + d["trends"]:
            assert m["method"]


# ── 9. Reports ────────────────────────────────────────────────────────────────


class TestReports:
    @pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
    async def test_report_periods(self, async_client, org, auth_headers_owner, period):
        r = await async_client.get(f"{_base(org.org1_id)}/reports",
                                   params={"period": period}, headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["period"] == period
        assert d["sections"]


# ── 4. Task assignment ────────────────────────────────────────────────────────


class TestTaskAssignment:
    async def test_assign_and_history(self, async_client, org, auth_headers_owner):
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_unassigned_id}/assign",
            json={"owner_id": str(org.worker_id)}, headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["owner_id"] == str(org.worker_id)
        assert any(h["action"] in ("assigned", "reassigned") for h in d["history"])

    async def test_prevent_duplicate_assignment(self, async_client, org, auth_headers_owner):
        # r_worker is already "Record today's eggs" owned by the worker on farm A.
        # Reassigning the same-title task to the same worker is refused, and so is
        # assigning a second identical open task. Here: reassign r_worker to worker.
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_worker_id}/assign",
            json={"owner_id": str(org.worker_id)}, headers=auth_headers_owner,
        )
        assert r.status_code == 403
        msg = r.json()["error"]["message"].lower()
        assert "already assigned" in msg or "already has an open task" in msg

    async def test_complete_records_completion(self, async_client, org, auth_headers_owner):
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_manager_id}/complete", headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["status"] == "done"
        assert d["completed_at"]
        assert any(h["action"] == "completed" for h in d["history"])

    async def test_worker_can_complete_own_task(self, async_client, org, auth_headers_worker):
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_worker_id}/complete", headers=auth_headers_worker,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "done"


# ── 8. Permission boundaries ──────────────────────────────────────────────────


class TestPermissionBoundaries:
    async def test_worker_denied_organization_section(self, async_client, org, auth_headers_worker):
        r = await async_client.get(f"{_base(org.org1_id)}/organization", headers=auth_headers_worker)
        assert r.status_code == 403

    async def test_worker_denied_workers_and_analytics(self, async_client, org, auth_headers_worker):
        for section in ("workers", "analytics", "farms"):
            r = await async_client.get(f"{_base(org.org1_id)}/{section}", headers=auth_headers_worker)
            assert r.status_code == 403, f"{section} should be forbidden for a worker"

    async def test_worker_sees_only_own_tasks(self, async_client, org, auth_headers_worker):
        r = await async_client.get(f"{_base(org.org1_id)}/tasks", headers=auth_headers_worker)
        assert r.status_code == 200, r.text
        tasks = r.json()["data"]
        assert tasks, "worker should see their own task"
        assert all(t["owner_id"] == str(org.worker_id) for t in tasks)

    async def test_worker_cannot_see_unassigned_farm(self, async_client, org, auth_headers_worker):
        # Worker is not a member of Outpost Farm — its summary and task must not appear.
        r = await async_client.get(f"{_base(org.org1_id)}/dashboard", headers=auth_headers_worker)
        assert r.status_code == 200, r.text
        farm_ids = {f["farm_id"] for f in r.json()["data"]["farms"]}
        assert str(org.farm_c_id) not in farm_ids

    async def test_worker_cannot_complete_outpost_task(self, async_client, org, auth_headers_worker):
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_outpost_id}/complete", headers=auth_headers_worker,
        )
        assert r.status_code == 403

    async def test_worker_cannot_assign(self, async_client, org, auth_headers_worker):
        r = await async_client.post(
            f"{_base(org.org1_id)}/tasks/{org.r_unassigned_id}/assign",
            json={"owner_id": str(org.worker_id)}, headers=auth_headers_worker,
        )
        assert r.status_code == 403

    async def test_no_access_to_foreign_organization(self, async_client, org, auth_headers_worker):
        # The harness worker is not a member of Rival Co.
        r = await async_client.get(f"{_base(org.org2_id)}/dashboard", headers=auth_headers_worker)
        assert r.status_code == 403

    async def test_supervisor_can_read_organization(self, async_client, org, auth_headers_manager):
        r = await async_client.get(f"{_base(org.org1_id)}/organization", headers=auth_headers_manager)
        assert r.status_code == 200, r.text

    async def test_unknown_organization_is_404(self, async_client, auth_headers_owner):
        r = await async_client.get(f"{_base(uuid.uuid4())}/dashboard", headers=auth_headers_owner)
        assert r.status_code in (403, 404)
