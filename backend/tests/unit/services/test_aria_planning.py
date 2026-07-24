"""
ARIA planner — the pure engine.

Forecasting is where fabrication is easiest to hide: a projection always looks
authoritative. So the tests that carry the most weight are about restraint —
thin history must produce no number at all, confidence must track data
completeness rather than the tidiness of the result, and a budget must never
invent a line for a category nobody has spent on.

The simulator gets its own scrutiny: it must be a pure function of facts, so a
"what if" can never alter the farm it is reasoning about.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from app.services import aria_planning as plan
from app.services.aria_intelligence import FarmFacts, FlockStage
from app.services.aria_planning import Confidence

TODAY = date(2026, 7, 24)


def facts(**kw) -> FarmFacts:
    """A farm with a month of solid records. Override to thin it out."""
    base = dict(
        farm_name="Test Farm",
        as_of=TODAY,
        active_flocks=1,
        total_birds=480,
        initial_birds=500,
        eggs_this_week=2660,
        eggs_prev_week=2600,
        feed_this_week_kg=Decimal("406"),
        feed_prev_week_kg=Decimal("400"),
        water_this_week_litres=Decimal("840"),
        mortality_this_week=4,
        mortality_prev_week=3,
        feed_stock_kg=Decimal("1200"),
        feed_history_days=28,
        egg_history_days=28,
        water_history_days=28,
        mortality_history_days=28,
        days_since_weighin=3,
        days_since_any_log=0,
        houses=[{"name": "House 1", "capacity": 600, "birds": 480,
                 "flock_name": "Layers A", "occupied": True}],
        cycles=[{"name": "Layers A", "placement_date": "2026-03-01", "days_elapsed": 145,
                 "cycle_days": 500, "days_remaining": 355,
                 "expected_close_date": "2027-07-14", "birds": 500}],
        expense_by_category={"Feed": Decimal("60000"), "Vaccines": Decimal("4000")},
        expense_window_days=30,
        revenue=Decimal("90000"),
        feed_cost=Decimal("60000"),
        gross_profit=Decimal("26000"),
        is_profitable=True,
        flock_stages=[FlockStage("Layers A", 145)],
    )
    base.update(kw)
    return FarmFacts(**base)


class TestConfidenceRule:
    """Confidence tracks data completeness only — never the shape of the result."""

    @pytest.mark.parametrize(
        "days,expected",
        [(30, Confidence.HIGH), (14, Confidence.HIGH), (13, Confidence.MEDIUM),
         (7, Confidence.MEDIUM), (6, Confidence.LOW), (3, Confidence.LOW),
         (2, Confidence.NONE), (0, Confidence.NONE)],
    )
    def test_thresholds(self, days, expected):
        assert plan.confidence_from_history(days) is expected


class TestFeedForecast:
    def test_projects_from_recorded_usage(self):
        f = plan.forecast_feed(facts())
        assert f.daily_rate_kg == Decimal("58.000")   # 406 / 7
        assert f.days_remaining == 20                  # 1200 / 58
        assert f.depletion_date == "2026-08-13"
        assert f.confidence is Confidence.HIGH

    def test_horizon_requirements(self):
        f = plan.forecast_feed(facts())
        assert f.required_7d_kg == Decimal("406.00")
        assert f.required_30d_kg == Decimal("1740.00")
        assert f.required_cycle_kg is not None

    def test_states_method_assumptions_and_evidence(self):
        f = plan.forecast_feed(facts())
        assert f.method
        assert f.assumptions
        assert f.evidence

    def test_thin_history_refuses_to_project(self):
        """Two days of records must produce no number at all."""
        f = plan.forecast_feed(facts(feed_history_days=2))
        assert f.daily_rate_kg is None
        assert f.days_remaining is None
        assert f.confidence is Confidence.NONE
        assert any(plan.NOT_ENOUGH_DATA in n for n in f.notes)

    def test_rate_divides_by_recorded_days_not_the_calendar_week(self):
        """
        Dividing 4 days of records by 7 would understate the rate and overstate
        how long the feed lasts — the exact direction that empties a store.
        """
        f = plan.forecast_feed(facts(feed_history_days=4, feed_this_week_kg=Decimal("232")))
        assert f.daily_rate_kg == Decimal("58.000")   # 232 / 4, not / 7

    def test_no_stock_on_record_gives_no_depletion_date(self):
        f = plan.forecast_feed(facts(feed_stock_kg=None))
        assert f.days_remaining is None
        assert f.depletion_date is None
        assert any("inventory" in n.lower() for n in f.notes)
        # But horizon requirements still work — those need no stock figure.
        assert f.required_7d_kg is not None

    def test_no_cycle_on_record_gives_no_cycle_total(self):
        f = plan.forecast_feed(facts(cycles=[]))
        assert f.required_cycle_kg is None
        assert any("cycle" in n.lower() for n in f.notes)


class TestProductionForecast:
    def test_produces_each_metric_for_each_horizon(self):
        out = plan.forecast_production(facts())
        keys = {f.key for f in out}
        for metric in ("eggs", "mortality", "water", "feed"):
            for h in (1, 7, 30):
                assert f"{metric}_{h}d" in keys

    def test_every_forecast_exposes_its_method(self):
        for f in plan.forecast_production(facts()):
            assert f.method
            assert f.evidence

    def test_thin_history_is_unavailable_not_zero(self):
        out = plan.forecast_production(facts(egg_history_days=1))
        eggs = [f for f in out if f.key.startswith("eggs_")]
        assert eggs
        for f in eggs:
            assert f.available is False
            assert f.value == plan.NOT_ENOUGH_DATA

    def test_unrecorded_water_is_unavailable(self):
        out = plan.forecast_production(facts(water_this_week_litres=None, water_history_days=0))
        water = [f for f in out if f.key.startswith("water_")]
        for f in water:
            assert f.available is False


class TestSimulatorPurity:
    def test_simulation_never_mutates_the_facts(self):
        """
        The safety property. A what-if must be a pure function — it computes a
        hypothetical and returns it, and cannot touch the farm it reasons about.
        """
        f = facts()
        before = deepcopy(f)
        for scenario, mag in [("add_birds", 500), ("mortality_change", 2),
                              ("feed_price_change", 10), ("production_change", -5)]:
            plan.simulate(f, scenario, mag)
        assert f == before


class TestScenarios:
    def test_add_birds_projects_feed_and_housing(self):
        r = plan.simulate(facts(), "add_birds", 100)
        assert r.available
        labels = {c.label for c in r.changes}
        assert "Birds" in labels
        assert "Feed per day" in labels
        assert "Housing used" in labels

    def test_add_birds_beyond_capacity_is_called_out(self):
        r = plan.simulate(facts(), "add_birds", 500)   # 480 + 500 > 600 capacity
        assert any("exceed" in i.lower() for i in r.implications)

    def test_mortality_increase_flags_the_critical_line(self):
        r = plan.simulate(facts(), "mortality_change", 3)   # 3% of flock/week
        assert any("critical" in i.lower() or "2%" in i for i in r.implications)

    def test_feed_price_rise_reduces_profit(self):
        r = plan.simulate(facts(), "feed_price_change", 10)
        profit = next(c for c in r.changes if c.label == "Gross profit")
        assert "KES" in profit.projected

    def test_feed_price_without_recorded_cost_is_unavailable(self):
        r = plan.simulate(facts(feed_cost=None), "feed_price_change", 10)
        assert r.available is False
        assert plan.NOT_ENOUGH_DATA in r.note

    def test_production_drop(self):
        r = plan.simulate(facts(), "production_change", -5)
        change = next(c for c in r.changes if c.label == "Eggs per week")
        assert int(change.projected) < int(change.current)

    def test_unknown_scenario_is_refused(self):
        r = plan.simulate(facts(), "make_me_rich", 100)
        assert r.available is False

    def test_zero_magnitude_asks_for_input(self):
        assert plan.simulate(facts(), "add_birds", 0).available is False

    def test_every_available_scenario_states_assumptions(self):
        for scenario, mag in [("add_birds", 100), ("mortality_change", 1),
                              ("feed_price_change", 5), ("production_change", -5)]:
            r = plan.simulate(facts(), scenario, mag)
            assert r.assumptions, scenario


class TestCapacityPlanner:
    def test_computes_utilisation_and_space(self):
        c = plan.plan_capacity(facts())
        assert c.total_capacity == 600
        assert c.total_birds == 480
        assert c.available_space == 120
        assert c.utilisation_pct == 80.0

    def test_overcrowding_is_detected_and_explained(self):
        c = plan.plan_capacity(facts(
            total_birds=590,
            houses=[{"name": "House 1", "capacity": 600, "birds": 590, "occupied": True}],
        ))
        house = c.houses[0]
        assert house.state == "over"
        assert c.recommendations

    def test_unused_capacity_is_detected(self):
        c = plan.plan_capacity(facts(
            total_birds=100,
            houses=[{"name": "House 1", "capacity": 600, "birds": 100, "occupied": True}],
        ))
        assert c.houses[0].state == "under"
        assert any("room for more" in r.lower() for r in c.recommendations)

    def test_no_houses_says_so(self):
        c = plan.plan_capacity(facts(houses=[]))
        assert c.utilisation_pct is None
        assert any(plan.NOT_ENOUGH_DATA in n for n in c.notes)

    def test_house_without_capacity_is_flagged_not_guessed(self):
        c = plan.plan_capacity(facts(
            houses=[{"name": "Shed", "capacity": 0, "birds": 50, "occupied": True}]
        ))
        assert c.houses[0].state == "unknown"
        assert c.notes


class TestBudget:
    def test_scales_recorded_categories_to_the_period(self):
        b = plan.plan_budget(facts(), "weekly")
        assert b.available
        feed = next(l for l in b.lines if l.category == "Feed")
        assert feed.amount == Decimal("14000.00")   # 60000/30*7
        assert b.total == Decimal("14933.33")

    def test_monthly_period(self):
        b = plan.plan_budget(facts(), "monthly")
        assert b.total == Decimal("64000.00")

    def test_only_recorded_categories_appear(self):
        """No invented line for a category nobody has spent on."""
        b = plan.plan_budget(facts())
        assert {l.category for l in b.lines} == {"Feed", "Vaccines"}
        assert any("not yet recorded" in n.lower() or "absent" in n.lower() for n in b.notes)

    def test_no_expenses_means_no_budget(self):
        b = plan.plan_budget(facts(expense_by_category={}))
        assert b.available is False
        assert any(plan.NOT_ENOUGH_DATA in n for n in b.notes)

    def test_every_line_states_its_basis(self):
        for line in plan.plan_budget(facts()).lines:
            assert "recorded over" in line.basis

    def test_cycle_budget_without_cycle_is_refused(self):
        b = plan.plan_budget(facts(cycles=[]), "cycle")
        assert b.available is False


class TestCashFlow:
    def test_projects_both_sides_and_nets_them(self):
        c = plan.project_cashflow(facts(), days=30)
        assert c.expected_expenses == Decimal("64000.00")
        assert c.expected_income == Decimal("90000.00")
        assert c.net == Decimal("26000.00")
        assert c.outlook == "surplus"

    def test_shortfall_detected(self):
        c = plan.project_cashflow(facts(revenue=Decimal("30000")), days=30)
        assert c.outlook == "shortfall"
        assert c.net < 0

    def test_no_revenue_means_unknown_not_zero(self):
        c = plan.project_cashflow(facts(revenue=None), days=30)
        assert c.expected_income is None
        assert c.outlook == "unknown"
        assert any("revenue" in n.lower() for n in c.notes)

    def test_upcoming_costs_are_listed(self):
        c = plan.project_cashflow(facts(vaccinations_overdue=2, inventory_out=["Layers Mash"]))
        assert any("vaccination" in u.lower() for u in c.upcoming)
        assert any("Layers Mash" in u for u in c.upcoming)

    def test_assumptions_always_stated(self):
        assert plan.project_cashflow(facts()).assumptions


class TestCalendar:
    def test_generates_entries_with_reasons(self):
        entries = plan.build_calendar(facts(vaccinations_overdue=1), days=30)
        assert entries
        for e in entries:
            assert e.why
            assert e.kind in ("vaccination", "inspection", "cleaning", "inventory", "recording")

    def test_is_chronological(self):
        entries = plan.build_calendar(facts(), days=30)
        assert [e.on for e in entries] == sorted(e.on for e in entries)

    def test_respects_the_horizon(self):
        entries = plan.build_calendar(facts(), days=3)
        assert all(e.on <= (TODAY.replace(day=27)).isoformat() for e in entries)

    def test_feed_purchase_scheduled_before_depletion(self):
        # 1200kg at 58kg/day ≈ 20 days, so a 30-day window should schedule a buy.
        entries = plan.build_calendar(facts(), days=30)
        assert any("Buy feed" in e.title for e in entries)

    def test_brooding_flock_gets_cleaning(self):
        entries = plan.build_calendar(facts(flock_stages=[FlockStage("Chicks", 10)]), days=30)
        assert any("brooder" in e.title.lower() for e in entries)


class TestPlanningReport:
    @pytest.mark.parametrize("period", ["7d", "30d", "cycle"])
    def test_builds_for_each_period(self, period):
        r = plan.build_planning_report(facts(), period)
        assert r.period == period
        assert r.feed is not None
        assert r.capacity is not None
        assert r.risks

    def test_surfaces_real_risks(self):
        r = plan.build_planning_report(facts(vaccinations_overdue=2), "30d")
        assert any("overdue" in x.lower() for x in r.risks)

    def test_quiet_farm_says_no_risks_rather_than_inventing_one(self):
        quiet = facts(feed_stock_kg=Decimal("100000"), vaccinations_overdue=0,
                      inventory_out=[], revenue=Decimal("500000"))
        r = plan.build_planning_report(quiet, "7d")
        assert any("no planning risks" in x.lower() for x in r.risks)
