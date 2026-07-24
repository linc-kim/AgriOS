"""
ARIA supervisor — over HTTP, against a real database.

The pure engine is exhaustively unit-tested; these confirm the endpoints wire
real farm data through it, that the two write paths are genuinely idempotent
(an unattended process must not duplicate its own alerts), and that none of it
touches an AI provider.
"""

import pytest
from sqlalchemy import func, select  # noqa: F401  (kept for future direct assertions)

from app.models.automation import Reminder
from app.models.platform import Notification


pytestmark = pytest.mark.asyncio


def _base(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aria"


async def _notifications(client, workspace, headers) -> list[dict]:
    """The notification list unwrapped — the endpoint returns {notifications, total, unread_count}."""
    r = await client.get(f"/api/v1/farms/{workspace.farm.id}/notifications", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["notifications"]


async def _notification_count(client, workspace, headers) -> int:
    return len(await _notifications(client, workspace, headers))


class TestSupervisorSnapshot:
    async def test_returns_monitors_alerts_priorities_and_briefing(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/supervisor", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert {"briefing", "overall", "health_score", "monitors", "alerts", "priorities"} <= set(d)

        # All eight monitors, each explaining itself.
        assert len(d["monitors"]) == 8
        for m in d["monitors"]:
            assert m["why"]
            assert m["state"] in ("normal", "watch", "warning", "critical")

    async def test_briefing_marks_missing_data_honestly(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/supervisor", headers=auth_headers_owner)
        sections = r.json()["data"]["briefing"]["sections"]
        # Every section is either available with a value, or explicitly says so.
        for s in sections:
            if not s["available"]:
                assert s["value"] == "Not enough recorded data."

    async def test_priorities_are_ranked_sequentially(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/supervisor", headers=auth_headers_owner)
        ranks = [p["rank"] for p in r.json()["data"]["priorities"]]
        assert ranks == sorted(ranks)
        assert ranks == list(range(1, len(ranks) + 1))

    async def test_read_is_side_effect_free(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        A dashboard refresh must never write. Only sync=true does.

        Counted through the API rather than the test session: the endpoint
        commits on its own connection, so reading through the outer transaction
        both misses the write and breaks the fixture's savepoint.
        """
        before = await _notification_count(async_client, workspace, auth_headers_owner)

        await async_client.get(f"{_base(workspace.farm.id)}/supervisor", headers=auth_headers_owner)
        await async_client.get(f"{_base(workspace.farm.id)}/supervisor", headers=auth_headers_owner)

        assert await _notification_count(async_client, workspace, auth_headers_owner) == before


async def _provoke_mortality_alert(client, workspace, headers) -> None:
    """
    Give the farm a real problem to notice.

    The fixture farm has no daily logs, so every monitor is correctly
    "unmeasured → NORMAL" and the supervisor raises nothing. Without this the
    notification and archive tests pass vacuously against zero rows, proving
    only that nothing happened. Heavy losses on today's log push the mortality
    monitor to CRITICAL through the same endpoint a farmer would use.
    """
    from datetime import date

    r = await client.post(
        f"/api/v1/farms/{workspace.farm.id}/flocks/{workspace.flock.id}/logs",
        json={
            "log_date": date.today().isoformat(),
            "mortality_count": 60,          # ~12% of a 500-bird flock — critical
            "feed_consumed_kg": "55",
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text


class TestAlertsAreActuallyRaised:
    async def test_real_condition_produces_alert_and_notification(
        self, async_client, workspace, auth_headers_owner
    ):
        """The alert → notification path, exercised against a genuine breach."""
        await _provoke_mortality_alert(async_client, workspace, auth_headers_owner)

        r = await async_client.get(
            f"{_base(workspace.farm.id)}/supervisor?sync=true", headers=auth_headers_owner
        )
        assert r.status_code == 200, r.text
        alerts = r.json()["data"]["alerts"]
        assert any(a["monitor"] == "mortality" for a in alerts), alerts

        mortality = next(a for a in alerts if a["monitor"] == "mortality")
        assert mortality["severity"] == "critical"
        assert mortality["evidence"]
        assert mortality["action"]

        # It reached the notification centre with a severity-mapped priority.
        rows = await _notifications(async_client, workspace, auth_headers_owner)
        assert any("Mortality" in n["title"] for n in rows), rows

    async def test_alert_notification_is_not_duplicated(
        self, async_client, workspace, auth_headers_owner
    ):
        await _provoke_mortality_alert(async_client, workspace, auth_headers_owner)

        url = f"{_base(workspace.farm.id)}/supervisor?sync=true"
        await async_client.get(url, headers=auth_headers_owner)
        after_first = await _notification_count(async_client, workspace, auth_headers_owner)
        assert after_first > 0, "expected the breach to raise a notification"

        await async_client.get(url, headers=auth_headers_owner)
        await async_client.get(url, headers=auth_headers_owner)
        assert await _notification_count(async_client, workspace, auth_headers_owner) == after_first


class TestIdempotentSync:
    async def test_running_sync_twice_creates_nothing_the_second_time(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        The defining property of an unattended supervisor. Whatever the first
        pass writes, the second must recognise and skip — otherwise a farmer
        wakes to the same alert twenty times.
        """
        url = f"{_base(workspace.farm.id)}/supervisor?sync=true"

        first = await async_client.get(url, headers=auth_headers_owner)
        assert first.status_code == 200, first.text

        counts = await self._counts(async_client, workspace, auth_headers_owner)

        second = await async_client.get(url, headers=auth_headers_owner)
        assert second.status_code == 200, second.text

        assert await self._counts(async_client, workspace, auth_headers_owner) == counts

    async def _counts(self, client, workspace, headers) -> tuple[int, int]:
        notifications = await _notifications(client, workspace, headers)
        rem = await client.get(
            f"/api/v1/farms/{workspace.farm.id}/automation/reminders", headers=headers
        )
        reminders = rem.json()["data"]
        return len(notifications), len(reminders)


class TestAlertsAndPriorities:
    async def test_alerts_endpoint(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/alerts", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        for a in r.json()["data"]:
            # An alert is a crossed threshold — never a NORMAL monitor.
            assert a["severity"] in ("watch", "warning", "critical")
            assert a["reason"] and a["action"] and a["evidence"]

    async def test_priorities_endpoint(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/priorities", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        for p in r.json()["data"]:
            assert p["why"]
            assert p["source"] in ("alert", "vaccination", "reminder", "routine")


class TestTimelineAndReports:
    async def test_timeline_returns_recorded_events(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/timeline", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        events = r.json()["data"]
        # Newest first.
        stamps = [e["at"] for e in events]
        assert stamps == sorted(stamps, reverse=True)
        for e in events:
            assert e["kind"] in ("vaccination", "production", "feed", "mortality", "reminder", "weighin")

    @pytest.mark.parametrize("period", ["today", "7d", "30d"])
    async def test_report_for_each_period(
        self, async_client, workspace, auth_headers_owner, period
    ):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/reports?period={period}", headers=auth_headers_owner
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["period"] == period
        assert d["sections"]

    async def test_thirty_day_report_declines_to_estimate(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/reports?period=30d", headers=auth_headers_owner
        )
        d = r.json()["data"]
        production = next(s for s in d["sections"] if s["label"] == "Production")
        assert production["available"] is False
        assert production["value"] == "Not enough recorded data."
        assert d["notes"]

    async def test_invalid_period_rejected(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/reports?period=90d", headers=auth_headers_owner
        )
        assert r.status_code == 422


class TestNotificationArchive:
    async def test_archive_and_restore(self, async_client, workspace, auth_headers_owner):
        # Make sure at least one supervisor notification exists.
        # Provoke a real alert so there is genuinely something to archive —
        # skipping here would leave the endpoint untested.
        await _provoke_mortality_alert(async_client, workspace, auth_headers_owner)
        await async_client.get(f"{_base(workspace.farm.id)}/supervisor?sync=true", headers=auth_headers_owner)
        rows = await _notifications(async_client, workspace, auth_headers_owner)
        assert rows, "expected the provoked breach to produce a notification"

        nid = rows[0]["id"]
        arch = await async_client.patch(
            f"/api/v1/farms/{workspace.farm.id}/notifications/{nid}/archive?archived=true",
            headers=auth_headers_owner,
        )
        assert arch.status_code == 200, arch.text
        assert arch.json()["data"]["is_archived"] is True

        restored = await async_client.patch(
            f"/api/v1/farms/{workspace.farm.id}/notifications/{nid}/archive?archived=false",
            headers=auth_headers_owner,
        )
        assert restored.json()["data"]["is_archived"] is False


class TestNoAIProvider:
    async def test_supervision_never_calls_an_ai_provider(
        self, async_client, workspace, auth_headers_owner, monkeypatch
    ):
        import app.services.ai_provider as ai_provider

        async def _explode(*a, **k):  # pragma: no cover
            raise AssertionError("supervision must not consult an AI provider")

        monkeypatch.setattr(ai_provider, "complete", _explode)

        for path in ("/supervisor", "/alerts", "/priorities", "/timeline", "/reports"):
            r = await async_client.get(f"{_base(workspace.farm.id)}{path}", headers=auth_headers_owner)
            assert r.status_code == 200, f"{path}: {r.text}"
