"""
Aviculture Intelligence — the Mission Control strategic engine (Module 15, Part 11).

Mission Control orchestrates; this pure engine derives the insights. These tests
lock the frozen guarantees that need no database or model: risks/overdue/breeding/
incubation/finance/population signals are raised only from recorded evidence,
every insight cites its source figure with that figure's honesty label, insights
are ranked most-serious first, and nothing is fabricated when data is missing.
"""

from app.services import aviculture_intelligence as ai


def _lbl(label, value, detail=""):
    return {"label": label, "value": value, "detail": detail}


def _dashboard(**over):
    d = {
        "collection": {"total": _lbl("recorded", 12), "by_species": {"African Grey": 12},
                       "by_status": {}, "by_sex": {}, "by_lifecycle_stage": {}},
        "infrastructure": {"total_occupied": 10},
        "breeding": {"active_pairs": 2, "active_programs": 1},
        "incubation": {"active_batches": 1, "statistics": {
            "eggs_set": _lbl("recorded", 10), "fertility_rate_pct": _lbl("calculated", 80.0),
            "hatch_rate_pct": _lbl("calculated", 70.0), "failed": _lbl("recorded", 1)}},
        "health": {
            "active_birds": _lbl("recorded", 12),
            "mortality_rate_pct": _lbl("calculated", 2.0),
            "vaccination_coverage_pct": _lbl("calculated", 90.0),
            "active_quarantines": _lbl("recorded", 0),
            "active_disease_events": _lbl("recorded", 0),
            "preventive_due": {"due_count": _lbl("calculated", 0), "overdue_count": _lbl("calculated", 0)},
        },
        "finance": {"sale_income": _lbl("recorded", 5000), "net": _lbl("calculated", 1500.0),
                    "collection_value": _lbl("recorded", 120000.0)},
    }
    d.update(over)
    return d


def _forecast(net=0.5, projected=15, current=12, confidence="medium"):
    return {"current": _lbl("recorded", current), "net_daily_change": _lbl("calculated", net),
            "forecast": _lbl("forecast", projected), "confidence": confidence, "horizon_days": 90}


class TestHealthyCollection:
    def test_no_risks_when_all_clean(self):
        b = ai.build_briefing(dashboard=_dashboard(), forecast=_forecast(), due_items=[], workflows=[])
        assert b.counts[ai.CRITICAL] == 0 and b.counts[ai.WARNING] == 0
        assert "healthy" in b.headline.lower() or "stable" in b.headline.lower()
        # Priorities never empty — a healthy collection still gets a steady-state line.
        assert b.priorities and "No elevated" in b.priorities[0]


class TestRiskDetection:
    def test_active_disease_is_critical_with_evidence(self):
        d = _dashboard()
        d["health"]["active_disease_events"] = _lbl("recorded", 2)
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        crit = [i for i in b.insights if i.severity == ai.CRITICAL]
        assert crit and crit[0].category == "risk"
        ev = crit[0].evidence[0]
        assert ev.source == "health.active_disease_events" and ev.value == "2" and ev.fact_type == "recorded"
        # ARIA never diagnoses — the detail must say so.
        assert "does not diagnose" in crit[0].detail

    def test_high_mortality_is_warning(self):
        d = _dashboard()
        d["health"]["mortality_rate_pct"] = _lbl("calculated", 18.0)
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        assert any(i.title.startswith("Mortality") and i.severity == ai.WARNING for i in b.insights)

    def test_insights_ranked_most_serious_first(self):
        d = _dashboard()
        d["health"]["active_disease_events"] = _lbl("recorded", 1)  # critical
        d["health"]["vaccination_coverage_pct"] = _lbl("calculated", 30.0)  # watch
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        severities = [ai._SEVERITY_RANK[i.severity] for i in b.insights]
        assert severities == sorted(severities)


class TestOverdueWork:
    def test_urgent_due_items_surface(self):
        due = [{"kind": "health_due", "title": "Vaccination due: AG-001", "priority": "critical",
                "reason": "overdue", "suggested_due_on": "2026-07-20", "dedup_key": "k1"}]
        b = ai.build_briefing(dashboard=_dashboard(), forecast=_forecast(), due_items=due, workflows=[])
        ow = [i for i in b.insights if i.category == "overdue_work"]
        assert ow and ow[0].severity == ai.CRITICAL
        assert b.summaries["automation"]["by_priority"]["critical"] == 1


