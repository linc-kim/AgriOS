"""
BSF Harvest & Frass Engines (Module 16, Part 4) — deterministic unit tests.

Locks readiness signalling, yield maths, harvest-quantity validation, and the
moisture-adjusted frass maths — with the honesty rule that missing inputs yield
``unknown``, never a guess.
"""

from app.services import bsf_frass_engine as frass
from app.services import bsf_harvest_engine as harvest


# ── Harvest engine ────────────────────────────────────────────────────────────

def test_readiness_by_stage():
    assert harvest.harvest_readiness("prepupae")["value"] == "ready"
    assert harvest.harvest_readiness("mature_larvae")["value"] == "ready"
    assert harvest.harvest_readiness("feeding_larvae")["value"] == "approaching"
    assert harvest.harvest_readiness("egg")["value"] == "not_ready"
    assert harvest.harvest_readiness("adult")["value"] == "past_window"
    assert harvest.harvest_readiness(None)["label"] == "unknown"


def test_expected_yield_forecast_and_unknown():
    # 10,000 g biomass × 0.6 harvest ratio = 6 kg.
    res = harvest.expected_yield_kg(10_000, 0.6)
    assert res["label"] == "forecast" and res["value"] == 6.0
    assert harvest.expected_yield_kg(10_000, None)["label"] == "unknown"


def test_yield_pct():
    # 3 kg harvested from a 10,000 g (10 kg) batch = 30%.
    assert harvest.yield_pct(3, 10_000)["value"] == 30.0
    assert harvest.yield_pct(3, 0)["label"] == "unknown"


def test_validate_harvest_quantity_partial_bounds():
    # Batch has 5,000 g = 5 kg biomass.
    ok = harvest.validate_harvest_quantity(4, 5000, is_complete=False)
    assert ok["valid"] is True
    over = harvest.validate_harvest_quantity(6, 5000, is_complete=False)
    assert over["valid"] is False
    # Complete harvest is not bounded by biomass.
    assert harvest.validate_harvest_quantity(6, 5000, is_complete=True)["valid"] is True
    # Unknown biomass is permitted but unbounded.
    assert harvest.validate_harvest_quantity(6, None, is_complete=False)["valid"] is True
    assert harvest.validate_harvest_quantity(0, 5000, is_complete=False)["valid"] is False


# ── Frass engine ──────────────────────────────────────────────────────────────

def test_moisture_adjusted_dry_weight():
    # 10 kg at 40% moisture → 6 kg dry.
    assert frass.moisture_adjusted_dry_kg(10, 40)["value"] == 6.0
    assert frass.moisture_adjusted_dry_kg(10, None)["label"] == "unknown"


def test_frass_yield_pct():
    # 15 kg frass from 100 kg feed = 15%.
    assert frass.frass_yield_pct(15, 100)["value"] == 15.0
    assert frass.frass_yield_pct(15, 0)["label"] == "unknown"


def test_frass_per_biomass():
    assert frass.frass_per_biomass_pct(15, 5)["value"] == 300.0
    assert frass.frass_per_biomass_pct(15, None)["label"] == "unknown"


def test_frass_summary_shape():
    s = frass.frass_summary(10, 40, feed_consumed_kg=100, biomass_gained_kg=5)
    assert s["weight_kg"]["label"] == "recorded"
    assert s["dry_weight_kg"]["value"] == 6.0
    assert s["frass_yield_pct"]["value"] == 10.0
