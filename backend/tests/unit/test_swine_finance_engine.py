"""
Swine Finance Engine (Module 20, Milestone 8) — pure, deterministic invariants.

Revenue and costs are recorded facts; margin/ROI/per-unit costs are calculated and
never stored. A zero denominator yields unknown, never a fabricated ratio.
"""

from app.services import swine_finance_engine as eng


class TestPnl:
    def test_pnl_math(self):
        p = eng.pnl_summary(revenue=1000, revenue_events=5, feed_cost=400, feed_events=10,
                            operating_cost=200, operating_entries=3, currency="USD")
        assert p["revenue"]["value"] == 1000.0
        assert p["total_cost"]["value"] == 600.0
        assert p["gross_margin"]["value"] == 400.0
        assert p["gross_margin_pct"]["value"] == 40.0   # 400/1000
        assert p["roi_pct"]["value"] == 66.7            # 400/600 ≈ 66.7

    def test_zero_revenue_margin_pct_unknown(self):
        p = eng.pnl_summary(revenue=0, revenue_events=0, feed_cost=100, feed_events=1,
                            operating_cost=0, operating_entries=0)
        assert p["gross_margin"]["value"] == -100.0
        assert p["gross_margin_pct"]["label"] == eng.UNKNOWN


class TestUnitEconomics:
    def test_per_unit_costs(self):
        u = eng.unit_economics(revenue=1000, total_cost=600, feed_cost=400, health_cost=120,
                               pig_count=10, sold_weight_kg=200, sold_head=8)
        assert u["cost_per_pig"]["value"] == 60.0        # 600/10
        assert u["revenue_per_pig"]["value"] == 100.0    # 1000/10
        assert u["cost_per_kg_sold"]["value"] == 3.0     # 600/200
        assert u["revenue_per_head_sold"]["value"] == 125.0  # 1000/8
        assert u["feed_cost_pct"]["value"] == 66.7       # 400/600
        assert u["health_cost_pct"]["value"] == 20.0     # 120/600

    def test_unknown_denominators(self):
        u = eng.unit_economics(revenue=0, total_cost=0, feed_cost=0, health_cost=0, pig_count=0)
        assert u["cost_per_pig"]["label"] == eng.UNKNOWN
        assert u["cost_per_kg_sold"]["label"] == eng.UNKNOWN
        assert u["revenue_per_head_sold"]["label"] == eng.UNKNOWN
