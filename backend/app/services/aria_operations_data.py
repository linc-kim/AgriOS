"""
ARIA operations director — the data layer.

The only part of the operations engine that touches the database. It resolves an
organization's farms and team, gathers a `FarmFacts`-backed snapshot per farm
through the *existing* Part 4/5 gatherers, maps reminders onto assignable tasks,
and merges each farm's timeline into one — then hands all of it to the pure
`aria_operations` engine.

Nothing here re-implements a domain. Facts come from
`aria_intelligence_data.gather_facts`, monitors and health from the Part 4/5
engine, the timeline from `aria_supervisor_data.gather_timeline`, tasks from the
`reminders` table. The director adds organization-scale composition and the
permission scope, not a parallel copy of the farm.

Two things this layer is strict about. **Permission scope** is resolved before
any farm data is read: a worker only ever sees the farms they are a member of, so
another farm's data is never gathered in the first place — there is nothing to
leak. **Task assignment** is the only write path, and it records every
assignment and completion into the reminder's `metadata` history, so a farm ends
up with a real, auditable record of who did what — without a new table or a
migration.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import FarmAccessException, NotFoundException
from app.models.auth import Role, User
from app.models.automation import Reminder
from app.models.farm import Farm, FarmMember
from app.models.organization import Organization, OrganizationMember
from app.models.platform import Notification
from app.services import (
    aria_intelligence as engine,
    aria_intelligence_data,
    aria_supervisor as supervisor,
    aria_supervisor_data,
)
from app.services import aria_operations as ops
from app.services.aria_operations import (
    DashboardFilter,
    FarmSnapshot,
    OrgNotification,
    OrgTimelineEvent,
    TaskStatus,
    TaskView,
    WorkerView,
)
from app.services.aria_supervisor import MonitorState

#: Severity a timeline kind carries, so the org feed can be filtered by urgency.
_KIND_SEVERITY = {
    "mortality": MonitorState.WARNING,
    "vaccination": MonitorState.NORMAL,
    "production": MonitorState.NORMAL,
    "feed": MonitorState.NORMAL,
    "weighin": MonitorState.NORMAL,
    "reminder": MonitorState.NORMAL,
}

_NOTIF_SEVERITY_ORDER = {"critical": 3, "high": 2, "normal": 1, "low": 0}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Access resolution ─────────────────────────────────────────────────────────


class OrgAccess:
    """
    The resolved access of one user to one organization.

    `role` is the effective operational role (their organization membership role
    if they hold one, otherwise the most privileged farm role they have within
    the org). `member_farm_ids` are the org's farms they are actually a member
    of — the ceiling the scope must not exceed.
    """

    def __init__(self, org: Organization, role: str, member_farm_ids: list[str],
                 org_farm_ids: list[str]):
        self.org = org
        self.role = role
        self.member_farm_ids = member_farm_ids
        self.org_farm_ids = org_farm_ids
        self.scope = ops.workspace_scope(
            role, member_farm_ids=member_farm_ids, org_farm_ids=org_farm_ids,
        )

    def visible_farm_ids(self) -> list[str]:
        """The farms this user may see: all org farms for managers, else their own."""
        if self.scope.farm_ids is None:
            return list(self.org_farm_ids)
        return list(self.scope.farm_ids)


#: Farm-role privilege order, to pick a user's effective role across memberships.
_ROLE_PRIORITY = [
    "enterprise_owner", "farm_owner", "farm_manager",
    "vet_consultant", "farm_worker", "viewer",
]


async def resolve_access(db: AsyncSession, org_id: uuid.UUID, user: User) -> OrgAccess:
    """
    Resolve — and enforce — a user's access to an organization.

    Raises if the user is neither an active organization member nor an active
    member of any farm the organization owns. This is the single choke point that
    keeps a supervisor from reaching another organization: no membership here
    means no data is ever gathered.
    """
    org = (
        await db.execute(
            select(Organization).where(
                Organization.id == org_id, Organization.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organization")

    # Every farm the organization owns.
    org_farm_ids = [
        str(r) for r in (
            await db.execute(
                select(Farm.id).where(
                    Farm.organization_id == org_id, Farm.deleted_at.is_(None)
                )
            )
        ).scalars().all()
    ]

    # Is the user an organization member? Use that role if so.
    org_role = (
        await db.execute(
            select(Role.name)
            .join(OrganizationMember, OrganizationMember.role_id == Role.id)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == "active",
                OrganizationMember.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    # Farms in this org the user is an active member of, with their roles.
    farm_rows = (
        await db.execute(
            select(FarmMember.farm_id, Role.name)
            .join(Role, Role.id == FarmMember.role_id)
            .where(
                FarmMember.user_id == user.id,
                FarmMember.status == "active",
                FarmMember.deleted_at.is_(None),
                FarmMember.farm_id.in_(org_farm_ids) if org_farm_ids else False,
            )
        )
    ).all()
    member_farm_ids = [str(fid) for fid, _ in farm_rows]
    farm_roles = [rname for _, rname in farm_rows]

    if org_role is None and not member_farm_ids:
        raise FarmAccessException("You are not a member of this organization.")

    # Effective role: org role wins; else the most privileged farm role.
    if org_role is not None:
        role = org_role
    else:
        role = next((r for r in _ROLE_PRIORITY if r in farm_roles), "viewer")

    return OrgAccess(org, role, member_farm_ids, org_farm_ids)


# ── Gatherers ─────────────────────────────────────────────────────────────────


async def _load_farms(db: AsyncSession, farm_ids: list[str]) -> list[Farm]:
    if not farm_ids:
        return []
    farms = (
        await db.execute(
            select(Farm).where(Farm.id.in_(farm_ids), Farm.deleted_at.is_(None))
        )
    ).scalars().all()
    # Deterministic order by name, then id.
    return sorted(farms, key=lambda f: (f.name.lower(), str(f.id)))


async def gather_farm_snapshots(
    db: AsyncSession, farms: list[Farm], user: User
) -> list[FarmSnapshot]:
    """One supervised snapshot per farm, via the existing Part 4/5 engine."""
    snapshots: list[FarmSnapshot] = []
    for farm in farms:
        facts = await aria_intelligence_data.gather_facts(db, farm, user)
        health = engine.compute_health_score(facts)
        monitors = supervisor.run_monitors(facts)
        snapshots.append(FarmSnapshot(
            farm_id=str(farm.id), farm_name=farm.name, facts=facts,
            health_score=health.score, monitors=monitors,
        ))
    return snapshots


async def gather_workers(
    db: AsyncSession, farm_ids: list[str]
) -> list[WorkerView]:
    """
    The team across a set of farms, one row per user.

    Built from farm memberships so a worker who belongs to several farms appears
    once, with every farm listed. Their operational role is the most privileged
    role they hold on any of these farms.
    """
    if not farm_ids:
        return []
    rows = (
        await db.execute(
            select(FarmMember.user_id, FarmMember.farm_id, Role.name, Farm.name, User.full_name)
            .join(Role, Role.id == FarmMember.role_id)
            .join(Farm, Farm.id == FarmMember.farm_id)
            .join(User, User.id == FarmMember.user_id)
            .where(
                FarmMember.farm_id.in_(farm_ids),
                FarmMember.status == "active",
                FarmMember.deleted_at.is_(None),
                FarmMember.user_id.isnot(None),
            )
        )
    ).all()

    by_user: dict[str, dict] = {}
    for user_id, farm_id, role_name, farm_name, full_name in rows:
        uid = str(user_id)
        entry = by_user.setdefault(uid, {
            "name": full_name or "Unnamed",
            "roles": [], "farm_ids": [], "farm_names": [],
        })
        entry["roles"].append(role_name)
        entry["farm_ids"].append(str(farm_id))
        entry["farm_names"].append(farm_name)

    workers: list[WorkerView] = []
    for uid, e in by_user.items():
        best_role = next((r for r in _ROLE_PRIORITY if r in e["roles"]), e["roles"][0])
        wr, label = ops.role_of_membership(best_role)
        workers.append(WorkerView(
            user_id=uid, name=e["name"], role=wr, role_label=label,
            farm_ids=sorted(set(e["farm_ids"])), farm_names=sorted(set(e["farm_names"])),
        ))
    return sorted(workers, key=lambda w: w.name.lower())


def _task_status(rem: Reminder, now: datetime) -> TaskStatus:
    if rem.is_done:
        return TaskStatus.DONE
    if rem.due_at and _aware(rem.due_at) < now:
        return TaskStatus.OVERDUE
    return TaskStatus.OPEN


async def gather_tasks(
    db: AsyncSession, farm_map: dict[str, str], *, include_done: bool = True
) -> list[TaskView]:
    """
    Reminders across the org's farms, mapped onto assignable tasks.

    Owner, dates and priority come straight off the reminder; the assignment and
    completion history comes from its `metadata` — so a task is a real record with
    provenance, not a shadow object.
    """
    farm_ids = list(farm_map.keys())
    if not farm_ids:
        return []
    now = datetime.now(tz=timezone.utc)

    filters = [Reminder.farm_id.in_(farm_ids), Reminder.deleted_at.is_(None)]
    if not include_done:
        filters.append(Reminder.is_done.is_(False))
    reminders = (
        await db.execute(select(Reminder).where(*filters))
    ).scalars().all()

    # Resolve owner names in one pass.
    owner_ids = {str(r.user_id) for r in reminders if r.user_id}
    names: dict[str, str] = {}
    if owner_ids:
        for uid, full in (
            await db.execute(select(User.id, User.full_name).where(User.id.in_(owner_ids)))
        ).all():
            names[str(uid)] = full or "Unnamed"

    tasks: list[TaskView] = []
    for r in reminders:
        assignment = (r.metadata_ or {}).get("assignment", {})
        owner_id = str(r.user_id) if r.user_id else None
        tasks.append(TaskView(
            task_id=str(r.id),
            farm_id=str(r.farm_id),
            farm_name=farm_map.get(str(r.farm_id), "farm"),
            title=r.title,
            status=_task_status(r, now),
            priority=r.priority,
            owner_id=owner_id,
            owner_name=names.get(owner_id) if owner_id else None,
            due_at=_aware(r.due_at) if r.due_at else None,
            created_at=_aware(r.created_at) if r.created_at else None,
            completed_at=_aware(r.done_at) if r.done_at else None,
            history=list(assignment.get("history", [])),
        ))
    return tasks


async def gather_org_timeline(
    db: AsyncSession, farms: list[Farm], tasks: list[TaskView], *, days: int = 30, limit: int = 200
) -> list[OrgTimelineEvent]:
    """
    Merge every farm's recorded activity into one worker-attributed feed.

    Operational events reuse `aria_supervisor_data.gather_timeline` (farm- and
    severity-attributed). Reminder completions are taken from the gathered tasks
    instead, because those carry the owner — so the feed's Worker column is real
    rather than blank.
    """
    events: list[OrgTimelineEvent] = []
    for farm in farms:
        farm_events = await aria_supervisor_data.gather_timeline(
            db, farm, days=days, limit=limit,
        )
        for e in farm_events:
            if e.kind == "reminder":
                continue  # replaced by worker-attributed task events below
            events.append(OrgTimelineEvent(
                at=e.at, farm_id=str(farm.id), farm_name=farm.name,
                kind=e.kind, title=e.title, detail=e.detail,
                severity=_KIND_SEVERITY.get(e.kind, MonitorState.NORMAL),
            ))

    # Worker-attributed completed tasks.
    for t in tasks:
        if t.status is TaskStatus.DONE and t.completed_at is not None:
            events.append(OrgTimelineEvent(
                at=t.completed_at, farm_id=t.farm_id, farm_name=t.farm_name,
                kind="reminder", title=f"Task completed: {t.title}",
                detail=t.owner_name or "", worker=t.owner_name,
                severity=MonitorState.NORMAL,
            ))
    return events


async def gather_notifications(
    db: AsyncSession, farm_map: dict[str, str], user: User, *, limit: int = 50
) -> list[OrgNotification]:
    """Recent notifications across the org's farms for this user."""
    farm_ids = list(farm_map.keys())
    if not farm_ids:
        return []
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.farm_id.in_(farm_ids),
                Notification.user_id == user.id,
                Notification.deleted_at.is_(None),
                Notification.is_archived.is_(False),
            ).order_by(Notification.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        OrgNotification(
            at=_aware(n.created_at), farm_id=str(n.farm_id),
            farm_name=farm_map.get(str(n.farm_id), "farm"),
            title=n.title, body=n.body, severity=n.priority,
        )
        for n in rows
    ]


