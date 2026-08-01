"""
Rabbit Bottleneck Engine (Module 17, Milestone 7) — pure determinism.

Only supplied metrics are evaluated; results are severity-ranked highest-impact
first; each cites evidence + impact + action (Spec Part 7 §11). Nothing is
fabricated when a metric is absent.
"""

from app.services import rabbit_bottleneck_engine as eng


def test_no_metrics_returns_empty():
    assert eng.analyze() == []


def test_critical_reproduction_detected():
    out = eng.analyze(kindling_rate_pct=30.0)
    assert len(out) == 1
    assert out[0]["constraint"] == "reproduction" and out[0]["severity"] == "critical"
    assert "30" in out[0]["evidence"] and out[0]["recommended_action"]


def test_severity_ordering_highest_first():
    out = eng.analyze(
        kindling_rate_pct=30.0,       # critical
        capacity_utilisation_pct=95,  # medium
        weaning_survival_pct=50.0,    # high
    )
    severities = [b["severity"] for b in out]
    assert severities == sorted(severities, key=lambda s: {"critical": 0, "high": 1, "medium": 2, "low": 3}[s])
    assert severities[0] == "critical"


def test_overcrowding_takes_precedence_over_utilisation():
    out = eng.analyze(overcrowded_cages=2, capacity_utilisation_pct=95)
    constraints = {b["constraint"] for b in out}
    assert "housing_overcrowding" in constraints
    assert "housing_capacity" not in constraints  # overcrowding supersedes the softer signal


def test_negative_margin_flags_profitability():
    out = eng.analyze(gross_margin_pct=-5.0)
    assert out[0]["constraint"] == "profitability" and out[0]["severity"] == "high"


def test_healthy_metrics_no_bottlenecks():
    out = eng.analyze(kindling_rate_pct=85, mortality_rate_pct=3, weaning_survival_pct=95,
                      capacity_utilisation_pct=50, overcrowded_cages=0, gross_margin_pct=40)
    assert out == []
