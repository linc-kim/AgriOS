"""
Rabbit Intelligence (Module 17, Milestone 10) — pure determinism.

build_briefing reads already-computed deterministic outputs into severity-ranked,
evidence-citing insights; it recomputes nothing and health insights are patterns,
not diagnoses (frozen §4.4).
"""

from app.services import rabbit_intelligence as intel


def _dashboard(**over):
    dash = {
        "recorded_facts": {"population": {"total_rabbits": {"label": "recorded", "value": 10}}},
        "reproduction": {"kindling_rate_pct": {"label": "calculated", "value": 40.0}},
        "health": {"mortality_rate_pct": {"label": "calculated", "value": 30.0}},
        "finance": {"pnl": {"gross_profit": {"label": "calculated", "value": -100.0},
                            "revenue": {"label": "recorded", "value": 50.0},
                            "total_cost": {"label": "calculated", "value": 150.0},
                            "gross_margin_pct": {"label": "calculated", "value": -200.0}}},
        "housing": {"overcrowded_cages": [{"cage_id": "x", "name": "C1"}]},
        "forecast": {},
        "bottlenecks": [{"constraint": "reproduction", "severity": "critical",
                         "evidence": "Kindling 40%", "impact": "Low output.",
                         "recommended_action": "Review bucks.", "confidence": "high"}],
    }
    dash.update(over)
    return dash


def test_briefing_ranks_and_cites_evidence():
    b = intel.build_briefing(dashboard=_dashboard(), forecast={}, growth=None,
                             bottlenecks=_dashboard()["bottlenecks"])
    # Critical insights sort first.
    assert b.insights[0].severity == "critical"
    cats = {i.category for i in b.insights}
    assert {"risk", "health", "finance", "housing", "reproduction"} <= cats
    # Health is a pattern, never a diagnosis.
    health = next(i for i in b.insights if i.category == "health")
    assert "not a veterinary diagnosis" in health.detail.lower()
    assert health.severity == "critical"  # 30% >= 25%
    # Loss surfaced with evidence citations.
    finance = next(i for i in b.insights if i.category == "finance")
    assert finance.evidence and finance.evidence[0].source.startswith("finance.")
    # Counts + headline + priorities.
    assert b.counts["critical"] >= 1
    assert "critical" in b.headline.lower()
    assert b.priorities


def test_healthy_farm_reports_on_track():
    dash = _dashboard(
        reproduction={"kindling_rate_pct": {"value": 85.0}},
        health={"mortality_rate_pct": {"value": 3.0}},
        finance={"pnl": {"gross_profit": {"value": 500.0}, "gross_margin_pct": {"value": 40.0}}},
        housing={"overcrowded_cages": []},
    )
    b = intel.build_briefing(dashboard=dash, forecast={}, growth=None, bottlenecks=[])
    assert b.counts["critical"] == 0 and b.counts["warning"] == 0
    assert "on track" in b.headline.lower()


def test_growth_overdue_flagged():
    growth = {"overall_percent": {"value": 20.0},
              "goals": [{"label": "Herd", "run_rate": {"verdict": {"value": "overdue"}}}]}
    b = intel.build_briefing(dashboard=_dashboard(), forecast={}, growth=growth, bottlenecks=[])
    assert any(i.category == "growth" and i.severity == "warning" for i in b.insights)
