"""
BSF Lifecycle Engine (Module 16, Part 2) — deterministic unit tests.

The engine is pure: same inputs → same outputs, no I/O. These tests lock the
transition rules, the species-driven development timeline, and the honesty
labels (unknown is never fabricated).
"""

from datetime import date

from app.services import bsf_lifecycle_engine as eng

PROFILE = {
    "lifecycle": {
        "egg_days": 4,
        "feeding_larvae_days": 12,
        "prepupae_days": 7,
    }
}


# ── Transition validation ─────────────────────────────────────────────────────

def test_forward_transition_is_valid():
    res = eng.validate_transition("egg", "hatchling")
    assert res["valid"] is True and res["skipped"] == []


def test_forward_skip_is_valid_but_reports_skipped_stages():
    res = eng.validate_transition("egg", "prepupae")
    assert res["valid"] is True
    assert res["skipped"] == ["hatchling", "feeding_larvae", "mature_larvae"]


def test_backward_transition_is_rejected():
    res = eng.validate_transition("prepupae", "egg")
    assert res["valid"] is False and "backward" in res["reason"].lower()


def test_same_stage_is_rejected():
    assert eng.validate_transition("pupae", "pupae")["valid"] is False


def test_unknown_target_stage_is_rejected():
    assert eng.validate_transition("egg", "banana")["valid"] is False


def test_initial_assignment_from_unknown_is_valid():
    assert eng.validate_transition(None, "feeding_larvae")["valid"] is True
    assert eng.validate_transition("unknown", "egg")["valid"] is True


def test_next_stage_progression_and_terminal():
    assert eng.next_stage("egg") == "hatchling"
    assert eng.next_stage("adult") is None
    assert eng.next_stage("unknown") is None


# ── Development timeline ───────────────────────────────────────────────────────

def test_expected_stage_days_reads_profile_or_none():
    assert eng.expected_stage_days(PROFILE, "egg") == 4
    assert eng.expected_stage_days(PROFILE, "pupae") is None  # not recorded
    assert eng.expected_stage_days(None, "egg") is None


def test_development_timeline_forecasts_known_and_marks_unknown():
    tl = eng.development_timeline(PROFILE, date(2026, 1, 1))
    by_stage = {s["stage"]: s for s in tl["stages"]}
    # egg has a recorded duration → forecast complete date.
    assert by_stage["egg"]["expected_complete_on"]["label"] == "forecast"
    assert by_stage["egg"]["expected_complete_on"]["value"] == "2026-01-05"
    # Once a gap (hatchling unknown) is hit, downstream dates degrade to unknown.
    assert by_stage["hatchling"]["expected_days"]["label"] == "unknown"
    assert by_stage["pupae"]["expected_complete_on"]["label"] == "unknown"


def test_timeline_without_start_date_is_unknown():
    tl = eng.development_timeline(PROFILE, None)
    assert all(s["expected_complete_on"]["label"] == "unknown" for s in tl["stages"])


# ── Stage pacing / premature detection ────────────────────────────────────────

def test_stage_pacing_flags_delayed():
    res = eng.stage_pacing(PROFILE, "egg", date(2026, 1, 1), as_of=date(2026, 1, 10))
    assert res["status"]["value"] == "delayed"
    assert res["days_in_stage"]["value"] == 9


def test_stage_pacing_on_track():
    res = eng.stage_pacing(PROFILE, "feeding_larvae", date(2026, 1, 1), as_of=date(2026, 1, 6))
    assert res["status"]["value"] == "on_track"


def test_stage_pacing_unknown_without_profile_duration():
    res = eng.stage_pacing(PROFILE, "pupae", date(2026, 1, 1), as_of=date(2026, 1, 6))
    assert res["status"]["label"] == "unknown"


def test_premature_advance_detection():
    # egg expects 4 days; advancing after 2 is premature.
    assert eng.is_premature_advance(PROFILE, "egg", date(2026, 1, 1), as_of=date(2026, 1, 3)) is True
    assert eng.is_premature_advance(PROFILE, "egg", date(2026, 1, 1), as_of=date(2026, 1, 6)) is False
    # Unknown durations never fabricate a premature signal.
    assert eng.is_premature_advance(PROFILE, "pupae", date(2026, 1, 1), as_of=date(2026, 1, 2)) is False
