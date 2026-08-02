"""
Greena — Swine Breeding Engine (Module 20, Milestone 3)

A PURE, deterministic engine: reproduction math for pigs over plain recorded data.
No I/O, no mutation — identical inputs always yield identical output. Everything
species-specific (gestation length, the dam/sire eligibility rules) is supplied by
:mod:`swine_config`, never branched here. Wright's genetics is delegated to
:mod:`swine_genetics` (which reuses the platform pedigree engine).

Every figure is honesty-labelled (Swine Doc 6 §5):
  recorded    — a value taken directly from a record
  calculated  — deterministically derived from records
  forecast    — a projected future date/value (never a recorded fact)
  estimated   — derived from an assumption (e.g. a default gestation)
  unknown     — the inputs to compute it were not recorded
  unavailable — the concept does not apply here

The engine never fabricates a rate: when the denominator is zero the result is
honestly ``unknown``, never a guessed number. Litter/farrowing performance metrics
(litter size, piglet survival) require farrowing data and arrive in Milestone 4.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services import swine_config as cfg

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
ESTIMATED = "estimated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _rate(numerator: int, denominator: int, detail: str) -> dict:
    if denominator <= 0:
        return _lab(UNKNOWN, None, "No denominator recorded yet.")
    return _lab(CALCULATED, round(numerator / denominator * 100, 1), detail)


# ── Breeding eligibility (Swine Doc 3 §7) ──────────────────────────────────────

def validate_eligibility(dam: dict, sire: dict | None, method: str, dam_has_open_cycle: bool) -> dict:
    """Deterministic breeding-eligibility check from recorded facts.

    ``dam``: {"sex","status"} — must be a breeding female (sow or gilt), active.
    ``sire``: {"sex","status"} or ``None`` — for natural mating (or AI with an
    on-farm boar) the sire must be an intact **boar**, active; a **barrow** is a
    castrated male and is NEVER a valid sire (the wether rule). For AI with external
    semen (``method='artificial'`` and no on-farm sire) the sire check is skipped —
    traceability then rests on the recorded semen source. Returns ``{"eligible":
    bool, "reasons": [...]}``.
    """
    reasons: list[str] = []
    if not cfg.is_breeding_female(dam.get("sex")):
        reasons.append("The dam must be recorded as a sow or a gilt.")
    if dam.get("status") != "active":
        reasons.append(f"The dam is not active (status: {dam.get('status')}).")

    if sire is not None:
        if not cfg.is_intact_male(sire.get("sex")):
            reasons.append("The sire must be recorded as a boar (a barrow is never a valid sire).")
        if sire.get("status") != "active":
            reasons.append(f"The sire is not active (status: {sire.get('status')}).")
    elif method != "artificial":
        # Natural / embryo-transfer services need a sire; only AI may omit an
        # on-farm boar (external semen).
        reasons.append("A sire is required for a natural service.")

    if dam_has_open_cycle:
        reasons.append("The dam already has an open breeding cycle.")
    return {"eligible": not reasons, "reasons": reasons}


# ── Gestation (Swine Doc 3 §9) ─────────────────────────────────────────────────

def expected_farrowing_date(service_date: date | None, gestation_days: int) -> date | None:
    """Forecast farrowing date = service_date + gestation. ``None`` if no service
    date. ``gestation_days`` is resolved by the caller (~114d, breed-overridable)."""
    if service_date is None:
        return None
    return service_date + timedelta(days=gestation_days)


def gestation_progress(
    service_date: date | None, today: date, gestation_days: int, *, breed_specified: bool = False
) -> dict:
    """Deterministic gestation progress. Days elapsed is a calculated fact; the
    remaining count and due date are forecasts against the gestation length
    (``estimated`` when it is the species default, ``forecast`` when a breed override
    was supplied)."""
    if service_date is None:
        return {
            "days_elapsed": _lab(UNKNOWN, None, "No service date recorded."),
            "days_remaining": _lab(UNKNOWN, None, "No service date recorded."),
            "expected_farrowing_date": _lab(UNKNOWN, None, "No service date recorded."),
            "overdue": False,
        }
    due = service_date + timedelta(days=gestation_days)
    elapsed = (today - service_date).days
    remaining = (due - today).days
    gest_label = FORECAST if breed_specified else ESTIMATED
    return {
        "days_elapsed": _lab(CALCULATED, elapsed, "today − service_date."),
        "days_remaining": _lab(gest_label, remaining, "expected farrowing − today."),
        "expected_farrowing_date": _lab(gest_label, due.isoformat(),
                                        f"service_date + {gestation_days} days gestation."),
        "overdue": remaining < 0,
    }


# ── Sire fertility (Swine Doc 6 §7) ────────────────────────────────────────────

def sire_fertility(breedings: list[dict]) -> dict:
    """Per-boar fertility from recorded services and their resolved outcomes.

    ``breedings`` each carry ``outcome`` — the breeding's resolved result, set from
    the pregnancy lifecycle (``pending`` until checked, then ``pregnant`` /
    ``not_pregnant`` / ``failed``)."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("outcome") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("outcome") == "pregnant")
    return {
        "services": _lab(RECORDED, services),
        "confirmed_pregnancies": _lab(RECORDED, pregnancies),
        "checked_services": _lab(RECORDED, checked),
        "fertility_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
    }


# ── Dam service history (Swine Doc 6 §7) ───────────────────────────────────────

