"""
Swine Breeding Engine (Module 20, Milestone 3) — pure, deterministic invariants.

Locks the reproduction math without a database: eligibility (incl. the barrow rule),
gestation forecast, and honesty-labelled rates that never fabricate a denominator.
"""

from datetime import date

from app.services import swine_breeding_engine as eng


class TestEligibility:
    def test_sow_x_boar_is_eligible(self):
        v = eng.validate_eligibility(
            {"sex": "sow", "status": "active"}, {"sex": "boar", "status": "active"}, "natural", False
        )
        assert v["eligible"] is True and v["reasons"] == []

    def test_gilt_is_a_valid_dam(self):
        v = eng.validate_eligibility(
            {"sex": "gilt", "status": "active"}, {"sex": "boar", "status": "active"}, "natural", False
        )
        assert v["eligible"] is True

    def test_barrow_is_never_a_valid_sire(self):
        v = eng.validate_eligibility(
            {"sex": "sow", "status": "active"}, {"sex": "barrow", "status": "active"}, "natural", False
        )
        assert v["eligible"] is False
        assert any("barrow" in r for r in v["reasons"])

    def test_boar_cannot_be_a_dam(self):
        v = eng.validate_eligibility(
            {"sex": "boar", "status": "active"}, {"sex": "boar", "status": "active"}, "natural", False
        )
        assert v["eligible"] is False

    def test_natural_service_requires_a_sire(self):
        v = eng.validate_eligibility({"sex": "sow", "status": "active"}, None, "natural", False)
        assert v["eligible"] is False
        assert any("sire is required" in r for r in v["reasons"])

    def test_ai_may_omit_on_farm_sire(self):
        v = eng.validate_eligibility({"sex": "sow", "status": "active"}, None, "artificial", False)
        assert v["eligible"] is True

    def test_open_cycle_blocks_reservice(self):
        v = eng.validate_eligibility(
            {"sex": "sow", "status": "active"}, {"sex": "boar", "status": "active"}, "natural", True
        )
        assert v["eligible"] is False
        assert any("open breeding cycle" in r for r in v["reasons"])

    def test_inactive_stock_is_ineligible(self):
        v = eng.validate_eligibility(
            {"sex": "sow", "status": "sold"}, {"sex": "boar", "status": "active"}, "natural", False
        )
        assert v["eligible"] is False


class TestGestation:
    def test_expected_farrowing_is_service_plus_gestation(self):
        assert eng.expected_farrowing_date(date(2026, 1, 1), 114) == date(2026, 4, 25)
        assert eng.expected_farrowing_date(None, 114) is None

    def test_gestation_progress_labels_and_overdue(self):
        p = eng.gestation_progress(date(2026, 1, 1), date(2026, 2, 1), 114)
        assert p["days_elapsed"]["value"] == 31
        assert p["overdue"] is False
        # Past the due date → overdue.
        p2 = eng.gestation_progress(date(2026, 1, 1), date(2026, 5, 1), 114)
        assert p2["overdue"] is True

    def test_gestation_unknown_without_service_date(self):
        p = eng.gestation_progress(None, date(2026, 2, 1), 114)
        assert p["days_elapsed"]["label"] == eng.UNKNOWN


class TestRates:
    def test_conception_rate_over_checked_services(self):
        breedings = [
            {"service_date": date(2026, 1, 1), "pregnancy_result": "pregnant", "method": "natural"},
            {"service_date": date(2026, 1, 2), "pregnancy_result": "not_pregnant", "method": "artificial"},
            {"service_date": date(2026, 1, 3), "pregnancy_result": "unknown", "method": "natural"},
        ]
        s = eng.reproduction_summary(breedings)
        assert s["total_services"]["value"] == 3
        assert s["checked_services"]["value"] == 2
        assert s["total_pregnancies"]["value"] == 1
        assert s["ai_services"]["value"] == 1
        # conception = pregnancies / checked = 1/2 = 50%
        assert s["conception_rate_pct"]["value"] == 50.0

    def test_zero_denominator_is_unknown_not_zero(self):
        s = eng.reproduction_summary([])
        assert s["conception_rate_pct"]["label"] == eng.UNKNOWN
        assert s["conception_rate_pct"]["value"] is None
