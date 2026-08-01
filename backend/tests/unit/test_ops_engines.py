"""
Operations Planner (Platform Module 5) — deterministic engine unit tests.

Every engine is pure and independently testable (spec Doc 4 §4: "Each engine
shall always produce identical outputs for identical inputs."). These tests lock
the recurrence maths, dependency ordering/cycle detection, scheduling packing,
conflict detection, labour/resource allocation, workload balancing, capacity
bottleneck + growth projection, compliance status, optimisation thresholds and
routine generation — plus the honesty rule that missing data is ``unknown`` /
``unavailable``, never fabricated.
"""

from datetime import date

from app.services import ops_common as oc
from app.services import (
    ops_capacity_engine as capacity,
    ops_compliance_engine as compliance,
    ops_conflict_engine as conflict,
    ops_dependency_engine as dependency,
    ops_labor_engine as labor,
    ops_optimization_engine as optimization,
    ops_recurrence_engine as recurrence,
    ops_resource_engine as resource,
    ops_routine_generation_engine as generation,
    ops_scheduling_engine as scheduling,
    ops_workload_engine as workload,
)

WS, WE = date(2026, 1, 1), date(2026, 1, 31)


# ── ops_common honesty helpers ────────────────────────────────────────────────

def test_fact_types_match_honesty_framework():
    assert oc.FactType.RECORDED.value == "recorded_fact"
    assert oc.FactType.RECOMMENDATION.value == "strategic_recommendation"
    assert oc.unknown()["fact_type"] == "unknown"
    assert oc.unavailable()["value"] is None


def test_add_months_clamps_day():
    assert oc.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert oc.add_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert oc.add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


# ── Recurrence engine ─────────────────────────────────────────────────────────

def test_recurrence_daily_every_3_days_phase_from_start():
    rule = {"frequency": "daily", "interval": 3, "start_date": "2026-01-01"}
    out = recurrence.expand(rule, WS, date(2026, 1, 10))
    assert out == [date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 7), date(2026, 1, 10)]


def test_recurrence_weekly_byday():
    rule = {"frequency": "weekly", "byday": ["MO", "FR"], "start_date": "2026-01-01"}
    out = recurrence.expand(rule, WS, date(2026, 1, 12))
    # Jan 2026: Fri 2, Mon 5, Fri 9, Mon 12.
    assert out == [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 9), date(2026, 1, 12)]


def test_recurrence_biweekly_phase():
    rule = {"frequency": "weekly", "interval": 2, "byday": ["TH"], "start_date": "2026-01-01"}
    out = recurrence.expand(rule, WS, WE)
    # Start week contains Thu Jan 1; every 2nd week → Jan 1, 15, 29.
    assert out == [date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 29)]


def test_recurrence_monthly_bymonthday_clamps():
    rule = {"frequency": "monthly", "bymonthday": [31], "start_date": "2026-01-31"}
    out = recurrence.expand(rule, date(2026, 1, 1), date(2026, 3, 31))
    assert out == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_recurrence_quarterly_step():
    rule = {"frequency": "quarterly", "start_date": "2026-01-15"}
    out = recurrence.expand(rule, date(2026, 1, 1), date(2026, 12, 31))
    assert out == [date(2026, 1, 15), date(2026, 4, 15), date(2026, 7, 15), date(2026, 10, 15)]


def test_recurrence_exceptions_and_holidays_excluded():
    rule = {"frequency": "daily", "start_date": "2026-01-01", "exceptions": ["2026-01-02"]}
    out = recurrence.expand(rule, WS, date(2026, 1, 4), holidays={date(2026, 1, 3)})
    assert out == [date(2026, 1, 1), date(2026, 1, 4)]


def test_recurrence_seasonal_uses_explicit_dates():
    rule = {"frequency": "seasonal", "dates": ["2026-01-05", "2026-02-01"]}
    out = recurrence.expand(rule, WS, WE)
    assert out == [date(2026, 1, 5)]  # only the in-window date


def test_recurrence_unknown_frequency_returns_empty_and_summary_unknown():
    assert recurrence.expand({"frequency": "fortnightly"}, WS, WE) == []
    assert recurrence.summary({}, WS, WE)["occurrences"]["fact_type"] == "unknown"


