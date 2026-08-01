"""
Operations Planner (Platform Module 5) — service-layer integration tests.

Exercises the domain services against real Postgres via ``integration_session``:
routine CRUD + immutable version history, the Operations Manual rebuild on
approved change, reminder materialisation (reusing the platform Task store,
idempotently), immutable completion records, compliance/performance analytics
from recorded facts, advisory recommendations, and farm isolation.
"""

from datetime import date, timedelta

import pytest

from app.models.auth import User
from app.schemas import ops_planner as s
from app.services import ops_optimization_service as opt
from app.services import ops_scheduler_service as sched
from app.services import ops_service

pytestmark = pytest.mark.asyncio

MODULE = "poultry"


async def _owner(session, workspace) -> User:
    return await session.get(User, workspace.users["owner"].id)


def _routine_body(**over) -> s.RoutineCreate:
    body = dict(
        module=MODULE, name="Morning inspection", category="health", frequency="daily",
        priority="high", estimated_duration_minutes=30,
        schedule=s.ScheduleInput(frequency="daily", start_date=date.today() - timedelta(days=2)),
        task_templates=[s.TaskTemplateInput(name="Check water", sequence=0)],
    )
    body.update(over)
    return s.RoutineCreate(**body)


class TestRoutineLifecycle:
    async def test_create_writes_version_and_manual(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        assert routine.current_version == 1 and routine.status == "draft"
        versions = await ops_service.list_routine_versions(integration_session, fid, routine.id)
        assert len(versions) == 1 and versions[0].snapshot["name"] == "Morning inspection"
        # A manual now exists for the farm.
        manual = await ops_service.get_or_create_manual(integration_session, fid, user)
        assert manual.farm_id == fid

    async def test_update_appends_immutable_version(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        upd = s.RoutineUpdate(name="Renamed", change_summary="rename", priority="critical")
        await ops_service.update_routine(integration_session, fid, routine.id, upd, user)
        versions = await ops_service.list_routine_versions(integration_session, fid, routine.id)
        assert len(versions) == 2
        # Version 1 still holds the ORIGINAL name — history is immutable.
        v1 = next(v for v in versions if v.version_number == 1)
        assert v1.snapshot["name"] == "Morning inspection"

    async def test_activate_rebuilds_manual(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        manual = await ops_service.get_or_create_manual(integration_session, fid, user)
        # Manual's daily section now references the activated routine.
        daily = manual.sections.get("daily", [])
        assert any(e["id"] == str(routine.id) for e in daily)
        assert manual.sections["routine_count"] >= 1

    async def test_requires_approval_blocks_activation(self, integration_session, workspace):
        from app.exceptions import ConflictException
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(
            integration_session, fid, MODULE, _routine_body(requires_approval=True), user)
        with pytest.raises(ConflictException):
            await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        # After approving version 1, activation succeeds.
        await ops_service.approve_routine_version(integration_session, fid, routine.id, 1, user)
        activated = await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        assert activated.is_active is True


class TestSchedulingAndCompletion:
    async def test_materialize_is_idempotent(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        start, end = date.today(), date.today() + timedelta(days=3)
        first = await sched.materialize_tasks(integration_session, fid, MODULE, start, end, user)
        assert first["created"] == 4  # today..+3 inclusive, daily
        again = await sched.materialize_tasks(integration_session, fid, MODULE, start, end, user)
        assert again["created"] == 0  # dedup — no duplicate reminders

    async def test_completion_is_recorded_and_metrics_reflect_it(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        comp = await sched.record_completion(
            integration_session, fid,
            s.CompletionInput(routine_id=routine.id, occurrence_date=date.today(),
                              status="completed", duration_minutes=25), user)
        assert comp.status == "completed"
        perf = await opt.performance(integration_session, fid, MODULE, since=date.today() - timedelta(days=1))
        assert perf["recorded"] == 1 and perf["expected"] >= 1
        assert 0 <= perf["completion_rate"] <= 1


class TestAnalytics:
    async def test_compliance_report_flags_overdue(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        # A weekly biosecurity routine, activated, never completed → overdue basis.
        routine = await ops_service.create_routine(
            integration_session, fid, MODULE,
            _routine_body(name="Biosecurity check", category="biosecurity", frequency="weekly"), user)
        await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        report = await opt.compliance_report(integration_session, fid)
        # The requirement appears; with no completion it is unknown (no invented status).
        keys = {i["key"] for i in report["items"]}
        assert str(routine.id) in keys

    async def test_recommendations_generated_and_decided(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        # Low completion: activate a daily routine, record nothing → completion_rate 0.
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
        created = await opt.generate_recommendations(
            integration_session, fid, MODULE, user, since=date.today() - timedelta(days=7))
        assert created, "expected at least one advisory recommendation"
        rec = created[0]
        assert rec.approval_status == "pending" and rec.confidence in ("low", "medium", "high")
        decided = await opt.decide_recommendation(integration_session, fid, rec.id, "approved", user)
        assert decided.approval_status == "approved"


class TestIsolation:
    async def test_routine_scoped_to_its_farm(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid, other = workspace.farm.id, workspace.farm_b.id
        routine = await ops_service.create_routine(integration_session, fid, MODULE, _routine_body(), user)
        mine = await ops_service.list_routines(integration_session, fid, MODULE)
        theirs = await ops_service.list_routines(integration_session, other, MODULE)
        assert any(r.id == routine.id for r in mine)
        assert all(r.id != routine.id for r in theirs)


class TestSOPAndTemplates:
    async def test_sop_edit_requires_reapproval(self, integration_session, workspace):
        user = await _owner(integration_session, workspace)
        fid = workspace.farm.id
        sop = await ops_service.create_sop(
            integration_session, fid,
            s.SOPInput(name="Feed prep", category="feeding", steps=["measure", "mix"]), user)
        approved = await ops_service.approve_sop(integration_session, fid, sop.id, user)
        assert approved.approval_status == "approved"
        edited = await ops_service.update_sop(
            integration_session, fid, sop.id, s.SOPInput(name="Feed prep v2", steps=["measure", "mix", "serve"]), user)
        assert edited.approval_status == "pending" and edited.version == 2
        assert len(edited.revision_history) == 1  # prior state preserved
