"""
Rabbit Finance Engine (Module 17, Milestone 6) — pure determinism.

Confirmed inputs (revenue, feed cost, operating cost) are echoed ``recorded``;
derivations are ``calculated`` from them; zero denominators yield ``unknown`` —
never a fabricated ratio (ledger CON-M6-4).
"""

from app.services import rabbit_finance_engine as eng


class TestPnl:
    def test_confirmed_and_derived(self):
        s = eng.pnl_summary(
            revenue=1000, revenue_events=2, feed_cost=200, feed_events=3,
            operating_cost=100, operating_entries=1, currency="KES",
        )
        assert s["revenue"]["label"] == eng.RECORDED and s["revenue"]["value"] == 1000.0
        assert s["feed_cost"]["value"] == 200.0
        assert s["operating_cost"]["value"] == 100.0
        assert s["total_cost"]["label"] == eng.CALCULATED and s["total_cost"]["value"] == 300.0
        assert s["gross_profit"]["value"] == 700.0
        assert s["gross_margin_pct"]["value"] == 70.0
        assert s["roi_pct"]["value"] == round(700 / 300 * 100, 2)
        assert s["currency"] == "KES"

    def test_no_revenue_margin_unknown(self):
        s = eng.pnl_summary(revenue=0, revenue_events=0, feed_cost=50, feed_events=1,
                            operating_cost=0, operating_entries=0)
        assert s["gross_margin_pct"]["label"] == eng.UNKNOWN
        assert s["roi_pct"]["value"] is not None  # cost 50 > 0 → roi computable (negative)

    def test_no_cost_roi_unknown(self):
        s = eng.pnl_summary(revenue=100, revenue_events=1, feed_cost=0, feed_events=0,
                            operating_cost=0, operating_entries=0)
        assert s["roi_pct"]["label"] == eng.UNKNOWN


class TestUnitEconomics:
    def test_all_metrics(self):
        e = eng.unit_economics(
            revenue=1000, total_cost=300, feed_cost=200, vet_cost=50,
            rabbit_count=10, sold_weight_kg=20, litters=2, breeding_does=3,
        )
        assert e["cost_per_rabbit"]["value"] == 30.0
        assert e["profit_per_rabbit"]["value"] == 70.0        # (1000-300)/10
        assert e["cost_per_kg_sold"]["value"] == 15.0          # 300/20
        assert e["profit_per_litter"]["value"] == 350.0        # 700/2
        assert e["profit_per_breeding_doe"]["value"] == round(700 / 3, 2)
        assert e["feed_cost_pct"]["value"] == round(200 / 300 * 100, 2)
        assert e["vet_cost_pct"]["value"] == round(50 / 300 * 100, 2)

    def test_zero_denominators_unknown(self):
        e = eng.unit_economics(revenue=0, total_cost=0, feed_cost=0, vet_cost=0,
                              rabbit_count=0, sold_weight_kg=0, litters=0, breeding_does=0)
        for key in ("cost_per_rabbit", "cost_per_kg_sold", "profit_per_litter",
                    "profit_per_breeding_doe", "feed_cost_pct"):
            assert e[key]["label"] == eng.UNKNOWN
