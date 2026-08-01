"""
Greena — Operations Planner: shared honesty helpers for the deterministic engines.

Every value an Operations Planner engine surfaces carries a ``fact_type`` drawn
from Greena's Honesty Framework (spec Doc 1 §HONESTY). This mirrors the existing
conventions — ``mission_control.FactType`` and ``growth_planner_engine._lbl`` —
rather than inventing a new one; it simply covers all seven labels the Operations
Planner spec enumerates and adds the four-part explanation every recommendation
must carry (Evidence · Reasoning · Confidence · Limitations).

Pure module: no I/O, no clock, no model. Imported by every ``ops_*_engine``.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum


class FactType(str, Enum):
    RECORDED = "recorded_fact"
    CALCULATED = "calculated"
    FORECAST = "forecast"
    RECOMMENDATION = "strategic_recommendation"
    AI = "ai_suggestion"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"


def value(fact_type: FactType, val, detail: str = "", **extra) -> dict:
    """A single honesty-labelled value: ``{fact_type, value, detail, ...}``."""
    out = {"fact_type": fact_type.value, "value": val, "detail": detail}
    out.update(extra)
    return out


def recorded(val, detail: str = "", **extra) -> dict:
    return value(FactType.RECORDED, val, detail, **extra)


def calculated(val, detail: str = "", **extra) -> dict:
    return value(FactType.CALCULATED, val, detail, **extra)


def forecast(val, detail: str = "", **extra) -> dict:
    return value(FactType.FORECAST, val, detail, **extra)


def recommendation(val, detail: str = "", **extra) -> dict:
    return value(FactType.RECOMMENDATION, val, detail, **extra)


def unknown(detail: str = "Not enough recorded data.", **extra) -> dict:
    return value(FactType.UNKNOWN, None, detail, **extra)


def unavailable(detail: str = "Unavailable.", **extra) -> dict:
    return value(FactType.UNAVAILABLE, None, detail, **extra)


def explain(evidence, reasoning: str, confidence: str, limitations: str) -> dict:
    """The four-part justification every recommendation must carry (spec §HONESTY).

    ``confidence`` is one of low | medium | high. Never omit ``limitations`` — an
    honest recommendation states what it does not know.
    """
    return {
        "evidence": evidence,
        "reasoning": reasoning,
        "confidence": confidence,
        "limitations": limitations,
    }


# ── Small deterministic date helpers shared by the recurrence/scheduling engines ─

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def parse_date(v) -> date | None:
    """Accept a ``date`` or an ISO ``YYYY-MM-DD`` string; anything else → None."""
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (ValueError, TypeError):
        return None


def parse_dates(seq) -> set[date]:
    out: set[date] = set()
    for v in seq or ():
        d = parse_date(v)
        if d is not None:
            out.add(d)
    return out


def add_months(d: date, months: int) -> date:
    """Add ``months`` to ``d``, clamping the day to the target month's length."""
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    # Clamp day (e.g. Jan 31 + 1 month → Feb 28/29).
    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)
    last_day = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(d.day, last_day))


def priority_rank(priority: str) -> int:
    """Higher = more urgent. Unknown priorities sort as ``normal``."""
    return {"low": 0, "normal": 1, "high": 2, "critical": 3}.get(priority, 1)
