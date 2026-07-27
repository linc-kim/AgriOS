"""
ARIA — the operations director.

Parts 4–6 made ARIA the brain of a single farm: it watches, plans and answers
for one flock of records. Part 7 lifts that same brain to an entire
organization — many farms, many workers, many supervisors — without inventing a
second way of thinking about a farm. Every organization figure here is built by
*aggregating the per-farm `FarmFacts` the existing engine already produces*, so
the multi-farm view can never disagree with the single-farm one.

The module is pure by construction, exactly like `aria_supervisor` and
`aria_planning`. Each function takes plain snapshots — a `FarmSnapshot` per farm,
lists of already-gathered tasks/workers/timeline events — and returns plain data.
`aria_operations_data` does all the I/O and hands the results in. That split is
what lets the organization intelligence be exercised exhaustively in tests, and
it is what guarantees the director can only ever reason about numbers a real
service computed from real records.

The honesty rules from Part 4 get *stricter* at organization scale, because an
average across farms is the easiest place in the whole system to fabricate a
number. Three rules run through everything:

*Never average unavailable data.* A farm that has recorded no water is not a
farm that used zero water. Every aggregate is computed only over the farms that
actually recorded the metric, and it always reports which farms those were, which
farms were missing, and how it was calculated.

*Never hide a missing farm.* A comparison that silently drops the two farms with
no data is a lie of omission. Missing farms are carried alongside every ranking,
never removed from it.

*Unknown stays Unknown.* When a figure cannot be computed from records — an
organization profit with no finance data anywhere — it is returned unavailable
with the reason, never estimated to make a dashboard look complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.services.aria_intelligence import FarmFacts
from app.services.aria_supervisor import (
    Monitor,
    MonitorState,
    _STATE_RANK,
    overall_state,
)


# ── Inputs ────────────────────────────────────────────────────────────────────


@dataclass
class FarmSnapshot:
    """
    One farm's supervised state, as plain values.

    Assembled by the data layer from the Part 4/5 engine: the `FarmFacts`
    snapshot, its health score, and the eight monitors already run over it. The
    operations engine never re-derives any of this — it aggregates it.
    """

    farm_id: str
    farm_name: str
    facts: FarmFacts
    health_score: int
    monitors: list[Monitor] = field(default_factory=list)

    @property
    def overall(self) -> MonitorState:
        return overall_state(self.monitors)


class TaskStatus(str, Enum):
    OPEN = "open"
    OVERDUE = "overdue"
    DONE = "done"


@dataclass
class TaskView:
    """
    An assignable unit of work — a Reminder, seen through the operations lens.

    The data layer maps a `Reminder` row onto this (its owner, farm, dates and
    priority), so the engine reasons about assignment and completion without a
    parallel task model of its own.
    """

    task_id: str
    farm_id: str
    farm_name: str
    title: str
    status: TaskStatus
    priority: str
    owner_id: str | None
    owner_name: str | None
    due_at: datetime | None
    created_at: datetime | None
    completed_at: datetime | None
    #: Reassignment/completion events, oldest first: {at, action, actor, detail}.
    history: list[dict] = field(default_factory=list)


class WorkerRole(str, Enum):
    """The operational role a worker fills, derived from their membership role."""

    MANAGER = "manager"          # farm_owner / enterprise_owner — org operations
    SUPERVISOR = "supervisor"    # farm_manager — assigned farms
    WORKER = "worker"            # farm_worker — assigned work
    VET = "veterinarian"         # vet_consultant
    ACCOUNTANT = "accountant"    # (custom, finance-only)
    VIEWER = "viewer"
    CUSTOM = "custom"


@dataclass
class WorkerView:
    """A member of the organization, with the farms they belong to."""

    user_id: str
    name: str
    role: WorkerRole
    role_label: str
    farm_ids: list[str] = field(default_factory=list)
    farm_names: list[str] = field(default_factory=list)


@dataclass
class OrgTimelineEvent:
    """A merged, farm- and worker-attributed activity event."""

    at: datetime
    farm_id: str
    farm_name: str
    kind: str
    title: str
    detail: str = ""
    worker: str | None = None
    severity: MonitorState = MonitorState.NORMAL

    @property
    def dedupe_key(self) -> tuple:
        # Two producers recording the same real event (e.g. a reminder that also
        # surfaces as an alert) collapse to one row.
        return (self.farm_id, self.kind, self.title, self.at.replace(microsecond=0))


@dataclass
class OrgNotification:
    at: datetime
    farm_id: str
    farm_name: str
    title: str
    body: str
    severity: str


# ── Provenance-carrying aggregate ─────────────────────────────────────────────


@dataclass
class Aggregate:
    """
    One organization-level figure, with the provenance the honesty rules demand.

    `available` is False when no farm contributed — the value is then None and
    the method explains why. `source_farms` and `missing_farms` are always
    populated so a reader can see exactly which farms are behind (or absent from)
    the number.
    """

    key: str
    label: str
    value: str | None
    unit: str
    available: bool
    source_farms: list[str]
    missing_farms: list[str]
    method: str


def _agg_number(
    key: str,
    label: str,
    unit: str,
    contributions: list[tuple[str, Decimal | int | float | None]],
    *,
    how: str,
    reduce: str = "sum",
    round_to: int = 0,
) -> Aggregate:
    """
    Fold per-farm contributions into one aggregate, carrying provenance.

    `contributions` is a list of `(farm_name, value_or_None)`. A None value means
    the farm did not record the metric — it goes to `missing_farms` and is never
    folded into a sum or an average.
    """
    present = [(n, Decimal(str(v))) for n, v in contributions if v is not None]
    missing = [n for n, v in contributions if v is None]
    source = [n for n, _ in present]

    if not present:
        return Aggregate(
            key, label, None, unit, False, source, missing,
            f"No farm has recorded {label.lower()} — reported as unknown, not zero.",
        )

    total = sum((v for _, v in present), Decimal("0"))
    if reduce == "avg":
        result = total / len(present)
        method = f"{how} · averaged over {len(present)} farm(s) with data"
    else:
        result = total
        method = f"{how} · summed over {len(present)} farm(s) with data"

    if missing:
        method += f"; {len(missing)} farm(s) excluded for missing data"

    q = Decimal(10) ** -round_to
    result = result.quantize(q)
    text = str(int(result)) if round_to == 0 else f"{result:.{round_to}f}"
    return Aggregate(key, label, text, unit, True, source, missing, method)


# ── 1. Organization intelligence ──────────────────────────────────────────────


@dataclass
class OrgPriority:
    rank: int
    label: str
    why: str
    farm_id: str
    farm_name: str
    severity: MonitorState
    source: str


@dataclass
class OrganizationFacts:
    organization_name: str
    as_of: date
    farm_count: int
    farm_names: list[str]
    overall: MonitorState
    health: Aggregate
    production: Aggregate
    mortality: Aggregate
    feed_usage: Aggregate
    water_usage: Aggregate
    inventory: Aggregate
    financial: Aggregate
    priorities: list[OrgPriority]
    #: Farms with no records at all, so the org view can flag data gaps.
    silent_farms: list[str] = field(default_factory=list)


def _mortality_rate(f: FarmFacts) -> float | None:
    if f.days_since_any_log is None or f.total_birds <= 0:
        return None
    return f.mortality_this_week / f.total_birds * 100


def build_organization_facts(
    snapshots: list[FarmSnapshot],
    *,
    organization_name: str,
    as_of: date,
) -> OrganizationFacts:
    """
    Aggregate every farm's `FarmFacts` into one organization snapshot.

    Every figure is provenance-carrying: it names the farms that contributed, the
    farms that were missing, and the arithmetic used. Nothing is estimated to
    fill a gap — an aggregate with no contributing farm is returned unavailable.
    """
    names = [s.farm_name for s in snapshots]

    health = _agg_number(
        "health", "Organization health", "/100",
        [(s.farm_name, s.health_score) for s in snapshots],
        how="Mean of per-farm health scores", reduce="avg",
    )
    production = _agg_number(
        "production", "Weekly production", "eggs",
        [(s.farm_name, s.facts.eggs_this_week if s.facts.days_since_egg_log is not None else None)
         for s in snapshots],
        how="Eggs collected in the last 7 days",
    )
    mortality = _agg_number(
        "mortality", "Weekly mortality", "birds",
        [(s.farm_name, s.facts.mortality_this_week if s.facts.days_since_any_log is not None else None)
         for s in snapshots],
        how="Birds lost in the last 7 days",
    )
    feed_usage = _agg_number(
        "feed", "Weekly feed usage", "kg",
        [(s.farm_name, s.facts.feed_this_week_kg if s.facts.days_since_feed_log is not None else None)
         for s in snapshots],
        how="Feed consumed in the last 7 days", round_to=1,
    )
    water_usage = _agg_number(
        "water", "Weekly water usage", "L",
        [(s.farm_name, s.facts.water_this_week_litres) for s in snapshots],
        how="Water consumed in the last 7 days", round_to=1,
    )

    # Inventory: count items needing attention across the org, but only over
    # farms that actually track inventory — a farm tracking nothing is missing,
    # not a farm with a full store.
    inv_contribs = [
        (s.farm_name,
         (len(s.facts.inventory_low) + len(s.facts.inventory_out)) if s.facts.inventory_tracked else None)
        for s in snapshots
    ]
    inventory = _agg_number(
        "inventory", "Items needing reorder", "items", inv_contribs,
        how="Low + out-of-stock items",
    )

    # Financial: net profit, only over farms with recorded finance.
    fin_contribs = [
        (s.farm_name, s.facts.gross_profit if s.facts.is_profitable is not None else None)
        for s in snapshots
    ]
    financial = _agg_number(
        "financial", "Net position", "", fin_contribs,
        how="Sum of per-farm gross profit/loss", round_to=2,
    )

    priorities = _org_priorities(snapshots)
    silent = [s.farm_name for s in snapshots if s.facts.days_since_any_log is None]
    overall = _worst_state([s.overall for s in snapshots])

    return OrganizationFacts(
        organization_name=organization_name,
        as_of=as_of,
        farm_count=len(snapshots),
        farm_names=names,
        overall=overall,
        health=health,
        production=production,
        mortality=mortality,
        feed_usage=feed_usage,
        water_usage=water_usage,
        inventory=inventory,
        financial=financial,
        priorities=priorities,
        silent_farms=silent,
    )


def _worst_state(states: list[MonitorState]) -> MonitorState:
    if not states:
        return MonitorState.NORMAL
    return max(states, key=lambda s: _STATE_RANK[s])


def _org_priorities(snapshots: list[FarmSnapshot], *, limit: int = 10) -> list[OrgPriority]:
    """
    Rank what the organization must attend to, from one rule set.

    Every farm's non-normal monitors compete on a single scale (monitor severity
    × a small nudge for the farm's overall health), so the same organization
    state always produces the same ordered list, and every item names its farm.
    """
    scored: list[tuple[int, str, OrgPriority]] = []
    for s in snapshots:
        for m in s.monitors:
            if m.state is MonitorState.NORMAL:
                continue
            score = _STATE_RANK[m.state] * 100 + (100 - s.health_score)
            key = f"{s.farm_id}:{m.key}"
            scored.append((score, key, OrgPriority(
                rank=0, label=f"{s.farm_name}: {m.label} {m.state.value}",
                why=m.why, farm_id=s.farm_id, farm_name=s.farm_name,
                severity=m.state, source=m.key,
            )))

    scored.sort(key=lambda t: (-t[0], t[1]))
    out: list[OrgPriority] = []
    for i, (_score, _key, item) in enumerate(scored[:limit], start=1):
        item.rank = i
        out.append(item)
    return out


# ── 2. Cross-farm comparison ──────────────────────────────────────────────────


@dataclass
class FarmRank:
    farm_id: str
    farm_name: str
    value: float | None
    display: str
    available: bool


@dataclass
class Ranking:
    key: str
    label: str
    unit: str
    higher_is_better: bool
    ranked: list[FarmRank]        # farms with data, best → worst
    missing: list[FarmRank]       # farms without data — never hidden
    best: FarmRank | None
    needs_attention: FarmRank | None
    average: str | None
    method: str


@dataclass
class CrossFarmComparison:
    farm_count: int
    rankings: list[Ranking]


def _rank_metric(
    key: str,
    label: str,
    unit: str,
    higher_is_better: bool,
    values: list[tuple[str, str, float | None, str]],
    *,
    method: str,
    round_to: int = 1,
) -> Ranking:
    """
    Order farms by one metric, keeping missing farms visible.

    `values` is `(farm_id, farm_name, value_or_None, display)`. Farms with a
    value are ranked best-first per `higher_is_better`; farms without are carried
    in `missing` and excluded from the average — never dropped.
    """
    present = [FarmRank(fid, fn, v, disp, True) for fid, fn, v, disp in values if v is not None]
    missing = [FarmRank(fid, fn, None, "Not enough recorded data.", False)
               for fid, fn, v, disp in values if v is None]

    present.sort(key=lambda r: (-(r.value or 0) if higher_is_better else (r.value or 0), r.farm_name))
    missing.sort(key=lambda r: r.farm_name)

    best = present[0] if present else None
    needs = present[-1] if present else None
    avg_text: str | None = None
    if present:
        avg = sum(r.value for r in present) / len(present)  # type: ignore[misc]
        avg_text = f"{avg:.{round_to}f}"

    full_method = method
    if missing:
        full_method += f"; {len(missing)} farm(s) shown without data, excluded from best/average"
    return Ranking(
        key=key, label=label, unit=unit, higher_is_better=higher_is_better,
        ranked=present, missing=missing, best=best, needs_attention=needs,
        average=avg_text, method=full_method,
    )


def compare_farms(snapshots: list[FarmSnapshot]) -> CrossFarmComparison:
    """
    Rank farms on the six operational metrics the spec names.

    Best, average and needs-attention are computed only over farms with data;
    farms missing a metric are always shown, never hidden, so a comparison can
    never flatter the organization by omission.
    """

    def prod(s: FarmSnapshot) -> tuple[float | None, str]:
        if s.facts.days_since_egg_log is None:
            return None, ""
        return float(s.facts.eggs_this_week), f"{s.facts.eggs_this_week} eggs/wk"

    def mort(s: FarmSnapshot) -> tuple[float | None, str]:
        r = _mortality_rate(s.facts)
        return (None, "") if r is None else (r, f"{r:.2f}%/wk")

    def feed_eff(s: FarmSnapshot) -> tuple[float | None, str]:
        f = s.facts
        if f.days_since_egg_log is None or f.days_since_feed_log is None or f.feed_this_week_kg <= 0:
            return None, ""
        eff = f.eggs_this_week / float(f.feed_this_week_kg)
        return eff, f"{eff:.2f} eggs/kg"

    def water_eff(s: FarmSnapshot) -> tuple[float | None, str]:
        f = s.facts
        if f.days_since_egg_log is None or f.water_this_week_litres is None or f.water_this_week_litres <= 0:
            return None, ""
        eff = f.eggs_this_week / float(f.water_this_week_litres)
        return eff, f"{eff:.2f} eggs/L"

    def biosecurity(s: FarmSnapshot) -> tuple[float | None, str]:
        # Lower disease score = stronger biosecurity. Always available (defaults low).
        return float(s.facts.disease_score), f"risk {s.facts.disease_score}/100 ({s.facts.disease_level})"

    def health(s: FarmSnapshot) -> tuple[float | None, str]:
        return float(s.health_score), f"{s.health_score}/100"

    rankings = [
        _rank_metric("production", "Production", "eggs/wk", True,
                     [(s.farm_id, s.farm_name, *prod(s)) for s in snapshots],
                     method="Eggs collected per farm in the last 7 days", round_to=0),
        _rank_metric("mortality", "Mortality", "%/wk", False,
                     [(s.farm_id, s.farm_name, *mort(s)) for s in snapshots],
                     method="Weekly losses as a share of each farm's flock", round_to=2),
        _rank_metric("feed_efficiency", "Feed efficiency", "eggs/kg", True,
                     [(s.farm_id, s.farm_name, *feed_eff(s)) for s in snapshots],
                     method="Eggs per kg of feed, over farms recording both", round_to=2),
        _rank_metric("water_efficiency", "Water efficiency", "eggs/L", True,
                     [(s.farm_id, s.farm_name, *water_eff(s)) for s in snapshots],
                     method="Eggs per litre of water, over farms recording both", round_to=2),
        _rank_metric("biosecurity", "Biosecurity", "risk", False,
                     [(s.farm_id, s.farm_name, *biosecurity(s)) for s in snapshots],
                     method="Inferred disease-risk score (lower is stronger)", round_to=0),
        _rank_metric("health", "Health score", "/100", True,
                     [(s.farm_id, s.farm_name, *health(s)) for s in snapshots],
                     method="Composite per-farm health score", round_to=0),
    ]
    return CrossFarmComparison(farm_count=len(snapshots), rankings=rankings)


# ── 4. Task assignment (pure rules) ───────────────────────────────────────────


@dataclass
class AssignmentCheck:
    allowed: bool
    reason: str


def can_assign(task: TaskView, new_owner_id: str, open_tasks: list[TaskView]) -> AssignmentCheck:
    """
    Decide whether an assignment is permitted, deterministically.

    Prevents duplicate assignments: the same open task title, on the same farm,
    already owned by the target worker, is refused. A completed task never blocks
    a fresh assignment.
    """
    if task.status is TaskStatus.DONE:
        return AssignmentCheck(False, "This task is already completed.")
    if task.owner_id == new_owner_id and task.status is not TaskStatus.DONE:
        return AssignmentCheck(False, "This task is already assigned to that worker.")
    dupe = any(
        t.task_id != task.task_id
        and t.status is not TaskStatus.DONE
        and t.farm_id == task.farm_id
        and t.owner_id == new_owner_id
        and t.title.strip().lower() == task.title.strip().lower()
        for t in open_tasks
    )
    if dupe:
        return AssignmentCheck(False, "That worker already has an open task with this title on this farm.")
    return AssignmentCheck(True, "OK")


# ── 5. Operations dashboard ───────────────────────────────────────────────────


@dataclass
class FarmSummary:
    farm_id: str
    farm_name: str
    overall: MonitorState
    health_score: int
    open_tasks: int
    overdue_tasks: int
    alert_count: int
    silent: bool


@dataclass
class OperationsDashboard:
    as_of: date
    organization: OrganizationFacts
    farms: list[FarmSummary]
    alerts: list[OrgTimelineEvent]        # current org alerts (severity-tagged)
    priorities: list[OrgPriority]
    tasks: list[TaskView]
    workers: list[WorkerView]
    notifications: list[OrgNotification]
    operational_status: str


@dataclass
class DashboardFilter:
    farm_id: str | None = None
    worker_id: str | None = None
    severity: MonitorState | None = None
    since: datetime | None = None
    until: datetime | None = None


def _task_matches(t: TaskView, flt: DashboardFilter) -> bool:
    if flt.farm_id and t.farm_id != flt.farm_id:
        return False
    if flt.worker_id and t.owner_id != flt.worker_id:
        return False
    if flt.since and t.due_at and t.due_at < flt.since:
        return False
    if flt.until and t.due_at and t.due_at > flt.until:
        return False
    return True


def build_dashboard(
    *,
    organization: OrganizationFacts,
    snapshots: list[FarmSnapshot],
    tasks: list[TaskView],
    workers: list[WorkerView],
    alerts: list[OrgTimelineEvent],
    notifications: list[OrgNotification],
    flt: DashboardFilter | None = None,
) -> OperationsDashboard:
    """
    Assemble the unified operations dashboard, applying any active filter.

    Purely a composition of already-gathered pieces — the dashboard invents
    nothing. Filtering by farm, worker, severity and date is applied here so the
    same gathered data serves every view.
    """
    flt = flt or DashboardFilter()

    def farm_ok(fid: str) -> bool:
        return not flt.farm_id or fid == flt.farm_id

    def sev_ok(sev: MonitorState) -> bool:
        return not flt.severity or _STATE_RANK[sev] >= _STATE_RANK[flt.severity]

    tasks_f = [t for t in tasks if _task_matches(t, flt)]
    alerts_f = [
        a for a in alerts
        if farm_ok(a.farm_id) and sev_ok(a.severity)
        and (not flt.since or a.at >= flt.since) and (not flt.until or a.at <= flt.until)
    ]
    workers_f = [
        w for w in workers
        if (not flt.worker_id or w.user_id == flt.worker_id)
        and (not flt.farm_id or flt.farm_id in w.farm_ids)
    ]
    priorities_f = [p for p in organization.priorities if farm_ok(p.farm_id) and sev_ok(p.severity)]

    summaries: list[FarmSummary] = []
    for s in snapshots:
        if not farm_ok(s.farm_id):
            continue
        ftasks = [t for t in tasks_f if t.farm_id == s.farm_id]
        summaries.append(FarmSummary(
            farm_id=s.farm_id, farm_name=s.farm_name, overall=s.overall,
            health_score=s.health_score,
            open_tasks=sum(1 for t in ftasks if t.status is not TaskStatus.DONE),
            overdue_tasks=sum(1 for t in ftasks if t.status is TaskStatus.OVERDUE),
            alert_count=sum(1 for a in alerts_f if a.farm_id == s.farm_id),
            silent=s.facts.days_since_any_log is None,
        ))

    status = _operational_status(summaries, alerts_f)
    return OperationsDashboard(
        as_of=organization.as_of,
        organization=organization,
        farms=summaries,
        alerts=sorted(alerts_f, key=lambda a: (-_STATE_RANK[a.severity], a.at))[:50],
        priorities=priorities_f,
        tasks=sorted(tasks_f, key=_task_sort_key),
        workers=workers_f,
        notifications=sorted(notifications, key=lambda n: n.at, reverse=True)[:50],
        operational_status=status,
    )


def _task_sort_key(t: TaskView) -> tuple:
    status_rank = {TaskStatus.OVERDUE: 0, TaskStatus.OPEN: 1, TaskStatus.DONE: 2}
    return (status_rank[t.status], t.due_at or datetime.max, t.title)


def _operational_status(farms: list[FarmSummary], alerts: list[OrgTimelineEvent]) -> str:
    if not farms:
        return "No farms in scope."
    worst = _worst_state([f.overall for f in farms])
    crit = sum(1 for a in alerts if a.severity is MonitorState.CRITICAL)
    if worst is MonitorState.CRITICAL:
        return f"Action required — {crit} critical alert(s) across the organization."
    if worst is MonitorState.WARNING:
        return "Attention needed — one or more farms are in warning."
    if worst is MonitorState.WATCH:
        return "Stable — minor items to watch."
    return "All farms operating normally."


# ── 6. Organization timeline ──────────────────────────────────────────────────


def merge_timeline(
    events: list[OrgTimelineEvent],
    *,
    farm_id: str | None = None,
    worker: str | None = None,
    severity: MonitorState | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[OrgTimelineEvent]:
    """
    Merge every farm's events into one feed, newest first, deduplicated.

    Two producers recording the same real event collapse to a single row via
    `dedupe_key`, so a reminder that also raised an alert is not shown twice.
    Filters (farm, worker, severity, date) narrow the merged feed without ever
    reordering it inconsistently.
    """
    seen: set[tuple] = set()
    merged: list[OrgTimelineEvent] = []
    for e in sorted(events, key=lambda x: x.at, reverse=True):
        if e.dedupe_key in seen:
            continue
        seen.add(e.dedupe_key)
        if farm_id and e.farm_id != farm_id:
            continue
        if worker and e.worker != worker:
            continue
        if severity and _STATE_RANK[e.severity] < _STATE_RANK[severity]:
            continue
        if since and e.at < since:
            continue
        if until and e.at > until:
            continue
        merged.append(e)
    return merged[:limit]


# ── 7. Performance analytics ──────────────────────────────────────────────────


@dataclass
class Metric:
    key: str
    label: str
    value: str | None
    unit: str
    available: bool
    method: str            # the exact calculation, always exposed
    detail: str = ""


@dataclass
class WorkerPerformance:
    user_id: str
    name: str
    assigned: int
    completed: int
    overdue: int
    completion_rate: str | None    # None when nothing assigned
    avg_completion_hours: str | None
    method: str


@dataclass
class PerformanceAnalytics:
    workers: list[WorkerPerformance]
    farm_productivity: list[Metric]
    org_metrics: list[Metric]
    trends: list[Metric]


def _completion_hours(t: TaskView) -> float | None:
    if t.completed_at is None or t.created_at is None:
        return None
    delta = t.completed_at - t.created_at
    return max(0.0, delta.total_seconds() / 3600)


def performance_analytics(
    snapshots: list[FarmSnapshot],
    tasks: list[TaskView],
    workers: list[WorkerView],
) -> PerformanceAnalytics:
    """
    Deterministic performance metrics, each exposing its own calculation.

    Nothing here is a black box: every metric carries the arithmetic used, and a
    metric that cannot be computed from records (inventory turnover with no
    movement data) is returned unavailable rather than guessed.
    """
    # Per-worker completion.
    worker_perf: list[WorkerPerformance] = []
    for w in sorted(workers, key=lambda x: x.name):
        wt = [t for t in tasks if t.owner_id == w.user_id]
        assigned = len(wt)
        completed = sum(1 for t in wt if t.status is TaskStatus.DONE)
        overdue = sum(1 for t in wt if t.status is TaskStatus.OVERDUE)
        rate = f"{completed / assigned * 100:.0f}%" if assigned else None
        hours = [h for h in (_completion_hours(t) for t in wt) if h is not None]
        avg_h = f"{sum(hours) / len(hours):.1f}" if hours else None
        worker_perf.append(WorkerPerformance(
            user_id=w.user_id, name=w.name, assigned=assigned, completed=completed,
            overdue=overdue, completion_rate=rate, avg_completion_hours=avg_h,
            method="completed ÷ assigned; average completion time from done_at − created_at",
        ))

    # Farm productivity: eggs per bird per farm.
    farm_prod: list[Metric] = []
    for s in sorted(snapshots, key=lambda x: x.farm_name):
        f = s.facts
        if f.days_since_egg_log is None or f.total_birds <= 0:
            farm_prod.append(Metric(
                f"prod:{s.farm_id}", f"{s.farm_name} productivity", None, "eggs/bird/wk",
                False, "eggs_this_week ÷ active birds — no egg log or bird count recorded",
            ))
        else:
            v = f.eggs_this_week / f.total_birds
            farm_prod.append(Metric(
                f"prod:{s.farm_id}", f"{s.farm_name} productivity", f"{v:.2f}", "eggs/bird/wk",
                True, "eggs_this_week ÷ active birds",
                detail=f"{f.eggs_this_week} eggs ÷ {f.total_birds} birds",
            ))

    # Org-wide metrics.
    org_metrics = [
        _org_production_efficiency(snapshots),
        _missed_reminders(tasks),
        _task_completion_time(tasks),
        _inventory_turnover(snapshots),
    ]

    # Trend summaries: org production week-on-week.
    trends = [_org_production_trend(snapshots)]

    return PerformanceAnalytics(
        workers=worker_perf, farm_productivity=farm_prod,
        org_metrics=org_metrics, trends=trends,
    )


def _org_production_efficiency(snapshots: list[FarmSnapshot]) -> Metric:
    eggs = 0
    feed = Decimal("0")
    used = 0
    for s in snapshots:
        f = s.facts
        if f.days_since_egg_log is not None and f.days_since_feed_log is not None and f.feed_this_week_kg > 0:
            eggs += f.eggs_this_week
            feed += f.feed_this_week_kg
            used += 1
    if used == 0:
        return Metric("prod_efficiency", "Production efficiency", None, "eggs/kg", False,
                      "total eggs ÷ total feed — no farm recorded both this week")
    v = eggs / float(feed)
    return Metric("prod_efficiency", "Production efficiency", f"{v:.2f}", "eggs/kg", True,
                  f"total eggs ÷ total feed across {used} farm(s) recording both",
                  detail=f"{eggs} eggs ÷ {feed}kg")


def _missed_reminders(tasks: list[TaskView]) -> Metric:
    overdue = sum(1 for t in tasks if t.status is TaskStatus.OVERDUE)
    total_open = sum(1 for t in tasks if t.status is not TaskStatus.DONE)
    return Metric("missed_reminders", "Missed reminders", str(overdue), "tasks", True,
                  "tasks past their due date and not completed",
                  detail=f"{overdue} overdue of {total_open} open")


def _task_completion_time(tasks: list[TaskView]) -> Metric:
    hours = [h for h in (_completion_hours(t) for t in tasks) if h is not None]
    if not hours:
        return Metric("completion_time", "Avg task completion time", None, "hours", False,
                      "mean of (done_at − created_at) — no completed tasks with both timestamps")
    v = sum(hours) / len(hours)
    return Metric("completion_time", "Avg task completion time", f"{v:.1f}", "hours", True,
                  f"mean of (done_at − created_at) over {len(hours)} completed task(s)")


def _inventory_turnover(snapshots: list[FarmSnapshot]) -> Metric:
    # Honest by design: turnover needs consumption-over-stock movement data that
    # FarmFacts does not carry, so it is reported unavailable rather than faked.
    tracked = sum(s.facts.inventory_tracked for s in snapshots)
    return Metric(
        "inventory_turnover", "Inventory turnover", None, "×", False,
        "consumed ÷ average stock over the period — movement history is not "
        "aggregated into FarmFacts, so turnover is not computed here",
        detail=f"{tracked} item(s) tracked across the organization",
    )


def _org_production_trend(snapshots: list[FarmSnapshot]) -> Metric:
    this_w = 0
    prev_w = 0
    used = 0
    for s in snapshots:
        f = s.facts
        if f.days_since_egg_log is not None:
            this_w += f.eggs_this_week
            prev_w += f.eggs_prev_week
            used += 1
    if used == 0 or prev_w <= 0:
        return Metric("prod_trend", "Production trend", None, "%", False,
                      "week-on-week change in total eggs — insufficient history")
    change = (this_w - prev_w) / prev_w * 100
    direction = "up" if change > 1 else "down" if change < -1 else "steady"
    return Metric("prod_trend", "Production trend", f"{change:+.1f}", "%", True,
                  "(this week − last week) ÷ last week, summed across farms with data",
                  detail=f"{this_w} vs {prev_w} eggs — {direction}")


# ── 8. Role-based workspace ───────────────────────────────────────────────────
#
# The policy layer for "no permission leaks". It maps a membership role to an
# operational tier, decides which dashboard sections that tier may see, and
# narrows the visible farm set. The data layer enforces the farm scope against
# real membership; this defines what each tier is *allowed* to see so the API and
# the UI agree on one rule set.


#: Membership role → operational tier.
_ROLE_TIER = {
    "super_admin": "administrator",
    "platform_admin": "administrator",
    "enterprise_owner": "administrator",
    "farm_owner": "manager",
    "farm_manager": "supervisor",
    "farm_worker": "worker",
    "vet_consultant": "readonly",
    "viewer": "readonly",
}

#: Sections each tier may see. Ordered from most to least privileged.
_TIER_SECTIONS = {
    "administrator": {
        "organization", "comparison", "dashboard", "timeline",
        "analytics", "reports", "tasks", "workers", "financial", "all_tasks",
    },
    "manager": {
        "organization", "comparison", "dashboard", "timeline",
        "analytics", "reports", "tasks", "workers", "financial", "all_tasks",
    },
    "supervisor": {
        "organization", "comparison", "dashboard", "timeline",
        "analytics", "reports", "tasks", "workers",
    },
    "worker": {"dashboard", "timeline", "tasks"},
    "readonly": {"organization", "comparison", "dashboard", "timeline", "reports"},
}


@dataclass
class WorkspaceScope:
    tier: str
    sections: set[str]
    #: Farm ids the tier may see. None means "every farm in the organization".
    farm_ids: list[str] | None
    #: True when this tier only ever sees tasks it personally owns.
    own_tasks_only: bool
    #: True when this tier may (re)assign and complete others' tasks.
    can_assign: bool
    reason: str


def workspace_scope(
    role: str,
    *,
    member_farm_ids: list[str],
    org_farm_ids: list[str],
) -> WorkspaceScope:
    """
    Resolve what one role may see and do across the organization.

    * administrator / manager — the whole organization.
    * supervisor — only the farms they are assigned to.
    * worker — only their assigned farms, and only their own tasks.
    * readonly (vet / viewer) — their assigned farms, no assignment powers.

    The farm scope returned here is the ceiling the data layer must not exceed.
    A worker asking for another farm's tasks gets an empty scope, not a leak.
    """
    tier = _ROLE_TIER.get(role, "readonly")
    sections = set(_TIER_SECTIONS.get(tier, _TIER_SECTIONS["readonly"]))

    if tier in ("administrator", "manager"):
        farm_ids: list[str] | None = None      # all org farms
        reason = "Organization-wide access."
    else:
        # Only farms the user is actually a member of, intersected with the org.
        allowed = [fid for fid in member_farm_ids if fid in org_farm_ids]
        farm_ids = allowed
        reason = f"Scoped to {len(allowed)} assigned farm(s)."

    return WorkspaceScope(
        tier=tier,
        sections=sections,
        farm_ids=farm_ids,
        own_tasks_only=(tier == "worker"),
        can_assign=(tier in ("administrator", "manager", "supervisor")),
        reason=reason,
    )


def role_of_membership(role: str) -> tuple[WorkerRole, str]:
    """Map a membership role key to an operational WorkerRole and its label."""
    mapping = {
        "enterprise_owner": (WorkerRole.MANAGER, "Farm Manager"),
        "farm_owner": (WorkerRole.MANAGER, "Farm Manager"),
        "farm_manager": (WorkerRole.SUPERVISOR, "Supervisor"),
        "farm_worker": (WorkerRole.WORKER, "Worker"),
        "vet_consultant": (WorkerRole.VET, "Veterinarian"),
        "viewer": (WorkerRole.VIEWER, "Viewer"),
    }
    return mapping.get(role, (WorkerRole.CUSTOM, role.replace("_", " ").title()))


# ── 9. Organization reports ───────────────────────────────────────────────────


@dataclass
class ReportSection:
    label: str
    value: str
    available: bool = True
    method: str = ""


@dataclass
class OrganizationReport:
    period: str               # daily | weekly | monthly
    label: str
    as_of: date
    organization_name: str
    farm_count: int
    sections: list[ReportSection]
    risks: list[str]
    priorities: list[str]
    notes: list[str]


_REPORT_PERIODS = {
    "daily": "Daily operations report",
    "weekly": "Weekly operations report",
    "monthly": "Monthly operations report",
}


def build_organization_report(
    org: OrganizationFacts,
    analytics: PerformanceAnalytics,
    tasks: list[TaskView],
    *,
    period: str,
) -> OrganizationReport:
    """
    An export-ready organization report for a period.

    Composed entirely from the aggregates and analytics above, so every line is
    already provenance-carrying. A monthly report does not fabricate a monthly
    total from a weekly window — the aggregates state their own window, and lines
    without data are marked unavailable rather than estimated.
    """
    label = _REPORT_PERIODS.get(period, _REPORT_PERIODS["weekly"])

    def sec(a: Aggregate) -> ReportSection:
        unit = f" {a.unit}".rstrip() if a.unit else ""
        return ReportSection(
            label=a.label,
            value=(f"{a.value}{unit}" if a.available and a.value is not None
                   else "Not enough recorded data."),
            available=a.available, method=a.method,
        )

    sections = [
        sec(org.production), sec(org.financial), sec(org.mortality),
        sec(org.feed_usage), sec(org.water_usage), sec(org.inventory),
        sec(org.health),
    ]

    # Task completion line.
    done = sum(1 for t in tasks if t.status is TaskStatus.DONE)
    overdue = sum(1 for t in tasks if t.status is TaskStatus.OVERDUE)
    total = len(tasks)
    sections.append(ReportSection(
        label="Task completion",
        value=(f"{done}/{total} completed, {overdue} overdue" if total else "No tasks in scope."),
        available=bool(total),
        method="counts over all tasks in the reporting scope",
    ))

    # Alerts line.
    alert_count = sum(1 for p in org.priorities if p.severity is not MonitorState.NORMAL)
    sections.append(ReportSection(
        label="Open alerts",
        value=str(alert_count),
        method="non-normal monitors across all farms",
    ))

    risks = _outstanding_risks(org, tasks)
    priorities = [f"{p.rank}. {p.label}" for p in org.priorities[:5]]

    notes: list[str] = []
    if org.silent_farms:
        notes.append(
            "No records at all for: " + ", ".join(org.silent_farms)
            + " — these farms contribute nothing to the totals above."
        )
    if period == "monthly":
        notes.append(
            "Production, feed, water and mortality are aggregated over 7-day "
            "windows. A 30-day total is not extrapolated from a week, so those "
            "lines report the most recent recorded window."
        )

    return OrganizationReport(
        period=period, label=label, as_of=org.as_of,
        organization_name=org.organization_name, farm_count=org.farm_count,
        sections=sections, risks=risks, priorities=priorities, notes=notes,
    )


def _outstanding_risks(org: OrganizationFacts, tasks: list[TaskView]) -> list[str]:
    risks: list[str] = []
    for p in org.priorities:
        if p.severity in (MonitorState.CRITICAL, MonitorState.WARNING):
            risks.append(f"{p.farm_name}: {p.why}")
    overdue = sum(1 for t in tasks if t.status is TaskStatus.OVERDUE)
    if overdue:
        risks.append(f"{overdue} task(s) are overdue across the organization.")
    if org.silent_farms:
        risks.append(
            f"{len(org.silent_farms)} farm(s) have recorded nothing recently: "
            + ", ".join(org.silent_farms) + "."
        )
    return risks[:12]
