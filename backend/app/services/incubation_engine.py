"""
Greena — Incubation Engine (Module 15, Part 5)

A PURE, deterministic engine (Doc 14 §2-3). Given recorded egg/batch data and a
species profile it computes the incubation schedule, progress and hatch
statistics. No I/O, no mutation — the same inputs always yield the same result.

Species-aware without hardcoding (Doc 16 §5): incubation period, temperature,
humidity, turning and lockdown timing are read from the species ``profile`` dict.
When a value is not recorded the engine reports it as ``unknown`` rather than
inventing one, and statistics degrade to "not enough recorded data" — never a
fabricated rate (Doc 04 §19, Doc 15 §15). Genetic/biological outcomes are always
probabilities, never guarantees (Doc 01 §12).
"""

from __future__ import annotations

from datetime import date, timedelta

RECORDED = "recorded"
CALCULATED = "calculated"
RECOMMENDATION = "recommendation"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Eggs that have entered incubation (were "set").
_SET_STATUSES = ("set", "candled", "lockdown", "hatched", "failed")
_DEFAULT_LOCKDOWN_BEFORE = 3  # days before hatch, when the profile is silent


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def _incubation_block(profile: dict | None) -> dict:
    """Pull the incubation sub-profile from a species profile, tolerant of shape.
    Looks under ``incubation`` first, then ``breeding`` (Doc 16 §5)."""
    if not isinstance(profile, dict):
        return {}
    inc = profile.get("incubation")
    if isinstance(inc, dict) and inc:
        return inc
    br = profile.get("breeding")
    return br if isinstance(br, dict) else {}


# ── Schedule ──────────────────────────────────────────────────────────────────

def incubation_schedule(
    species_profile: dict | None,
    set_on: date | None,
    *,
    override_days: int | None = None,
    override_temp: float | None = None,
    override_humidity: float | None = None,
) -> dict:
    """Compute a batch's incubation schedule from the species profile.

    Everything is honesty-labelled. Manual overrides are treated as recorded
    facts; profile-derived values as recorded (from the catalog); dates as
    calculated. Missing incubation period → dates are unknown, not guessed.
    """
    inc = _incubation_block(species_profile)

    days = override_days if override_days is not None else (
        inc.get("incubation_days") or inc.get("days") or inc.get("incubation_period")
    )
    days_label = RECORDED if days is not None else UNKNOWN

    lockdown_before = inc.get("lockdown_days_before") or _DEFAULT_LOCKDOWN_BEFORE

    temp = override_temp if override_temp is not None else (inc.get("temp_c") or inc.get("temperature_c"))
    humidity = override_humidity if override_humidity is not None else (inc.get("humidity_pct") or inc.get("humidity"))
    turning = inc.get("turning_per_day") or inc.get("turns_per_day")

    expected_hatch = None
    expected_lockdown = None
    if set_on is not None and days is not None:
        expected_hatch = set_on + timedelta(days=int(days))
        expected_lockdown = expected_hatch - timedelta(days=int(lockdown_before))

    return {
        "incubation_days": _lbl(days_label, days,
                                "From the species profile or manual override." if days is not None
                                else "No incubation period recorded for this species."),
        "expected_lockdown_on": _lbl(
            CALCULATED if expected_lockdown else UNKNOWN,
            expected_lockdown.isoformat() if expected_lockdown else None,
            f"set date + incubation days − {lockdown_before} (lockdown)."),
        "expected_hatch_on": _lbl(
            CALCULATED if expected_hatch else UNKNOWN,
            expected_hatch.isoformat() if expected_hatch else None,
            "set date + incubation days."),
        "target_temperature_c": _lbl(RECORDED if temp is not None else UNKNOWN, temp,
                                     "Recommended incubation temperature."),
        "target_humidity_pct": _lbl(RECORDED if humidity is not None else UNKNOWN, humidity,
                                    "Recommended incubation humidity."),
        "turning_per_day": _lbl(RECORDED if turning is not None else UNKNOWN, turning,
                                "Recommended daily egg turns."),
    }


