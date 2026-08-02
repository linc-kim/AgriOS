"""
Small Ruminant Growth & Feed engines (Modules 18/19, Milestone 4) — PURE.

Locks the deterministic growth/feed math (shared by both species) and its honesty
labelling: ADG needs two dated weights, deviation needs a breed curve, FCR needs a
positive gain — every missing input is 'unknown'/'unavailable', never fabricated.
"""

from datetime import date

from app.services import small_ruminant_growth_engine as g
from app.services import small_ruminant_feed_engine as f


def test_adg_needs_two_dated_weights():
    assert g.average_daily_gain([{"recorded_on": date(2026, 1, 1), "weight_kg": 5}])["label"] == "unknown"
    weights = [{"recorded_on": date(2026, 1, 1), "weight_kg": 5.0},
               {"recorded_on": date(2026, 1, 11), "weight_kg": 7.0}]
    adg = g.average_daily_gain(weights)
    assert adg["label"] == "calculated" and adg["value"] == 0.2  # 2kg / 10d


def test_expected_weight_interpolates_and_refuses_extrapolation():
    curve = [{"age_days": 0, "weight_kg": 3.0}, {"age_days": 100, "weight_kg": 23.0}]
    mid = g.expected_weight(50, curve)
    assert mid["label"] == "estimated" and mid["value"] == 13.0
    assert g.expected_weight(200, curve)["label"] == "unknown"   # outside range → not fabricated
    assert g.expected_weight(50, None)["label"] == "unknown"


def test_weight_analysis_deviation_and_percentile():
    weights = [{"recorded_on": date(2026, 1, 1), "weight_kg": 3.0},
               {"recorded_on": date(2026, 4, 11), "weight_kg": 20.0}]
    curve = [{"age_days": 0, "weight_kg": 3.0}, {"age_days": 100, "weight_kg": 23.0}]
    a = g.weight_analysis(weights, dob=date(2026, 1, 1), growth_curve=curve)
    assert a["latest_weight_kg"]["value"] == 20.0
    assert a["expected_weight_kg"]["label"] == "estimated"      # 100 days → 23
    assert a["deviation_kg"]["value"] == -3.0                   # 20 − 23 (under target)
    pct = g.growth_percentile(20.0, [10.0, 15.0, 25.0])
    assert pct["value"] == round(2 / 3 * 100, 1)


def test_fcr_only_with_positive_gain():
    assert f.feed_conversion(10.0, 0.0)["label"] == "unavailable"
    assert f.feed_conversion(10.0, None)["label"] == "unknown"
    assert f.feed_conversion(10.0, 2.5)["value"] == 4.0  # 10 / 2.5


def test_feed_summary_costs_and_conversion():
    records = [{"quantity_kg": 5.0, "cost": 10.0}, {"quantity_kg": 5.0, "cost": None}]
    s = f.feed_summary(records, weight_gain_kg=2.0)
    assert s["total_feed_kg"]["value"] == 10.0
    assert s["total_cost"]["value"] == 10.0
    assert s["feed_conversion_ratio"]["value"] == 5.0  # 10kg / 2kg gain
    empty = f.feed_summary([], weight_gain_kg=None)
    assert empty["feed_conversion_ratio"]["label"] == "unknown"
