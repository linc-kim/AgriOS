"""
Valuation Engine — pure collection-valuation engine (Module 15, Part 7).

Locks the honesty contract: a bird's value is the best-available RECORDED figure
(manual > sale > purchase > unknown); unvalued birds are excluded and flagged,
never assigned a fabricated value; the P&L view is a calculation over recorded
facts. This engine does not duplicate the Finance engine.
"""

from decimal import Decimal

from app.services import valuation_engine as ve


class TestBirdValue:
    def test_manual_valuation_wins(self):
        r = ve.bird_value(
            [{"method": "appraised", "amount": 50000, "valued_on": "2026-07-01"}],
            purchase_amount=12000, sale_amount=None)
        assert r["value"] == 50000.0 and r["basis"] == "appraised" and r["label"] == ve.RECORDED

    def test_latest_manual_valuation_chosen(self):
        r = ve.bird_value([
            {"method": "market", "amount": 30000, "valued_on": "2026-06-01"},
            {"method": "market", "amount": 40000, "valued_on": "2026-07-01"},
        ])
        assert r["value"] == 40000.0

    def test_sale_over_purchase(self):
        r = ve.bird_value([], purchase_amount=10000, sale_amount=25000)
        assert r["value"] == 25000.0 and r["basis"] == "sale"

    def test_purchase_fallback(self):
        r = ve.bird_value([], purchase_amount=8000)
        assert r["value"] == 8000.0 and r["basis"] == "purchase"

    def test_no_basis_is_unknown(self):
        r = ve.bird_value([])
        assert r["value"] is None and r["label"] == ve.UNKNOWN


class TestCollectionValuation:
    def test_totals_and_unvalued(self):
        birds = [ve.bird_value([{"method": "appraised", "amount": 50000, "valued_on": "2026-07-01"}]),
                 ve.bird_value([], purchase_amount=12000),
                 ve.bird_value([])]
        cv = ve.collection_valuation(birds)
        assert cv["total_value"]["value"] == 62000.0 and cv["total_value"]["label"] == ve.CALCULATED
        assert cv["birds_valued"]["value"] == 2 and cv["birds_unvalued"]["value"] == 1
        assert cv["by_basis"]["appraised"] == 50000.0

    def test_empty_is_unknown(self):
        cv = ve.collection_valuation([])
        assert cv["total_value"]["label"] == ve.UNKNOWN


class TestFinanceSummary:
    def test_net_is_income_minus_costs(self):
        coll = ve.collection_valuation([ve.bird_value([], purchase_amount=10000)])
        s = ve.finance_summary(sale_income=Decimal("45000"), purchase_costs=Decimal("10000"),
                               operational_expenses=Decimal("5000"), collection_value=coll)
        assert s["sale_income"]["value"] == 45000.0 and s["sale_income"]["label"] == ve.RECORDED
        assert s["net"]["value"] == 30000.0 and s["net"]["label"] == ve.CALCULATED
        assert s["collection_value"]["value"] == 10000.0
