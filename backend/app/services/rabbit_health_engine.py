"""
Greena — Rabbit Health Engine (Module 17, Milestone 5)

A PURE, deterministic engine (GMIS §1.3, §5): health and mortality analytics over
recorded facts. No I/O, no mutation. Every figure is honesty-labelled and every
conclusion is traceable to recorded records.

Constitutional guarantee (frozen **§4.4**): the engine **never diagnoses**. It
reports *patterns* — mortality/recovery rates, cause and condition frequencies,
vaccination compliance — each stamped with a "pattern, not a veterinary
diagnosis" disclaimer. Missing denominators yield ``unknown``; a rate is never
fabricated (Spec Part 9 §19).
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

_DISCLAIMER = "A recorded pattern, not a veterinary diagnosis."


def _lab(label: str, value: Any, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _rate(num: int, den: int, detail: str) -> dict:
    if den <= 0:
        return _lab(UNKNOWN, None, "No denominator recorded yet.")
    return _lab(CALCULATED, round(num / den * 100, 1), detail)


# ── Mortality ────────────────────────────────────────────────────────────────────

def mortality_rate(deceased: int, total_ever: int) -> dict:
    """Deaths ÷ all rabbits ever recorded × 100 (Spec Part 7 §7)."""
    return _rate(deceased, total_ever, "deceased ÷ total-ever rabbits × 100.")


def mortality_by_cause(mortality_records: list[dict]) -> list[dict]:
    """Cause breakdown (recorded counts + share). ``records``: each {"cause": str}.
    A pattern only — never an inference of what will happen next."""
    counts = Counter(r.get("cause") or "unknown" for r in mortality_records)
    total = sum(counts.values())
    return [
        {"cause": cause, "count": _lab(RECORDED, n),
         "share_pct": _rate(n, total, "cause count ÷ total deaths × 100.")}
        for cause, n in counts.most_common()
    ]


def mortality_trend(mortality_records: list[dict]) -> list[dict]:
    """Monthly death counts (recorded). ``records``: each {"occurred_on": date}."""
    counts: Counter = Counter()
    for r in mortality_records:
        d = r.get("occurred_on")
        if isinstance(d, date):
            counts[f"{d.year:04d}-{d.month:02d}"] += 1
    return [{"month": m, "deaths": _lab(RECORDED, counts[m])} for m in sorted(counts)]


# ── Recovery / treatment ──────────────────────────────────────────────────────────

_CLINICAL_TYPES = ("illness", "injury", "treatment", "surgery")


def recovery_rate(health_records: list[dict]) -> dict:
    """Resolved ÷ concluded clinical events × 100. Only events with a terminal
    status (resolved) count as concluded; still-open/ongoing events are excluded
    so the rate reflects actual outcomes, not optimism."""
    clinical = [r for r in health_records if r.get("event_type") in _CLINICAL_TYPES]
    concluded = [r for r in clinical if r.get("status") in ("resolved",)]
    ongoing = [r for r in clinical if r.get("status") in ("open", "ongoing")]
    denom = len(concluded) + len(ongoing)
    return {
        "clinical_events": _lab(RECORDED, len(clinical)),
        "resolved": _lab(RECORDED, len(concluded)),
        "ongoing": _lab(RECORDED, len(ongoing)),
        "recovery_rate_pct": _rate(len(concluded), denom, "resolved ÷ (resolved + ongoing) × 100."),
    }


def condition_frequency(health_records: list[dict]) -> list[dict]:
    """Recurring-condition pattern: counts by event type (Spec Part 7 §7). A
    pattern for the farmer's attention — never a diagnosis."""
    counts = Counter(r.get("event_type") or "note" for r in health_records)
    return [{"event_type": t, "count": _lab(RECORDED, n)} for t, n in counts.most_common()]


# ── Vaccination compliance ────────────────────────────────────────────────────────

def vaccination_compliance(vaccinations: list[dict], today: date) -> dict:
    """Compliance from recorded vaccinations with a ``next_due_on``. Overdue =
    due date already passed (recorded facts, no forecast)."""
    with_due = [v for v in vaccinations if v.get("next_due_on")]
    overdue = [v for v in with_due if v["next_due_on"] < today]
    upcoming = [v for v in with_due if v["next_due_on"] >= today]
    return {
        "total_vaccinations": _lab(RECORDED, len(vaccinations)),
        "scheduled_next_doses": _lab(RECORDED, len(with_due)),
        "overdue": _lab(RECORDED, len(overdue), "Next-dose date already passed."),
        "upcoming": _lab(RECORDED, len(upcoming)),
    }


# ── Composite summary ─────────────────────────────────────────────────────────────

def health_summary(
    *, deceased: int, total_ever: int, mortality_records: list[dict],
    health_records: list[dict], vaccinations: list[dict], today: date,
) -> dict:
    """Compose the deterministic health picture. Every block is a recorded/
    calculated pattern; nothing here is a diagnosis (frozen §4.4)."""
    return {
        "mortality_rate_pct": mortality_rate(deceased, total_ever),
        "mortality_by_cause": mortality_by_cause(mortality_records),
        "mortality_trend": mortality_trend(mortality_records),
        "recovery": recovery_rate(health_records),
        "condition_frequency": condition_frequency(health_records),
        "vaccination_compliance": vaccination_compliance(vaccinations, today),
        "disclaimer": _DISCLAIMER,
    }
