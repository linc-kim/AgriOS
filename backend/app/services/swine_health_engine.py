"""
Greena — Swine Health Engine (Module 20, Milestone 6)

A PURE, deterministic engine over recorded clinical data. No I/O, no mutation.

Constitutional guarantee (frozen **§4.4**): the engine **never diagnoses** and never
prescribes. It aggregates recorded facts (disease cases, vaccinations, treatments,
mortality, withdrawals) into honesty-labelled counts and rates, each carrying a
"pattern, not a veterinary diagnosis" disclaimer where it summarises health. Missing
denominators yield ``unknown``, never a fabricated rate. The shape here is generic
(counts/rates over events) so it can later back a shared livestock-health engine for
poultry / fish / small ruminants / dairy / rabbits.
"""

from __future__ import annotations

from datetime import date
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"

_DISCLAIMER = (
    "Deterministic summary of recorded clinical facts — a pattern, not a veterinary "
    "diagnosis. Diagnoses and treatment decisions require a qualified veterinarian."
)


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _rate(numerator: int, denominator: int, detail: str) -> dict:
    if denominator <= 0:
        return _lab(UNKNOWN, None, "No denominator recorded.")
    return _lab(CALCULATED, round(numerator / denominator * 100, 1), detail)


def mortality_rate(deaths: int, population: int) -> dict:
    """Deaths ÷ population × 100 (population = deaths + currently-alive at risk)."""
    return _rate(deaths, population, "deaths ÷ population × 100.")


def disease_incidence(cases: int, population: int) -> dict:
    return _rate(cases, population, "disease cases ÷ population × 100.")


def active_withdrawals(treatments: list[dict], today: date) -> dict:
    """Treatments whose recorded meat-withdrawal date has not yet passed (a compliance
    fact, never inferred). ``treatments`` each {"withdrawal_until": date|None}."""
    active = [t for t in treatments if t.get("withdrawal_until") and t["withdrawal_until"] >= today]
    return _lab(RECORDED, len(active), "Treatments with a withdrawal period still in effect.")


def health_summary(counts: dict, *, today: date | None = None, treatments: list[dict] | None = None) -> dict:
    """Herd health dashboard from recorded counts (Swine Doc 6 §11).

    ``counts`` supplies recorded tallies (open_disease_cases, confirmed_cases,
    vaccinations, treatments, procedures, observations, lab_tests, active_isolations,
    deaths, population). Everything is a recorded/calculated fact with the §4.4
    disclaimer — nothing here is a diagnosis.
    """
    deaths = int(counts.get("deaths") or 0)
    population = int(counts.get("population") or 0)
    cases = int(counts.get("total_disease_cases") or 0)
    withdrawals = active_withdrawals(treatments or [], today or date.today())

    return {
        "open_disease_cases": _lab(RECORDED, int(counts.get("open_disease_cases") or 0)),
        "confirmed_disease_cases": _lab(RECORDED, int(counts.get("confirmed_cases") or 0)),
        "total_disease_cases": _lab(RECORDED, cases),
        "vaccinations": _lab(RECORDED, int(counts.get("vaccinations") or 0)),
        "treatments": _lab(RECORDED, int(counts.get("treatments") or 0)),
        "procedures": _lab(RECORDED, int(counts.get("procedures") or 0)),
        "observations": _lab(RECORDED, int(counts.get("observations") or 0)),
        "lab_tests": _lab(RECORDED, int(counts.get("lab_tests") or 0)),
        "active_isolations": _lab(RECORDED, int(counts.get("active_isolations") or 0)),
        "active_withdrawals": withdrawals,
        "deaths": _lab(RECORDED, deaths),
        "mortality_rate_pct": mortality_rate(deaths, population),
        "disease_incidence_pct": disease_incidence(cases, population),
        "disclaimer": _DISCLAIMER,
    }
