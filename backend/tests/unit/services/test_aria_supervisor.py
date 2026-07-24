"""
ARIA supervisor — the pure engine.

A supervisor speaks first, unprompted, so the tests that carry the most weight
are the ones about restraint: unmeasured data must never become an alarm, an
alert must correspond to a threshold that was actually crossed, and the ranking
must be identical for identical input. Those three properties are what make an
always-on watcher trustworthy rather than noisy.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.services import aria_supervisor as sup
from app.services.aria_intelligence import FarmFacts
from app.services.aria_supervisor import MonitorState

TODAY = date(2026, 7, 24)
NOW = datetime(2026, 7, 24, 6, 0, 0)


def facts(**kw) -> FarmFacts:
    """A quiet, well-run farm. Override fields to push a monitor."""
    base = dict(
        farm_name="Test Farm",
        as_of=TODAY,
        active_flocks=1,
        total_birds=490,
        initial_birds=500,
        eggs_today=380,
        eggs_this_week=2600,
        eggs_prev_week=2550,
        hen_day_pct=76.0,
        feed_today_kg=Decimal("58"),
        feed_this_week_kg=Decimal("400"),
        feed_prev_week_kg=Decimal("395"),
        mortality_this_week=1,
        mortality_prev_week=1,
        days_since_feed_log=0,
        days_since_egg_log=0,
        days_since_any_log=0,
        days_since_weighin=3,
        days_since_water_log=0,
        water_today_litres=Decimal("120"),
        water_this_week_litres=Decimal("820"),
        water_prev_week_litres=Decimal("800"),
        inventory_tracked=5,
        disease_level="low",
        disease_score=10,
    )
    base.update(kw)
    return FarmFacts(**base)


class TestMonitorsCoverEverything:
    def test_all_eight_monitors_run(self):
        monitors = sup.run_monitors(facts())
        assert len(monitors) == 8
        assert {m.key for m in monitors} == {
            "mortality", "feed", "water", "production",
            "vaccinations", "population", "inventory", "biosecurity",
        }

    def test_every_monitor_explains_itself(self):
        for m in sup.run_monitors(facts(mortality_this_week=15, vaccinations_overdue=2)):
            assert m.why, f"{m.key} gave no reason"

    def test_quiet_farm_is_normal(self):
        monitors = sup.run_monitors(facts())
        assert sup.overall_state(monitors) is MonitorState.NORMAL


class TestUnmeasuredIsNotAnAlarm:
    """
    The defining restraint. A farm that records nothing is not a farm in crisis,
    and a supervisor that treats silence as an emergency gets muted.
    """

    def test_no_water_data_is_normal_and_flagged_unmeasured(self):
        m = sup.monitor_water(facts(water_this_week_litres=None, water_prev_week_litres=None))
        assert m.state is MonitorState.NORMAL
        assert m.unmeasured is True
        assert sup.NOT_ENOUGH_DATA in m.why

    def test_no_logs_at_all_produces_no_alerts(self):
        blank = FarmFacts(farm_name="New Farm", as_of=TODAY)
        alerts = sup.build_alerts(blank, now=NOW)
        assert alerts == []

    def test_unmeasured_monitors_never_alert(self):
        blank = FarmFacts(farm_name="New Farm", as_of=TODAY)
        for m in sup.run_monitors(blank):
            if m.unmeasured:
                assert m.state is MonitorState.NORMAL

    def test_no_inventory_tracked_is_normal(self):
        m = sup.monitor_inventory(facts(inventory_tracked=0))
        assert m.state is MonitorState.NORMAL
        assert m.unmeasured is True


class TestMortalityMonitor:
    def test_high_rate_is_critical(self):
        m = sup.monitor_mortality(facts(mortality_this_week=12, total_birds=500))
        assert m.state is MonitorState.CRITICAL

    def test_moderate_rate_is_warning(self):
        m = sup.monitor_mortality(facts(mortality_this_week=6, total_birds=500))
        assert m.state is MonitorState.WARNING

    def test_rising_but_low_is_watch(self):
        m = sup.monitor_mortality(facts(mortality_this_week=3, mortality_prev_week=0, total_birds=500))
        assert m.state is MonitorState.WATCH

    def test_evidence_cites_recorded_numbers(self):
        m = sup.monitor_mortality(facts(mortality_this_week=12, total_birds=500))
        assert any("12" in e for e in m.evidence)


class TestWaterMonitor:
    def test_sharp_drop_is_critical(self):
        m = sup.monitor_water(facts(water_this_week_litres=Decimal("500"),
                                    water_prev_week_litres=Decimal("800")))
        assert m.state is MonitorState.CRITICAL

    def test_moderate_drop_is_warning(self):
        m = sup.monitor_water(facts(water_this_week_litres=Decimal("670"),
                                    water_prev_week_litres=Decimal("800")))
        assert m.state is MonitorState.WARNING

    def test_spike_is_watch(self):
        m = sup.monitor_water(facts(water_this_week_litres=Decimal("1100"),
                                    water_prev_week_litres=Decimal("800")))
        assert m.state is MonitorState.WATCH


class TestOtherMonitors:
    def test_feed_out_soon_is_critical(self):
        assert sup.monitor_feed(facts(feed_days_remaining=1)).state is MonitorState.CRITICAL

    def test_production_collapse_is_critical(self):
        m = sup.monitor_production(facts(eggs_this_week=1800, eggs_prev_week=2600))
        assert m.state is MonitorState.CRITICAL

    def test_two_overdue_vaccinations_is_critical(self):
        assert sup.monitor_vaccinations(facts(vaccinations_overdue=2)).state is MonitorState.CRITICAL

    def test_out_of_stock_is_critical(self):
        m = sup.monitor_inventory(facts(inventory_out=["Layers Mash"]))
        assert m.state is MonitorState.CRITICAL

    def test_population_heavy_loss_is_critical(self):
        m = sup.monitor_population(facts(total_birds=400, initial_birds=500))
        assert m.state is MonitorState.CRITICAL

    def test_biosecurity_is_always_labelled_inferred(self):
        m = sup.monitor_biosecurity(facts())
        assert "infer" in m.why.lower()


class TestAlerts:
    def test_alerts_only_for_non_normal_monitors(self):
        f = facts(mortality_this_week=12, total_birds=500)
        monitors = sup.run_monitors(f)
        alerts = sup.build_alerts(f, now=NOW, monitors=monitors)
        non_normal = {m.key for m in monitors if m.state is not MonitorState.NORMAL}
        assert {a.monitor for a in alerts} == non_normal

    def test_every_alert_is_fully_specified(self):
        alerts = sup.build_alerts(facts(mortality_this_week=12, vaccinations_overdue=2), now=NOW)
        assert alerts
        for a in alerts:
            assert a.severity is not MonitorState.NORMAL
            assert a.reason and a.action and a.evidence
            assert a.raised_at == NOW
            assert a.key

    def test_alert_keys_are_stable_across_runs(self):
        """The dedupe identity — the same condition must produce the same key."""
        f = facts(mortality_this_week=12)
        first = {a.key for a in sup.build_alerts(f, now=NOW)}
        later = {a.key for a in sup.build_alerts(f, now=NOW + timedelta(hours=6))}
        assert first == later

    def test_no_duplicate_keys_within_a_run(self):
        alerts = sup.build_alerts(facts(mortality_this_week=12, vaccinations_overdue=2,
                                        inventory_out=["Feed"]), now=NOW)
        keys = [a.key for a in alerts]
        assert len(keys) == len(set(keys))

    def test_most_severe_first(self):
        alerts = sup.build_alerts(facts(mortality_this_week=12, vaccinations_due_week=1), now=NOW)
        ranks = [sup._STATE_RANK[a.severity] for a in alerts]
        assert ranks == sorted(ranks, reverse=True)


class TestPriorityEngine:
    def test_deterministic_for_identical_input(self):
        f = facts(mortality_this_week=12, vaccinations_overdue=1, inventory_low=["Feed"])
        a = [p.key for p in sup.build_priorities(f, now=NOW)]
        b = [p.key for p in sup.build_priorities(f, now=NOW)]
        assert a == b

    def test_alerts_outrank_routine_recording(self):
        f = facts(mortality_this_week=12, days_since_any_log=2)
        items = sup.build_priorities(f, now=NOW)
        alert_rank = next(p.rank for p in items if p.source == "alert")
        routine_rank = next(p.rank for p in items if p.source == "routine")
        assert alert_rank < routine_rank

    def test_ranks_are_sequential_from_one(self):
        items = sup.build_priorities(facts(mortality_this_week=12), now=NOW)
        assert [p.rank for p in items] == list(range(1, len(items) + 1))

    def test_overdue_reminder_outranks_upcoming_one(self):
        f = facts(upcoming_reminders=[
            {"title": "Upcoming task", "due_at": "2026-07-26T06:00:00", "overdue": False},
            {"title": "Late task", "due_at": "2026-07-20T06:00:00", "overdue": True},
        ])
        items = sup.build_priorities(f, now=NOW)
        late = next(p for p in items if "Late task" in p.label)
        upcoming = next(p for p in items if "Upcoming task" in p.label)
        assert late.rank < upcoming.rank

    def test_every_priority_explains_why(self):
        for p in sup.build_priorities(facts(mortality_this_week=12), now=NOW):
            assert p.why


class TestBriefing:
    def _brief(self, f):
        monitors = sup.run_monitors(f)
        priorities = sup.build_priorities(f, now=NOW)
        return sup.build_supervisor_briefing(f, health_score=80, monitors=monitors, priorities=priorities)

    def test_has_every_required_section(self):
        b = self._brief(facts())
        labels = {s.label for s in b.sections}
        assert {"Overall health", "Production", "Mortality", "Feed", "Water",
                "Upcoming reminders", "Vaccinations due"} <= labels

    def test_missing_data_says_not_enough_recorded_data(self):
        b = self._brief(facts(water_this_week_litres=None, days_since_egg_log=None))
        water = next(s for s in b.sections if s.label == "Water")
        assert water.value == sup.NOT_ENOUGH_DATA
        assert water.available is False

    def test_never_invents_a_number_for_missing_data(self):
        b = self._brief(FarmFacts(farm_name="New Farm", as_of=TODAY))
        for s in b.sections:
            if not s.available:
                assert s.value == sup.NOT_ENOUGH_DATA

    def test_suggested_actions_present(self):
        assert self._brief(facts(mortality_this_week=12)).suggested_actions


class TestReports:
    @pytest.mark.parametrize("period", ["today", "7d", "30d"])
    def test_report_builds_for_each_period(self, period):
        r = sup.build_report(facts(), period)
        assert r.period == period
        assert r.sections

    def test_thirty_day_report_declines_to_estimate(self):
        """
        FarmFacts only carries 7-day aggregates. Extrapolating them to 30 days
        would be exactly the fabrication the honesty rules forbid, so the report
        states the limitation instead.
        """
        r = sup.build_report(facts(), "30d")
        production = next(s for s in r.sections if s.label == "Production")
        assert production.value == sup.NOT_ENOUGH_DATA
        assert any("estimat" in n.lower() for n in r.notes)

    def test_missing_finance_is_stated(self):
        r = sup.build_report(facts(is_profitable=None), "7d")
        fin = next(s for s in r.sections if s.label == "Financial summary")
        assert fin.value == sup.NOT_ENOUGH_DATA


class TestReminderProposals:
    def test_proposes_reorder_for_out_of_stock(self):
        props = sup.propose_reminders(facts(inventory_out=["Layers Mash"]))
        assert any("Layers Mash" in p.title for p in props)

    def test_skips_titles_that_already_exist(self):
        """No duplicate reminders — the first line of defence, before the DB."""
        f = facts(inventory_out=["Layers Mash"], reminder_titles=["Reorder Layers Mash"])
        assert not any("Layers Mash" in p.title for p in sup.propose_reminders(f))

    def test_matching_is_case_insensitive(self):
        f = facts(inventory_out=["Layers Mash"], reminder_titles=["reorder layers mash"])
        assert not any("Layers Mash" in p.title for p in sup.propose_reminders(f))

    def test_proposes_weighin_when_stale(self):
        props = sup.propose_reminders(facts(days_since_weighin=20))
        assert any("Weigh" in p.title for p in props)


class TestTimeline:
    def test_orders_newest_first_and_caps(self):
        events = [
            sup.TimelineEvent(at=datetime(2026, 7, 20, 8), kind="feed", title="old"),
            sup.TimelineEvent(at=datetime(2026, 7, 24, 8), kind="feed", title="new"),
            sup.TimelineEvent(at=datetime(2026, 7, 22, 8), kind="feed", title="mid"),
        ]
        out = sup.build_timeline(events, limit=2)
        assert [e.title for e in out] == ["new", "mid"]