def test_recurrence_is_deterministic():
    rule = {"frequency": "weekly", "byday": ["MO", "WE", "FR"], "start_date": "2026-01-01"}
    assert recurrence.expand(rule, WS, WE) == recurrence.expand(rule, WS, WE)


# ── Dependency engine ─────────────────────────────────────────────────────────

FEED_CHAIN = [
    {"id": "receive", "name": "Receive feed"},
    {"id": "inspect", "name": "Inspect feed", "depends_on": ["receive"]},
    {"id": "store", "name": "Store feed", "depends_on": ["inspect"]},
    {"id": "prepare", "name": "Prepare feed", "depends_on": ["store"]},
    {"id": "feed", "name": "Feed animals", "depends_on": ["prepare"]},
]


def test_dependency_topological_order():
    r = dependency.topological_order(FEED_CHAIN)
    assert r["ok"] is True
    assert r["order"] == ["receive", "inspect", "store", "prepare", "feed"]


def test_dependency_detects_cycle():
    cyclic = [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]
    r = dependency.topological_order(cyclic)
    assert r["ok"] is False and r["order"] == []
    assert set(r["cycles"][0]) == {"a", "b"}


def test_dependency_reports_missing_prerequisite():
    r = dependency.topological_order([{"id": "x", "depends_on": ["ghost"]}])
    assert r["unmet_refs"] == [{"task": "x", "missing_prerequisite": "ghost"}]


def test_dependency_blocked_and_ready():
    blocked = dependency.blocked_tasks(FEED_CHAIN, completed={"receive"})
    ids = {b["id"] for b in blocked}
    assert "inspect" not in ids  # its only prereq is complete
    assert "store" in ids
    assert dependency.ready_tasks(FEED_CHAIN, completed={"receive"}) == ["inspect"]


# ── Scheduling engine ─────────────────────────────────────────────────────────

def test_scheduling_packs_and_overflows():
    occ = [
        {"date": "2026-01-02", "routine_id": "a", "name": "A", "duration": 300, "priority": "high"},
        {"date": "2026-01-02", "routine_id": "b", "name": "B", "duration": 300, "priority": "low"},
    ]
    r = scheduling.distribute(occ, daily_minutes=480)
    assert len(r["scheduled"]) == 1 and r["scheduled"][0]["routine_id"] == "a"  # high first
    assert len(r["unscheduled"]) == 1 and r["unscheduled"][0]["routine_id"] == "b"
    assert r["unscheduled"][0]["reason"]["fact_type"] == "unavailable"


def test_scheduling_respects_dependency_order_same_day():
    occ = [
        {"date": "2026-01-02", "routine_id": "feed", "name": "Feed", "duration": 30,
         "depends_on": ["prep"], "priority": "high"},
        {"date": "2026-01-02", "routine_id": "prep", "name": "Prep", "duration": 30, "priority": "low"},
    ]
    r = scheduling.distribute(occ, daily_minutes=480)
    names = [s["routine_id"] for s in r["scheduled"]]
    assert names == ["prep", "feed"]  # prerequisite first despite lower priority
    assert r["scheduled"][0]["start_minute"] < r["scheduled"][1]["start_minute"]


# ── Conflict engine ───────────────────────────────────────────────────────────

def test_conflict_worker_double_booking():
    items = [
        {"routine_id": "a", "name": "A", "date": "2026-01-02", "start": 360, "end": 420, "worker_id": "w1"},
        {"routine_id": "b", "name": "B", "date": "2026-01-02", "start": 400, "end": 460, "worker_id": "w1"},
    ]
    cs = conflict.detect(items)
    assert any(c["type"] == "worker_conflict" and c["severity"] == "high" for c in cs)
    assert cs[0]["resolution"]["fact_type"] == "strategic_recommendation"


def test_conflict_no_overlap_no_conflict():
    items = [
        {"routine_id": "a", "name": "A", "date": "2026-01-02", "start": 360, "end": 420, "worker_id": "w1"},
        {"routine_id": "b", "name": "B", "date": "2026-01-02", "start": 420, "end": 480, "worker_id": "w1"},
    ]
    assert conflict.detect(items) == []


def test_conflict_duplicate_routine():
    items = [
        {"routine_id": "a", "name": "Milking", "date": "2026-01-02", "start": 360, "end": 420},
        {"routine_id": "b", "name": "Milking", "date": "2026-01-02", "start": 360, "end": 420},
    ]
    assert any(c["type"] == "duplicate_routine" for c in conflict.detect(items))


