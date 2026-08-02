"""
Greena — Small Ruminant Health Engine (Modules 18/19, Milestone 5)

A PURE, deterministic engine shared by goats and sheep: health, deworming, hoof
and mortality analytics over recorded facts. No I/O, no mutation. Every figure is
honesty-labelled and traceable to records.

Constitutional guarantee (frozen **§4.4**): the engine **never diagnoses**. It
reports *patterns* — mortality/recovery rates, cause and condition frequencies,
vaccination + deworming compliance, hoof-condition frequency — each stamped with a
"pattern, not a veterinary diagnosis" disclaimer. Missing denominators yield
``unknown``; a rate is never fabricated.
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


# ── Mortality ────────────────────────────────────────────────────────────────

def mortality_rate(deceased: int, total_ever: int) -> dict:
    return _rate(deceased, total_ever, "deceased ÷ total-ever animals × 100.")


def mortality_by_cause(mortality_records: list[dict]) -> list[dict]:
    counts = Counter(r.get("cause") or "unknown" for r in mortality_records)
    total = sum(counts.values())
    return [
        {"cause": cause, "count": _lab(RECORDED, n),
         "share_pct": _rate(n, total, "cause count ÷ total deaths × 100.")}
        for cause, n in counts.most_common()
    ]


def mortality_trend(mortality_records: list[dict]) -> list[dict]:
    counts: Counter = Counter()
    for r in mortality_records:
        d = r.get("occurred_on")
        if isinstance(d, date):
            counts[f"{d.year:04d}-{d.month:02d}"] += 1
    return [{"month": m, "deaths": _lab(RECORDED, counts[m])} for m in sorted(counts)]


# ── Recovery / conditions ──────────────────────────────────────────────────────

_CLINICAL_TYPES = ("illness", "injury", "treatment", "surgery")


def recovery_rate(health_records: list[dict]) -> dict:
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
    counts = Counter(r.get("event_type") or "note" for r in health_records)
    return [{"event_type": t, "count": _lab(RECORDED, n)} for t, n in counts.most_common()]


# ── Compliance (vaccination + deworming) ───────────────────────────────────────

def _compliance(records: list[dict], today: date, label_total: str) -> dict:
    with_due = [r for r in records if r.get("next_due_on")]
    overdue = [r for r in with_due if r["next_due_on"] < today]
    upcoming = [r for r in with_due if r["next_due_on"] >= today]
    return {
        label_total: _lab(RECORDED, len(records)),
        "scheduled_next": _lab(RECORDED, len(with_due)),
        "overdue": _lab(RECORDED, len(overdue), "Next-due date already passed."),
        "upcoming": _lab(RECORDED, len(upcoming)),
    }


def vaccination_compliance(vaccinations: list[dict], today: date) -> dict:
    return _compliance(vaccinations, today, "total_vaccinations")


def deworming_compliance(dewormings: list[dict], today: date) -> dict:
    """Deworming compliance + recorded FAMACHA distribution (anaemia scores).
    FAMACHA is a recorded assessment; the engine never infers parasite status."""
    base = _compliance(dewormings, today, "total_dewormings")
    famacha = Counter(str(r["famacha_score"]) for r in dewormings if r.get("famacha_score") is not None)
    base["famacha_distribution"] = [
        {"score": s, "count": _lab(RECORDED, n)} for s, n in sorted(famacha.items())
    ]
    return base


# ── Hoof care ──────────────────────────────────────────────────────────────────

def hoof_summary(hoof_records: list[dict], today: date) -> dict:
    """Hoof-condition frequency + overdue inspections (recorded patterns)."""
    conditions = Counter(r.get("condition") or "unknown" for r in hoof_records)
    with_due = [r for r in hoof_records if r.get("next_due_on")]
    overdue = [r for r in with_due if r["next_due_on"] < today]
    return {
        "total_records": _lab(RECORDED, len(hoof_records)),
        "condition_frequency": [{"condition": c, "count": _lab(RECORDED, n)}
                                for c, n in conditions.most_common()],
        "overdue_followups": _lab(RECORDED, len(overdue), "Scheduled hoof follow-up date already passed."),
    }


# ── Composite summary ──────────────────────────────────────────────────────────

def health_summary(
    *, deceased: int, total_ever: int, mortality_records: list[dict],
    health_records: list[dict], vaccinations: list[dict], dewormings: list[dict],
    hoof_records: list[dict], today: date,
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
        "deworming_compliance": deworming_compliance(dewormings, today),
        "hoof_summary": hoof_summary(hoof_records, today),
        "disclaimer": _DISCLAIMER,
    }
