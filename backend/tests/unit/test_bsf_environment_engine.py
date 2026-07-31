"""
BSF Environment Engine (Module 16, Part 3) — deterministic unit tests.

Locks threshold assessment against species ranges, severity grading, and the
honesty rule: a parameter with no recommended range (or no reading) is never
judged against a fabricated threshold.
"""

from app.services import bsf_environment_engine as eng

PROFILE = {
    "environment": {
        "temp_min_c": 27, "temp_max_c": 35,
        "humidity_min_pct": 60, "humidity_max_pct": 70,
    }
}


def test_reading_within_range_is_ok():
    res = eng.assess_reading(PROFILE, {"temperature_c": 30, "humidity_pct": 65})
    assert res["overall"] == "ok" and res["violations"] == []
    assert res["parameters"]["temperature"]["value"] == "ok"


def test_below_minimum_is_flagged():
    res = eng.assess_reading(PROFILE, {"temperature_c": 26})
    assert res["overall"] in ("warning", "critical")
    v = res["violations"][0]
    assert v["parameter"] == "temperature" and v["status"] == "below"


def test_far_above_maximum_is_critical():
    # Band is 8°C wide; 45 is 10°C over max → >25% of band → critical.
    res = eng.assess_reading(PROFILE, {"temperature_c": 45})
    assert res["overall"] == "critical"
    assert res["violations"][0]["severity"] == "critical"


def test_slightly_above_is_warning():
    # 36 is 1°C over the 35 max → within 25% of the 8°C band → warning.
    res = eng.assess_reading(PROFILE, {"temperature_c": 36})
    assert res["violations"][0]["severity"] == "warning"


def test_parameter_without_range_is_recorded_not_judged():
    # Moisture has no range in PROFILE → recorded, never a violation.
    res = eng.assess_reading(PROFILE, {"moisture_pct": 999})
    assert res["parameters"]["moisture"]["label"] == "recorded"
    assert all(v["parameter"] != "moisture" for v in res["violations"])


def test_missing_reading_value_is_unknown():
    res = eng.assess_reading(PROFILE, {"humidity_pct": 65})
    assert res["parameters"]["temperature"]["label"] == "unknown"


def test_no_profile_never_fabricates_violations():
    res = eng.assess_reading(None, {"temperature_c": 5, "humidity_pct": 5})
    assert res["overall"] == "ok" and res["violations"] == []


def test_stability_needs_two_points():
    assert eng.stability([{"temperature_c": 30}], "temperature_c")["label"] == "unknown"
    res = eng.stability(
        [{"temperature_c": 30}, {"temperature_c": 32}, {"temperature_c": 28}], "temperature_c"
    )
    assert res["label"] == "calculated" and res["value"] > 0