def _org_alerts_from_snapshots(snapshots: list[FarmSnapshot], now: datetime) -> list[OrgTimelineEvent]:
    """Current alerts across farms, as severity-tagged timeline events."""
    alerts: list[OrgTimelineEvent] = []
    for s in snapshots:
        for a in supervisor.build_alerts(s.facts, now=now, monitors=s.monitors):
            alerts.append(OrgTimelineEvent(
                at=a.raised_at, farm_id=s.farm_id, farm_name=s.farm_name,
                kind=a.monitor, title=a.title, detail=a.reason, severity=a.severity,
            ))
    return alerts


# ── Orchestration (read) ──────────────────────────────────────────────────────


async def _snapshots_for(db: AsyncSession, access: OrgAccess, user: User,
                         farm_id_filter: str | None = None) -> tuple[list[Farm], list[FarmSnapshot]]:
    visible = access.visible_farm_ids()
    if farm_id_filter:
        if farm_id_filter not in visible:
            raise FarmAccessException("You do not have access to that farm.")
        visible = [farm_id_filter]
    farms = await _load_farms(db, visible)
    snapshots = await gather_farm_snapshots(db, farms, user)
    return farms, snapshots


async def organization_overview(db: AsyncSession, access: OrgAccess, user: User) -> ops.OrganizationFacts:
    _farms, snapshots = await _snapshots_for(db, access, user)
    return ops.build_organization_facts(
        snapshots, organization_name=access.org.name, as_of=date.today(),
    )


