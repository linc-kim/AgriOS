"""
Small Ruminant Finance engine (Modules 18/19, Milestone 8) — PURE.

Locks the deterministic P&L / unit-economics math and honesty labelling: revenue
and costs are recorded, margins/ROI/per-unit are calculated, and a zero
denominator is 'unknown' — never a fabricated ratio.
"""

from app.services import small_ruminant_finance_engine as f


def test_pnl_summary_margins_and_roi():
    pnl = f.pnl_summary(revenue=1000, revenue_events=5, feed_cost=300, feed_events=10,
                        operating_cost=200, operating_entries=4, currency="KES")
    assert pnl["revenue"]["label"] == "recorded" and pnl["revenue"]["value"] == 1000.0
    assert pnl["total_cost"]["value"] == 500.0
    assert pnl["gross_margin"]["value"] == 500.0
    assert pnl["gross_margin_pct"]["value"] == 50.0
    assert pnl["roi_pct"]["value"] == 100.0  # 500 / 500


def test_pnl_zero_revenue_is_unknown_ratio():
    pnl = f.pnl_summary(revenue=0, revenue_events=0, feed_cost=100, feed_events=1,
                        operating_cost=0, operating_entries=0)
    assert pnl["gross_margin"]["value"] == -100.0
    assert pnl["gross_margin_pct"]["label"] == "unknown"  # no revenue denominator


def test_unit_economics_per_unit_and_missing_denominators():
    ue = f.unit_economics(revenue=1000, total_cost=500, feed_cost=300, vet_cost=50, animal_count=10,
                          sold_weight_kg=40, milk_litres=None, wool_kg=None)
    assert ue["cost_per_animal"]["value"] == 50.0
    assert ue["revenue_per_animal"]["value"] == 100.0
    assert ue["cost_per_kg_sold"]["value"] == 12.5   # 500 / 40
    assert ue["cost_per_litre_milk"]["label"] == "unknown"   # no milk → not fabricated
    assert ue["cost_per_kg_wool"]["label"] == "unknown"
    assert ue["feed_cost_pct"]["value"] == 60.0
    assert ue["vet_cost_pct"]["value"] == 10.0
