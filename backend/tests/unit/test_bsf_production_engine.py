"""
BSF Production Engine (Module 16, Part 2) — deterministic unit tests.

Locks the production maths and, critically, the honesty contract: every metric
degrades to ``unknown`` when its recorded inputs are missing — never a guess.
"""

from app.services import bsf_production_engine as eng


# ── Point metrics ─────────────────────────────────────────────────────────────

def test_average_weight_mg():
    # 10,000 larvae weighing 2,000 g → 200 mg each.
    res = eng.average_weight_mg(10_000, 2000)
    assert res["label"] == "calculated" and res["value"] == 200.0


def test_average_weight_unknown_without_inputs():
    assert eng.average_weight_mg(0, 2000)["label"] == "unknown"
    assert eng.average_weight_mg(10_000, None)["label"] == "unknown"


def test_survival_rate_clamped_and_calculated():
    assert eng.survival_rate_pct(1000, 850)["value"] == 85.0
    # Clamp above 100 (data error) rather than emit an impossible rate.
    assert eng.survival_rate_pct(1000, 1200)["value"] == 100.0
    assert eng.survival_rate_pct(0, 100)["label"] == "unknown"


def test_capacity_utilisation():
    assert eng.capacity_utilisation_pct(5000, 10000)["value"] == 50.0
    assert eng.capacity_utilisation_pct(5000, 0)["label"] == "unknown"


def test_growth_rate():
    res = eng.growth_rate_g_per_day(1000, 2500, 5)
    assert res["label"] == "calculated" and res["value"] == 300.0
    assert eng.growth_rate_g_per_day(1000, 2500, 0)["label"] == "unknown"


def test_production_velocity():
    assert eng.production_velocity_g_per_day(3600, 12)["value"] == 300.0
    assert eng.production_velocity_g_per_day(None, 12)["label"] == "unknown"


# ── Split / merge validation ──────────────────────────────────────────────────

def test_validate_split_within_parent():
    res = eng.validate_split(10_000, [4000, 3000, 2000])
    assert res["valid"] is True and res["allocated"] == 9000 and res["remainder"] == 1000


def test_validate_split_over_allocation_rejected():
    res = eng.validate_split(10_000, [6000, 6000])
    assert res["valid"] is False and res["remainder"] == -2000


def test_validate_split_unknown_parent_is_permitted_but_flagged():
    res = eng.validate_split(None, [4000, 3000])
    assert res["valid"] is True and res["remainder"] is None


def test_validate_split_rejects_negative():
    assert eng.validate_split(10_000, [-1])["valid"] is False


def test_merge_totals_excludes_unknowns():
    res = eng.merge_totals([1000, None, 3000], [500, 600, None])
    assert res["total_population"]["value"] == 4000
    assert res["total_biomass_g"]["value"] == 1100.0
    # Detail reports the coverage so the total is never silently understated.
    assert "2/3" in res["total_population"]["detail"]


def test_split_child_biomass_is_forecast():
    res = eng.split_child_biomass(2000, 10_000, 2500)
    assert res["label"] == "forecast" and res["value"] == 500.0
    assert eng.split_child_biomass(None, 10_000, 2500)["label"] == "unknown"
