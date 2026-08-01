"""
Rabbit Feed Efficiency Engine (Module 17, Milestone 4) — pure determinism.

FCR is only produced where both feed and a positive weight gain exist; otherwise
``unavailable``/``unknown`` — never a fabricated ratio (ledger CON-M4-4).
"""

from datetime import date

from app.services import rabbit_feed_engine as eng


class TestFeedConversion:
    def test_fcr_computed(self):
        assert eng.feed_conversion(30.0, 10.0)["value"] == 3.0

    def test_zero_gain_unavailable(self):
        assert eng.feed_conversion(30.0, 0.0)["label"] == eng.UNAVAILABLE

    def test_missing_inputs_unknown(self):
        assert eng.feed_conversion(None, 10.0)["label"] == eng.UNKNOWN
        assert eng.feed_conversion(30.0, None)["label"] == eng.UNKNOWN


class TestFeedSummary:
    def _records(self):
        return [
            {"quantity_kg": 5, "cost": 250, "fed_on": date(2026, 1, 1)},
            {"quantity_kg": 5, "cost": 250, "fed_on": date(2026, 1, 2)},
        ]

    def test_totals_and_cost(self):
        s = eng.feed_summary(self._records())
        assert s["feeding_events"]["value"] == 2
        assert s["total_feed_kg"]["value"] == 10.0
        assert s["total_cost"]["value"] == 500.0
        assert s["cost_per_kg_feed"]["value"] == 50.0

    def test_fcr_with_gain(self):
        s = eng.feed_summary(self._records(), weight_gain_g=2000)  # 2 kg gain
        assert s["feed_conversion_ratio"]["value"] == 5.0  # 10 kg feed / 2 kg gain

    def test_fcr_unknown_without_gain(self):
        s = eng.feed_summary(self._records())
        assert s["feed_conversion_ratio"]["label"] == eng.UNKNOWN

    def test_no_costs_unknown(self):
        s = eng.feed_summary([{"quantity_kg": 3, "cost": None, "fed_on": date(2026, 1, 1)}])
        assert s["total_cost"]["label"] == eng.UNKNOWN
        assert s["total_feed_kg"]["value"] == 3.0
