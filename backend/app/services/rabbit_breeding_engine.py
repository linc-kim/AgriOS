"""
Greena — Rabbit Breeding Engine (Module 17, Milestone 3)

A PURE, deterministic engine (GMIS §1.3, §5): rabbit reproduction math over plain
recorded data. No I/O, no mutation — identical inputs always yield identical
output, so it is trivially testable and reusable by services, Mission Control and
(for explanation only) ARIA. Genetics (Wright's inbreeding/relatedness) is NOT
here — it is delegated to the shared platform ``pedigree_engine`` (ledger
CON-M3-1) via :mod:`rabbit_genetics`.

Every figure is honesty-labelled (Spec Part 9 §17):
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

# ── Honesty labels ─────────────────────────────────────────────────────────────

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
ESTIMATED = "estimated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

DEFAULT_GESTATION_DAYS = 31  # standard domestic-rabbit gestation (ledger CON-M3-4)


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


# ── Breeding eligibility (Spec Part 4 §6) ──────────────────────────────────────

def validate_eligibility(doe: dict, buck: dict, doe_has_open_breeding: bool) -> dict:
    """Deterministic breeding-eligibility check from recorded facts.

    ``doe``/``buck``: {"sex","status"}. Returns ``{"eligible": bool,
    "reasons": [...]}`` — the reasons list is empty when eligible. The engine
    states rules; the service supplies ``doe_has_open_breeding`` from the DB.
    """
    reasons: list[str] = []
    if doe.get("sex") != "doe":
        reasons.append("The dam must be recorded as a doe.")
    if buck.get("sex") != "buck":
        reasons.append("The sire must be recorded as a buck.")
    if doe.get("status") != "active":
        reasons.append(f"The doe is not active (status: {doe.get('status')}).")
    if buck.get("status") != "active":
        reasons.append(f"The buck is not active (status: {buck.get('status')}).")
    if doe_has_open_breeding:
        reasons.append("The doe already has an open breeding cycle.")
    return {"eligible": not reasons, "reasons": reasons}


# ── Gestation (Spec Part 3 §7) ─────────────────────────────────────────────────

def expected_kindling_date(service_date: date | None, gestation_days: int | None = None) -> date | None:
    """Forecast kindling date = service_date + gestation. ``None`` if no service
    date. Uses the breed gestation when supplied, else the default (an estimate)."""
    if service_date is None:
        return None
    days = gestation_days if gestation_days else DEFAULT_GESTATION_DAYS
    return service_date + timedelta(days=days)


def gestation_progress(
    service_date: date | None, today: date, gestation_days: int | None = None
) -> dict:
    """Deterministic gestation progress. Days elapsed is a calculated fact; the
    remaining count and the due date are forecasts against the (possibly default)
    gestation length."""
    if service_date is None:
        return {
            "days_elapsed": _lab(UNKNOWN, None, "No service date recorded."),
            "days_remaining": _lab(UNKNOWN, None, "No service date recorded."),
            "expected_kindling_date": _lab(UNKNOWN, None, "No service date recorded."),
            "overdue": False,
        }
    days = gestation_days if gestation_days else DEFAULT_GESTATION_DAYS
    due = service_date + timedelta(days=days)
    elapsed = (today - service_date).days
    remaining = (due - today).days
    gest_label = FORECAST if gestation_days else ESTIMATED
    return {
        "days_elapsed": _lab(CALCULATED, elapsed, "today − service_date."),
        "days_remaining": _lab(gest_label, remaining, "expected kindling − today."),
        "expected_kindling_date": _lab(gest_label, due.isoformat(),
                                       f"service_date + {days} days gestation."),
        "overdue": remaining < 0,
    }


# ── Litter performance (Spec Part 2 §6, Part 4 §6) ─────────────────────────────

def litter_performance(litter: dict) -> dict:
    """Deterministic litter performance from recorded birth/wean counts.

    ``litter``: {"total_kits","live_kits","stillbirths","weaned_kits","mortality",
    "avg_birth_weight_g","status"}. Weaning survival is only meaningful once the
    litter is weaned/closed — otherwise it is honestly unavailable (still nursing).
    """
    total = int(litter.get("total_kits") or 0)
    live = int(litter.get("live_kits") or 0)
    stillbirths = int(litter.get("stillbirths") or 0)
    weaned = int(litter.get("weaned_kits") or 0)
    status = litter.get("status")

    live_birth_rate = _rate(live, total, "live_kits ÷ total_kits × 100.")

    if status in ("weaned", "closed"):
        weaning_survival = _rate(weaned, live, "weaned_kits ÷ live_kits × 100.")
    else:
        weaning_survival = _lab(UNAVAILABLE, None, "Litter not yet weaned.")

    return {
        "total_kits": _lab(RECORDED, total),
        "live_kits": _lab(RECORDED, live),
        "stillbirths": _lab(RECORDED, stillbirths),
        "weaned_kits": _lab(RECORDED, weaned),
        "pre_wean_mortality": _lab(RECORDED, int(litter.get("mortality") or 0)),
        "avg_birth_weight_g": (
            _lab(RECORDED, _num(litter.get("avg_birth_weight_g")))
            if litter.get("avg_birth_weight_g") is not None
            else _lab(UNKNOWN, None, "No birth weight recorded.")
        ),
        "live_birth_rate_pct": live_birth_rate,
        "weaning_survival_pct": weaning_survival,
    }


# ── Doe productivity (Spec Part 2 §13, Part 7 §4) ──────────────────────────────

def _kindling_interval_days(kindling_dates: list[date]) -> float | None:
    dates = sorted(d for d in kindling_dates if d is not None)
    if len(dates) < 2:
        return None
    gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    return round(sum(gaps) / len(gaps), 1)


def doe_productivity(breedings: list[dict], litters: list[dict]) -> dict:
    """Per-doe reproductive performance. ``breedings`` each {"service_date",
    "pregnancy_result","status"}; ``litters`` each litter dict (see
    ``litter_performance``) plus ``kindling_date``."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    kindlings = len(litters)
    total_kits = sum(int(li.get("total_kits") or 0) for li in litters)
    live_kits = sum(int(li.get("live_kits") or 0) for li in litters)
    weaned = sum(int(li.get("weaned_kits") or 0) for li in litters)
    interval = _kindling_interval_days([li.get("kindling_date") for li in litters])

    return {
        "services": _lab(RECORDED, services),
        "pregnancies": _lab(RECORDED, pregnancies),
        "kindlings": _lab(RECORDED, kindlings),
        "litters": _lab(RECORDED, kindlings),
        "total_kits_born": _lab(RECORDED, total_kits),
        "total_kits_weaned": _lab(RECORDED, weaned),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
        "kindling_rate_pct": _rate(kindlings, services, "kindlings ÷ services × 100."),
        "avg_litter_size": (
            _lab(CALCULATED, round(total_kits / kindlings, 1), "total_kits ÷ litters.")
            if kindlings else _lab(UNKNOWN, None, "No litters recorded.")
        ),
        "kit_survival_pct": _rate(weaned, live_kits, "weaned ÷ live_kits × 100."),
        "avg_kindling_interval_days": (
            _lab(CALCULATED, interval, "Mean gap between consecutive kindlings.")
            if interval is not None else _lab(UNKNOWN, None, "Fewer than two litters recorded.")
        ),
    }


