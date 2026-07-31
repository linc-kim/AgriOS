"""
BSF Forecast, Bottleneck & Score engines (Module 16, Part 6) — unit tests.

Locks the reporting contract at the engine level: forecasts are always labelled
``forecast`` (never confirmed) and carry method/assumptions/confidence/limitations;
bottlenecks are severity-ranked with evidence; composite scores are calculated,
bounded and degrade to unknown/unavailable — never a filler value.
"""

from app.services import bsf_bottleneck_engine as bottleneck
from app.services import bsf_forecast_engine as forecast
from app.services import bsf_score_engine as score


# ── Forecast engine ───────────────────────────────────────────────────────────

def test_flow_forecast_is_labelled_forecast_with_metadata():
    # 60 kg harvested over a 30-day window → 2 kg/day → 60 kg over 30-day horizon.
    r = forecast.project_flow(60, 30, 30, observations=6, quantity="harvest", unit="kg")
    assert r["forecast"]["label"] == "forecast" and r["forecast"]["value"] == 60.0
    assert r["daily_rate"]["label"] == "calculated" and r["daily_rate"]["value"] == 2.0
    assert r["method"] and r["assumptions"] and r["limitations"]
    assert r["confidence"] == "medium"  # 6 observations


def test_flow_forecast_unknown_without_window_or_data():
    assert forecast.project_flow(None, 30, 30, observations=0, quantity="x", unit="kg")["forecast"]["label"] == "unknown"
    assert forecast.project_flow(10, 0, 30, observations=1, quantity="x", unit="kg")["forecast"]["label"] == "unknown"


def test_stock_forecast_floors_at_zero():
    # current 100, losing 10/day over 10-day window, 30-day horizon → floored at 0.
    r = forecast.project_stock(100, -100, 10, 30, observations=3, quantity="biomass", unit="g")
    assert r["forecast"]["label"] == "forecast" and r["forecast"]["value"] == 0.0


def test_confidence_scales_with_observations():
    assert forecast.project_flow(10, 10, 10, observations=2, quantity="x", unit="kg")["confidence"] == "low"
    assert forecast.project_flow(10, 10, 10, observations=25, quantity="x", unit="kg")["confidence"] == "high"


# ── Bottleneck engine ─────────────────────────────────────────────────────────

def test_bottlenecks_ranked_and_evidenced():
    result = bottleneck.analyze(
        survival_rate_pct=35, capacity_utilisation_pct=95,
        feedstock_available_kg=5, feed_conversion_ratio=7,
    )
    # Critical survival must rank first.
    assert result[0]["constraint"] == "survival" and result[0]["severity"] == "critical"
    assert all("evidence" in b and "recommended_action" in b for b in result)
    # Severity ordering is non-decreasing.
    ranks = [{"critical": 0, "high": 1, "medium": 2, "low": 3}[b["severity"]] for b in result]
    assert ranks == sorted(ranks)


def test_unsupplied_metrics_not_evaluated():
    # Only survival supplied and healthy → no bottlenecks fabricated.
    assert bottleneck.analyze(survival_rate_pct=90) == []
    assert bottleneck.top_bottleneck([]) is None


# ── Score engine ──────────────────────────────────────────────────────────────

def test_scores_calculated_and_bounded():
    assert score.production_score(85, None)["value"] == 85.0
    assert score.production_score(85, 96)["value"] == 75.0  # capacity penalty
    assert score.financial_score(60)["value"] == 60.0
    assert score.health_score(30)["value"] == 70.0
    # Clamp.
    assert score.financial_score(150)["value"] == 100.0


def test_scores_unknown_without_inputs_and_growth_unavailable():
    assert score.production_score(None, None)["label"] == "unknown"
    assert score.financial_score(None)["label"] == "unknown"
    assert score.growth_score()["label"] == "unavailable"


def test_business_health_is_mean_of_available():
    prod = score.production_score(80, None)
    fin = score.financial_score(60)
    unknown = score.sustainability_score(None)
    bh = score.business_health_score([prod, fin, unknown])
    assert bh["label"] == "calculated" and bh["value"] == 70.0  # mean(80,60)
