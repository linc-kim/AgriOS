"""
Swine Intelligence (Module 20, Milestone 10) — pure, deterministic invariants.

The briefing reads composed dashboard outputs and flags risks with evidence +
confidence; health insights are patterns (recommend a vet), never diagnoses (§4.4).
"""

from app.services import swine_intelligence as intel


def _dash(**over):
    d = {
        "population": {"value": 100},
        "reproduction": {"conception_rate_pct": {"value": 90.0}, "total_services": {"value": 20}},
        "farrowing": {"pre_wean_survival_pct": {"value": 92.0}, "avg_litter_size": {"value": 12.0}},
        "health": {"mortality_rate_pct": {"value": 2.0}, "open_disease_cases": {"value": 0},
                   "active_withdrawals": {"value": 0}},
        "finance": {"pnl": {"gross_margin": {"value": 500.0}, "gross_margin_pct": {"value": 25.0},
                            "revenue": {"value": 2000.0}, "total_cost": {"value": 1500.0}}},
        "housing": {"overcrowded_pens": [], "biosecurity": {"flagged": {"value": 0}}},
    }
    d.update(over)
    return d


def test_healthy_farm_is_on_track():
    b = intel.build_briefing(dashboard=_dash())
    assert b.counts["critical"] == 0 and b.counts["warning"] == 0
    assert "on track" in b.headline


def test_high_mortality_is_flagged_as_pattern_not_diagnosis():
    b = intel.build_briefing(dashboard=_dash(
        health={"mortality_rate_pct": {"value": 18.0}, "open_disease_cases": {"value": 1},
                "active_withdrawals": {"value": 0}}))
    mortality = next(i for i in b.insights if "mortality" in i.title.lower())
    assert mortality.severity == "critical"          # ≥ 15%
    assert "not a veterinary diagnosis" in mortality.detail
    assert mortality.evidence[0].source == "health.mortality_rate_pct"


def test_low_conception_and_survival_flagged():
    b = intel.build_briefing(dashboard=_dash(
        reproduction={"conception_rate_pct": {"value": 60.0}, "total_services": {"value": 20}},
        farrowing={"pre_wean_survival_pct": {"value": 70.0}, "avg_litter_size": {"value": 10.0}}))
    titles = " ".join(i.title.lower() for i in b.insights)
    assert "conception" in titles and "survival" in titles


def test_loss_and_overcrowding_flagged_with_evidence():
    b = intel.build_briefing(dashboard=_dash(
        finance={"pnl": {"gross_margin": {"value": -100.0}, "gross_margin_pct": {"value": -5.0},
                         "revenue": {"value": 500.0}, "total_cost": {"value": 600.0}}},
        housing={"overcrowded_pens": [{"id": "x"}], "biosecurity": {"flagged": {"value": 0}}}))
    cats = {i.category for i in b.insights}
    assert "finance" in cats and "housing" in cats
    # Every insight carries a reason + at least one evidence item (explainable).
    assert all(i.detail and i.evidence for i in b.insights)


def test_active_withdrawal_watch():
    b = intel.build_briefing(dashboard=_dash(
        health={"mortality_rate_pct": {"value": 1.0}, "open_disease_cases": {"value": 0},
                "active_withdrawals": {"value": 3}}))
    assert any("withdrawal" in i.title.lower() for i in b.insights)
