"""
Mission Control — the pure strategic engine.

Mission Control turns a vision into a plan by orchestrating the existing engines,
so the tests that matter most are about the honesty contract: every figure is
labelled (recorded / forecast / recommendation), progress is measured from an
honest baseline and explained, projections are never promises, and a qualitative
mission with no number still produces a coherent phased plan. Determinism is the
other pillar — the same mission and facts always yield the same roadmap.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services import mission_control as mc
from app.services.aria_intelligence import FarmFacts

TODAY = date(2026, 10, 25)
CREATED = date(2026, 7, 25)
TARGET = date(2027, 7, 25)


def facts(**kw) -> FarmFacts:
    base = dict(
        farm_name="Demo", as_of=TODAY, active_flocks=1, total_birds=3200, initial_birds=3500,
        eggs_today=2600, eggs_this_week=18000, eggs_prev_week=17500,
        feed_this_week_kg=Decimal("2400"), mortality_this_week=20, mortality_prev_week=18,
        days_since_feed_log=0, days_since_egg_log=0, days_since_any_log=0, days_since_water_log=0,
        water_this_week_litres=Decimal("5000"), inventory_tracked=5, disease_level="low", disease_score=10,
        revenue=Decimal("540000"), expenses=Decimal("410000"), gross_profit=Decimal("130000"),
        is_profitable=True, feed_days_remaining=20,
        houses=[{"name": "H1", "capacity": 1000, "birds": 1000}, {"name": "H2", "capacity": 1000, "birds": 1000}],
    )
    base.update(kw)
    return FarmFacts(**base)


def mission(**kw) -> mc.MissionSpec:
    base = dict(
        name="Reach 10,000 Layers", description="Scale up", target_date=TARGET,
        metrics=[mc.Metric("birds", "Layers", 10000, "birds", primary=True)],
        constraints=["No loans"], priorities=["Low mortality"],
        assumptions=[{"key": "take_loans", "value": "false"}, {"key": "risk_tolerance", "value": "low"}],
        policies=[{"key": "max_mortality", "statement": "Maximum mortality target: 3%", "category": "risk", "value": 3}],
        baseline={"birds": 500}, created_on=CREATED, status="active",
    )
    base.update(kw)
    return mc.MissionSpec(**base)


# ── Discovery ─────────────────────────────────────────────────────────────────


class TestDiscovery:
    def test_questions_are_fixed_and_keyed(self):
        qs = mc.discovery_questions()
        assert len(qs) >= 8
        keys = {q.key for q in qs}
        assert {"current_birds", "capital_available", "take_loans", "risk_tolerance"} <= keys

    def test_answers_become_editable_assumptions(self):
        a = mc.assumptions_from_answers({"take_loans": False, "capital_available": 200000})
        assert all(x["source"] == "interview" for x in a)
        assert any(x["key"] == "capital_available" for x in a)


# ── Roadmap ───────────────────────────────────────────────────────────────────


class TestRoadmap:
    def test_phases_from_baseline_to_target(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY, phases=3)
        names = [p.name for p in rm.phases]
        assert names[0] == "Current state" and names[-1] == "Mission achieved"
        assert rm.baseline_value == 500 and rm.target_value == 10000
        # Phase bird targets increase monotonically.
        targets = [p.bird_target for p in rm.phases if p.index in (1, 2, 3)]
        assert targets == sorted(targets)

    def test_infrastructure_derived_from_capacity(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        p3 = next(p for p in rm.phases if p.index == 3)
        assert any("additional house" in s for s in p3.infrastructure)

    def test_every_phase_has_completion_criteria_and_risks(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        for p in rm.phases:
            if p.index >= 1 and p.name != "Mission achieved":
                assert p.completion_criteria
                assert p.risks

    def test_qualitative_mission_still_phases(self):
        m = mission(metrics=[mc.Metric("qualitative", "Become fully organic", None, primary=True)], baseline={})
        rm = mc.build_roadmap(m, facts(), today=TODAY)
        assert rm.metric_kind == "qualitative"
        assert len([p for p in rm.phases if p.index >= 1]) >= 3

    def test_deterministic(self):
        a = mc.build_roadmap(mission(), facts(), today=TODAY)
        b = mc.build_roadmap(mission(), facts(), today=TODAY)
        assert [p.bird_target for p in a.phases] == [p.bird_target for p in b.phases]


# ── Progress ──────────────────────────────────────────────────────────────────


class TestProgress:
    def test_completion_from_honest_baseline(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        p = mc.build_progress(mission(), facts(), rm, today=TODAY)
        # (3200 - 500) / (10000 - 500) = 28.4%
        assert 28 <= p.completion_pct <= 29
        assert "started at 500" in p.completion_explanation

    def test_forecast_completion_is_labelled_forecast(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        p = mc.build_progress(mission(), facts(), rm, today=TODAY)
        assert p.forecasted_completion.fact_type is mc.FactType.FORECAST

    def test_no_baseline_data_is_honest(self):
        m = mission(metrics=[mc.Metric("profit", "Annual profit", 2_000_000, "KES", primary=True)],
                    baseline={})
        f = facts(is_profitable=None, gross_profit=None, revenue=None)
        rm = mc.build_roadmap(m, f, today=TODAY)
        p = mc.build_progress(m, f, rm, today=TODAY)
        assert p.completion_pct == 0.0

    def test_time_elapsed_computed(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        p = mc.build_progress(mission(), facts(), rm, today=TODAY)
        assert p.time_elapsed_pct is not None
        assert p.time_remaining_days is not None


# ── Daily mission ─────────────────────────────────────────────────────────────


class TestDaily:
    def test_daily_links_tasks_to_phase(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        prog = mc.build_progress(mission(), facts(), rm, today=TODAY)
        d = mc.daily_mission(mission(), facts(), rm, prog, today=TODAY)
        assert d.headline
        assert d.critical_tasks
        assert all(t.fact_type for t in d.critical_tasks)
        assert d.kpis and any("progress" in k.label.lower() for k in d.kpis)


# ── Adaptation ────────────────────────────────────────────────────────────────


class TestAdaptation:
    def test_on_track_needs_no_revision(self):
        a = mc.evaluate_adaptation(mission(), facts(), today=TODAY)
        assert a.needed is False

    def test_mortality_over_policy_triggers(self):
        # 200/3200 = 6.25%/wk, over the 3% policy.
        a = mc.evaluate_adaptation(mission(), facts(mortality_this_week=200), today=TODAY)
        assert a.needed is True
        assert any("mortality" in r.lower() for r in a.reasons)

    def test_production_drop_triggers(self):
        # Egg production down 43% week on week (10000 vs 17500) — over the 15% line.
        a = mc.evaluate_adaptation(mission(), facts(eggs_this_week=10000, eggs_prev_week=17500), today=TODAY)
        assert a.needed is True
        assert any("production" in r.lower() for r in a.reasons)

    def test_behind_schedule_triggers(self):
        # Almost all time elapsed but little progress → behind schedule.
        m = mission(target_date=date(2026, 11, 1))  # ~1 week left, created 3 months ago
        a = mc.evaluate_adaptation(m, facts(total_birds=600), today=TODAY)
        assert a.needed is True


# ── Health, plan, manual, reports, dashboard ──────────────────────────────────


class TestComposites:
    def test_mission_health_scored_and_explained(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        prog = mc.build_progress(mission(), facts(), rm, today=TODAY)
        h = mc.mission_health(mission(), facts(), prog)
        assert 0 <= h.score <= 100
        assert h.grade in ("excellent", "good", "fair", "poor")
        assert all(f.explanation for f in h.factors)
        assert sum(f.max_score for f in h.factors) == 100

    def test_business_plan_sections_labelled(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        plan = mc.build_business_plan(mission(), facts(), rm, today=TODAY)
        headings = {s.heading for s in plan.sections}
        assert {"Executive summary", "Current position", "Financial strategy", "Risk register"} <= headings
        # Current position is recorded facts.
        cur = next(s for s in plan.sections if s.heading == "Current position")
        assert all(v.fact_type is mc.FactType.RECORDED for v in cur.body)

    def test_manual_has_required_sections(self):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        man = mc.build_manual(mission(), facts(), rm, today=TODAY)
        headings = {s.heading for s in man.sections}
        for needed in ("Daily routine", "Emergency procedures", "Hiring checklist", "Supplier checklist"):
            assert needed in headings
        emerg = next(s for s in man.sections if s.heading == "Emergency procedures")
        assert any("vet" in i.lower() and "not diagnose" in i.lower() for i in emerg.items)

    @pytest.mark.parametrize("period", ["weekly", "monthly", "quarterly", "annual"])
    def test_reports(self, period):
        rm = mc.build_roadmap(mission(), facts(), today=TODAY)
        prog = mc.build_progress(mission(), facts(), rm, today=TODAY)
        r = mc.build_report(mission(), facts(), rm, prog, period=period, today=TODAY)
        assert r.period == period
        assert r.health.score >= 0
        assert r.recommended_actions

    def test_dashboard_bundle(self):
        d = mc.build_dashboard(mission(), facts(), today=TODAY)
        assert d.completion_pct > 0
        assert d.current_phase
        assert d.daily.headline
        assert d.health.score >= 0


# ── Honesty labels ────────────────────────────────────────────────────────────


class TestHonesty:
    def test_recorded_helper_labels_recorded(self):
        assert mc.recorded("x", 5).fact_type is mc.FactType.RECORDED

    def test_forecast_helper_labels_forecast(self):
        assert mc.forecast("x", 5).fact_type is mc.FactType.FORECAST

    def test_unknown_stays_unknown(self):
        v = mc.recorded("Net", None, "KES")
        assert v.value is None and v.available is False
