"""
Swine Feed Engine (Module 20, Milestone 5) — pure, deterministic invariants.

Feed totals/cost are recorded facts; FCR is only produced with a positive weight
gain, otherwise honestly unavailable/unknown (never fabricated).
"""

from app.services import swine_feed_engine as eng


class TestFeedSummary:
    def test_totals_and_cost_per_kg(self):
        s = eng.feed_summary([
            {"quantity_kg": 10, "cost": 40},
            {"quantity_kg": 5, "cost": 20},
        ], days=5)
        assert s["feeding_events"]["value"] == 2
        assert s["total_feed_kg"]["value"] == 15.0
        assert s["total_cost"]["value"] == 60.0
        assert s["cost_per_kg_feed"]["value"] == 4.0
        assert s["avg_daily_feed_kg"]["value"] == 3.0

    def test_fcr_unknown_without_weight_gain(self):
        s = eng.feed_summary([{"quantity_kg": 10, "cost": None}])
        assert s["feed_conversion_ratio"]["label"] == eng.UNKNOWN
        assert s["total_cost"]["label"] == eng.UNKNOWN

    def test_fcr_calculated_with_positive_gain(self):
        s = eng.feed_summary([{"quantity_kg": 12}], weight_gain_kg=4.0)
        assert s["feed_conversion_ratio"]["value"] == 3.0  # 12 / 4

    def test_fcr_unavailable_with_zero_gain(self):
        assert eng.feed_conversion(10.0, 0.0)["label"] == eng.UNAVAILABLE

    def test_empty_log(self):
        s = eng.feed_summary([])
        assert s["total_feed_kg"]["value"] == 0.0
        assert s["feed_conversion_ratio"]["label"] == eng.UNKNOWN
