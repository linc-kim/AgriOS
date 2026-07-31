"""
Greena — Growth Planner Engine (Platform, introduced by Module 16)

A PURE, deterministic engine (Spec Part 4 §12, Part 6 §7). Computes goal progress,
planned-vs-actual variance, deterministic realism checks, milestone roll-ups and
revision diffs from recorded plan data + recorded "actual" values. No I/O, no
mutation.

Honesty (per the Growth Planner Contract): baseline/target are ``recorded``;
progress %/variance/required-rate are ``calculated``; projected completion is
``forecast``; a missing actual is ``unknown`` — never invented. ARIA explains
these outputs; it never overwrites the plan.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _dec(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def goal_progress(baseline, target, actual) -> dict:
    """Progress toward a goal = (actual − baseline) ÷ (target − baseline) × 100.

    Handles baseline=None (treated as 0). Clamped to [0, 100] for the headline
    percent; raw actual/target are echoed as recorded facts. Missing actual →
    ``unknown`` (no fabricated progress).
    """
    tgt = _dec(target)
    act = _dec(actual)
    base = _dec(baseline) or Decimal(0)
    if tgt is None:
        return {"percent": _lbl(UNKNOWN, None, "No target recorded.")}
    if act is None:
        return {"percent": _lbl(UNKNOWN, None, "No recorded actual for this metric yet."),
                "target": _lbl(RECORDED, float(tgt)), "baseline": _lbl(RECORDED, float(base))}
    denom = tgt - base
    if denom == 0:
        pct = Decimal(100) if act >= tgt else Decimal(0)
    else:
        pct = ((act - base) / denom) * Decimal(100)
    clamped = max(Decimal(0), min(pct, Decimal(100)))
    return {
        "percent": _lbl(CALCULATED, float(round(clamped, 1)), "(actual − baseline) ÷ (target − baseline)."),
        "raw_percent": _lbl(CALCULATED, float(round(pct, 1)), "Unclamped — may exceed 100 when target surpassed."),
        "actual": _lbl(RECORDED, float(act), "Recorded operational value."),
        "target": _lbl(RECORDED, float(tgt)),
        "baseline": _lbl(RECORDED, float(base)),
        "achieved": _lbl(CALCULATED, bool(act >= tgt), "actual ≥ target."),
    }


def required_run_rate(baseline, target, actual, target_date: date | None, as_of: date | None = None) -> dict:
    """Deterministic realism check: the per-day gain still required to hit target by
    the deadline, and a feasibility verdict vs the observed rate so far."""
    tgt = _dec(target)
    act = _dec(actual)
    base = _dec(baseline) or Decimal(0)
    if tgt is None or act is None or target_date is None:
        return {"verdict": _lbl(UNKNOWN, "unknown", "Requires target, recorded actual and a target date.")}
    as_of = as_of or date.today()
    days_left = (target_date - as_of).days
    remaining = tgt - act
    if remaining <= 0:
        return {"verdict": _lbl(CALCULATED, "achieved", "Target already met or exceeded."),
                "required_daily": _lbl(CALCULATED, 0.0)}
    if days_left <= 0:
        return {"verdict": _lbl(CALCULATED, "overdue", "Target date has passed with the goal unmet."),
                "required_daily": _lbl(UNKNOWN, None)}
    required_daily = remaining / Decimal(days_left)
    return {
        "days_remaining": _lbl(CALCULATED, days_left),
        "remaining_to_target": _lbl(CALCULATED, float(round(remaining, 3))),
        "required_daily": _lbl(CALCULATED, float(round(required_daily, 4)),
                               "remaining ÷ days left — the pace needed from now."),
        "verdict": _lbl(CALCULATED, "on_pace_needed",
                        "Compare required_daily with the recorded daily rate to judge realism."),
    }


def realism_verdict(required_daily: float | None, observed_daily: float | None) -> dict:
    """Feasible/ambitious/unrealistic from required vs observed daily rate.

    Evidence-based and deterministic; ARIA explains it, never enforces it
    (Spec Part 6 §11). Unknown when either rate is missing.
    """
    if required_daily is None or observed_daily is None:
        return _lbl(UNKNOWN, "unknown", "Requires both the required and the recorded daily rate.")
    if observed_daily <= 0:
        return _lbl(CALCULATED, "unrealistic",
                    "No positive recorded progress rate; the target is not currently on track.")
    ratio = required_daily / observed_daily
    if ratio <= 1.0:
        verdict = "feasible"
        detail = "Recorded pace already meets or exceeds what the target needs."
    elif ratio <= 2.0:
        verdict = "ambitious"
        detail = f"Target needs ~{round(ratio, 2)}× the current recorded pace."
    else:
        verdict = "unrealistic"
        detail = f"Target needs ~{round(ratio, 2)}× the current recorded pace — very unlikely without change."
    return _lbl(CALCULATED, verdict, detail)


def milestone_rollup(milestones: list[dict]) -> dict:
    """Counts by status and the next actionable milestone (lowest sequence, open)."""
    counts: dict[str, int] = {}
    for m in milestones:
        counts[m.get("status", "pending")] = counts.get(m.get("status", "pending"), 0) + 1
    total = len(milestones)
    achieved = counts.get("achieved", 0)
    open_ms = sorted(
        [m for m in milestones if m.get("status") in ("pending", "in_progress")],
        key=lambda m: m.get("sequence", 0))
    completion = round((achieved / total) * 100, 1) if total else None
    return {
        "total": _lbl(RECORDED, total),
        "by_status": counts,
        "completion_pct": _lbl(CALCULATED if completion is not None else UNKNOWN, completion,
                               "achieved ÷ total milestones."),
        "next_milestone": open_ms[0] if open_ms else None,
    }


def diff_revisions(snapshot_a: dict, snapshot_b: dict) -> dict:
    """Structured diff between two immutable plan snapshots (Spec Part 6 §6)."""
    def _index(snap, key):
        # Identity is the stable business key (metric_key for goals, title for
        # milestones), NOT the row id — so an edit that replaces the row still
        # reads as a "change", not a remove+add.
        return {g.get("metric_key") or g.get("title") or g.get("id"): g for g in (snap.get(key) or [])}

    diff: dict = {"plan": {}, "goals": {"added": [], "removed": [], "changed": []},
                  "milestones": {"added": [], "removed": [], "changed": []}}

    for field in ("title", "description", "status"):
        if snapshot_a.get(field) != snapshot_b.get(field):
            diff["plan"][field] = {"from": snapshot_a.get(field), "to": snapshot_b.get(field)}

    for key in ("goals", "milestones"):
        a_idx, b_idx = _index(snapshot_a, key), _index(snapshot_b, key)
        for k in b_idx.keys() - a_idx.keys():
            diff[key]["added"].append(b_idx[k])
        for k in a_idx.keys() - b_idx.keys():
            diff[key]["removed"].append(a_idx[k])
        for k in a_idx.keys() & b_idx.keys():
            changes = {f: {"from": a_idx[k].get(f), "to": b_idx[k].get(f)}
                       for f in set(a_idx[k]) | set(b_idx[k])
                       if a_idx[k].get(f) != b_idx[k].get(f) and f not in ("id",)}
            if changes:
                diff[key]["changed"].append({"key": k, "changes": changes})
    return diff
