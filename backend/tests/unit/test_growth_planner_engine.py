"""
Growth Planner Engine (Platform, Module 16) — deterministic unit tests.

Locks progress maths, the evidence-based realism verdict, milestone roll-up and
revision diffing — with the honesty rule that a missing actual is ``unknown``,
never a fabricated progress value.
"""

from datetime import date

from app.services import growth_planner_engine as eng


# ── Goal progress ─────────────────────────────────────────────────────────────

def test_goal_progress_with_baseline():
    # baseline 1000, target 5000, actual 2800 → (2800-1000)/(5000-1000) = 45%.
    r = eng.goal_progress(1000, 5000, 2800)
    assert r["percent"]["label"] == "calculated" and r["percent"]["value"] == 45.0
    assert r["achieved"]["value"] is False


def test_goal_progress_clamps_and_flags_achieved():
    r = eng.goal_progress(0, 100, 120)
    assert r["percent"]["value"] == 100.0  # clamped
    assert r["raw_percent"]["value"] == 120.0
    assert r["achieved"]["value"] is True


def test_goal_progress_unknown_without_actual():
    assert eng.goal_progress(0, 100, None)["percent"]["label"] == "unknown"


# ── Realism ───────────────────────────────────────────────────────────────────

def test_required_run_rate():
    r = eng.required_run_rate(0, 100, 40, date(2026, 1, 31), as_of=date(2026, 1, 1))
    # 60 remaining over 30 days → 2/day.
    assert r["required_daily"]["value"] == 2.0
    assert r["days_remaining"]["value"] == 30


def test_required_run_rate_achieved_and_overdue():
    assert eng.required_run_rate(0, 100, 100, date(2026, 12, 1))["verdict"]["value"] == "achieved"
    assert eng.required_run_rate(0, 100, 40, date(2020, 1, 1))["verdict"]["value"] == "overdue"


def test_realism_verdict_tiers():
    assert eng.realism_verdict(1.0, 2.0)["value"] == "feasible"     # need ≤ observed
    assert eng.realism_verdict(3.0, 2.0)["value"] == "ambitious"    # ~1.5×
    assert eng.realism_verdict(10.0, 2.0)["value"] == "unrealistic" # 5×
    assert eng.realism_verdict(5.0, 0)["value"] == "unrealistic"    # no progress
    assert eng.realism_verdict(None, 2.0)["label"] == "unknown"


# ── Milestones ────────────────────────────────────────────────────────────────

def test_milestone_rollup():
    ms = [
        {"sequence": 1, "status": "achieved"},
        {"sequence": 2, "status": "in_progress"},
        {"sequence": 3, "status": "pending"},
    ]
    r = eng.milestone_rollup(ms)
    assert r["completion_pct"]["value"] == 33.3
    assert r["next_milestone"]["sequence"] == 2  # lowest-seq open


def test_milestone_rollup_empty():
    r = eng.milestone_rollup([])
    assert r["completion_pct"]["label"] == "unknown" and r["next_milestone"] is None


# ── Revision diff ─────────────────────────────────────────────────────────────

def test_diff_revisions_detects_changes():
    a = {"title": "Plan", "status": "active",
         "goals": [{"id": "g1", "target_value": 1000}],
         "milestones": [{"id": "m1", "status": "pending"}]}
    b = {"title": "Plan v2", "status": "active",
         "goals": [{"id": "g1", "target_value": 2000}, {"id": "g2", "target_value": 500}],
         "milestones": [{"id": "m1", "status": "achieved"}]}
    d = eng.diff_revisions(a, b)
    assert d["plan"]["title"] == {"from": "Plan", "to": "Plan v2"}
    assert any(g["id"] == "g2" for g in d["goals"]["added"])
    assert d["goals"]["changed"][0]["changes"]["target_value"] == {"from": 1000, "to": 2000}
    assert d["milestones"]["changed"][0]["changes"]["status"] == {"from": "pending", "to": "achieved"}
