"""
Conversational recording, over HTTP.

This is the acceptance test for Module 13's core claim: a farmer can record farm
data by talking, ARIA asks for what is missing, and nothing is written until they
confirm. It exercises the real endpoint against a real database.

The offline test is the one that matters most architecturally — it asserts that
none of this touches an AI provider.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.flock import DailyLog, ProductionRecord


pytestmark = pytest.mark.asyncio


def _url(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aria/record"


async def _post(client, farm_id, headers, text, state=None):
    body = {"text": text}
    if state is not None:
        body["state"] = state
    r = await client.post(_url(farm_id), json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


class TestRecordingConversation:
    async def test_mortality_asks_then_saves(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        The headline flow. "Three birds died" is incomplete on a multi-flock
        farm; on this single-flock fixture the flock resolves automatically, so
        ARIA moves straight to the clinical probes and then confirmation.
        """
        farm_id = workspace.farm.id

        first = await _post(async_client, farm_id, auth_headers_owner, "three birds died this morning")
        assert first["handled"] is True
        assert first["saved"] is False
        assert first["stage"] in ("collecting", "probing", "confirming")

        state = first["state"]
        # Skip through any probes.
        guard = 0
        while state and first["stage"] in ("probing", "collecting") and guard < 6:
            first = await _post(async_client, farm_id, auth_headers_owner, "skip", state)
            state = first.get("state")
            guard += 1
            if first["stage"] == "confirming":
                break

        assert first["stage"] == "confirming"
        assert "save" in first["reply"].lower()

        confirmed = await _post(async_client, farm_id, auth_headers_owner, "yes", state)
        assert confirmed["saved"] is True
        assert confirmed["module"] == "livestock"

    async def test_nothing_is_written_before_confirmation(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        The safety property. A farmer who starts a record and walks away must
        leave no row behind.

        Checked through the API rather than a session query: the endpoint commits
        on its own connection, so reading through the test's outer transaction
        both misses the write and breaks the savepoint the fixture holds.
        """
        farm_id = workspace.farm.id
        flock_id = workspace.flock.id

        async def mortality_total() -> int:
            r = await async_client.get(
                f"/api/v1/farms/{farm_id}/flocks/{flock_id}/logs",
                headers=auth_headers_owner,
            )
            assert r.status_code == 200, r.text
            rows = r.json()["data"]
            rows = rows.get("items", rows) if isinstance(rows, dict) else rows
            return sum(int(row.get("mortality_count") or 0) for row in rows)

        before = await mortality_total()
        opened = await _post(async_client, farm_id, auth_headers_owner, "four birds died today")
        assert opened["saved"] is False
        assert await mortality_total() == before

    async def test_declining_writes_nothing(
        self, async_client, workspace, auth_headers_owner
    ):
        farm_id = workspace.farm.id
        turn = await _post(async_client, farm_id, auth_headers_owner, "two birds died today")
        state = turn.get("state")

        guard = 0
        while state and turn["stage"] in ("probing", "collecting") and guard < 6:
            turn = await _post(async_client, farm_id, auth_headers_owner, "skip", state)
            state = turn.get("state")
            guard += 1
            if turn["stage"] == "confirming":
                break

        declined = await _post(async_client, farm_id, auth_headers_owner, "no", state)
        assert declined["saved"] is False
        assert declined["stage"] == "cancelled"

    async def test_egg_count_records(self, async_client, workspace, auth_headers_owner):
        farm_id = workspace.farm.id
        turn = await _post(async_client, farm_id, auth_headers_owner, "collected 12 trays today")
        assert turn["handled"] is True
        # Trays are converted, and the assumption is stated.
        assert "360" in turn["reply"]

        confirmed = await _post(async_client, farm_id, auth_headers_owner, "yes", turn["state"])
        assert confirmed["saved"] is True
        assert confirmed["module"] == "production"

    async def test_question_is_not_handled_as_a_record(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        "How many birds died this week?" must fall through to the Q&A path, not
        open a mortality record.
        """
        farm_id = workspace.farm.id
        turn = await _post(
            async_client, farm_id, auth_headers_owner, "how many birds died this week?"
        )
        assert turn["handled"] is False
        assert turn["saved"] is False


class TestReminderCreation:
    async def test_reminder_flows_through_and_saves(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        "Remind me to vaccinate on Tuesday" runs the same parse-confirm-write
        pipeline as a farm record, but lands in the Reminder module.
        """
        farm_id = workspace.farm.id
        turn = await _post(
            async_client, farm_id, auth_headers_owner, "remind me to buy feed tomorrow"
        )
        assert turn["handled"] is True
        assert turn["stage"] == "confirming"

        confirmed = await _post(async_client, farm_id, auth_headers_owner, "yes", turn["state"])
        assert confirmed["saved"] is True
        assert confirmed["module"] == "reminders"

        # It really appears in the reminders list.
        r = await async_client.get(
            f"/api/v1/farms/{farm_id}/automation/reminders", headers=auth_headers_owner
        )
        assert r.status_code == 200, r.text
        rows = r.json()["data"]
        rows = rows.get("items", rows) if isinstance(rows, dict) else rows
        assert any("buy feed" in (row.get("title") or "").lower() for row in rows)


class TestOfflineGuarantee:
    async def test_recording_never_calls_an_ai_provider(
        self, async_client, workspace, auth_headers_owner, monkeypatch
    ):
        """
        Module 13 requires that operational actions work without Gemini or
        Claude. Rather than trust the architecture, blow up if either provider
        is reached during a full record-and-save.
        """
        import app.services.ai_provider as ai_provider

        async def _explode(*args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("recording must not consult an AI provider")

        monkeypatch.setattr(ai_provider, "complete", _explode)

        farm_id = workspace.farm.id
        turn = await _post(async_client, farm_id, auth_headers_owner, "collected 300 eggs today")
        confirmed = await _post(async_client, farm_id, auth_headers_owner, "yes", turn["state"])
        assert confirmed["saved"] is True


class TestPermissions:
    async def test_worker_may_record(self, async_client, workspace, auth_headers_worker):
        """
        Workers do the logging. Making them escalate to record a dead bird is
        how farms end up with no data.
        """
        farm_id = workspace.farm.id
        r = await async_client.post(
            _url(farm_id), json={"text": "two birds died today"}, headers=auth_headers_worker
        )
        assert r.status_code == 200, r.text

    async def test_viewer_may_not_record(self, async_client, workspace, auth_headers_viewer):
        farm_id = workspace.farm.id
        r = await async_client.post(
            _url(farm_id), json={"text": "two birds died today"}, headers=auth_headers_viewer
        )
        assert r.status_code in (401, 403)
