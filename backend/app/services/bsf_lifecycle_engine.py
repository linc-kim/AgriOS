"""
Greena — BSF Lifecycle Engine (Module 16, Part 2)

A PURE, deterministic engine (Spec Part 4 §3, §5). Given a batch's recorded
stage/dates and a species profile it validates lifecycle transitions and computes
expected development timelines, delayed-development and premature-transition
signals. No I/O, no mutation — the same inputs always yield the same result.

Species-aware without hardcoding (Spec Part 3 §5): expected stage durations are
read from the species ``profile`` dict. When a value is not recorded the engine
reports it as ``unknown`` rather than inventing one (Spec Part 9 §17-19).

The lifecycle order (Spec Part 2 §6, Part 4 §5):
    egg → hatchling → feeding_larvae → mature_larvae → prepupae → pupae → adult
"""

from __future__ import annotations

from datetime import date, timedelta

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
UNKNOWN = "unknown"
UNAVAILABLE = "unavailable"

# Ordered production lifecycle (excludes the sentinel "unknown").
LIFECYCLE_ORDER: tuple[str, ...] = (
    "egg", "hatchling", "feeding_larvae", "mature_larvae", "prepupae", "pupae", "adult",
)

# Profile keys that may carry the expected duration (days) of each stage.
_STAGE_DURATION_KEYS: dict[str, tuple[str, ...]] = {
    "egg": ("egg_days", "incubation_days", "egg_stage_days"),
    "hatchling": ("hatchling_days", "neonate_days"),
    "feeding_larvae": ("feeding_larvae_days", "larvae_days", "larval_days"),
    "mature_larvae": ("mature_larvae_days", "prepupation_days"),
    "prepupae": ("prepupae_days", "prepupal_days"),
    "pupae": ("pupae_days", "pupal_days"),
    "adult": ("adult_days", "adult_lifespan_days"),
}


def _lbl(label: str, value, detail: str = "") -> dict:
    return {"label": label, "value": value, "detail": detail}


def stage_index(stage: str | None) -> int:
    """Position of a stage in the lifecycle order, or -1 if unknown/unordered."""
    if stage in LIFECYCLE_ORDER:
        return LIFECYCLE_ORDER.index(stage)
    return -1


def _lifecycle_block(profile: dict | None) -> dict:
    if not isinstance(profile, dict):
        return {}
    for key in ("lifecycle", "development", "stages"):
        block = profile.get(key)
        if isinstance(block, dict) and block:
            return block
    return profile if isinstance(profile, dict) else {}


def expected_stage_days(profile: dict | None, stage: str) -> int | None:
    """Expected duration (days) of a stage from the species profile, else None."""
    block = _lifecycle_block(profile)
    for key in _STAGE_DURATION_KEYS.get(stage, ()):
        val = block.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return None


# ── Transition validation (Spec Part 4 §5) ────────────────────────────────────

def validate_transition(from_stage: str | None, to_stage: str) -> dict:
    """Deterministically validate a lifecycle stage change.

    Returns ``{"valid": bool, "reason": str, "skipped": [stages]}``. Transitions
    are forward-only within :data:`LIFECYCLE_ORDER`; backward moves must be
    recorded as corrections, not advances. Skipping intermediate stages is
    permitted but reported so callers can surface it.
    """
    if to_stage not in LIFECYCLE_ORDER:
        return {"valid": False, "reason": f"{to_stage!r} is not a valid lifecycle stage.", "skipped": []}

    to_idx = stage_index(to_stage)
    from_idx = stage_index(from_stage)

    if from_stage is None or from_idx == -1:
        # No known current stage → any real stage is an acceptable starting point.
        return {"valid": True, "reason": "Initial stage assignment.", "skipped": []}

    if to_idx == from_idx:
        return {"valid": False, "reason": f"Batch is already at stage {to_stage!r}.", "skipped": []}
    if to_idx < from_idx:
        return {
            "valid": False,
            "reason": f"Cannot move backward {from_stage!r} → {to_stage!r}; record a correction instead.",
            "skipped": [],
        }
    skipped = list(LIFECYCLE_ORDER[from_idx + 1:to_idx])
    return {"valid": True, "reason": "Forward lifecycle transition.", "skipped": skipped}