async def cross_farm(db: AsyncSession, access: OrgAccess, user: User) -> ops.CrossFarmComparison:
    _farms, snapshots = await _snapshots_for(db, access, user)
    return ops.compare_farms(snapshots)


async def operations_dashboard(
    db: AsyncSession, access: OrgAccess, user: User, *, flt: DashboardFilter | None = None
) -> ops.OperationsDashboard:
    flt = flt or DashboardFilter()
    farms, snapshots = await _snapshots_for(db, access, user, farm_id_filter=flt.farm_id)
    farm_map = {str(f.id): f.name for f in farms}

    tasks = await gather_tasks(db, farm_map)
    if access.scope.own_tasks_only:
        tasks = [t for t in tasks if t.owner_id == str(user.id)]

    workers = await gather_workers(db, list(farm_map.keys()))
    notifications = await gather_notifications(db, farm_map, user)
    org = ops.build_organization_facts(
        snapshots, organization_name=access.org.name, as_of=date.today(),
    )
    alerts = _org_alerts_from_snapshots(snapshots, datetime.now())

    return ops.build_dashboard(
        organization=org, snapshots=snapshots, tasks=tasks, workers=workers,
        alerts=alerts, notifications=notifications, flt=flt,
    )


async def organization_timeline(
    db: AsyncSession, access: OrgAccess, user: User, *,
    days: int = 30, limit: int = 100, farm_id: str | None = None,
    worker: str | None = None, severity: MonitorState | None = None,
) -> list[OrgTimelineEvent]:
    farms, _snapshots = await _snapshots_for(db, access, user, farm_id_filter=farm_id)
    farm_map = {str(f.id): f.name for f in farms}
    tasks = await gather_tasks(db, farm_map)
    if access.scope.own_tasks_only:
        tasks = [t for t in tasks if t.owner_id == str(user.id)]
    events = await gather_org_timeline(db, farms, tasks, days=days, limit=limit * 3)
    return ops.merge_timeline(
        events, farm_id=farm_id, worker=worker, severity=severity, limit=limit,
    )


