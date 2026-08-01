"""
Greena — Operations Planner: Recurrence Engine (deterministic, pure).

Expands a recurrence rule into the concrete dates it fires within a window,
honouring holidays, exceptions, suspensions and seasonal windows. Identical input
→ identical output, always. No I/O, no clock (the window bounds are passed in).

A recurrence rule is a plain dict (the shape stored on ``ops_schedule``)::

    {
      "frequency": "daily|weekly|monthly|quarterly|semiannual|annual|hourly|seasonal|custom",
      "interval": 1,                 # every N frequency units
      "byday": ["MO","WE","FR"],     # weekly: which weekdays
      "bymonthday": [1, 15],          # monthly+: which days of month
      "start_date": "2026-01-01",
      "end_date": "2026-12-31",       # optional
      "exceptions": ["2026-04-07"],   # excluded/suspended dates
      "dates": ["2026-03-01"],        # explicit dates for custom/seasonal
    }
"""

from __future__ import annotations

from datetime import date, timedelta

from app.services import ops_common as oc

_SIMPLE_MONTH_STEP = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}


def expand(rule: dict, window_start: date, window_end: date,
           holidays: set[date] | None = None) -> list[date]:
    """Return the sorted, de-duplicated dates ``rule`` fires within
    ``[window_start, window_end]``, excluding holidays/exceptions.

    ``hourly`` fires on every eligible day (the intra-day times live in the
    rule's ``time_windows`` and are applied by the scheduling engine, not here).
    """
    if window_start > window_end:
        return []
    holidays = holidays or set()
    freq = (rule.get("frequency") or "daily").lower()
    interval = max(1, int(rule.get("interval") or 1))
    start = oc.parse_date(rule.get("start_date")) or window_start
    end = oc.parse_date(rule.get("end_date"))
    excluded = oc.parse_dates(rule.get("exceptions")) | set(holidays)

    lo = max(window_start, start)
    hi = window_end if end is None else min(window_end, end)
    if lo > hi:
        return []

    if freq in ("custom", "seasonal"):
        hits = {d for d in oc.parse_dates(rule.get("dates")) if lo <= d <= hi}
    elif freq in ("daily", "hourly"):
        hits = _daily(lo, hi, start, interval)
    elif freq == "weekly":
        hits = _weekly(lo, hi, start, interval, rule.get("byday") or [])
    elif freq in _SIMPLE_MONTH_STEP:
        hits = _monthly(lo, hi, start, interval * _SIMPLE_MONTH_STEP[freq],
                        rule.get("bymonthday") or [])
    else:  # unknown frequency → no fabricated occurrences
        hits = set()

    return sorted(d for d in hits if d not in excluded)


def next_occurrence(rule: dict, after: date, horizon_days: int = 366,
                    holidays: set[date] | None = None) -> date | None:
    """The first occurrence strictly after ``after`` within ``horizon_days``."""
    dates = expand(rule, after + timedelta(days=1), after + timedelta(days=horizon_days), holidays)
    return dates[0] if dates else None


def summary(rule: dict, window_start: date, window_end: date,
            holidays: set[date] | None = None) -> dict:
    """Honesty-labelled count of occurrences in the window (a calculated value)."""
    dates = expand(rule, window_start, window_end, holidays)
    if not rule.get("frequency"):
        return {"occurrences": oc.unknown("No recurrence frequency recorded.")}
    return {
        "count": oc.calculated(len(dates), "Occurrences the rule fires in the window."),
        "first": oc.calculated(dates[0].isoformat(), "First occurrence.") if dates
        else oc.unknown("No occurrences in this window."),
        "last": oc.calculated(dates[-1].isoformat(), "Last occurrence.") if dates
        else oc.unknown("No occurrences in this window."),
        "dates": [d.isoformat() for d in dates],
    }


# ── frequency kernels ─────────────────────────────────────────────────────────

def _daily(lo: date, hi: date, start: date, interval: int) -> set[date]:
    # Align to the recurrence's own phase so "every 3 days" counts from start.
    offset = (lo - start).days % interval
    first = lo + timedelta(days=(interval - offset) % interval)
    out, d = set(), first
    while d <= hi:
        out.add(d)
        d += timedelta(days=interval)
    return out


def _weekly(lo: date, hi: date, start: date, interval: int, byday: list[str]) -> set[date]:
    codes = [c for c in byday if c in oc.WEEKDAY_CODES] or [oc.WEEKDAY_CODES[start.weekday()]]
    wanted = {oc.WEEKDAY_CODES.index(c) for c in codes}
    # Week phase measured from the Monday of start's week.
    start_week_monday = start - timedelta(days=start.weekday())
    out = set()
    d = lo
    while d <= hi:
        if d.weekday() in wanted:
            weeks = ((d - timedelta(days=d.weekday())) - start_week_monday).days // 7
            if weeks >= 0 and weeks % interval == 0:
                out.add(d)
        d += timedelta(days=1)
    return out


def _monthly(lo: date, hi: date, start: date, month_step: int, bymonthday: list[int]) -> set[date]:
    days = [int(x) for x in bymonthday] or [start.day]
    out = set()
    # Walk anchor months from start by month_step, emitting requested days.
    anchor = date(start.year, start.month, 1)
    # Rewind/advance anchor near the window for efficiency.
    while anchor > lo:
        anchor = oc.add_months(anchor, -month_step)
    while True:
        month_first = anchor
        if month_first > hi:
            break
        # Last day of this month.
        nxt = oc.add_months(month_first, 1)
        last_day = (nxt - timedelta(days=1)).day
        for dd in days:
            day = min(dd, last_day) if dd > 0 else last_day  # -1 style → month end
            candidate = date(month_first.year, month_first.month, day)
            if lo <= candidate <= hi:
                out.add(candidate)
        anchor = oc.add_months(anchor, month_step)
    return out
