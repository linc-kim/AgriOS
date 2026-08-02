"""
Greena — Small Ruminant Breeding Engine (Modules 18/19, Milestone 3)

A PURE, deterministic engine: reproduction math for goats and sheep over plain
recorded data. No I/O, no mutation — identical inputs always yield identical
output. One engine serves both species; everything species-specific (gestation
length, the dam/sire biological roles, the kid/lamb noun) is passed in from the
species config by the service, never branched here. Wright's genetics
(inbreeding/relatedness) is delegated to :mod:`small_ruminant_genetics`.

Every figure is honesty-labelled (Goat Doc 8 §15):
  recorded    — a value taken directly from a record
  calculated  — deterministically derived from records
  forecast    — a projected future date/value (never a recorded fact)
  estimated   — derived from an assumption (e.g. a default gestation)
  unknown     — the inputs to compute it were not recorded
  unavailable — the concept does not apply here

The engine never fabricates a rate: when the denominator is zero the result is
honestly ``unknown``, never a guessed number.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.services import small_ruminant_species_config as cfg

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
ESTIMATED = "estimated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _num(v) -> float | None:
    if v is None:
        return None
    return float(v) if isinstance(v, Decimal) else v


def _rate(numerator: int, denominator: int, detail: str) -> dict:
    if denominator <= 0:
        return _lab(UNKNOWN, None, "No denominator recorded yet.")
    return _lab(CALCULATED, round(numerator / denominator * 100, 1), detail)


# ── Breeding eligibility (Goat Doc 3 §7) — species-neutral via biological role ─

def validate_eligibility(species: str, dam: dict, sire: dict, dam_has_open_breeding: bool) -> dict:
    """Deterministic breeding-eligibility check from recorded facts.

    ``dam``/``sire``: {"sex","status"}. The sex rule is expressed biologically
    (dam=female, sire=male) and resolved through the species config, so the same
    logic validates goat doe×buck and sheep ewe×ram. Returns ``{"eligible": bool,
    "reasons": [...]}``.
    """
    reasons: list[str] = []
    female_term = cfg.get_config(species)["female_term"]
    male_term = cfg.get_config(species)["male_term"]
    # Breeding requires INTACT animals: an intact female (doe/ewe) and an intact
    # male (buck/ram). A wether is a castrated male — biologically male ancestry,
    # but infertile, so it is never a valid sire.
    if dam.get("sex") != female_term:
        reasons.append(f"The dam must be recorded as a {female_term}.")
    if sire.get("sex") != male_term:
        reasons.append(f"The sire must be recorded as a {male_term}.")
    if dam.get("status") != "active":
        reasons.append(f"The dam is not active (status: {dam.get('status')}).")
    if sire.get("status") != "active":
        reasons.append(f"The sire is not active (status: {sire.get('status')}).")
    if dam_has_open_breeding:
        reasons.append("The dam already has an open breeding cycle.")
    return {"eligible": not reasons, "reasons": reasons}


# ── Gestation (Goat Doc 3 §12.2) ───────────────────────────────────────────────

def expected_birth_date(
    service_date: date | None, gestation_days: int, *, breed_specified: bool = False
) -> date | None:
    """Forecast birth date = service_date + gestation. ``None`` if no service date.
    ``gestation_days`` is resolved by the caller from the species config (goat 150,
    sheep 147) with an optional breed override."""
    if service_date is None:
        return None
    return service_date + timedelta(days=gestation_days)


def gestation_progress(
    service_date: date | None, today: date, gestation_days: int, *, breed_specified: bool = False
) -> dict:
    """Deterministic gestation progress. Days elapsed is a calculated fact; the
    remaining count and due date are forecasts against the gestation length
    (``estimated`` when it is the species default, ``forecast`` when a breed
    override was supplied)."""
    if service_date is None:
        return {
            "days_elapsed": _lab(UNKNOWN, None, "No service date recorded."),
            "days_remaining": _lab(UNKNOWN, None, "No service date recorded."),
            "expected_birth_date": _lab(UNKNOWN, None, "No service date recorded."),
            "overdue": False,
        }
    due = service_date + timedelta(days=gestation_days)
    elapsed = (today - service_date).days
    remaining = (due - today).days
    gest_label = FORECAST if breed_specified else ESTIMATED
    return {
        "days_elapsed": _lab(CALCULATED, elapsed, "today − service_date."),
        "days_remaining": _lab(gest_label, remaining, "expected birth − today."),
        "expected_birth_date": _lab(gest_label, due.isoformat(),
                                    f"service_date + {gestation_days} days gestation."),
        "overdue": remaining < 0,
    }


# ── Birth performance (Goat Doc 2 §9) ──────────────────────────────────────────

def birth_performance(birth: dict) -> dict:
    """Deterministic performance for one birth (kidding/lambing) from recorded
    counts. ``birth``: {"total_born","live_born","stillborn","weaned","mortality",
    "avg_birth_weight_kg","status"}. Weaning survival is only meaningful once the
    litter is weaned/closed — otherwise it is honestly unavailable (still nursing).
    """
    total = int(birth.get("total_born") or 0)
    live = int(birth.get("live_born") or 0)
    stillborn = int(birth.get("stillborn") or 0)
    weaned = int(birth.get("weaned") or 0)
    status = birth.get("status")

    live_birth_rate = _rate(live, total, "live_born ÷ total_born × 100.")
    if status in ("weaned", "closed"):
        weaning_survival = _rate(weaned, live, "weaned ÷ live_born × 100.")
    else:
        weaning_survival = _lab(UNAVAILABLE, None, "Litter not yet weaned.")

    return {
        "total_born": _lab(RECORDED, total),
        "live_born": _lab(RECORDED, live),
        "stillborn": _lab(RECORDED, stillborn),
        "weaned": _lab(RECORDED, weaned),
        "pre_wean_mortality": _lab(RECORDED, int(birth.get("mortality") or 0)),
        "avg_birth_weight_kg": (
            _lab(RECORDED, _num(birth.get("avg_birth_weight_kg")))
            if birth.get("avg_birth_weight_kg") is not None
            else _lab(UNKNOWN, None, "No birth weight recorded.")
        ),
        "live_birth_rate_pct": live_birth_rate,
        "weaning_survival_pct": weaning_survival,
    }


# ── Dam productivity (Goat Doc 7 §4) ───────────────────────────────────────────

def _birth_interval_days(birth_dates: list[date]) -> float | None:
    dates = sorted(d for d in birth_dates if d is not None)
    if len(dates) < 2:
        return None
    gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    return round(sum(gaps) / len(gaps), 1)


def dam_productivity(breedings: list[dict], births: list[dict]) -> dict:
    """Per-dam reproductive performance. ``breedings`` each {"service_date",
    "pregnancy_result"}; ``births`` each birth dict plus ``birth_date``."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    parturitions = len(births)
    total_born = sum(int(bi.get("total_born") or 0) for bi in births)
    live_born = sum(int(bi.get("live_born") or 0) for bi in births)
    weaned = sum(int(bi.get("weaned") or 0) for bi in births)
    interval = _birth_interval_days([bi.get("birth_date") for bi in births])

    return {
        "services": _lab(RECORDED, services),
        "pregnancies": _lab(RECORDED, pregnancies),
        "births": _lab(RECORDED, parturitions),
        "total_born": _lab(RECORDED, total_born),
        "total_weaned": _lab(RECORDED, weaned),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
        "birth_rate_pct": _rate(parturitions, services, "births ÷ services × 100."),
        "avg_litter_size": (
            _lab(CALCULATED, round(total_born / parturitions, 2), "total_born ÷ births.")
            if parturitions else _lab(UNKNOWN, None, "No births recorded.")
        ),
        "offspring_survival_pct": _rate(weaned, live_born, "weaned ÷ live_born × 100."),
        "avg_birth_interval_days": (
            _lab(CALCULATED, interval, "Mean gap between consecutive births.")
            if interval is not None else _lab(UNKNOWN, None, "Fewer than two births recorded.")
        ),
    }


