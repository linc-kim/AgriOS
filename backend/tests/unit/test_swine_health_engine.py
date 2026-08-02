"""
Swine Health Engine (Module 20, Milestone 6) — pure, deterministic invariants.

The engine never diagnoses (frozen §4.4): it aggregates recorded facts into
honesty-labelled counts/rates and always carries the disclaimer.
"""

from datetime import date

from app.services import swine_health_engine as eng


def test_mortality_rate_and_zero_denominator():
    assert eng.mortality_rate(2, 100)["value"] == 2.0
    z = eng.mortality_rate(0, 0)
    assert z["label"] == eng.UNKNOWN and z["value"] is None


def test_active_withdrawals_counts_only_unexpired():
    today = date(2026, 6, 1)
    treatments = [
        {"withdrawal_until": date(2026, 6, 10)},  # active
        {"withdrawal_until": date(2026, 5, 1)},   # expired
        {"withdrawal_until": None},               # none
    ]
    assert eng.active_withdrawals(treatments, today)["value"] == 1


def test_health_summary_has_disclaimer_and_facts():
    s = eng.health_summary(
        {"open_disease_cases": 2, "confirmed_cases": 1, "total_disease_cases": 3,
         "vaccinations": 5, "treatments": 4, "deaths": 2, "population": 100},
        today=date(2026, 6, 1),
        treatments=[{"withdrawal_until": date(2026, 6, 5)}],
    )
    assert s["disclaimer"].startswith("Deterministic summary")
    assert s["open_disease_cases"]["value"] == 2
    assert s["mortality_rate_pct"]["value"] == 2.0
    assert s["active_withdrawals"]["value"] == 1
    # Never emits a diagnosis field.
    assert "diagnosis" not in s
