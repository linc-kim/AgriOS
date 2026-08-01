"""
Rabbit Breeding Engine (Module 17, Milestone 3) — pure determinism.

Locks the honesty contract: eligibility rules, gestation forecasts, litter
performance, doe/buck productivity and herd reproduction rates. Zero denominators
yield ``unknown``, never a fabricated number.
"""

from datetime import date

from app.services import rabbit_breeding_engine as eng


class TestEligibility:
    def test_valid_pair_is_eligible(self):
        v = eng.validate_eligibility({"sex": "doe", "status": "active"},
                                     {"sex": "buck", "status": "active"}, False)
        assert v["eligible"] is True and v["reasons"] == []

    def test_sex_and_status_and_open_cycle_rejected(self):
        v = eng.validate_eligibility({"sex": "buck", "status": "active"},
                                     {"sex": "buck", "status": "sold"}, True)
        assert v["eligible"] is False
        assert any("doe" in r for r in v["reasons"])
        assert any("not active" in r for r in v["reasons"])
        assert any("open breeding" in r for r in v["reasons"])


class TestGestation:
    def test_expected_kindling_date_default_31(self):
        assert eng.expected_kindling_date(date(2026, 1, 1)) == date(2026, 2, 1)

    def test_expected_kindling_date_breed_override(self):
        assert eng.expected_kindling_date(date(2026, 1, 1), 30) == date(2026, 1, 31)

    def test_no_service_date_is_none(self):
        assert eng.expected_kindling_date(None) is None

    def test_gestation_progress_labels(self):
        prog = eng.gestation_progress(date(2026, 1, 1), date(2026, 1, 11), 31)
        assert prog["days_elapsed"]["value"] == 10
        assert prog["days_elapsed"]["label"] == eng.CALCULATED
        assert prog["days_remaining"]["value"] == 21
        assert prog["days_remaining"]["label"] == eng.FORECAST  # breed gestation supplied
        assert prog["overdue"] is False

    def test_gestation_progress_default_is_estimated(self):
        prog = eng.gestation_progress(date(2026, 1, 1), date(2026, 1, 5))
        assert prog["days_remaining"]["label"] == eng.ESTIMATED  # default gestation → estimate

    def test_gestation_progress_unknown_without_service(self):
        prog = eng.gestation_progress(None, date(2026, 1, 5))
        assert prog["days_elapsed"]["label"] == eng.UNKNOWN


class TestLitterPerformance:
    def test_weaned_litter_survival(self):
        p = eng.litter_performance({
            "total_kits": 8, "live_kits": 7, "stillbirths": 1,
            "weaned_kits": 6, "mortality": 1, "avg_birth_weight_g": 55, "status": "weaned",
        })
        assert p["live_birth_rate_pct"]["value"] == 87.5     # 7/8
        assert p["weaning_survival_pct"]["value"] == round(6 / 7 * 100, 1)
        assert p["avg_birth_weight_g"]["value"] == 55.0

    def test_active_litter_weaning_survival_unavailable(self):
        p = eng.litter_performance({
            "total_kits": 6, "live_kits": 6, "stillbirths": 0,
            "weaned_kits": 0, "mortality": 0, "avg_birth_weight_g": None, "status": "active",
        })
        assert p["weaning_survival_pct"]["label"] == eng.UNAVAILABLE
        assert p["avg_birth_weight_g"]["label"] == eng.UNKNOWN


class TestProductivity:
    def _breedings(self):
        return [
            {"service_date": date(2026, 1, 1), "pregnancy_result": "pregnant", "status": "kindled"},
            {"service_date": date(2026, 3, 1), "pregnancy_result": "pregnant", "status": "kindled"},
            {"service_date": date(2026, 5, 1), "pregnancy_result": "not_pregnant", "status": "not_pregnant"},
        ]

    def _litters(self):
        return [
            {"kindling_date": date(2026, 2, 1), "total_kits": 8, "live_kits": 8, "weaned_kits": 7,
             "stillbirths": 0, "mortality": 1, "status": "weaned"},
            {"kindling_date": date(2026, 4, 1), "total_kits": 6, "live_kits": 6, "weaned_kits": 6,
             "stillbirths": 0, "mortality": 0, "status": "weaned"},
        ]

    def test_doe_productivity_rates(self):
        p = eng.doe_productivity(self._breedings(), self._litters())
        assert p["services"]["value"] == 3
        assert p["pregnancies"]["value"] == 2
        assert p["kindlings"]["value"] == 2
        assert p["pregnancy_rate_pct"]["value"] == round(2 / 3 * 100, 1)
        assert p["avg_litter_size"]["value"] == 7.0            # 14/2
        assert p["kit_survival_pct"]["value"] == round(13 / 14 * 100, 1)
        assert p["avg_kindling_interval_days"]["value"] == 59  # Feb1 → Apr1

    def test_buck_fertility(self):
        p = eng.buck_fertility(self._breedings())
        assert p["services"]["value"] == 3
        assert p["confirmed_pregnancies"]["value"] == 2
        assert p["fertility_rate_pct"]["value"] == round(2 / 3 * 100, 1)  # 2 preg / 3 checked

    def test_reproduction_summary_no_data_is_unknown(self):
        s = eng.reproduction_summary([], [])
        assert s["pregnancy_rate_pct"]["label"] == eng.UNKNOWN
        assert s["avg_litter_size"]["label"] == eng.UNKNOWN


class TestBreedingValueRanking:
    def test_ranks_by_weaned_and_flags_unproven(self):
        ranked = eng.breeding_value_ranking([
            {"rabbit_id": "d1", "internal_ref": "RB-1", "kindlings": 2, "total_kits_weaned": 12, "kit_survival_pct": 90},
            {"rabbit_id": "d2", "internal_ref": "RB-2", "kindlings": 1, "total_kits_weaned": 4, "kit_survival_pct": 80},
            {"rabbit_id": "d3", "internal_ref": "RB-3", "kindlings": 0, "total_kits_weaned": 0, "kit_survival_pct": None},
        ])
        assert ranked[0]["internal_ref"] == "RB-1"          # most kits weaned ranks first
        assert ranked[-1]["internal_ref"] == "RB-3"         # unproven ranks last
        assert ranked[-1]["score"]["label"] == eng.UNKNOWN  # insufficient evidence, not a fake zero