def buck_fertility(breedings: list[dict]) -> dict:
    """Per-buck fertility from recorded services and their pregnancy results."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("pregnancy_result") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    return {
        "services": _lab(RECORDED, services),
        "confirmed_pregnancies": _lab(RECORDED, pregnancies),
        "checked_services": _lab(RECORDED, checked),
        "fertility_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
    }


# ── Herd reproduction summary (Spec Part 7 §4) ─────────────────────────────────

def reproduction_summary(breedings: list[dict], litters: list[dict]) -> dict:
    """Herd-level deterministic reproduction dashboard."""
    services = sum(1 for b in breedings if b.get("service_date") is not None)
    checked = sum(1 for b in breedings if b.get("pregnancy_result") in ("pregnant", "not_pregnant"))
    pregnancies = sum(1 for b in breedings if b.get("pregnancy_result") == "pregnant")
    kindlings = len(litters)
    total_kits = sum(int(li.get("total_kits") or 0) for li in litters)
    live_kits = sum(int(li.get("live_kits") or 0) for li in litters)
    weaned = sum(int(li.get("weaned_kits") or 0) for li in litters)

    return {
        "total_services": _lab(RECORDED, services),
        "total_pregnancies": _lab(RECORDED, pregnancies),
        "total_litters": _lab(RECORDED, kindlings),
        "total_kits_born": _lab(RECORDED, total_kits),
        "total_kits_weaned": _lab(RECORDED, weaned),
        "conception_rate_pct": _rate(pregnancies, checked, "pregnancies ÷ checked services × 100."),
        "pregnancy_rate_pct": _rate(pregnancies, services, "pregnancies ÷ services × 100."),
        "kindling_rate_pct": _rate(kindlings, services, "kindlings ÷ services × 100."),
        "avg_litter_size": (
            _lab(CALCULATED, round(total_kits / kindlings, 1), "total_kits ÷ litters.")
            if kindlings else _lab(UNKNOWN, None, "No litters recorded.")
        ),
        "kit_survival_pct": _rate(weaned, live_kits, "weaned ÷ live_kits × 100."),
    }


# ── Breeding-value ranking (Spec Part 7 §5 — advisory) ─────────────────────────

def breeding_value_ranking(does: list[dict]) -> list[dict]:
    """Rank does by a transparent, deterministic composite of recorded
    performance (advisory only — never a directive). ``does``: each
    {"rabbit_id","internal_ref","kindlings","total_kits_weaned","kit_survival_pct"}.

    Score = kits weaned (the outcome that matters), tie-broken by survival then
    litters. Does with no litters are unranked (insufficient evidence), not
    penalised with a fabricated zero score.
    """
    ranked: list[dict] = []
    for d in does:
        kindlings = int(d.get("kindlings") or 0)
        weaned = int(d.get("total_kits_weaned") or 0)
        survival = d.get("kit_survival_pct")
        if kindlings == 0:
            ranked.append({
                "rabbit_id": d.get("rabbit_id"),
                "internal_ref": d.get("internal_ref"),
                "score": _lab(UNKNOWN, None, "No litters recorded — insufficient evidence."),
                "weaned": weaned, "kindlings": kindlings,
            })
            continue
        score = round(weaned + (float(survival) / 100 if survival else 0) + kindlings * 0.1, 3)
        ranked.append({
            "rabbit_id": d.get("rabbit_id"),
            "internal_ref": d.get("internal_ref"),
            "score": _lab(CALCULATED, score,
                          "kits weaned + survival fraction + 0.1 × litters (advisory)."),
            "weaned": weaned, "kindlings": kindlings,
        })
    # Ranked entries first (by score desc), then the unranked (unknown score).
    ranked.sort(key=lambda r: (r["score"]["value"] is not None, r["score"]["value"] or 0), reverse=True)
    return ranked
