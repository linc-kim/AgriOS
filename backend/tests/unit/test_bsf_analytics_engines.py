"""
BSF Health, Sustainability & Finance engines (Module 16, Part 5) — unit tests.

Locks the deterministic maths and the honesty discipline: mortality flags are
patterns not diagnoses, sustainability estimates are labelled estimates, and the
P&L keeps CONFIRMED records (recorded) distinct from CALCULATED derivations —
never fabricating a projection.
"""

from app.services import bsf_finance_engine as fin
from app.services import bsf_health_engine as health
from app.services import bsf_sustainability_engine as sus


# ── Health engine ─────────────────────────────────────────────────────────────

def test_mortality_rate_and_clamp():
    assert health.mortality_rate_pct(150, 1000)["value"] == 15.0
    assert health.mortality_rate_pct(2000, 1000)["value"] == 100.0  # clamp
    assert health.mortality_rate_pct(150, 0)["label"] == "unknown"


def test_health_flag_is_pattern_not_diagnosis():
    hi = health.health_flag(300, 1000)  # 30% ≥ 20% threshold
    assert hi["value"] == "attention" and "not a veterinary diagnosis" in hi["detail"].lower()
    lo = health.health_flag(50, 1000)
    assert lo["value"] == "normal"
    assert health.health_flag(None, 1000)["label"] == "unknown"


def test_mortality_trend_direction():
    assert health.mortality_trend([10, 10, 40, 50])["value"] == "rising"
    assert health.mortality_trend([50, 40, 10, 10])["value"] == "falling"
    assert health.mortality_trend([10])["label"] == "unknown"


# ── Sustainability engine ─────────────────────────────────────────────────────

def test_waste_diverted_is_recorded_fact():
    assert sus.organic_waste_diverted_kg(500)["label"] == "recorded"
    assert sus.organic_waste_diverted_kg(None)["label"] == "unknown"


def test_waste_conversion_efficiency():
    # (25 biomass + 75 frass) / 500 feed = 20%.
    assert sus.waste_conversion_efficiency_pct(500, 25, 75)["value"] == 20.0
    assert sus.waste_conversion_efficiency_pct(0, 25, 75)["label"] == "unknown"


def test_carbon_estimate_only_with_factor_and_labelled_estimate():
    r = sus.carbon_diversion_estimate_kg(500, 0.5)
    assert r["label"] == "estimate" and r["value"] == 250.0
    # No fabricated factor.
    assert sus.carbon_diversion_estimate_kg(500, None)["label"] == "unknown"


# ── Finance engine (P&L) ──────────────────────────────────────────────────────

def test_pnl_confirmed_vs_calculated():
    s = fin.pnl_summary(revenue=1000, revenue_events=2, operating_cost=400,
                        cost_entries=3, harvested_kg=50, currency="KES")
    # Confirmed records are RECORDED and cite their source counts.
    assert s["revenue"]["label"] == "recorded" and "2 recorded" in s["revenue"]["detail"]
    assert s["operating_cost"]["label"] == "recorded" and "3 BSF-tagged" in s["operating_cost"]["detail"]
    # Derivations are CALCULATED.
    assert s["gross_profit"]["label"] == "calculated" and s["gross_profit"]["value"] == 600.0
    assert s["gross_margin_pct"]["value"] == 60.0
    assert s["cost_per_kg"]["value"] == 8.0
    assert s["roi_pct"]["value"] == 150.0
    assert s["currency"] == "KES"


def test_pnl_unknowns_when_no_facts():
    s = fin.pnl_summary(revenue=0, revenue_events=0, operating_cost=0,
                        cost_entries=0, harvested_kg=0)
    assert s["gross_margin_pct"]["label"] == "unknown"
    assert s["cost_per_kg"]["label"] == "unknown"
    assert s["roi_pct"]["label"] == "unknown"
    # Gross profit is still a clean calculated zero.
    assert s["gross_profit"]["value"] == 0.0
