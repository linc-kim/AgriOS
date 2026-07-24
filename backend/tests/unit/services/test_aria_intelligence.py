"""
ARIA farm intelligence — the pure engine.

Because every output is a pure function of a FarmFacts snapshot, the whole
operations-manager brain can be pinned without a database. The tests that carry
the most weight are the two discipline rules: a trend is only given a cause when
a co-recorded factor supports it, and anything ARIA can't measure (biosecurity,
missing records) is reported honestly rather than fabricated.
"""

from datetime import date
from decimal import Decimal

from app.services import aria_intelligence as ai
from app.services.aria_intelligence import FarmFacts, FlockStage, FactorStatus, Priority

TODAY = date(2026, 7, 23)


def healthy_facts(**overrides) -> FarmFacts:
    """A well-run farm; override individual fields per test."""
    base = dict(
        farm_name="Test Farm",
        as_of=TODAY,
        active_flocks=1,
        total_birds=500,
        avg_bird_age_days=140,
        flock_stages=[FlockStage("Layers A", 140)],
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
        days_since_mortality_log=0,
        days_since_weighin=5,
        days_since_egg_log=0,
        days_since_any_log=0,
        disease_score=10,
        disease_level="low",
        vaccinations_overdue=0,
    )
    base.update(overrides)
    return FarmFacts(**base)


class TestHealthScore:
    def test_well_run_farm_scores_high(self):
        h = ai.compute_health_score(healthy_facts())
        assert h.score >= 70
        assert h.grade in ("good", "excellent")
        assert len(h.factors) == 5

    def test_every_factor_explains_itself(self):
        h = ai.compute_health_score(healthy_facts())
        for factor in h.factors:
            assert factor.explanation, f"{factor.key} has no explanation"

    def test_overdue_vaccination_drops_the_score(self):
        h = ai.compute_health_score(healthy_facts(vaccinations_overdue=2))
        vac = next(x for x in h.factors if x.key == "vaccination")
        assert vac.status is not FactorStatus.OK
        assert "overdue" in vac.explanation.lower()

    def test_high_mortality_fails_that_factor(self):
        h = ai.compute_health_score(healthy_facts(mortality_this_week=20, total_birds=500))
        mort = next(x for x in h.factors if x.key == "mortality")
        assert mort.status is FactorStatus.FAIL

    def test_no_records_tanks_record_keeping(self):
        h = ai.compute_health_score(healthy_facts(days_since_any_log=None))
        rk = next(x for x in h.factors if x.key == "record_keeping")
        assert rk.status is FactorStatus.FAIL
        assert rk.score <= 4

    def test_biosecurity_is_labelled_inferred(self):
        """It can't be measured, so it must say so rather than assert a number."""
        h = ai.compute_health_score(healthy_facts())
        bio = next(x for x in h.factors if x.key == "biosecurity")
        assert "infer" in bio.explanation.lower()
        assert bio.max_score == 20
        # Never awarded full marks — good practice can't be confirmed from records.
        assert bio.score < 20


class TestInsights:
    def test_no_feed_logged_is_flagged(self):
        insights = ai.build_insights(healthy_facts(days_since_feed_log=3))
        assert any(i.key == "no_feed_logged" for i in insights)

    def test_rising_mortality_is_flagged_high_priority(self):
        insights = ai.build_insights(healthy_facts(mortality_this_week=6, mortality_prev_week=2))
        m = next(i for i in insights if i.key == "mortality_up")
        assert m.priority is Priority.HIGH

    def test_production_drop_is_flagged(self):
        insights = ai.build_insights(healthy_facts(eggs_this_week=2000, eggs_prev_week=2600))
        assert any(i.key == "production_drop" for i in insights)

    def test_every_insight_has_the_full_structure(self):
        insights = ai.build_insights(
            healthy_facts(days_since_feed_log=3, vaccinations_overdue=1, mortality_this_week=8, mortality_prev_week=2)
        )
        assert insights
        for i in insights:
            assert i.problem and i.reason and i.action and i.benefit
            assert i.confidence in ("high", "medium", "low")
            assert i.sources

    def test_healthy_farm_has_few_or_no_insights(self):
        insights = ai.build_insights(healthy_facts())
        # A well-run farm shouldn't be nagged; weigh-in may be the only nudge.
        assert all(i.priority is not Priority.HIGH for i in insights)


