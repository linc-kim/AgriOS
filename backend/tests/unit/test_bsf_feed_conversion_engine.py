"""
BSF Feed Conversion Engine (Module 16, Part 3) — deterministic unit tests.

Locks the FCR / bioconversion / utilisation maths and the honesty contract:
every metric degrades to ``unknown`` when inputs are missing, and the trend
detector needs ≥2 points before it will speak.
"""

from app.services import bsf_feed_conversion_engine as eng


def test_fcr_basic_and_direction():
    # 20 kg feed → 5 kg biomass gain → FCR 4.0.
    assert eng.feed_conversion_ratio(20, 5)["value"] == 4.0


def test_fcr_unknown_without_gain():
    assert eng.feed_conversion_ratio(20, 0)["label"] == "unknown"
    assert eng.feed_conversion_ratio(None, 5)["label"] == "unknown"


def test_bioconversion_rate():
    # 5 kg biomass from 20 kg feed = 25%.
    assert eng.bioconversion_rate_pct(20, 5)["value"] == 25.0
    assert eng.bioconversion_rate_pct(0, 5)["label"] == "unknown"


def test_waste_processed_is_recorded_fact():
    res = eng.waste_processed_kg(20)
    assert res["label"] == "recorded" and res["value"] == 20.0
    assert eng.waste_processed_kg(None)["label"] == "unknown"


def test_feed_utilisation_clamped():
    assert eng.feed_utilisation_pct(8, 10)["value"] == 80.0
    # Consumed > supplied (data quirk) clamps at 100.
    assert eng.feed_utilisation_pct(12, 10)["value"] == 100.0
    assert eng.feed_utilisation_pct(8, 0)["label"] == "unknown"


def test_conversion_summary_shape():
    s = eng.conversion_summary(20, 5, 25)
    assert s["feed_conversion_ratio"]["value"] == 4.0
    assert s["bioconversion_rate_pct"]["value"] == 25.0
    assert s["feed_utilisation_pct"]["value"] == 80.0
    assert s["feed_consumed_kg"]["label"] == "recorded"


def test_efficiency_trend_declining_and_improving():
    assert eng.efficiency_trend([3.0, 3.5, 4.2])["value"] == "declining"
    assert eng.efficiency_trend([4.2, 3.0])["value"] == "improving"
    assert eng.efficiency_trend([3.0, 3.0])["value"] == "stable"


def test_efficiency_trend_unknown_with_one_point():
    assert eng.efficiency_trend([3.0])["label"] == "unknown"
    assert eng.efficiency_trend([None, None])["label"] == "unknown"
