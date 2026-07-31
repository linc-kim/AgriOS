"""
BSF Intelligence (Module 16, Part 8) — deterministic unit tests.

Locks the Mission Control contract at the engine level: the briefing READS engine
outputs (never recomputes), every insight cites evidence, insights are severity-
ranked, and low-confidence/limitations are carried — never hidden certainty.
"""

from app.services import bsf_intelligence as intel


def _dashboard(*, gross_profit=500.0, margin=40.0, mortality_flag="normal", mortality=5.0):
    return {
        "recorded_facts": {"active_batches": {"label": "recorded", "value": 3},
                           "total_batches": {"label": "recorded", "value": 5}},
        "analytics": {
            "production": {"survival_rate_pct": {"label": "calculated", "value": 90.0},
                           "feed_conversion_ratio": {"label": "calculated", "value": 2.5}},
            "health": {"flag": {"label": "calculated", "value": mortality_flag},
                       "mortality_rate_pct": {"label": "calculated", "value": mortality}},
            "finance": {"gross_profit": {"label": "calculated", "value": gross_profit},
                        "gross_margin_pct": {"label": "calculated", "value": margin},
                        "revenue": {"label": "recorded", "value": 1000.0},
                        "operating_cost": {"label": "recorded", "value": 1000.0 - gross_profit}},
            "sustainability": {},
        },
        "scores": {"business_health": {"label": "calculated", "value": 70.0}},
        "forecast": {"harvest_kg": {"forecast": {"label": "forecast", "value": 60.0}}},
        "bottlenecks": [],
        "top_bottleneck": None,
    }


def test_briefing_reads_and_ranks_and_cites_evidence():
    dash = _dashboard(gross_profit=-200.0, margin=-20.0, mortality_flag="attention", mortality=30.0)
    dash["bottlenecks"] = [{"constraint": "feedstock_supply", "severity": "high",
                            "evidence": "Only 5kg available", "impact": "Feeding will stall",
                            "recommended_action": "Secure supply", "confidence": "high"}]
    b = intel.build_briefing(dashboard=dash, forecast=dash["forecast"], growth=None,
                             bottlenecks=dash["bottlenecks"])
    # Insights present and every one cites evidence.
    assert b.insights and all(i.evidence for i in b.insights)
    # Severity-ranked (non-decreasing).
    ranks = [{"critical": 0, "warning": 1, "watch": 2, "info": 3}[i.severity] for i in b.insights]
    assert ranks == sorted(ranks)
    # The loss and the mortality pattern and the bottleneck all surfaced.
    cats = {i.category for i in b.insights}
    assert {"finance", "risk"} <= cats
    # Finance insight cites the recorded finance figures.
    fin = next(i for i in b.insights if i.category == "finance")
    assert any(e.source == "finance.gross_profit" for e in fin.evidence)


def test_healthy_farm_has_calm_headline_and_no_false_risks():
    dash = _dashboard()
    b = intel.build_briefing(dashboard=dash, forecast=dash["forecast"], growth=None, bottlenecks=[])
    assert "on track" in b.headline.lower()
    assert b.counts["critical"] == 0 and b.counts["warning"] == 0


def test_growth_deviation_flags_overdue_and_carries_limitations():
    dash = _dashboard()
    growth = {
        "overall_percent": {"label": "calculated", "value": 20.0},
        "goals": [{"label": "Total harvest", "metric_key": "total_harvest_kg",
                   "run_rate": {"verdict": {"label": "calculated", "value": "overdue"}}}],
        "milestones": {},
    }
    b = intel.build_briefing(dashboard=dash, forecast=dash["forecast"], growth=growth, bottlenecks=[])
    growth_insight = next(i for i in b.insights if i.category == "growth")
    assert growth_insight.severity == "warning" and growth_insight.limitations
    # ARIA explains; it does not change the plan — the copy says so.
    assert "will not change the plan" in growth_insight.detail.lower()


def test_recomputes_nothing_uses_supplied_labels():
    # A figure labelled 'calculated' by its engine stays 'calculated' in evidence.
    dash = _dashboard(gross_profit=-1.0, margin=-1.0)
    b = intel.build_briefing(dashboard=dash, forecast=dash["forecast"], growth=None, bottlenecks=[])
    fin = next(i for i in b.insights if i.category == "finance")
    ev = next(e for e in fin.evidence if e.source == "finance.gross_profit")
    assert ev.fact_type == "calculated" and ev.value == "-1.0"
