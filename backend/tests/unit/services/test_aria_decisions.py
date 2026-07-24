"""
ARIA decision support — the case, not a verdict.

The defining property under test: ARIA never pretends certainty. Every decision
must carry what's missing, and when the data needed to judge isn't there, the
lean is need_info and the answer asks for it rather than guessing.
"""

from datetime import date
from decimal import Decimal

from app.services import aria_decisions as dec
from app.services.aria_intelligence import FarmFacts

TODAY = date(2026, 7, 23)


def facts(**kw) -> FarmFacts:
    base = dict(farm_name="F", as_of=TODAY, total_birds=500)
    base.update(kw)
    return FarmFacts(**base)


class TestRouting:
    def test_recognises_decision_questions(self):
        assert dec.looks_like_decision("can I afford another flock?")
        assert dec.looks_like_decision("should I change feed?")
        assert dec.looks_like_decision("should I vaccinate today?")

    def test_ignores_non_decisions(self):
        assert not dec.looks_like_decision("how many eggs today")
        assert not dec.looks_like_decision("what is coccidiosis")
        assert dec.decide("how is my farm", facts()) is None


class TestAlwaysHonest:
    def test_every_decision_lists_what_is_missing(self):
        for q in ("can I afford another flock?", "should I change feed?"):
            d = dec.decide(q, facts())
            assert d is not None
            assert d.missing, f"{q} should surface missing information"

    def test_never_a_bare_verdict(self):
        d = dec.decide("can I afford another flock?", facts(is_profitable=True, gross_profit=Decimal("50000")))
        # Even a positive lean carries caveats.
        assert d.assumptions and d.risks
        assert d.lean in ("consider", "caution", "hold", "need_info")


class TestNewFlock:
    def test_profitable_leans_consider(self):
        d = dec.decide("can I afford another flock?", facts(is_profitable=True, gross_profit=Decimal("80000")))
        assert d.lean == "consider"
        assert any("profitable" in p.lower() for p in d.pros)

    def test_unprofitable_leans_caution(self):
        d = dec.decide("should I buy more chicks?", facts(is_profitable=False, gross_profit=Decimal("-10000")))
        assert d.lean == "caution"

    def test_no_finance_data_needs_info(self):
        d = dec.decide("can I afford another flock?", facts())
        assert d.lean == "need_info"
        assert any("finance" in m.lower() for m in d.missing)

    def test_high_disease_risk_adds_caution(self):
        d = dec.decide("can I afford another flock?",
                       facts(is_profitable=True, gross_profit=Decimal("80000"), disease_level="high"))
        assert d.lean == "caution"
        assert any("disease" in c.lower() for c in d.cons)


class TestVaccinateToday:
    def test_overdue_leans_consider(self):
        d = dec.decide("should I vaccinate today?", facts(vaccinations_overdue=2))
        assert d.lean == "consider"

    def test_nothing_due_leans_hold(self):
        d = dec.decide("should I vaccinate today?", facts())
        assert d.lean == "hold"
        assert "no need" in d.headline.lower() or "nothing is due" in d.headline.lower()

    def test_healthy_birds_caveat_present(self):
        d = dec.decide("should I vaccinate today?", facts(vaccinations_overdue=1))
        assert any("healthy" in c.lower() for c in d.cons)


class TestChangeFeed:
    def test_high_feed_cost_leans_consider(self):
        d = dec.decide("should I change feed?", facts(feed_cost_pct=Decimal("70")))
        assert d.lean == "consider"

    def test_gradual_transition_is_an_assumption(self):
        d = dec.decide("should I change feed?", facts(feed_cost_pct=Decimal("70")))
        assert any("gradual" in a.lower() or "transition" in a.lower() for a in d.assumptions)