async def analytics(db: AsyncSession, access: OrgAccess, user: User) -> ops.PerformanceAnalytics:
    farms, snapshots = await _snapshots_for(db, access, user)
    farm_map = {str(f.id): f.name for f in farms}
    tasks = await gather_tasks(db, farm_map)
    workers = await gather_workers(db, list(farm_map.keys()))
    return ops.performance_analytics(snapshots, tasks, workers)


async def organization_report(
    db: AsyncSession, access: OrgAccess, user: User, *, period: str
) -> ops.OrganizationReport:
    farms, snapshots = await _snapshots_for(db, access, user)
    farm_map = {str(f.id): f.name for f in farms}
    tasks = await gather_tasks(db, farm_map)
    workers = await gather_workers(db, list(farm_map.keys()))
    org = ops.build_organization_facts(
        snapshots, organization_name=access.org.name, as_of=date.today(),
    )
    perf = ops.performance_analytics(snapshots, tasks, workers)
    return ops.build_organization_report(org, perf, tasks, period=period)


async def list_workers(db: AsyncSession, access: OrgAccess) -> list[WorkerView]:
    return await gather_workers(db, access.visible_farm_ids())


async def list_tasks(
    db: AsyncSession, access: OrgAccess, user: User, *,
    farm_id: str | None = None, worker_id: str | None = None, include_done: bool = True,
) -> list[TaskView]:
    farms, _snapshots = await _snapshots_for(db, access, user, farm_id_filter=farm_id)
    farm_map = {str(f.id): f.name for f in farms}
    tasks = await gather_tasks(db, farm_map, include_done=include_done)
    if access.scope.own_tasks_only:
        tasks = [t for t in tasks if t.owner_id == str(user.id)]
    elif worker_id:
        tasks = [t for t in tasks if t.owner_id == worker_id]
    return sorted(tasks, key=ops._task_sort_key)


