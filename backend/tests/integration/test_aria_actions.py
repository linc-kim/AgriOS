"""
ARIA write path — against a real database.

The unit tests prove ARIA parses a sentence and asks the right questions. These
prove the last step: that a confirmed payload lands as a correct row, through
the same domain services the forms use, with an audit trail.

The cases that matter most are the additive one (two mortality reports in a day
must sum, not overwrite) and the refusals (no flock, no write).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.flock import DailyLog, ProductionRecord, WeighinRecord
from app.models.health import VaccinationRecord
from app.models.platform import AuditLog
from app.services import aria_actions
from app.services.aria_nlu import Intent


pytestmark = pytest.mark.asyncio


async def _farm(session, farm_id):
    from app.models.farm import Farm
    return (await session.execute(select(Farm).where(Farm.id == str(farm_id)))).scalar_one()


async def _user(session, user_id):
    from app.models.auth import User
    return (await session.execute(select(User).where(User.id == str(user_id)))).scalar_one()


class TestFlockResolution:
    async def test_single_active_flock_resolves_without_a_reference(
        self, integration_session, workspace
    ):
        """
        Asking "which flock?" of a farmer with one flock is pure friction, and
        there is nothing to be ambiguous about.
        """
        match, candidates = await aria_actions.resolve_flock(
            integration_session, workspace.farm.id, None
        )
        assert match is not None
        assert match.id == workspace.flock.id
        assert len(candidates) == 1

    async def test_resolves_by_name_fragment(self, integration_session, workspace):
        flocks = await aria_actions.list_active_flocks(
            integration_session, workspace.farm.id
        )
        token = flocks[0].label.split()[0]
        match, _ = await aria_actions.resolve_flock(
            integration_session, workspace.farm.id, token
        )
        assert match is not None
        assert match.id == workspace.flock.id

    async def test_unknown_reference_does_not_resolve(self, integration_session, workspace):
        """A name that matches nothing is a question, never a fallback."""
        match, candidates = await aria_actions.resolve_flock(
            integration_session, workspace.farm.id, "zzz-nonexistent"
        )
        assert match is None
        assert candidates  # the caller can offer these as options


class TestMortalityWrite:
    async def test_records_mortality_on_the_daily_log(
        self, integration_session, workspace
    ):
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=3)

        result = await aria_actions.execute(
            integration_session,
            farm,
            user,
            {
                "intent": Intent.RECORD_MORTALITY.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "count": 3,
                    "date": when.isoformat(),
                },
            },
        )

        assert result.ok, result.error
        assert result.module == "livestock"

        log = (
            await integration_session.execute(
                select(DailyLog).where(
                    DailyLog.flock_id == str(workspace.flock.id),
                    DailyLog.log_date == when,
                )
            )
        ).scalar_one()
        assert log.mortality_count == 3

    async def test_second_report_same_day_adds_rather_than_replaces(
        self, integration_session, workspace
    ):
        """
        Two birds in the morning and one in the afternoon is three that day.
        The daily log upserts on (flock, date), so a naive write would discard
        the earlier report and quietly understate mortality.
        """
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=4)

        base = {
            "intent": Intent.RECORD_MORTALITY.value,
            "slots": {"flock_id": str(workspace.flock.id), "date": when.isoformat()},
        }
        first = {**base, "slots": {**base["slots"], "count": 2}}
        second = {**base, "slots": {**base["slots"], "count": 1}}

        assert (await aria_actions.execute(integration_session, farm, user, first)).ok
        assert (await aria_actions.execute(integration_session, farm, user, second)).ok

        log = (
            await integration_session.execute(
                select(DailyLog).where(
                    DailyLog.flock_id == str(workspace.flock.id),
                    DailyLog.log_date == when,
                )
            )
        ).scalar_one()
        assert log.mortality_count == 3

    async def test_clinical_probe_answers_are_stored(
        self, integration_session, workspace
    ):
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=5)

        result = await aria_actions.execute(
            integration_session,
            farm,
            user,
            {
                "intent": Intent.RECORD_MORTALITY.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "count": 1,
                    "date": when.isoformat(),
                    "symptoms": "coughing and swollen eyes",
                    "others_affected": "two more look unwell",
                },
            },
        )
        assert result.ok, result.error

        log = (
            await integration_session.execute(
                select(DailyLog).where(
                    DailyLog.flock_id == str(workspace.flock.id),
                    DailyLog.log_date == when,
                )
            )
        ).scalar_one()
        assert "coughing" in (log.notes or "")

    async def test_missing_flock_is_refused_not_guessed(
        self, integration_session, workspace
    ):
        """
        The guarantee, at the write boundary. Even if the dialogue were bypassed,
        no flock means no row.
        """
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)

        result = await aria_actions.execute(
            integration_session,
            farm,
            user,
            {"intent": Intent.RECORD_MORTALITY.value, "slots": {"count": 3}},
        )
        assert not result.ok
        assert result.error is not None


class TestOtherWrites:
    async def test_egg_production(self, integration_session, workspace):
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=6)

        result = await aria_actions.execute(
            integration_session, farm, user,
            {
                "intent": Intent.RECORD_EGGS.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "count": 360,
                    "broken": 5,
                    "date": when.isoformat(),
                },
            },
        )
        assert result.ok, result.error

        record = (
            await integration_session.execute(
                select(ProductionRecord).where(
                    ProductionRecord.flock_id == str(workspace.flock.id),
                    ProductionRecord.record_date == when,
                )
            )
        ).scalar_one()
        assert record.eggs_collected == 360
        assert record.broken_eggs == 5

    async def test_vaccination(self, integration_session, workspace):
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=2)

        result = await aria_actions.execute(
            integration_session, farm, user,
            {
                "intent": Intent.RECORD_VACCINATION.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "vaccine_name": "Newcastle Disease (ND)",
                    "date": when.isoformat(),
                },
            },
        )
        assert result.ok, result.error

        record = (
            await integration_session.execute(
                select(VaccinationRecord).where(
                    VaccinationRecord.flock_id == str(workspace.flock.id),
                    VaccinationRecord.administered_date == when,
                )
            )
        ).scalars().first()
        assert record is not None
        assert "Newcastle" in record.vaccine_name

    async def test_weigh_in(self, integration_session, workspace):
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=7)

        result = await aria_actions.execute(
            integration_session, farm, user,
            {
                "intent": Intent.RECORD_WEIGHT.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "sample_size": 20,
                    "average_weight_kg": "1.8",
                    "date": when.isoformat(),
                },
            },
        )
        assert result.ok, result.error

        record = (
            await integration_session.execute(
                select(WeighinRecord).where(
                    WeighinRecord.flock_id == str(workspace.flock.id),
                    WeighinRecord.weighed_at == when,
                )
            )
        ).scalars().first()
        assert record is not None
        assert record.average_weight_kg == Decimal("1.8")


class TestAudit:
    async def test_conversational_writes_are_audited(
        self, integration_session, workspace
    ):
        """
        A conversational write has no form submission to point at later, so the
        audit entry is the only provenance. It records that ARIA was the route.
        """
        farm = await _farm(integration_session, workspace.farm.id)
        user = await _user(integration_session, workspace.users["owner"].id)
        when = date.today() - timedelta(days=8)

        result = await aria_actions.execute(
            integration_session, farm, user,
            {
                "intent": Intent.RECORD_MORTALITY.value,
                "slots": {
                    "flock_id": str(workspace.flock.id),
                    "count": 1,
                    "date": when.isoformat(),
                },
            },
        )
        assert result.ok, result.error

        entries = (
            await integration_session.execute(
                select(AuditLog).where(
                    AuditLog.farm_id == str(farm.id),
                    AuditLog.resource_type == "daily_log",
                )
            )
        ).scalars().all()
        assert any(
            (e.new_value or {}).get("via") == "aria_conversation" for e in entries
        )
