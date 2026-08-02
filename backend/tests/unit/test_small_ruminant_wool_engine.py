"""
Small Ruminant Wool engine (Modules 18/19, Milestone 7) — PURE.

Locks the deterministic fleece/clip math and honesty labelling: micron banding
from a recorded measurement, clean weight only with a recorded yield, value only
with a supplied price — nothing fabricated.
"""

from app.services import small_ruminant_wool_engine as w


def test_micron_grade_bands():
    assert w.micron_grade(None)["label"] == "unknown"
    assert w.micron_grade(17.0)["value"] == "superfine"
    assert w.micron_grade(19.5)["value"] == "fine"
    assert w.micron_grade(22.0)["value"] == "medium"
    assert w.micron_grade(28.0)["value"] == "strong"
    assert w.micron_grade(40.0)["value"] == "carpet"


def test_clean_weight_needs_recorded_yield():
    assert w.clean_weight_kg(4.0, None)["label"] == "unknown"   # yield never assumed
    assert w.clean_weight_kg(None, 65)["label"] == "unknown"
    assert w.clean_weight_kg(4.0, 65.0)["value"] == 2.6         # 4 × 0.65


def test_wool_value_needs_price():
    assert w.wool_value(2.6, None)["label"] == "unknown"
    assert w.wool_value(2.6, 10.0)["value"] == 26.0


def test_fleece_analysis_and_clip_summary():
    fleece = {"greasy_weight_kg": 4.0, "clean_yield_pct": 65.0, "staple_length_cm": 9.0, "micron": 19.0}
    a = w.fleece_analysis(fleece, price_per_kg=10.0)
    assert a["clean_weight_kg"]["value"] == 2.6
    assert a["micron_grade"]["value"] == "fine"
    assert a["estimated_value"]["value"] == 26.0  # clean 2.6 × 10

    clip = w.clip_summary(
        [{"greasy_weight_kg": 4.0, "clean_yield_pct": 65.0, "micron": 19.0, "grade": "fine"},
         {"greasy_weight_kg": 3.0, "clean_yield_pct": 60.0, "micron": 21.0, "grade": "medium"}],
        price_per_kg=10.0,
    )
    assert clip["total_greasy_kg"]["value"] == 7.0
    assert clip["total_clean_kg"]["value"] == round(2.6 + 1.8, 3)
    assert clip["avg_micron"]["value"] == 20.0