def dam_service_history(breedings: list[dict]) -> dict:
    """Per-sow reproductive history from recorded services. Litter/farrowing
    productivity (litter size, piglet survival, farrowing interval) is added in
    Milestone 4 once farrowing records exist."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("outcome") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("outcome") == "pregnant")
    return {
        "services": _lab(RECORDED, services),
        "confirmed_pregnancies": _lab(RECORDED, pregnancies),
        "conception_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
    }


# ── Herd reproduction summary (Swine Doc 6 §5) ─────────────────────────────────

def reproduction_summary(breedings: list[dict]) -> dict:
    """Herd-level deterministic reproduction dashboard from breeding records.

    Conception rate is over *checked* services (a true fertility measure); the
    pregnancy rate is over all services. Farrowing rate, litter size and piglet
    survival require farrowing records and are added in Milestone 4.
    """
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("outcome") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("outcome") == "pregnant")
    ai = sum(1 for b in breedings if b.get("method") == "artificial")
    natural = sum(1 for b in breedings if b.get("method") == "natural")
    return {
        "total_services": _lab(RECORDED, services),
        "checked_services": _lab(RECORDED, checked),
        "total_pregnancies": _lab(RECORDED, pregnancies),
        "natural_services": _lab(RECORDED, natural),
        "ai_services": _lab(RECORDED, ai),
        "conception_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
    }


# ── Farrowing & litter performance (Swine Doc 3 §11, Doc 6 §8) — Milestone 4 ────

def farrowing_performance(litter: dict) -> dict:
    """Deterministic performance for one litter from recorded counts.

    ``litter``: {"total_born","born_alive","stillborn","mummified","weaned",
    "mortality","avg_birth_weight_kg","status"}. Pre-wean survival is only meaningful
    once the litter is weaned — otherwise it is honestly unavailable (still nursing).
    """
    total = int(litter.get("total_born") or 0)
    alive = int(litter.get("born_alive") or 0)
    stillborn = int(litter.get("stillborn") or 0)
    mummified = int(litter.get("mummified") or 0)
    weaned = int(litter.get("weaned") or 0)
    status = litter.get("status")

    if status in ("weaned", "closed"):
        survival = _rate(weaned, alive, "weaned ÷ born_alive × 100.")
    else:
        survival = _lab(UNAVAILABLE, None, "Litter not yet weaned.")

    return {
        "total_born": _lab(RECORDED, total),
        "born_alive": _lab(RECORDED, alive),
        "stillborn": _lab(RECORDED, stillborn),
        "mummified": _lab(RECORDED, mummified),
        "weaned": _lab(RECORDED, weaned),
        "pre_wean_mortality": _lab(RECORDED, int(litter.get("mortality") or 0)),
        "live_birth_rate_pct": _rate(alive, total, "born_alive ÷ total_born × 100."),
        "stillborn_rate_pct": _rate(stillborn, total, "stillborn ÷ total_born × 100."),
        "mummified_rate_pct": _rate(mummified, total, "mummified ÷ total_born × 100."),
        "pre_wean_survival_pct": survival,
    }


def litter_summary(litters: list[dict], services: int = 0) -> dict:
    """Herd-level litter/farrowing analytics (Swine Doc 6 §8).

    ``litters`` each a litter dict; ``services`` the count of recorded breeding
    services (for the farrowing rate). Rates never fabricate a denominator.
    """
    farrowings = len(litters)
    total_born = sum(int(x.get("total_born") or 0) for x in litters)
    born_alive = sum(int(x.get("born_alive") or 0) for x in litters)
    stillborn = sum(int(x.get("stillborn") or 0) for x in litters)
    mummified = sum(int(x.get("mummified") or 0) for x in litters)
    weaned = sum(int(x.get("weaned") or 0) for x in litters)
    weaned_litters = [x for x in litters if x.get("status") in ("weaned", "closed")]
    weaned_alive = sum(int(x.get("born_alive") or 0) for x in weaned_litters)

    return {
        "total_farrowings": _lab(RECORDED, farrowings),
        "total_born": _lab(RECORDED, total_born),
        "total_born_alive": _lab(RECORDED, born_alive),
        "total_stillborn": _lab(RECORDED, stillborn),
        "total_mummified": _lab(RECORDED, mummified),
        "total_weaned": _lab(RECORDED, weaned),
        "avg_litter_size": (
            _lab(CALCULATED, round(total_born / farrowings, 2), "total_born ÷ farrowings.")
            if farrowings else _lab(UNKNOWN, None, "No farrowings recorded.")
        ),
        "avg_born_alive": (
            _lab(CALCULATED, round(born_alive / farrowings, 2), "born_alive ÷ farrowings.")
            if farrowings else _lab(UNKNOWN, None, "No farrowings recorded.")
        ),
        "live_birth_rate_pct": _rate(born_alive, total_born, "Σborn_alive ÷ Σtotal_born × 100."),
        "stillborn_rate_pct": _rate(stillborn, total_born, "Σstillborn ÷ Σtotal_born × 100."),
        "mummified_rate_pct": _rate(mummified, total_born, "Σmummified ÷ Σtotal_born × 100."),
        "pre_wean_survival_pct": _rate(weaned, weaned_alive, "Σweaned ÷ Σborn_alive (weaned litters) × 100."),
        "farrowing_rate_pct": _rate(farrowings, services, "farrowings ÷ services × 100."),
    }
