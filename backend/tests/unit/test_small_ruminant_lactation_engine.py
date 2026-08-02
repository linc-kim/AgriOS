"""
Small Ruminant Lactation engine (Modules 18/19, Milestone 6) — PURE.

Locks the deterministic dairy math and its honesty labelling: stage from days in
milk, total/avg/peak from recorded sessions, a 305-day *projection* (forecast, not
a promise), and an advisory dry-off signal — never fabricated.
"""

from datetime import date

from app.services import small_ruminant_lactation_engine as l


def test_stage_from_days_in_milk():
    assert l.lactation_stage(None)["label"] == "unknown"
    assert l.lactation_stage(30)["value"] == "early"
    assert l.lactation_stage(120)["value"] == "mid"
    assert l.lactation_stage(260)["value"] == "late"


def test_metrics_sum_sessions_per_day():
    records = [
        {"recorded_on": date(2026, 1, 1), "quantity_liters": 1.5, "session": "am"},
        {"recorded_on": date(2026, 1, 1), "quantity_liters": 1.0, "session": "pm"},   # day total 2.5
        {"recorded_on": date(2026, 1, 2), "quantity_liters": 3.0, "session": "total"},  # peak day
    ]
    m = l.lactation_metrics(date(2026, 1, 1), records, date(2026, 1, 3))
    assert m["total_yield_l"]["value"] == 5.5
    assert m["peak_daily_yield_l"]["value"] == 3.0
    assert m["peak_date"]["value"] == "2026-01-02"
    assert m["avg_daily_yield_l"]["value"] == round(5.5 / 2, 3)
    # 305-day projection is a forecast, never recorded.
    assert m["projected_305_day_l"]["label"] == "forecast"


def test_metrics_unknown_without_records():
    m = l.lactation_metrics(date(2026, 1, 1), [], date(2026, 2, 1))
    assert m["total_yield_l"]["label"] == "unknown"
    assert m["days_in_milk"]["value"] == 31  # still computed from dates


def test_dry_off_recommendation_is_advisory():
    # Late lactation triggers a recommendation.
    late = l.dry_off_recommendation(250, 1.5)
    assert late["label"] == "recommendation" and late["value"] is True
    # Low yield triggers it too.
    low = l.dry_off_recommendation(100, 0.2)
    assert low["value"] is True
    # Neither → advisory False (not a directive).
    none = l.dry_off_recommendation(100, 2.0)
    assert none["value"] is False
    assert l.dry_off_recommendation(None, None)["label"] == "unknown"
