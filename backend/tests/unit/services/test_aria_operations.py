"""
ARIA operations director — the pure engine.

The organization view is the easiest place in the whole system to fabricate a
number: an average across farms hides a missing farm the moment you let it. So
the tests that carry the most weight here are about provenance and restraint —
every aggregate names its source and missing farms, no comparison drops a farm
with no data, and unknown stays unknown rather than becoming zero. Determinism is
the other pillar: the same organization state must always produce the same ranked
lists in the same order.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.services import aria_supervisor as sup
from app.services.aria_intelligence import FarmFacts, compute_health_score
from app.services.aria_supervisor import MonitorState
from app.services import aria_operations as ops
from app.services.aria_operations import (
    FarmSnapshot,
    TaskStatus,
    TaskView,
    WorkerRole,
    WorkerView,
    OrgTimelineEvent,
    OrgNotification,
    DashboardFilter,
)

TODAY = date(2026, 7, 25)
NOW = datetime(2026, 7, 25, 6, 0, 0)


def facts(**kw) -> FarmFacts:
    base = dict(
        farm_name="Farm", as_of=TODAY, active_flocks=1, total_birds=490,
        initial_birds=500, eggs_today=380, eggs_this_week=2600, eggs_prev_week=2500,
        hen_day_pct=76.0, feed_today_kg=Decimal("58"), feed_this_week_kg=Decimal("400"),
        feed_prev_week_kg=Decimal("395"), mortality_this_week=2, mortality_prev_week=1,
        days_since_feed_log=0, days_since_egg_log=0, days_since_any_log=0,
        days_since_weighin=3, days_since_water_log=0,
        water_today_litres=Decimal("120"), water_this_week_litres=Decimal("820"),
        water_prev_week_litres=Decimal("800"), inventory_tracked=5,
        disease_level="low", disease_score=10,
    )
    base.update(kw)
    return FarmFacts(**base)


def snap(fid: str, name: str, **kw) -> FarmSnapshot:
    f = facts(farm_name=name, **kw)
    h = compute_health_score(f)
    return FarmSnapshot(fid, name, f, h.score, sup.run_monitors(f))


def task(tid, farm_id="f1", farm_name="Farm A", owner_id="w1", owner_name="Winnie",
         status=TaskStatus.OPEN, title="Vaccinate", priority="normal",
         due=None, created=None, completed=None) -> TaskView:
    return TaskView(
        task_id=tid, farm_id=farm_id, farm_name=farm_name, title=title, status=status,
        priority=priority, owner_id=owner_id, owner_name=owner_name,
        due_at=due, created_at=created, completed_at=completed,
    )


# ── 1. Organization intelligence ──────────────────────────────────────────────


class TestOrganizationFacts:
    def test_aggregates_across_all_farms(self):
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "B")],
            organization_name="Org", as_of=TODAY,
        )
        assert org.farm_count == 2
        # 2600 + 2600 eggs summed.
        assert org.production.value == "5200"
        assert set(org.production.source_farms) == {"A", "B"}
        assert org.production.missing_farms == []

    def test_never_sums_missing_data(self):
        # B recorded no eggs — it must be excluded, not counted as zero.
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "B", days_since_egg_log=None)],
            organization_name="Org", as_of=TODAY,
        )
        assert org.production.value == "2600"
        assert org.production.source_farms == ["A"]
        assert org.production.missing_farms == ["B"]
        assert "excluded" in org.production.method

    def test_unknown_when_no_farm_has_data(self):
        org = ops.build_organization_facts(
            [snap("f1", "A", is_profitable=None), snap("f2", "B", is_profitable=None)],
            organization_name="Org", as_of=TODAY,
        )
        assert org.financial.available is False
        assert org.financial.value is None
        assert "unknown" in org.financial.method.lower()

    def test_health_is_averaged_not_summed(self):
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "B")],
            organization_name="Org", as_of=TODAY,
        )
        assert "averaged" in org.health.method

    def test_every_aggregate_carries_provenance(self):
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "B", days_since_feed_log=None)],
            organization_name="Org", as_of=TODAY,
        )
        for agg in (org.health, org.production, org.mortality, org.feed_usage,
                    org.water_usage, org.inventory, org.financial):
            assert agg.method, f"{agg.key} has no method"
            # source ∪ missing must cover the situation honestly.
            assert isinstance(agg.source_farms, list)
            assert isinstance(agg.missing_farms, list)

    def test_silent_farm_flagged(self):
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "Quiet", days_since_any_log=None)],
            organization_name="Org", as_of=TODAY,
        )
        assert org.silent_farms == ["Quiet"]

    def test_priorities_identify_their_farm(self):
        org = ops.build_organization_facts(
            [snap("f1", "A"), snap("f2", "Sick", mortality_this_week=40)],
            organization_name="Org", as_of=TODAY,
        )
        assert org.priorities
        for p in org.priorities:
            assert p.farm_name
            assert p.farm_id
        # The sick farm's mortality should be ranked, naming the farm.
        assert any(p.farm_name == "Sick" for p in org.priorities)

    def test_priorities_are_deterministic(self):
        snaps = [snap("f1", "A", mortality_this_week=30), snap("f2", "B", vaccinations_overdue=3)]
        a = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        b = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        assert [p.label for p in a.priorities] == [p.label for p in b.priorities]
        assert [p.rank for p in a.priorities] == list(range(1, len(a.priorities) + 1))


# ── 2. Cross-farm comparison ──────────────────────────────────────────────────


class TestCrossFarmComparison:
    def test_ranks_six_metrics(self):
        cmp = ops.compare_farms([snap("f1", "A"), snap("f2", "B")])
        assert {r.key for r in cmp.rankings} == {
            "production", "mortality", "feed_efficiency",
            "water_efficiency", "biosecurity", "health",
        }

    def test_best_and_needs_attention(self):
        cmp = ops.compare_farms([
            snap("f1", "High", eggs_this_week=3000),
            snap("f2", "Low", eggs_this_week=1000),
        ])
        prod = next(r for r in cmp.rankings if r.key == "production")
        assert prod.best.farm_name == "High"
        assert prod.needs_attention.farm_name == "Low"

    def test_lower_is_better_for_mortality(self):
        cmp = ops.compare_farms([
            snap("f1", "Clean", mortality_this_week=1),
            snap("f2", "Losing", mortality_this_week=30),
        ])
        mort = next(r for r in cmp.rankings if r.key == "mortality")
        assert mort.higher_is_better is False
        assert mort.best.farm_name == "Clean"

    def test_missing_farms_never_hidden(self):
        cmp = ops.compare_farms([
            snap("f1", "A"),
            snap("f2", "NoEggs", days_since_egg_log=None),
        ])
        prod = next(r for r in cmp.rankings if r.key == "production")
        assert [m.farm_name for m in prod.missing] == ["NoEggs"]
        assert all(m.available is False for m in prod.missing)
        assert "excluded from best/average" in prod.method

    def test_average_excludes_missing(self):
        cmp = ops.compare_farms([
            snap("f1", "A", eggs_this_week=2000),
            snap("f2", "B", eggs_this_week=4000),
            snap("f3", "C", days_since_egg_log=None),
        ])
        prod = next(r for r in cmp.rankings if r.key == "production")
        assert prod.average == "3000"   # (2000+4000)/2, not /3

    def test_deterministic_order(self):
        snaps = [snap("f1", "A", eggs_this_week=2000), snap("f2", "B", eggs_this_week=2000)]
        a = ops.compare_farms(snaps)
        b = ops.compare_farms(snaps)
        for ra, rb in zip(a.rankings, b.rankings):
            assert [x.farm_name for x in ra.ranked] == [x.farm_name for x in rb.ranked]


# ── 4. Task assignment rules ──────────────────────────────────────────────────


class TestAssignment:
    def test_allows_fresh_assignment(self):
        t = task("t1", owner_id=None, owner_name=None)
        assert ops.can_assign(t, "w2", [t]).allowed is True

    def test_refuses_reassign_to_same_owner(self):
        t = task("t1", owner_id="w1")
        chk = ops.can_assign(t, "w1", [t])
        assert chk.allowed is False
        assert "already assigned" in chk.reason

    def test_refuses_duplicate_open_task(self):
        existing = task("t1", owner_id="w2", title="Vaccinate", farm_id="f1")
        candidate = task("t2", owner_id="w1", title="Vaccinate", farm_id="f1")
        chk = ops.can_assign(candidate, "w2", [existing, candidate])
        assert chk.allowed is False
        assert "already has an open task" in chk.reason

    def test_completed_task_cannot_be_reassigned(self):
        t = task("t1", status=TaskStatus.DONE, owner_id="w1")
        assert ops.can_assign(t, "w2", [t]).allowed is False

    def test_same_title_different_farm_is_allowed(self):
        other = task("t1", owner_id="w2", title="Vaccinate", farm_id="f2", farm_name="B")
        candidate = task("t2", owner_id="w1", title="Vaccinate", farm_id="f1")
        assert ops.can_assign(candidate, "w2", [other, candidate]).allowed is True


# ── 5. Operations dashboard ───────────────────────────────────────────────────


class TestDashboard:
    def _dash(self, flt=None):
        snaps = [snap("f1", "A"), snap("f2", "B", mortality_this_week=40)]
        org = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        tasks = [
            task("t1", farm_id="f1", owner_id="w1", status=TaskStatus.OPEN),
            task("t2", farm_id="f2", owner_id="w2", status=TaskStatus.OVERDUE),
        ]
        workers = [
            WorkerView("w1", "Winnie", WorkerRole.WORKER, "Worker", ["f1"], ["A"]),
            WorkerView("w2", "Mark", WorkerRole.SUPERVISOR, "Supervisor", ["f2"], ["B"]),
        ]
        alerts = [
            OrgTimelineEvent(NOW, "f2", "B", "mortality", "Mortality critical",
                             severity=MonitorState.CRITICAL),
        ]
        notes = [OrgNotification(NOW, "f2", "B", "Alert", "body", "critical")]
        return ops.build_dashboard(
            organization=org, snapshots=snaps, tasks=tasks, workers=workers,
            alerts=alerts, notifications=notes, flt=flt,
        )

    def test_dashboard_has_all_sections(self):
        d = self._dash()
        assert len(d.farms) == 2
        assert d.tasks and d.workers and d.alerts and d.notifications
        assert d.operational_status

    def test_filter_by_farm(self):
        d = self._dash(DashboardFilter(farm_id="f2"))
        assert {f.farm_id for f in d.farms} == {"f2"}
        assert all(t.farm_id == "f2" for t in d.tasks)

    def test_filter_by_worker(self):
        d = self._dash(DashboardFilter(worker_id="w1"))
        assert all(t.owner_id == "w1" for t in d.tasks)

    def test_filter_by_severity(self):
        d = self._dash(DashboardFilter(severity=MonitorState.CRITICAL))
        assert all(a.severity is MonitorState.CRITICAL for a in d.alerts)

    def test_status_reflects_worst_farm(self):
        d = self._dash()
        # farm B has 40 losses/wk on 490 birds → critical mortality.
        assert "critical" in d.operational_status.lower() or "attention" in d.operational_status.lower()


# ── 6. Organization timeline ──────────────────────────────────────────────────


class TestTimeline:
    def test_merges_and_sorts_newest_first(self):
        events = [
            OrgTimelineEvent(NOW - timedelta(days=2), "f1", "A", "feed", "Feed"),
            OrgTimelineEvent(NOW, "f2", "B", "production", "Eggs"),
        ]
        merged = ops.merge_timeline(events)
        assert [e.title for e in merged] == ["Eggs", "Feed"]

    def test_deduplicates_identical_events(self):
        e = OrgTimelineEvent(NOW, "f1", "A", "reminder", "Vaccinate done")
        dup = OrgTimelineEvent(NOW, "f1", "A", "reminder", "Vaccinate done")
        merged = ops.merge_timeline([e, dup])
        assert len(merged) == 1

    def test_filters_by_farm_and_worker(self):
        events = [
            OrgTimelineEvent(NOW, "f1", "A", "feed", "Feed A", worker="Winnie"),
            OrgTimelineEvent(NOW, "f2", "B", "feed", "Feed B", worker="Mark"),
        ]
        assert len(ops.merge_timeline(events, farm_id="f1")) == 1
        assert len(ops.merge_timeline(events, worker="Mark")) == 1

    def test_events_carry_farm_and_severity(self):
        merged = ops.merge_timeline([
            OrgTimelineEvent(NOW, "f1", "Alpha", "mortality", "loss",
                             severity=MonitorState.WARNING),
        ])
        assert merged[0].farm_name == "Alpha"
        assert merged[0].severity is MonitorState.WARNING


# ── 7. Performance analytics ──────────────────────────────────────────────────


class TestAnalytics:
    def _analytics(self):
        snaps = [snap("f1", "A"), snap("f2", "B")]
        workers = [
            WorkerView("w1", "Winnie", WorkerRole.WORKER, "Worker", ["f1"], ["A"]),
        ]
        tasks = [
            task("t1", owner_id="w1", status=TaskStatus.DONE,
                 created=NOW - timedelta(hours=5), completed=NOW),
            task("t2", owner_id="w1", status=TaskStatus.OVERDUE),
        ]
        return ops.performance_analytics(snaps, tasks, workers)

    def test_worker_completion_rate(self):
        a = self._analytics()
        w = a.workers[0]
        assert w.assigned == 2
        assert w.completed == 1
        assert w.completion_rate == "50%"
        assert w.avg_completion_hours == "5.0"

    def test_every_metric_exposes_calculation(self):
        a = self._analytics()
        for m in a.farm_productivity + a.org_metrics + a.trends:
            assert m.method, f"{m.key} exposes no calculation"

    def test_inventory_turnover_is_honestly_unavailable(self):
        a = self._analytics()
        turnover = next(m for m in a.org_metrics if m.key == "inventory_turnover")
        assert turnover.available is False
        assert "not" in turnover.method.lower()

    def test_missed_reminders_counts_overdue(self):
        a = self._analytics()
        missed = next(m for m in a.org_metrics if m.key == "missed_reminders")
        assert missed.value == "1"

    def test_production_trend_direction(self):
        snaps = [snap("f1", "A", eggs_this_week=3000, eggs_prev_week=2000)]
        a = ops.performance_analytics(snaps, [], [])
        trend = next(m for m in a.trends if m.key == "prod_trend")
        assert trend.available is True
        assert trend.value.startswith("+")


# ── 8. Role-based workspace ───────────────────────────────────────────────────


class TestWorkspaceScope:
    def test_administrator_sees_everything(self):
        w = ops.workspace_scope("enterprise_owner", member_farm_ids=["f1"],
                                 org_farm_ids=["f1", "f2"])
        assert w.tier == "administrator"
        assert w.farm_ids is None      # all org farms
        assert w.can_assign is True
        assert "analytics" in w.sections and "financial" in w.sections

    def test_manager_sees_organization(self):
        w = ops.workspace_scope("farm_owner", member_farm_ids=["f1"],
                                 org_farm_ids=["f1", "f2"])
        assert w.tier == "manager"
        assert w.farm_ids is None

    def test_supervisor_scoped_to_assigned_farms(self):
        w = ops.workspace_scope("farm_manager", member_farm_ids=["f1"],
                                 org_farm_ids=["f1", "f2"])
        assert w.tier == "supervisor"
        assert w.farm_ids == ["f1"]
        assert w.can_assign is True

    def test_worker_sees_only_own_tasks(self):
        w = ops.workspace_scope("farm_worker", member_farm_ids=["f1"],
                                 org_farm_ids=["f1", "f2"])
        assert w.tier == "worker"
        assert w.own_tasks_only is True
        assert w.can_assign is False
        assert w.sections == {"dashboard", "timeline", "tasks"}

    def test_worker_cannot_reach_unassigned_farm(self):
        # Member of f1 only; org has f1,f2 → scope must not include f2.
        w = ops.workspace_scope("farm_worker", member_farm_ids=["f1"],
                                 org_farm_ids=["f1", "f2"])
        assert "f2" not in (w.farm_ids or [])

    def test_readonly_cannot_assign(self):
        for role in ("viewer", "vet_consultant"):
            w = ops.workspace_scope(role, member_farm_ids=["f1"], org_farm_ids=["f1"])
            assert w.can_assign is False

    def test_role_mapping(self):
        assert ops.role_of_membership("farm_manager")[0] is WorkerRole.SUPERVISOR
        assert ops.role_of_membership("vet_consultant")[0] is WorkerRole.VET
        assert ops.role_of_membership("something_custom")[0] is WorkerRole.CUSTOM


# ── 9. Organization reports ───────────────────────────────────────────────────


class TestReports:
    def _report(self, period="weekly"):
        snaps = [snap("f1", "A"), snap("f2", "B", mortality_this_week=40)]
        org = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        tasks = [
            task("t1", status=TaskStatus.DONE),
            task("t2", status=TaskStatus.OVERDUE),
        ]
        analytics = ops.performance_analytics(snaps, tasks, [])
        return ops.build_organization_report(org, analytics, tasks, period=period)

    def test_report_has_required_sections(self):
        r = self._report()
        labels = {s.label for s in r.sections}
        for needed in ("Weekly production", "Net position", "Weekly mortality",
                       "Weekly feed usage", "Items needing reorder", "Task completion"):
            assert needed in labels, f"missing {needed}"

    def test_report_lists_risks_and_priorities(self):
        r = self._report()
        assert r.risks
        assert r.priorities

    def test_unavailable_lines_are_marked(self):
        snaps = [snap("f1", "A", is_profitable=None)]
        org = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        analytics = ops.performance_analytics(snaps, [], [])
        r = ops.build_organization_report(org, analytics, [], period="weekly")
        fin = next(s for s in r.sections if s.label == "Net position")
        assert fin.available is False
        assert fin.value == "Not enough recorded data."

    def test_monthly_report_does_not_fabricate_totals(self):
        r = self._report(period="monthly")
        assert any("not extrapolated" in n or "7-day" in n for n in r.notes)

    def test_silent_farm_noted(self):
        snaps = [snap("f1", "A"), snap("f2", "Quiet", days_since_any_log=None)]
        org = ops.build_organization_facts(snaps, organization_name="Org", as_of=TODAY)
        analytics = ops.performance_analytics(snaps, [], [])
        r = ops.build_organization_report(org, analytics, [], period="weekly")
        assert any("Quiet" in n for n in r.notes)