def sire_fertility(breedings: list[dict]) -> dict:
    """Per-sire fertility from recorded services and their pregnancy results."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("pregnancy_result") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    return {
        "services": _lab(RECORDED, services),
        "confirmed_pregnancies": _lab(RECORDED, pregnancies),
        "checked_services": _lab(RECORDED, checked),
        "fertility_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
    }


# ── Herd/flock reproduction summary (Goat Doc 7 §4) ────────────────────────────

def reproduction_summary(breedings: list[dict], births: list[dict]) -> dict:
    """Herd/flock-level deterministic reproduction dashboard."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("pregnancy_result") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    parturitions = len(births)
    total_born = sum(int(bi.get("total_born") or 0) for bi in births)
    live_born = sum(int(bi.get("live_born") or 0) for bi in births)
    weaned = sum(int(bi.get("weaned") or 0) for bi in births)

    return {
        "total_services": _lab(RECORDED, services),
        "total_pregnancies": _lab(RECORDED, pregnancies),
        "total_births": _lab(RECORDED, parturitions),
        "total_offspring_born": _lab(RECORDED, total_born),
        "total_offspring_weaned": _lab(RECORDED, weaned),
        "conception_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
        "birth_rate_pct": _rate(parturitions, services, "births ÷ services × 100."),
        "avg_litter_size": (
            _lab(CALCULATED, round(total_born / parturitions, 2), "total_born ÷ births.")
            if parturitions else _lab(UNKNOWN, None, "No births recorded.")
        ),
        "offspring_survival_pct": _rate(weaned, live_born, "weaned ÷ live_born × 100."),
    }
