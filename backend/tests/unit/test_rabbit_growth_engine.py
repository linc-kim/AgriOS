"""
Rabbit Growth Engine (Module 17, Milestone 4) — pure determinism.

Locks the honesty contract: ADG needs ≥2 dated measurements, expected weight is
interpolated from the breed curve and is unknown outside its range, percentiles
rank against recorded peers, and missing data yields ``unknown`` (never a
fabricated number — Spec Part 4 §8).
"""

from datetime import date

from app.services import rabbit_growth_engine as eng


def _w(d, g):
    return {"recorded_on": d, "weight_g": g}


class TestADG:
    def test_adg_across_span(self):
        adg = eng.average_daily_gain([_w(date(2026, 1, 1), 1000), _w(date(2026, 1, 11), 1300)])
        assert adg["value"] == 30.0 and adg["label"] == eng.CALCULATED

    def test_single_measurement_unknown(self):
        assert eng.average_daily_gain([_w(date(2026, 1, 1), 1000)])["label"] == eng.UNKNOWN

    def test_same_day_unknown(self):
        adg = eng.average_daily_gain([_w(date(2026, 1, 1), 1000), _w(date(2026, 1, 1), 1100)])
        assert adg["label"] == eng.UNKNOWN


class TestExpectedWeight:
    CURVE = [{"age_days": 30, "weight_g": 1000}, {"age_days": 60, "weight_g": 2000}]

    def test_interpolates_within_range(self):
        exp = eng.expected_weight(45, self.CURVE)
        assert exp["value"] == 1500.0 and exp["label"] == eng.ESTIMATED

    def test_outside_range_unknown(self):
        assert eng.expected_weight(90, self.CURVE)["label"] == eng.UNKNOWN
        assert eng.expected_weight(10, self.CURVE)["label"] == eng.UNKNOWN

    def test_no_curve_unknown(self):
        assert eng.expected_weight(45, None)["label"] == eng.UNKNOWN


class TestWeightAnalysis:
    def test_full_analysis_with_curve(self):
        weights = [_w(date(2026, 1, 1), 1000), _w(date(2026, 1, 31), 2000)]
        curve = [{"age_days": 30, "weight_g": 1000}, {"age_days": 60, "weight_g": 2000}]
        a = eng.weight_analysis(weights, dob=date(2025, 12, 2), growth_curve=curve)
        assert a["latest_weight_g"]["value"] == 2000.0
        assert a["total_gain_g"]["value"] == 1000.0
        assert a["average_daily_gain"]["value"] == round(1000 / 30, 2)
        # DOB 2025-12-02 → age at 2026-01-31 is 60 days → expected 2000 → deviation 0.
        assert a["age_days"]["value"] == 60
        assert a["expected_weight_g"]["value"] == 2000.0
        assert a["deviation_g"]["value"] == 0.0

    def test_empty_is_unknown(self):
        a = eng.weight_analysis([], dob=None)
        assert a["latest_weight_g"]["label"] == eng.UNKNOWN
        assert a["measurements"]["value"] == 0


class TestSeriesAndPercentile:
    def test_series_gain_from_prev(self):
        series = eng.growth_series([_w(date(2026, 1, 1), 1000), _w(date(2026, 1, 11), 1300)], dob=date(2025, 12, 1))
        assert series[0]["gain_from_prev_g"] is None
        assert series[1]["gain_from_prev_g"] == 300.0
        assert series[1]["adg_from_prev"] == 30.0
        assert series[0]["age_days"] == 31

    def test_percentile_rank(self):
        pct = eng.growth_percentile(1500, [1000, 1200, 1400, 1600])
        assert pct["value"] == 75.0  # 3 of 4 peers lighter

    def test_percentile_empty_unknown(self):
        assert eng.growth_percentile(1500, [])["label"] == eng.UNKNOWN
