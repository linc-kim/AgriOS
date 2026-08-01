"""
Greena — Operations Planner: Compliance Engine (deterministic, pure).

Monitors recurring compliance requirements — vaccinations, biosecurity,
equipment servicing, regulatory inspections, worker training, safety inspections,
environmental monitoring — and raises alerts on overdue items (spec Doc 4 §13).
Pure and deterministic given ``as_of``; a requirement with no recorded history is
``unknown``, never assumed compliant.

Requirement dict::  {"key","label","category","interval_days":90,
                    "last_completed":"2026-01-01","due_date":"2026-04-01"}
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services import ops_common as oc


def evaluate(requirements: list[dict], as_of: date, due_soon_days: int = 7) -> dict:
    """Classify each requirement as compliant | due_soon | overdue | unknown and
    summarise. ``due_date`` is used if present, else derived from
    ``last_completed + interval_days``.
    """
    items = []
    counts = {"compliant": 0, "due_soon": 0, "overdue": 0, "unknown": 0}
    for req in requirements:
        due = oc.parse_date(req.get("due_date"))
        last = oc.parse_date(req.get("last_completed"))
        interval = req.get("interval_days")
        if due is None and last is not None and interval:
            due = last + timedelta(days=int(interval))

        if due is None:
            status = oc.unknown("No due date or completion history recorded.")
            bucket = "unknown"
        else:
            days = (due - as_of).days
            if days < 0:
                status = oc.calculated("overdue", f"Due {-days} day(s) ago.", days_overdue=-days)
                bucket = "overdue"
            elif days <= due_soon_days:
                status = oc.calculated("due_soon", f"Due in {days} day(s).", days_until_due=days)
                bucket = "due_soon"
            else:
                status = oc.calculated("compliant", f"Due in {days} day(s).", days_until_due=days)
                bucket = "compliant"
        counts[bucket] += 1
        item = {
            "key": req.get("key"), "label": req.get("label"),
            "category": req.get("category"),
            "due_date": due.isoformat() if due else None,
            "status": status,
        }
        if bucket == "overdue":
            item["alert"] = oc.recommendation(
                f"Complete '{req.get('label') or req.get('key')}' now",
                "A recurring compliance requirement is overdue.",
                evidence={"due_date": due.isoformat()}, confidence="high")
        items.append(item)

    items.sort(key=lambda r: (0 if _is(r, "overdue") else 1 if _is(r, "due_soon") else 2,
                              str(r.get("key"))))
    total = len(items)
    compliant = counts["compliant"]
    rate = round(compliant / total, 3) if total else None
    return {
        "items": items,
        "counts": counts,
        "compliance_rate": (oc.calculated(rate, "compliant ÷ total (unknowns excluded from numerator).")
                            if total else oc.unknown("No requirements recorded.")),
    }


def _is(item: dict, label: str) -> bool:
    return item.get("status", {}).get("value") == label