def test_conflict_resource_shortage_and_unknown():
    out = conflict.resource_shortages(
        [{"resource": "feed", "quantity": 120}, {"resource": "mystery", "quantity": 5}],
        {"feed": 100})
    by_res = {r["resource"]: r for r in out}
    assert by_res["feed"]["shortfall"]["value"] == 20.0
    assert by_res["mystery"]["status"]["fact_type"] == "unknown"


# ── Labor allocation engine ───────────────────────────────────────────────────

def test_labor_assigns_by_skill_and_load():
    tasks = [
        {"id": "t1", "name": "Vaccinate", "required_skills": ["vet"], "duration": 60, "priority": "high"},
        {"id": "t2", "name": "Clean", "required_skills": [], "duration": 60},
    ]
    workers = [
        {"id": "w_vet", "skills": ["vet"], "load": 0, "performance": 0.9},
        {"id": "w_gen", "skills": [], "load": 0, "performance": 0.8},
    ]
    r = labor.allocate(tasks, workers)
    amap = {a["task_id"]: a["worker_id"] for a in r["assignments"]}
    assert amap["t1"] == "w_vet"  # only the vet is eligible
    assert r["summary"]["assigned"]["value"] == 2


def test_labor_unassigned_when_no_eligible_worker():
    r = labor.allocate(
        [{"id": "t", "name": "Weld", "required_skills": ["welding"], "duration": 30}],
        [{"id": "w", "skills": ["feeding"]}])
    assert r["assignments"] == []
    assert r["unassigned"][0]["status"]["fact_type"] == "unavailable"


def test_labor_is_deterministic():
    tasks = [{"id": "t", "required_skills": [], "duration": 30}]
    workers = [{"id": "b", "skills": [], "load": 0}, {"id": "a", "skills": [], "load": 0}]
    r1 = labor.allocate(tasks, workers)
    r2 = labor.allocate(tasks, workers)
    assert r1["assignments"] == r2["assignments"]


# ── Resource allocation engine ────────────────────────────────────────────────

def test_resource_shortage_and_headroom():
    r = resource.allocate(
        [{"resource": "feed", "quantity": 60}, {"resource": "feed", "quantity": 60},
         {"resource": "gloves", "quantity": 10}],
        {"feed": 100, "gloves": 50})
    shorts = {s["resource"] for s in r["shortages"]}
    assert "feed" in shorts and "gloves" not in shorts
    allocs = {a["resource"]: a for a in r["allocations"]}
    assert allocs["gloves"]["headroom"]["value"] == 40.0


def test_resource_unknown_stock():
    r = resource.allocate([{"resource": "x", "quantity": 1}], {})
    assert r["shortages"][0]["status"]["fact_type"] == "unknown"


# ── Workload balancing engine ─────────────────────────────────────────────────

def test_workload_flags_overload_and_recommends_move():
    r = workload.balance(
        [{"worker_id": "w1", "minutes": 600}, {"worker_id": "w2", "minutes": 100}],
        {"w1": 480, "w2": 480})
    assert r["overloaded"][0]["worker_id"] == "w1"
    assert r["recommendation"]["fact_type"] == "strategic_recommendation"
    assert "w1" in r["recommendation"]["value"]


def test_workload_even_needs_no_recommendation():
    r = workload.balance(
        [{"worker_id": "w1", "minutes": 300}, {"worker_id": "w2", "minutes": 300}],
        {"w1": 480, "w2": 480})
    assert r["recommendation"] is None


def test_workload_empty_is_unknown():
    r = workload.balance([], {})
    assert r["fairness"]["spread"]["fact_type"] == "unknown"


# ── Capacity planning engine ──────────────────────────────────────────────────

def test_capacity_identifies_bottleneck():
    r = capacity.analyze(
        {"labor_hours": 46, "equipment_units": 2, "time_hours": 40},
        {"labor_hours": 48, "equipment_units": 4, "time_hours": 56})
    assert r["bottleneck"]["value"] == "labor_hours"
    assert r["dimensions"]["labor_hours"]["status"]["value"] == "tight"


