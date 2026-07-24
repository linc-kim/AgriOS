"""
ARIA planner — over HTTP, against a real database.

The pure engine is exhaustively unit-tested; these confirm the endpoints wire
real farm data through it and hold the two guarantees that matter operationally:
a simulation never touches farm data, and the calendar sync never duplicates a
reminder.
"""

import pytest


pytestmark = pytest.mark.asyncio


def _base(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aria"


async def _reminders(client, workspace, headers) -> list[dict]:
    r = await client.get(
        f"/api/v1/farms/{workspace.farm.id}/automation/reminders", headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _logs(client, workspace, headers) -> list[dict]:
    r = await client.get(
        f"/api/v1/farms/{workspace.farm.id}/flocks/{workspace.flock.id}/logs",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    return rows.get("items", rows) if isinstance(rows, dict) else rows


class TestPlanningSnapshot:
    async def test_returns_every_planning_section(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/planning", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert {"feed", "production", "capacity", "budget", "cashflow", "calendar"} <= set(d)

    async def test_read_does_not_create_reminders(
        self, async_client, workspace, auth_headers_owner
    ):
        """Opening the planning dashboard must not write. Only sync_calendar does."""
        before = len(await _reminders(async_client, workspace, auth_headers_owner))
        await async_client.get(f"{_base(workspace.farm.id)}/planning", headers=auth_headers_owner)
        await async_client.get(f"{_base(workspace.farm.id)}/planning", headers=auth_headers_owner)
        assert len(await _reminders(async_client, workspace, auth_headers_owner)) == before

    async def test_every_forecast_states_availability_and_confidence(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/planning", headers=auth_headers_owner)
        for item in r.json()["data"]["production"]:
            assert item["confidence"] in ("high", "medium", "low", "none")
            if not item["available"]:
                assert item["value"] == "Not enough recorded data."


class TestCalendarSyncIsIdempotent:
    async def test_syncing_twice_creates_nothing_the_second_time(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        A plan regenerated every morning must not deposit a fresh copy of every
        task. Duplicate reminders are how a farmer learns to ignore reminders.
        """
        url = f"{_base(workspace.farm.id)}/planning?sync_calendar=true"

        first = await async_client.get(url, headers=auth_headers_owner)
        assert first.status_code == 200, first.text
        after_first = len(await _reminders(async_client, workspace, auth_headers_owner))
        assert after_first > 0, "expected the calendar to create at least one reminder"

        await async_client.get(url, headers=auth_headers_owner)
        await async_client.get(url, headers=auth_headers_owner)
        assert len(await _reminders(async_client, workspace, auth_headers_owner)) == after_first


class TestSimulationsAreReadOnly:
    async def test_simulation_never_modifies_farm_data(
        self, async_client, workspace, auth_headers_owner
    ):
        """
        The safety property, checked end to end: running every scenario leaves
        the flock's records exactly as they were.
        """
        before = await _logs(async_client, workspace, auth_headers_owner)
        before_reminders = len(await _reminders(async_client, workspace, auth_headers_owner))

        for scenario, magnitude in [
            ("add_birds", 500),
            ("mortality_change", 2),
            ("feed_price_change", 10),
            ("production_change", -5),
        ]:
            r = await async_client.post(
                f"{_base(workspace.farm.id)}/simulations",
                json={"scenario": scenario, "magnitude": magnitude},
                headers=auth_headers_owner,
            )
            assert r.status_code == 200, r.text

        assert await _logs(async_client, workspace, auth_headers_owner) == before
        assert len(await _reminders(async_client, workspace, auth_headers_owner)) == before_reminders

    async def test_scenario_returns_current_projected_and_difference(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.post(
            f"{_base(workspace.farm.id)}/simulations",
            json={"scenario": "add_birds", "magnitude": 100},
            headers=auth_headers_owner,
        )
        d = r.json()["data"]
        assert d["available"] is True
        assert d["changes"]
        for c in d["changes"]:
            assert c["current"] and c["projected"] and c["difference"]
        assert d["assumptions"]

    async def test_unknown_scenario_is_refused_not_guessed(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.post(
            f"{_base(workspace.farm.id)}/simulations",
            json={"scenario": "make_me_rich", "magnitude": 100},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["available"] is False


class TestIndividualEndpoints:
    async def test_forecast(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/forecast", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        assert r.json()["data"]

    async def test_capacity(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/capacity", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert "total_capacity" in d and "houses" in d

    @pytest.mark.parametrize("period", ["weekly", "monthly", "cycle"])
    async def test_budget_periods(self, async_client, workspace, auth_headers_owner, period):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/budget?period={period}", headers=auth_headers_owner
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        # With no recorded spend the budget must decline rather than invent lines.
        if not d["available"]:
            assert any("Not enough recorded data." in n for n in d["notes"])
            assert d["lines"] == []

    async def test_budget_rejects_unknown_period(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/budget?period=daily", headers=auth_headers_owner
        )
        assert r.status_code == 422

    async def test_cashflow(self, async_client, workspace, auth_headers_owner):
        r = await async_client.get(f"{_base(workspace.farm.id)}/cashflow", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        assert r.json()["data"]["outlook"] in ("surplus", "shortfall", "unknown")

    async def test_calendar_entries_have_reasons(
        self, async_client, workspace, auth_headers_owner
    ):
        r = await async_client.get(f"{_base(workspace.farm.id)}/calendar", headers=auth_headers_owner)
        assert r.status_code == 200, r.text
        entries = r.json()["data"]
        assert [e["on"] for e in entries] == sorted(e["on"] for e in entries)
        for e in entries:
            assert e["why"]

    @pytest.mark.parametrize("period", ["7d", "30d", "cycle"])
    async def test_planning_report(self, async_client, workspace, auth_headers_owner, period):
        r = await async_client.get(
            f"{_base(workspace.farm.id)}/reports/planning?period={period}",
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["period"] == period
        assert d["risks"]
        assert {"feed", "capacity", "budget", "cashflow", "calendar"} <= set(d)


class TestNoAIProvider:
    async def test_planning_never_calls_an_ai_provider(
        self, async_client, workspace, auth_headers_owner, monkeypatch
    ):
        import app.services.ai_provider as ai_provider

        async def _explode(*a, **k):  # pragma: no cover
            raise AssertionError("planning must not consult an AI provider")

        monkeypatch.setattr(ai_provider, "complete", _explode)

        for path in ("/planning", "/forecast", "/capacity", "/budget",
                     "/cashflow", "/calendar", "/reports/planning"):
            r = await async_client.get(f"{_base(workspace.farm.id)}{path}", headers=auth_headers_owner)
            assert r.status_code == 200, f"{path}: {r.text}"

        r = await async_client.post(
            f"{_base(workspace.farm.id)}/simulations",
            json={"scenario": "add_birds", "magnitude": 50},
            headers=auth_headers_owner,
        )
        assert r.status_code == 200, r.text
