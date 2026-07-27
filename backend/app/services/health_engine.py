"""
Greena — Health Engine (Module 15, Part 6)

A PURE, deterministic engine for individual-bird health analytics (Doc 14 §2-3,
Doc 09 §10). Given recorded health data it computes weight/growth trends,
mortality and disease indicators, vaccination coverage and preventive-care-due —
all honesty-labelled. It never diagnoses, never fabricates a rate, and reports
"not enough recorded data" when a denominator is zero (Doc 04 §19, Doc 15 §6/§15).

The platform's flock-scoped health service cannot represent an individual bird's
history, so this is a distinct individual-bird engine, not a duplicate.
"""

from __future__ import annotations

from datetime import date, timedelta

RECORDED = "recorded"
CALCULATED = "calculated"
UNKNOWN = "unknown"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


# ── Weight / growth trend ─────────────────────────────────────────────────────

def weight_trend(weight_records: list[dict]) -> dict:
    """Deterministic weight trend from recorded weights (Doc 02 §17).

    ``weight_records``: each {"recorded_on": date, "weight_grams": number}. The
    series is sorted ascending; direction is a plain comparison of first vs latest.
    """
    pts = sorted(
        [r for r in weight_records if r.get("weight_grams") is not None],
        key=lambda r: r["recorded_on"],
    )
    if not pts:
        return {
            "count": _lbl(RECORDED, 0),
            "latest": _lbl(UNKNOWN, None, "No weights recorded."),
            "change_grams": _lbl(UNKNOWN, None),
            "direction": _lbl(UNKNOWN, None),
        }
    first = float(pts[0]["weight_grams"])
    latest = float(pts[-1]["weight_grams"])
    change = round(latest - first, 2)
    direction = "stable" if abs(change) < 1e-9 else ("up" if change > 0 else "down")
    return {
        "count": _lbl(RECORDED, len(pts)),
        "latest": _lbl(RECORDED, latest, f"Recorded {pts[-1]['recorded_on']}."),
        "first": _lbl(RECORDED, first, f"Recorded {pts[0]['recorded_on']}."),
        "change_grams": _lbl(CALCULATED, change, "latest − first recorded weight."),
        "direction": _lbl(CALCULATED, direction),
        "series": [{"date": str(p["recorded_on"]), "grams": float(p["weight_grams"])} for p in pts],
    }


# ── Coverage / rates ──────────────────────────────────────────────────────────

def _rate(num: int, den: int, detail: str) -> dict:
    if den <= 0:
        return _lbl(UNKNOWN, None, "Not enough recorded data.")
    return _lbl(CALCULATED, round(num / den * 100, 1), detail)


def vaccination_coverage(active_birds: int, vaccinated_birds: int) -> dict:
    return _rate(vaccinated_birds, active_birds, "birds with a vaccination record ÷ active birds × 100.")


def mortality_rate(deceased: int, total_ever: int) -> dict:
    return _rate(deceased, total_ever, "deceased ÷ all birds ever recorded × 100.")


def due_soon(records: list[dict], today: date, window_days: int = 14) -> dict:
    """Preventive-care items due within a window (Doc 11 §5). Records carrying a
    ``next_due_on`` that falls on/before today+window and are not resolved."""
    horizon = today + timedelta(days=window_days)
    due = [
        r for r in records
        if r.get("next_due_on") is not None
        and r.get("status") != "resolved"
        and r["next_due_on"] <= horizon
    ]
    overdue = [r for r in due if r["next_due_on"] < today]
    return {
        "due_count": _lbl(CALCULATED, len(due), f"Preventive items due within {window_days} days."),
        "overdue_count": _lbl(CALCULATED, len(overdue), "Preventive items already past due."),
    }


# ── Farm health summary (Mission Control / ARIA read this) ────────────────────

def health_summary(
    *,
    records: list[dict],
    active_birds: int,
    total_ever: int,
    deceased: int,
    vaccinated_birds: int,
    active_quarantines: int,
    active_diseases: int,
    today: date,
) -> dict:
    """Compose a deterministic, honesty-labelled farm-health snapshot. The
    strategic layer (Mission Control) reads this to weigh mission risk rather than
    recomputing it (Doc 08 §6, Doc 15 §7)."""
    by_type: dict[str, int] = {}
    for r in records:
        t = r.get("record_type", "observation")
        by_type[t] = by_type.get(t, 0) + 1
    due = due_soon(records, today)
    return {
        "records_total": _lbl(RECORDED, len(records)),
        "records_by_type": by_type,
        "active_birds": _lbl(RECORDED, active_birds),
        "mortality_rate_pct": mortality_rate(deceased, total_ever),
        "vaccination_coverage_pct": vaccination_coverage(active_birds, vaccinated_birds),
        "active_quarantines": _lbl(RECORDED, active_quarantines),
        "active_disease_events": _lbl(RECORDED, active_diseases),
        "preventive_due": due,
    }