class TestTrends:
    def test_production_rise_gets_a_cause_only_when_supported(self):
        """Up + mortality down + feed steady → a grounded explanation."""
        facts = healthy_facts(
            eggs_this_week=2800, eggs_prev_week=2500,
            mortality_this_week=1, mortality_prev_week=5,
            feed_this_week_kg=Decimal("400"), feed_prev_week_kg=Decimal("398"),
        )
        trends = ai.explain_trends(facts)
        egg = next(t for t in trends if t.metric == "egg_production")
        assert egg.grounded is True
        assert "because" in egg.explanation

    def test_production_rise_without_support_states_no_cause(self):
        """
        Up, but mortality also up and feed swung — nothing supports a cause, so
        ARIA must NOT invent one.
        """
        facts = healthy_facts(
            eggs_this_week=2800, eggs_prev_week=2500,
            mortality_this_week=6, mortality_prev_week=2,
            feed_this_week_kg=Decimal("300"), feed_prev_week_kg=Decimal("450"),
        )
        trends = ai.explain_trends(facts)
        egg = next(t for t in trends if t.metric == "egg_production")
        assert egg.grounded is False
        assert "because" not in egg.explanation.lower()

    def test_unprofitable_high_feed_cost_is_explained(self):
        facts = healthy_facts(is_profitable=False, feed_cost_pct=Decimal("70"))
        trends = ai.explain_trends(facts)
        assert any(t.metric == "profit" and t.grounded for t in trends)


class TestChecklist:
    def test_layers_get_collect_eggs(self):
        items = ai.build_checklist(healthy_facts())
        assert any(i.key == "collect_eggs" for i in items)

    def test_collect_eggs_marked_done_when_already_collected(self):
        items = ai.build_checklist(healthy_facts(eggs_today=380))
        eggs = next(i for i in items if i.key == "collect_eggs")
        assert eggs.done is True

    def test_brooding_flock_gets_brooder_task(self):
        facts = healthy_facts(flock_stages=[FlockStage("Chicks", 10)], hen_day_pct=None)
        items = ai.build_checklist(facts)
        assert any(i.key == "clean_brooder" for i in items)

    def test_overdue_vaccination_adds_vaccinate_task(self):
        items = ai.build_checklist(healthy_facts(vaccinations_overdue=1))
        assert any(i.key == "vaccinate" for i in items)

    def test_high_disease_risk_adds_inspection(self):
        items = ai.build_checklist(healthy_facts(disease_level="high"))
        assert any(i.key == "inspect_health" for i in items)

    def test_every_item_has_a_reason(self):
        items = ai.build_checklist(healthy_facts(disease_level="high", vaccinations_overdue=1))
        for i in items:
            assert i.reason


class TestBriefing:
    def test_briefing_is_built_from_data(self):
        facts = healthy_facts()
        health = ai.compute_health_score(facts)
        insights = ai.build_insights(facts)
        b = ai.build_briefing(facts, health, insights)
        assert b.greeting
        assert b.lines
        assert len(b.priorities) >= 1
        assert b.health_score == health.score

    def test_missing_feed_inventory_is_stated_honestly(self):
        """No fabrication: if feed-days is unknown, say so rather than guess."""
        facts = healthy_facts(feed_days_remaining=None)
        b = ai.build_briefing(facts, ai.compute_health_score(facts), [])
        assert any("feed stock" in n.lower() for n in b.notes)
        assert not any("days remaining" in line.lower() for line in b.lines)

    def test_feed_days_shown_when_known(self):
        facts = healthy_facts(feed_days_remaining=6)
        b = ai.build_briefing(facts, ai.compute_health_score(facts), [])
        assert any("6 days" in line for line in b.lines)

    def test_no_records_adds_honest_note(self):
        facts = healthy_facts(days_since_any_log=None)
        b = ai.build_briefing(facts, ai.compute_health_score(facts), [])
        assert any("no daily records" in n.lower() for n in b.notes)
