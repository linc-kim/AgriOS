"""
Operations Planner (Platform Module 5) — background job wiring.

The jobs extend the existing APScheduler registry (AD-13). These tests confirm
the farm-discovery helper only surfaces farms with active routines (with their
owner), and that the three job entry points are async callables — the job bodies
themselves reuse services covered by ``test_ops_services``.
"""

import asyncio
from datetime import date, timedelta

import pytest

from app.models.auth import User
from app.schemas import ops_planner as s
from app.services import ops_service, scheduler

pytestmark = pytest.mark.asyncio

MODULE = "poultry"


async def _owner(session, workspace) -> User:
    return await session.get(User, workspace.users["owner"].id)


async def test_farms_with_active_routines_lists_owner(integration_session, workspace):
    user = await _owner(integration_session, workspace)
    fid = workspace.farm.id
    routine = await ops_service.create_routine(
        integration_session, fid, MODULE,
        s.RoutineCreate(module=MODULE, name="Daily feed", category="feeding", frequency="daily",
                        schedule=s.ScheduleInput(frequency="daily",
                                                 start_date=date.today() - timedelta(days=1))),
        user)
    # Draft routine → farm not yet listed.
    before = await scheduler._farms_with_active_routines(integration_session)
    assert all(f.id != fid for f, _ in before)
    # Activate → farm now listed with its owner.
    await ops_service.set_routine_active(integration_session, fid, routine.id, True, user)
    after = await scheduler._farms_with_active_routines(integration_session)
    match = [(f, o) for f, o in after if f.id == fid]
    assert match, "activated farm should be discovered"
    assert match[0][1].id == workspace.users["owner"].id


async def test_ops_jobs_are_async_callables():
    for job in (scheduler.job_ops_materialize_tasks,
                scheduler.job_ops_compliance_scan,
                scheduler.job_ops_optimization_analysis):
        assert asyncio.iscoroutinefunction(job)