# ── Task assignment (the only write path) ─────────────────────────────────────


async def _load_reminder_in_scope(
    db: AsyncSession, access: OrgAccess, task_id: uuid.UUID
) -> Reminder:
    rem = (
        await db.execute(
            select(Reminder).where(Reminder.id == task_id, Reminder.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if rem is None:
        raise NotFoundException("Task")
    if str(rem.farm_id) not in access.visible_farm_ids():
        raise FarmAccessException("That task belongs to a farm you cannot access.")
    return rem


def _append_history(rem: Reminder, event: dict) -> None:
    """Append one event to the reminder's assignment history in metadata."""
    meta = dict(rem.metadata_ or {})
    assignment = dict(meta.get("assignment", {}))
    history = list(assignment.get("history", []))
    history.append(event)
    assignment["history"] = history
    meta["assignment"] = assignment
    # Reassign so SQLAlchemy detects the JSONB change.
    rem.metadata_ = meta


async def assign_task(
    db: AsyncSession, access: OrgAccess, task_id: uuid.UUID, new_owner_id: uuid.UUID, actor: User
) -> Reminder:
    """
    Assign or reassign a task to a worker, deterministically and without duplicates.

    The pure `can_assign` rule decides admissibility (no self-duplicate, no
    duplicate open title on the same farm, no reassigning a completed task); this
    persists the new owner and records the reassignment in history.
    """
    if not access.scope.can_assign:
        raise FarmAccessException("Your role cannot assign tasks.")
    rem = await _load_reminder_in_scope(db, access, task_id)

    # All open tasks on the same farm, so the duplicate-assignment rule can see
    # them. Farm name is display-only here, so an empty label is fine.
    all_tasks = await gather_tasks(db, {str(rem.farm_id): ""})
    target = next((t for t in all_tasks if t.task_id == str(rem.id)), None)
    if target is None:
        raise NotFoundException("Task")

    member = (
        await db.execute(
            select(FarmMember.id).where(
                FarmMember.farm_id == rem.farm_id,
                FarmMember.user_id == new_owner_id,
                FarmMember.status == "active",
                FarmMember.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise FarmAccessException("That worker is not a member of the task's farm.")

    check = ops.can_assign(target, str(new_owner_id), all_tasks)
    if not check.allowed:
        raise FarmAccessException(check.reason)

    previous = str(rem.user_id) if rem.user_id else None
    rem.user_id = new_owner_id
    now = datetime.now(tz=timezone.utc)
    meta = dict(rem.metadata_ or {})
    assignment = dict(meta.get("assignment", {}))
    assignment["assigned_by"] = str(actor.id)
    assignment["assigned_at"] = now.isoformat()
    meta["assignment"] = assignment
    rem.metadata_ = meta
    _append_history(rem, {
        "at": now.isoformat(),
        "action": "reassigned" if previous else "assigned",
        "actor": str(actor.id),
        "detail": f"assigned to {new_owner_id}",
    })
    rem.updated_at = now
    await db.commit()
    await db.refresh(rem)
    return rem


async def complete_task(
    db: AsyncSession, access: OrgAccess, task_id: uuid.UUID, actor: User
) -> Reminder:
    """
    Mark a task complete, recording who completed it and when.

    A worker may complete a task assigned to them; an assigner may complete any
    task in scope. Completing an already-complete task is idempotent.
    """
    rem = await _load_reminder_in_scope(db, access, task_id)

    is_owner = rem.user_id is not None and str(rem.user_id) == str(actor.id)
    if not (is_owner or access.scope.can_assign):
        raise FarmAccessException("You can only complete tasks assigned to you.")

    if rem.is_done:
        return rem  # idempotent

    now = datetime.now(tz=timezone.utc)
    rem.is_done = True
    rem.done_at = now
    rem.updated_at = now
    _append_history(rem, {
        "at": now.isoformat(),
        "action": "completed",
        "actor": str(actor.id),
        "detail": "marked complete",
    })
    await db.commit()
    await db.refresh(rem)
    return rem