def next_stage(from_stage: str | None) -> str | None:
    """The immediate next lifecycle stage, or None if terminal/unknown."""
    idx = stage_index(from_stage)
    if idx == -1 or idx >= len(LIFECYCLE_ORDER) - 1:
        return None
    return LIFECYCLE_ORDER[idx + 1]


# ── Development timeline & pacing (Spec Part 4 §5) ─────────────────────────────

def development_timeline(profile: dict | None, started_on: date | None) -> dict:
    """Expected date the batch reaches each downstream stage, honesty-labelled.

    Missing per-stage durations make later dates ``unknown`` rather than guessed.
    """
    stages: list[dict] = []
    cursor = started_on
    known = started_on is not None
    for stage in LIFECYCLE_ORDER:
        days = expected_stage_days(profile, stage)
        entry = {
            "stage": stage,
            "expected_days": _lbl(RECORDED if days is not None else UNKNOWN, days,
                                  "From species profile." if days is not None
                                  else "No expected duration recorded for this species."),
        }
        if known and days is not None and cursor is not None:
            cursor = cursor + timedelta(days=days)
            entry["expected_complete_on"] = _lbl(FORECAST, cursor.isoformat(),
                                                 "start date + cumulative stage durations.")
        else:
            known = False
            entry["expected_complete_on"] = _lbl(UNKNOWN, None,
                                                "Requires a start date and recorded stage durations.")
        stages.append(entry)
    return {"started_on": started_on.isoformat() if started_on else None, "stages": stages}


def stage_pacing(
    profile: dict | None,
    current_stage: str | None,
    stage_started_on: date | None,
    as_of: date | None = None,
) -> dict:
    """Compare recorded days-in-stage against the expected duration.

    Returns an honesty-labelled assessment: ``on_track`` | ``delayed`` |
    ``ahead`` | ``unknown``. "delayed" means the batch has spent longer in the
    stage than expected; "ahead" flags a *premature* readiness to advance.
    """
    as_of = as_of or date.today()
    expected = expected_stage_days(profile, current_stage) if current_stage else None
    if stage_started_on is None or current_stage not in LIFECYCLE_ORDER:
        return {
            "status": _lbl(UNKNOWN, "unknown", "Requires a recorded stage-start date."),
            "days_in_stage": _lbl(UNKNOWN, None, ""),
            "expected_days": _lbl(RECORDED if expected is not None else UNKNOWN, expected, ""),
        }

    days_in_stage = max((as_of - stage_started_on).days, 0)
    if expected is None:
        status = _lbl(UNKNOWN, "unknown", "No expected stage duration recorded for this species.")
    elif days_in_stage > expected:
        status = _lbl(CALCULATED, "delayed",
                      f"{days_in_stage}d in stage vs {expected}d expected — development is delayed.")
    elif days_in_stage < expected:
        status = _lbl(CALCULATED, "on_track",
                      f"{days_in_stage}d of an expected {expected}d in this stage.")
    else:
        status = _lbl(CALCULATED, "on_track", "At the expected stage duration.")
    return {
        "status": status,
        "days_in_stage": _lbl(CALCULATED, days_in_stage, "as_of − stage_started_on."),
        "expected_days": _lbl(RECORDED if expected is not None else UNKNOWN, expected,
                              "From species profile." if expected is not None else ""),
    }


def is_premature_advance(
    profile: dict | None, current_stage: str | None, stage_started_on: date | None,
    as_of: date | None = None,
) -> bool:
    """True when advancing now would be earlier than the recorded minimum stage
    duration allows. Unknown durations never flag as premature (no fabrication)."""
    expected = expected_stage_days(profile, current_stage) if current_stage else None
    if expected is None or stage_started_on is None:
        return False
    as_of = as_of or date.today()
    return max((as_of - stage_started_on).days, 0) < expected
