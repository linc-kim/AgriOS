"""
Greena — Aviculture Automation Engine (Module 15, Part 9)

A PURE, deterministic engine (Doc 11, Doc 14 §2-3). Given recorded aviculture
state it computes the operational items that are due — each with the fields the
constitution requires: Priority, Reason, Evidence, Suggested Due Date (Doc 11 §6),
plus a stable ``dedup_key`` so the service can materialise them idempotently.

It also owns the deterministic workflow stage templates and transitions (Doc 11
§8). It performs no I/O and no mutation; the same inputs always yield the same
result and nothing is invented — an item exists only because a recorded fact
implies it.

Materialisation into the platform Reminder/Notification engines is the service's
job; automation never performs irreversible actions on its own (Doc 11 §1).
"""

from __future__ import annotations

from datetime import date, timedelta

# Priorities (aligned with the platform Reminder/Notification priorities).
LOW, NORMAL, HIGH, CRITICAL = "low", "normal", "high", "critical"

_SOON_DAYS = 7


def _priority(due: date, today: date, *, overdue=HIGH, soon=NORMAL, later=LOW) -> str:
    if due < today:
        return overdue
    if due <= today + timedelta(days=_SOON_DAYS):
        return soon
    return later


def _item(kind, title, priority, reason, evidence, suggested_due_on, dedup_key) -> dict:
    return {
        "kind": kind, "title": title, "priority": priority, "reason": reason,
        "evidence": evidence,  # recorded facts this item is derived from
        "suggested_due_on": suggested_due_on.isoformat() if suggested_due_on else None,
        "dedup_key": dedup_key,
    }


def compute_operational_items(
    *,
    health_due: list[dict],
    documents_expiring: list[dict],
    incubation_batches: list[dict],
    aviary_tasks: list[dict],
    today: date,
    horizon_days: int = 30,
) -> list[dict]:
    """Compute all due/upcoming operational items from recorded state.

    Only items whose date falls on/before ``today + horizon_days`` (or are
    overdue) are surfaced, so the list stays actionable. Deterministic and
    order-stable.
    """
    horizon = today + timedelta(days=horizon_days)
    items: list[dict] = []

    # Preventive care due (health records carrying next_due_on) — Doc 11 §5.
    for h in health_due:
        due = h.get("next_due_on")
        if due is None or due > horizon:
            continue
        rt = h.get("record_type", "preventive")
        ref = h.get("bird_ref") or "bird"
        items.append(_item(
            "health_due", f"{rt.replace('_', ' ').capitalize()} due: {ref}",
            _priority(due, today, overdue=HIGH), f"Recorded {rt} for {ref} is next due {due}.",
            {"record_type": rt, "next_due_on": due.isoformat(), "bird_id": str(h.get("bird_id"))},
            due, f"avi:health_due:{h.get('bird_id')}:{rt}:{due}"))

    # Permit / certificate renewals (documents with expires_on) — Doc 11 §5.
    for d in documents_expiring:
        exp = d.get("expires_on")
        if exp is None or exp > horizon:
            continue
        ref = d.get("bird_ref") or "bird"
        dt = d.get("document_type", "document")
        items.append(_item(
            "permit_renewal", f"{dt.replace('_', ' ').capitalize()} expiring: {ref}",
            _priority(exp, today, overdue=CRITICAL, soon=HIGH),
            f"Recorded {dt} for {ref} expires {exp}.",
            {"document_type": dt, "expires_on": exp.isoformat(), "document_id": str(d.get("document_id"))},
            exp, f"avi:permit:{d.get('document_id')}:{exp}"))

    # Incubation milestones (lockdown, expected hatch) — Doc 11 §5.
    for b in incubation_batches:
        bid = b.get("batch_id")
        name = b.get("name") or "batch"
        lockdown = b.get("expected_lockdown_on")
        if lockdown is not None and lockdown <= horizon:
            items.append(_item(
                "incubation_lockdown", f"Lockdown due: {name}", _priority(lockdown, today),
                f"Batch '{name}' reaches lockdown on {lockdown}.",
                {"batch_id": str(bid), "expected_lockdown_on": lockdown.isoformat()},
                lockdown, f"avi:lockdown:{bid}:{lockdown}"))
        hatch = b.get("expected_hatch_on")
        if hatch is not None and hatch <= horizon:
            items.append(_item(
                "incubation_hatch", f"Expected hatch: {name}", _priority(hatch, today),
                f"Batch '{name}' is due to hatch on {hatch}.",
                {"batch_id": str(bid), "expected_hatch_on": hatch.isoformat()},
                hatch, f"avi:hatch:{bid}:{hatch}"))

    # Scheduled aviary cleaning / maintenance — Doc 11 §5-6.
    for t in aviary_tasks:
        due = t.get("scheduled_for")
        if due is None or due > horizon:
            continue
        tt = t.get("task_type", "task")
        av = t.get("aviary_name") or "aviary"
        items.append(_item(
            "aviary_task", f"{tt.capitalize()} due: {av}", _priority(due, today),
            f"Scheduled {tt} for {av} on {due}.",
            {"task_type": tt, "scheduled_for": due.isoformat(), "task_id": str(t.get("task_id")),
             "aviary_id": str(t.get("aviary_id"))},
            due, f"avi:aviary_task:{t.get('task_id')}"))

    # Stable ordering: overdue/high first, then by suggested date.
    _rank = {CRITICAL: 0, HIGH: 1, NORMAL: 2, LOW: 3}
    items.sort(key=lambda i: (_rank.get(i["priority"], 9), i["suggested_due_on"] or "9999"))
    return items


# ── Workflow templates (Doc 11 §8) ────────────────────────────────────────────

WORKFLOW_TEMPLATES: dict[str, list[str]] = {
    "intake": ["received", "quarantine", "health_check", "acclimatised", "in_collection"],
    "quarantine": ["isolated", "observation", "testing", "cleared", "released"],
    "treatment": ["diagnosed", "treatment", "monitoring", "recovered"],
    "incubation": ["set", "candling", "lockdown", "hatched"],
    "sale": ["listed", "reserved", "paid", "documents", "handover"],
    "purchase": ["sourced", "inspected", "quarantine", "acquired"],
    "transfer": ["initiated", "documents", "transported", "delivered"],
    "exhibition": ["entered", "prepared", "judged", "returned"],
}


def workflow_stages(workflow_type: str) -> list[str]:
    return WORKFLOW_TEMPLATES.get(workflow_type, [])


def first_stage(workflow_type: str) -> str | None:
    stages = workflow_stages(workflow_type)
    return stages[0] if stages else None


def next_stage(workflow_type: str, current: str) -> str | None:
    """The stage after ``current``, or None if ``current`` is the terminal stage."""
    stages = workflow_stages(workflow_type)
    if current not in stages:
        return None
    idx = stages.index(current)
    return stages[idx + 1] if idx + 1 < len(stages) else None


def is_terminal(workflow_type: str, stage: str) -> bool:
    stages = workflow_stages(workflow_type)
    return bool(stages) and stage == stages[-1]