# ── Progress ──────────────────────────────────────────────────────────────────

def incubation_progress(set_on: date | None, incubation_days: int | None, today: date, status: str) -> dict:
    """Deterministic day-of-incubation, phase and days remaining."""
    if set_on is None:
        return {"phase": _lbl(UNKNOWN, None, "Batch not yet set."), "day_number": _lbl(UNKNOWN, None)}

    day_number = (today - set_on).days
    if incubation_days is None:
        return {
            "day_number": _lbl(CALCULATED, day_number, "today − set date."),
            "phase": _lbl(UNKNOWN, None, "No incubation period recorded — cannot place phase."),
            "days_remaining": _lbl(UNKNOWN, None),
            "pct_elapsed": _lbl(UNKNOWN, None),
        }

    lockdown_day = incubation_days - _DEFAULT_LOCKDOWN_BEFORE
    remaining = incubation_days - day_number
    pct = round(min(100.0, max(0.0, day_number / incubation_days * 100)), 1) if incubation_days > 0 else None

    if status in ("completed", "cancelled"):
        phase = status
    elif day_number < 0:
        phase = "pre_set"
    elif day_number >= incubation_days:
        phase = "hatch_due"
    elif day_number >= lockdown_day:
        phase = "lockdown"
    else:
        phase = "incubating"

    return {
        "day_number": _lbl(CALCULATED, day_number, "today − set date."),
        "phase": _lbl(CALCULATED, phase, "Derived from day number and incubation period."),
        "days_remaining": _lbl(CALCULATED, remaining, "incubation days − day number."),
        "pct_elapsed": _lbl(CALCULATED if pct is not None else UNAVAILABLE, pct),
        "lockdown_due": day_number >= lockdown_day and day_number < incubation_days,
        "hatch_due": day_number >= incubation_days,
    }


def candling_day(set_on: date | None, candled_on: date) -> int | None:
    """Day of incubation a candling was performed (recorded → calculated)."""
    if set_on is None:
        return None
    return (candled_on - set_on).days


# ── Hatch statistics ──────────────────────────────────────────────────────────

def hatch_statistics(eggs: list[dict]) -> dict:
    """Deterministic fertility & hatch statistics from recorded eggs.

    ``eggs``: each {"status", "fertility_status"}. Rates are only reported when
    their denominator is a recorded fact; otherwise they read "not enough
    recorded data" (Doc 04 §19). No rate is ever fabricated.
    """
    total = len(eggs)
    set_count = sum(1 for e in eggs if e.get("status") in _SET_STATUSES)
    hatched = sum(1 for e in eggs if e.get("status") == "hatched")
    failed = sum(1 for e in eggs if e.get("status") == "failed")
    fertile = sum(1 for e in eggs if e.get("fertility_status") == "fertile")
    infertile = sum(1 for e in eggs if e.get("fertility_status") == "infertile")

    def rate(num: int, den: int, detail: str) -> dict:
        if den <= 0:
            return _lbl(UNKNOWN, None, "Not enough recorded data.")
        return _lbl(CALCULATED, round(num / den * 100, 1), detail)

    return {
        "eggs_total": _lbl(RECORDED, total, "Eggs recorded."),
        "eggs_set": _lbl(RECORDED, set_count, "Eggs that entered incubation."),
        "fertile": _lbl(RECORDED, fertile),
        "infertile": _lbl(RECORDED, infertile),
        "hatched": _lbl(RECORDED, hatched),
        "failed": _lbl(RECORDED, failed),
        "fertility_rate_pct": rate(fertile, set_count, "fertile ÷ eggs set × 100."),
        "hatch_rate_pct": rate(hatched, set_count, "hatched ÷ eggs set × 100."),
        "hatch_of_fertile_pct": rate(hatched, fertile, "hatched ÷ fertile × 100."),
    }