class TestBreedingAndIncubation:
    def test_pairs_without_programme_is_watch(self):
        d = _dashboard()
        d["breeding"] = {"active_pairs": 3, "active_programs": 0}
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        assert any(i.category == "breeding" and i.severity == ai.WATCH for i in b.insights)

    def test_low_hatch_rate_flagged_only_with_enough_eggs(self):
        d = _dashboard()
        d["incubation"]["statistics"]["hatch_rate_pct"] = _lbl("calculated", 20.0)
        d["incubation"]["statistics"]["eggs_set"] = _lbl("recorded", 10)
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        assert any(i.category == "incubation" and i.title.startswith("Hatch rate") for i in b.insights)

    def test_low_hatch_rate_not_flagged_on_tiny_sample(self):
        d = _dashboard()
        d["incubation"]["statistics"]["hatch_rate_pct"] = _lbl("calculated", 20.0)
        d["incubation"]["statistics"]["eggs_set"] = _lbl("recorded", 2)
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        assert not any(i.title.startswith("Hatch rate") for i in b.insights)


class TestFinanceAndPopulation:
    def test_recorded_loss_is_warning(self):
        d = _dashboard()
        d["finance"]["net"] = _lbl("calculated", -800.0)
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        assert any(i.category == "finance" and "loss" in i.title.lower() for i in b.insights)

    def test_missing_valuation_is_unknown_not_fabricated(self):
        d = _dashboard()
        d["finance"]["collection_value"] = None
        b = ai.build_briefing(dashboard=d, forecast=_forecast(), due_items=[], workflows=[])
        fin = [i for i in b.insights if i.category == "finance" and "valuation" in i.title.lower()]
        assert fin and fin[0].evidence[0].fact_type == "unknown" and fin[0].evidence[0].value is None

    def test_declining_population_is_a_forecast_not_a_promise(self):
        b = ai.build_briefing(dashboard=_dashboard(), forecast=_forecast(net=-0.3, projected=5, current=12),
                              due_items=[], workflows=[])
        pop = [i for i in b.insights if i.category == "population"]
        assert pop and "not a promise" in pop[0].detail
        assert any(e.fact_type == "forecast" for e in pop[0].evidence)


class TestHonestyCompleteness:
    """Doc 15 §15 — every recommendation explains evidence, reasoning, confidence, limitations."""

    def _all_insights(self):
        # A dashboard that trips every category at once.
        d = _dashboard()
        d["health"]["active_disease_events"] = _lbl("recorded", 1)
        d["health"]["active_quarantines"] = _lbl("recorded", 1)
        d["health"]["mortality_rate_pct"] = _lbl("calculated", 20.0)
        d["health"]["vaccination_coverage_pct"] = _lbl("calculated", 10.0)
        d["breeding"] = {"active_pairs": 2, "active_programs": 0}
        d["incubation"]["statistics"]["hatch_rate_pct"] = _lbl("calculated", 15.0)
        d["incubation"]["statistics"]["fertility_rate_pct"] = _lbl("calculated", 20.0)
        d["finance"]["net"] = _lbl("calculated", -500.0)
        d["finance"]["collection_value"] = None
        due = [{"kind": "health_due", "title": "Vax due", "priority": "critical",
                "reason": "overdue", "suggested_due_on": "2026-07-20", "dedup_key": "k"}]
        return ai.build_briefing(dashboard=d, forecast=_forecast(net=-0.5, projected=4, current=12, confidence="high"),
                                 due_items=due, workflows=[]).insights

    def test_every_insight_has_evidence_reasoning_confidence_limitations(self):
        insights = self._all_insights()
        assert len(insights) >= 6
        for i in insights:
            assert i.evidence, f"{i.title}: missing evidence"
            assert i.detail.strip(), f"{i.title}: missing reasoning"
            assert i.confidence in ("high", "medium", "low"), f"{i.title}: bad confidence"
            assert i.limitations.strip(), f"{i.title}: missing limitations"

    def test_forecast_insight_carries_forecast_confidence(self):
        pop = [i for i in self._all_insights() if i.category == "population"]
        assert pop and pop[0].confidence == "high"


class TestSummariesAndWorkflows:
    def test_summaries_carry_all_consumed_engines(self):
        b = ai.build_briefing(dashboard=_dashboard(), forecast=_forecast(),
                              due_items=[], workflows=[{"status": "active", "workflow_type": "quarantine"}])
        for key in ("health", "finance", "valuation", "breeding", "incubation",
                    "population_forecast", "automation", "workflows"):
            assert key in b.summaries
        assert b.summaries["workflows"]["active"] == 1
        assert b.summaries["workflows"]["by_type"]["quarantine"] == 1
