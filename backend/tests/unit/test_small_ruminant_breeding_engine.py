"""
Small Ruminant Breeding & Genetics engines (Modules 18/19, Milestone 3) — PURE.

These lock the deterministic reproduction math and prove the ONE engine serves
both species through the species config (no forked goat/sheep logic):

  * eligibility is expressed biologically (dam=female, sire=male) so goat doe×buck
    and sheep ewe×ram both pass, and a wether sire is rejected for either;
  * gestation forecasts use the species default (goat 150d, sheep 147d) with a
    breed override, and are labelled forecast/estimated — never recorded;
  * rates are honest: a zero denominator is 'unknown', never a fabricated number;
  * genetics reuses the platform pedigree engine — full sibs give the textbook
    offspring inbreeding F = 0.25.
"""

from datetime import date

from app.services import small_ruminant_breeding_engine as eng
from app.services import small_ruminant_genetics as gen
from app.services import small_ruminant_species_config as cfg


# ── Eligibility (species-neutral via biological role) ─────────────────────────

def test_eligibility_accepts_species_correct_pairing():
    goat = eng.validate_eligibility(
        "goat", {"sex": "doe", "status": "active"}, {"sex": "buck", "status": "active"}, False
    )
    assert goat["eligible"] and goat["reasons"] == []
    sheep = eng.validate_eligibility(
        "sheep", {"sex": "ewe", "status": "active"}, {"sex": "ram", "status": "active"}, False
    )
    assert sheep["eligible"]


def test_eligibility_rejects_wrong_roles_and_open_cycle():
    # A wether (castrated male) cannot be a sire.
    r = eng.validate_eligibility(
        "goat", {"sex": "doe", "status": "active"}, {"sex": "wether", "status": "active"}, False
    )
    assert not r["eligible"] and any("buck" in reason for reason in r["reasons"])
    # An open cycle blocks re-breeding.
    r2 = eng.validate_eligibility(
        "sheep", {"sex": "ewe", "status": "active"}, {"sex": "ram", "status": "active"}, True
    )
    assert not r2["eligible"] and any("open breeding" in reason for reason in r2["reasons"])


# ── Gestation forecast (species default + breed override) ─────────────────────

def test_expected_birth_uses_species_gestation():
    sd = date(2026, 1, 1)
    assert eng.expected_birth_date(sd, cfg.default_gestation_days("goat")) == date(2026, 5, 31)  # +150
    assert eng.expected_birth_date(sd, cfg.default_gestation_days("sheep")) == date(2026, 5, 28)  # +147
    assert eng.expected_birth_date(None, 150) is None


def test_gestation_progress_is_labelled_and_never_recorded():
    prog = eng.gestation_progress(date(2026, 1, 1), date(2026, 2, 1), 150, breed_specified=False)
    assert prog["days_elapsed"]["label"] == "calculated" and prog["days_elapsed"]["value"] == 31
    # Species-default gestation → estimated (not a recorded fact).
    assert prog["expected_birth_date"]["label"] == "estimated"
    prog2 = eng.gestation_progress(date(2026, 1, 1), date(2026, 2, 1), 148, breed_specified=True)
    assert prog2["expected_birth_date"]["label"] == "forecast"


# ── Birth performance & summaries ─────────────────────────────────────────────

def test_birth_performance_weaning_unavailable_until_weaned():
    active = eng.birth_performance({"total_born": 3, "live_born": 2, "stillborn": 1, "status": "active"})
    assert active["live_birth_rate_pct"]["value"] == round(2 / 3 * 100, 1)
    assert active["weaning_survival_pct"]["label"] == "unavailable"
    weaned = eng.birth_performance({"total_born": 3, "live_born": 2, "weaned": 2, "status": "weaned"})
    assert weaned["weaning_survival_pct"]["value"] == 100.0


def test_rates_are_unknown_without_a_denominator():
    summary = eng.reproduction_summary([], [])
    assert summary["pregnancy_rate_pct"]["label"] == "unknown"
    assert summary["avg_litter_size"]["label"] == "unknown"


def test_dam_productivity_avg_litter_and_interval():
    breedings = [{"service_date": date(2026, 1, 1), "pregnancy_result": "pregnant"},
                 {"service_date": date(2026, 7, 1), "pregnancy_result": "pregnant"}]
    births = [{"total_born": 2, "live_born": 2, "weaned": 2, "status": "weaned", "birth_date": date(2026, 5, 30)},
              {"total_born": 3, "live_born": 3, "weaned": 2, "status": "weaned", "birth_date": date(2026, 11, 26)}]
    p = eng.dam_productivity(breedings, births)
    assert p["avg_litter_size"]["value"] == 2.5  # (2+3)/2
    assert p["avg_birth_interval_days"]["value"] is not None


# ── Genetics (reuses platform pedigree engine) ────────────────────────────────

def test_full_sibs_give_textbook_offspring_inbreeding():
    # S × D are unrelated founders; A and B are full sibs (both children of S,D).
    parents = {"S": (None, None), "D": (None, None), "A": ("S", "D"), "B": ("S", "D")}
    # Pair the two full sibs (A male, B female for the sex check).
    result = gen.assess_pairing(
        "goat", {"id": "A", "sex": "buck"}, {"id": "B", "sex": "doe"}, parents
    )
    assert result["offspring_inbreeding"]["value"] == 0.25  # F = kinship(full sibs)
    assert result["risk_level"] == "high"
    assert result["offspring_inbreeding"]["label"] == "forecast"  # a probability, never recorded


def test_pairing_sex_rule_is_species_specific():
    parents = {"A": (None, None), "B": (None, None)}
    # A valid intact pairing passes the sex rule (unrelated → not blocking).
    ok = gen.assess_pairing("goat", {"id": "A", "sex": "buck"}, {"id": "B", "sex": "doe"}, parents)
    assert ok["blocking"] is False
    # A wether (castrated male) is never a valid sire.
    wether = gen.assess_pairing("goat", {"id": "A", "sex": "wether"}, {"id": "B", "sex": "doe"}, parents)
    assert wether["blocking"] is True and any("buck" in w["detail"] for w in wether["warnings"])
    # Config drives the message per species (sheep names a ram).
    sheep = gen.assess_pairing("sheep", {"id": "A", "sex": "ewe"}, {"id": "B", "sex": "ewe"}, parents)
    assert sheep["blocking"] is True and any("ram" in w["detail"] for w in sheep["warnings"])