def test_capacity_growth_projection_is_forecast():
    r = capacity.analyze({"labor_hours": 40}, {"labor_hours": 48}, growth_factor=1.5)
    proj = r["growth_projection"]
    assert proj["projected_bottleneck_utilisation"]["fact_type"] == "forecast"
    assert proj["verdict"]["value"] == "exceeds_capacity"  # 40/48*1.5 = 1.25


def test_capacity_missing_dimension_unknown():
    r = capacity.analyze({"labor_hours": 10}, {})
    assert r["dimensions"]["labor_hours"]["utilisation"]["fact_type"] == "unknown"


# ── Compliance engine ─────────────────────────────────────────────────────────

def test_compliance_overdue_due_soon_compliant_unknown():
    as_of = date(2026, 1, 10)
    reqs = [
        {"key": "vac", "label": "Vaccination", "due_date": "2026-01-05"},
        {"key": "svc", "label": "Servicing", "due_date": "2026-01-12"},
        {"key": "ins", "label": "Inspection", "due_date": "2026-03-01"},
        {"key": "trn", "label": "Training"},
    ]
    r = compliance.evaluate(reqs, as_of=as_of)
    byk = {i["key"]: i["status"]["value"] for i in r["items"]}
    assert byk["vac"] == "overdue" and byk["svc"] == "due_soon"
    assert byk["ins"] == "compliant" and byk["trn"] is None  # unknown → value None
    assert r["counts"]["overdue"] == 1
    # Overdue items sort first and carry an alert.
    assert r["items"][0]["key"] == "vac" and "alert" in r["items"][0]


def test_compliance_derives_due_from_last_plus_interval():
    r = compliance.evaluate(
        [{"key": "biosec", "last_completed": "2026-01-01", "interval_days": 30}],
        as_of=date(2026, 2, 15))
    assert r["items"][0]["status"]["value"] == "overdue"  # due 2026-01-31


# ── Optimization engine ───────────────────────────────────────────────────────

def test_optimization_recommends_below_threshold_only():
    r = optimization.analyze({"completion_rate": 0.7, "on_time_rate": 0.95, "sample_size": 80})
    kinds = " ".join(rec["value"] for rec in r["recommendations"])
    assert "incomplete routines" in kinds  # completion below target
    assert "late starts" not in kinds       # on-time above target
    assert r["recommendations"][0]["confidence"] == "high"  # n=80


def test_optimization_skips_missing_metrics_no_fabrication():
    r = optimization.analyze({"completion_rate": 0.5})
    assert "on_time_rate" in r["skipped"]
    assert all("limitations" in rec for rec in r["recommendations"])


def test_optimization_confidence_scales_with_sample():
    low = optimization.analyze({"completion_rate": 0.5, "sample_size": 5})
    assert low["recommendations"][0]["confidence"] == "low"


# ── Routine generation engine ─────────────────────────────────────────────────

TEMPLATES = [
    {"id": "t-layer", "name": "Layer daily", "module": "poultry", "enterprise_type": "layer",
     "category": "feeding", "estimated_time_minutes": 60, "default_schedule": {"frequency": "daily"}},
    {"id": "t-generic", "name": "Records", "module": "poultry", "enterprise_type": "",
     "category": "administration", "estimated_time_minutes": 20, "default_schedule": {"frequency": "daily"}},
    {"id": "t-bsf", "name": "BSF moisture", "module": "bsf", "enterprise_type": "commercial",
     "category": "environmental", "estimated_time_minutes": 15, "default_schedule": {"frequency": "daily"}},
]


def test_generation_matches_module_and_scales_duration():
    r = generation.generate(
        {"module": "poultry", "enterprise_type": "layer", "farm_size": 500}, TEMPLATES)
    names = {p["name"] for p in r["proposed"]}
    assert "Layer daily" in names and "Records" in names and "BSF moisture" not in names
    layer = next(p for p in r["proposed"] if p["name"] == "Layer daily")
    assert layer["estimated_duration_minutes"]["value"] == 78  # 60 * 1.3 band
    assert layer["status"]["fact_type"] == "strategic_recommendation"


def test_generation_reports_limitations_when_profile_thin():
    r = generation.generate({"module": "poultry"}, TEMPLATES)
    assert any("farm size" in lim for lim in r["limitations"])


def test_generation_is_deterministic():
    p = {"module": "poultry", "enterprise_type": "layer", "farm_size": 500}
    assert generation.generate(p, TEMPLATES) == generation.generate(p, TEMPLATES)
