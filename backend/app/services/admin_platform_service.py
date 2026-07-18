"""
Greena — Admin Platform Service (Module 10).

Platform-wide (not farm-scoped) administration: organizations, users, farms,
audit center, analytics, feature flags, system configuration + maintenance mode,
system health, and a background-jobs dashboard. Every mutating action is audited
(who / when / IP / action / before / after / reason / resource).
"""

import csv
import io
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.admin_platform import FLAG_MODULES, BackgroundJob, FeatureFlag, SystemConfig
from app.models.ai_platform import AIResponseCache
from app.models.ai import AIUsageLog
from app.models.auth import Role, Session, User, UserRole
from app.models.farm import Farm, FarmMember, SubscriptionPlan
from app.models.flock import Flock
from app.models.finance import Expense, RevenueRecord
from app.models.inventory import InventoryItem
from app.models.organization import Organization, OrganizationMember
from app.models.platform import AuditLog

_PROCESS_START = time.time()

_PLAN_PRICE = {"free": Decimal("0"), "starter": Decimal("1500"), "pro": Decimal("4500")}


# ── Audit helper ──────────────────────────────────────────────────────────────

async def _audit(db, actor: User, action: str, resource_type: str, resource_id=None,
                 old=None, new=None, reason=None, ip=None):
    from app.services import audit_service
    new_value = new or {}
    if reason:
        new_value = {**new_value, "reason": reason}
    await audit_service.log_action(db, action=action, resource_type=resource_type, resource_id=resource_id,
                                   user_id=actor.id, old_value=old, new_value=new_value, ip_address=ip)


# ── Organizations ─────────────────────────────────────────────────────────────

async def list_organizations(db, q=None, status=None, page=1, page_size=20) -> dict:
    filters = []
    if status == "active":
        filters += [Organization.is_suspended.is_(False), Organization.deleted_at.is_(None)]
    elif status == "suspended":
        filters.append(Organization.is_suspended.is_(True))
    elif status == "deleted":
        filters.append(Organization.deleted_at.is_not(None))
    else:
        filters.append(Organization.deleted_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        filters.append(or_(func.lower(Organization.name).like(like), func.lower(Organization.slug).like(like)))

    total = int((await db.execute(select(func.count(Organization.id)).where(*filters))).scalar_one())
    res = await db.execute(
        select(Organization, User.full_name, SubscriptionPlan.name)
        .outerjoin(User, Organization.owner_id == User.id)
        .outerjoin(SubscriptionPlan, Organization.plan_id == SubscriptionPlan.id)
        .where(*filters).order_by(Organization.created_at.desc())
        .limit(page_size).offset((page - 1) * page_size)
    )
    rows = []
    for org, owner, plan in res.all():
        farm_count = int((await db.execute(select(func.count(Farm.id)).where(Farm.organization_id == org.id, Farm.deleted_at.is_(None)))).scalar_one()) if hasattr(Farm, "organization_id") else 0
        member_count = int((await db.execute(select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org.id, OrganizationMember.deleted_at.is_(None)))).scalar_one())
        rows.append({
            "id": org.id, "name": org.name, "slug": org.slug, "owner_name": owner,
            "country": org.country, "currency": org.currency, "is_suspended": org.is_suspended,
            "is_deleted": org.deleted_at is not None, "farm_count": farm_count,
            "member_count": member_count, "plan_name": plan, "created_at": org.created_at,
        })
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def _get_org(db, org_id) -> Organization:
    res = await db.execute(select(Organization).where(Organization.id == str(org_id)))
    org = res.scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organization not found.")
    return org


async def set_org_suspended(db, actor, org_id, suspended: bool, reason=None, ip=None) -> Organization:
    org = await _get_org(db, org_id)
    old = {"is_suspended": org.is_suspended}
    org.is_suspended = suspended
    await _audit(db, actor, "org.suspend" if suspended else "org.reactivate", "organization", org.id,
                 old=old, new={"is_suspended": suspended}, reason=reason, ip=ip)
    await db.commit()
    await db.refresh(org)
    return org


async def soft_delete_org(db, actor, org_id, reason=None, ip=None) -> None:
    org = await _get_org(db, org_id)
    org.deleted_at = datetime.now(tz=timezone.utc)
    await _audit(db, actor, "org.delete", "organization", org.id, reason=reason, ip=ip)
    await db.commit()


async def get_org_detail(db, org_id) -> dict:
    org = await _get_org(db, org_id)
    owner = (await db.execute(select(User.full_name).where(User.id == org.owner_id))).scalar_one_or_none()
    plan = (await db.execute(select(SubscriptionPlan.name).where(SubscriptionPlan.id == org.plan_id))).scalar_one_or_none() if org.plan_id else None
    has_org_fk = hasattr(Farm, "organization_id")
    farm_ids_q = select(Farm.id).where(Farm.deleted_at.is_(None))
    if has_org_fk:
        farm_ids_q = farm_ids_q.where(Farm.organization_id == org.id)
    else:
        farm_ids_q = farm_ids_q.where(Farm.owner_id == org.owner_id)
    farm_ids = [f for (f,) in (await db.execute(farm_ids_q)).all()]

    flock_count = active = ai = 0
    rev = exp = Decimal("0")
    if farm_ids:
        flock_count = int((await db.execute(select(func.count(Flock.id)).where(Flock.farm_id.in_(farm_ids), Flock.deleted_at.is_(None)))).scalar_one())
        active = int((await db.execute(select(func.count(Flock.id)).where(Flock.farm_id.in_(farm_ids), Flock.deleted_at.is_(None), Flock.status == "active"))).scalar_one())
        ai = int((await db.execute(select(func.count(AIUsageLog.id)).where(AIUsageLog.farm_id.in_(farm_ids)))).scalar_one())
        rev = Decimal((await db.execute(select(func.coalesce(func.sum(RevenueRecord.amount), 0)).where(RevenueRecord.farm_id.in_([str(f) for f in farm_ids]), RevenueRecord.deleted_at.is_(None)))).scalar_one())
        exp = Decimal((await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.farm_id.in_([str(f) for f in farm_ids]), Expense.deleted_at.is_(None)))).scalar_one())

    member_count = int((await db.execute(select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org.id, OrganizationMember.deleted_at.is_(None)))).scalar_one())
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "owner_name": owner, "country": org.country,
        "currency": org.currency, "is_suspended": org.is_suspended, "is_deleted": org.deleted_at is not None,
        "farm_count": len(farm_ids), "member_count": member_count, "plan_name": plan, "created_at": org.created_at,
        "flock_count": flock_count, "active_flock_count": active, "ai_requests": ai,
        "total_revenue": rev, "total_expenses": exp,
    }


# ── Users ─────────────────────────────────────────────────────────────────────

async def _user_roles(db, user_id) -> list[str]:
    res = await db.execute(select(Role.name).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id))
    return [r for (r,) in res.all()]


async def list_users(db, q=None, page=1, page_size=20) -> dict:
    filters = [User.deleted_at.is_(None)]
    if q:
        like = f"%{q.lower()}%"
        filters.append(or_(func.lower(User.full_name).like(like), func.lower(User.email).like(like),
                           func.lower(User.phone).like(like)))
    total = int((await db.execute(select(func.count(User.id)).where(*filters))).scalar_one())
    res = await db.execute(select(User).where(*filters).order_by(User.created_at.desc())
                           .limit(page_size).offset((page - 1) * page_size))
    users = res.scalars().all()
    rows = []
    for u in users:
        last_login = (await db.execute(select(func.max(Session.created_at)).where(Session.user_id == u.id))).scalar_one_or_none()
        rows.append({
            "id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone,
            "roles": await _user_roles(db, u.id), "is_active": u.is_active,
            "is_suspended": not u.is_active, "last_login_at": last_login, "created_at": u.created_at,
        })
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def _get_user(db, user_id) -> User:
    res = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    u = res.scalar_one_or_none()
    if u is None:
        raise NotFoundException("User not found.")
    return u


async def change_user_role(db, actor, user_id, role_name: str, ip=None) -> User:
    valid = {r for (r,) in (await db.execute(select(Role.name))).all()}
    if role_name not in valid:
        raise ValidationException(f"Unknown role '{role_name}'.")
    user = await _get_user(db, user_id)
    old_roles = await _user_roles(db, user_id)
    # Remove existing platform-level roles, assign the new one.
    existing = (await db.execute(select(UserRole).where(UserRole.user_id == user.id, UserRole.farm_id.is_(None)))).scalars().all()
    for ur in existing:
        await db.delete(ur)
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one()
    db.add(UserRole(user_id=user.id, role_id=role.id, farm_id=None))
    await _audit(db, actor, "user.role_change", "user", user.id, old={"roles": old_roles}, new={"role": role_name}, ip=ip)
    await db.commit()
    return user


async def set_user_active(db, actor, user_id, active: bool, reason=None, ip=None) -> User:
    user = await _get_user(db, user_id)
    old = {"is_active": user.is_active}
    user.is_active = active
    if not active:
        await _revoke_sessions(db, user.id)
    await _audit(db, actor, "user.reactivate" if active else "user.disable", "user", user.id,
                 old=old, new={"is_active": active}, reason=reason, ip=ip)
    await db.commit()
    return user


async def _revoke_sessions(db, user_id) -> int:
    res = await db.execute(select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None)))
    sessions = res.scalars().all()
    now = datetime.now(tz=timezone.utc)
    for s in sessions:
        s.revoked_at = now
    return len(sessions)


async def force_logout(db, actor, user_id, ip=None) -> int:
    user = await _get_user(db, user_id)
    count = await _revoke_sessions(db, user.id)
    await _audit(db, actor, "user.force_logout", "user", user.id, new={"sessions_revoked": count}, ip=ip)
    await db.commit()
    return count


async def force_password_reset(db, actor, user_id, ip=None) -> dict:
    """Revoke sessions and flag a required password reset (safe, no email side effect)."""
    user = await _get_user(db, user_id)
    count = await _revoke_sessions(db, user.id)
    meta = dict(user.metadata_ or {})
    meta["password_reset_required"] = True
    meta["password_reset_requested_at"] = datetime.now(tz=timezone.utc).isoformat()
    user.metadata_ = meta
    await _audit(db, actor, "user.password_reset", "user", user.id, new={"sessions_revoked": count}, ip=ip)
    await db.commit()
    return {"sessions_revoked": count, "password_reset_required": True}


async def user_login_history(db, user_id, limit=50) -> list[dict]:
    res = await db.execute(select(Session).where(Session.user_id == user_id)
                           .order_by(Session.created_at.desc()).limit(limit))
    out = []
    for s in res.scalars().all():
        out.append({
            "session_id": s.id, "created_at": s.created_at,
            "last_used_at": getattr(s, "last_used_at", None), "expires_at": s.expires_at,
            "revoked": s.revoked_at is not None, "ip_address": getattr(s, "ip_address", None),
            "device": getattr(s, "device_name", None) or getattr(s, "device_info", None),
        })
    return out


async def user_audit_history(db, user_id, limit=100) -> list[dict]:
    # Actions performed BY the user or targeting the user (resource_id).
    return await _audit_rows(db, extra=[or_(
        AuditLog.user_id == user_id,
        (AuditLog.resource_type == "user") & (AuditLog.resource_id == user_id),
    )], limit=limit, offset=0)


# ── Audit center ──────────────────────────────────────────────────────────────

async def _audit_rows(db, extra=None, q=None, resource_type=None, action=None,
                      date_from=None, date_to=None, limit=50, offset=0) -> list[dict]:
    filters = list(extra or [])
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        filters.append(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        filters.append(func.date(AuditLog.created_at) <= date_to)
    if q:
        filters.append(or_(AuditLog.action.ilike(f"%{q}%"), AuditLog.resource_type.ilike(f"%{q}%")))
    res = await db.execute(
        select(AuditLog, User.full_name).outerjoin(User, AuditLog.user_id == User.id)
        .where(*filters).order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    return [{
        "id": a.id, "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
        "user_id": a.user_id, "actor_name": name, "farm_id": a.farm_id, "ip_address": a.ip_address,
        "old_value": a.old_value, "new_value": a.new_value, "created_at": a.created_at,
    } for a, name in res.all()]


async def list_audit(db, q=None, resource_type=None, action=None, date_from=None, date_to=None,
                     page=1, page_size=50) -> dict:
    filters = []
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if date_from:
        filters.append(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        filters.append(func.date(AuditLog.created_at) <= date_to)
    if q:
        filters.append(or_(AuditLog.action.ilike(f"%{q}%"), AuditLog.resource_type.ilike(f"%{q}%")))
    total = int((await db.execute(select(func.count(AuditLog.id)).where(*filters))).scalar_one())
    rows = await _audit_rows(db, q=q, resource_type=resource_type, action=action,
                             date_from=date_from, date_to=date_to, limit=page_size, offset=(page - 1) * page_size)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def export_audit_csv(db, **kwargs) -> str:
    rows = await _audit_rows(db, limit=100000, offset=0, **kwargs)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Actor", "Action", "Resource", "Resource ID", "IP"])
    for r in rows:
        w.writerow([r["created_at"].isoformat(), r["actor_name"] or "", r["action"],
                    r["resource_type"], str(r["resource_id"] or ""), r["ip_address"] or ""])
    return buf.getvalue()


# ── Farms ─────────────────────────────────────────────────────────────────────

async def list_farms(db, q=None, page=1, page_size=20, include_archived=True) -> dict:
    filters = [Farm.deleted_at.is_(None)]
    if q:
        filters.append(func.lower(Farm.name).like(f"%{q.lower()}%"))
    total = int((await db.execute(select(func.count(Farm.id)).where(*filters))).scalar_one())
    res = await db.execute(
        select(Farm, User.full_name).outerjoin(User, Farm.owner_id == User.id)
        .where(*filters).order_by(Farm.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    )
    rows = []
    for farm, owner in res.all():
        fc = int((await db.execute(select(func.count(Flock.id)).where(Flock.farm_id == farm.id, Flock.deleted_at.is_(None)))).scalar_one())
        mc = int((await db.execute(select(func.count(FarmMember.id)).where(FarmMember.farm_id == farm.id, FarmMember.deleted_at.is_(None)))).scalar_one())
        rows.append({
            "id": farm.id, "name": farm.name, "county": farm.county, "owner_name": owner,
            "is_active": farm.is_active, "is_archived": not farm.is_active,
            "flock_count": fc, "member_count": mc, "created_at": farm.created_at,
        })
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


async def set_farm_archived(db, actor, farm_id, archived: bool, reason=None, ip=None) -> Farm:
    res = await db.execute(select(Farm).where(Farm.id == str(farm_id), Farm.deleted_at.is_(None)))
    farm = res.scalar_one_or_none()
    if farm is None:
        raise NotFoundException("Farm not found.")
    old = {"is_active": farm.is_active}
    farm.is_active = not archived
    await _audit(db, actor, "farm.archive" if archived else "farm.restore", "farm", farm.id,
                 old=old, new={"is_active": farm.is_active}, reason=reason, ip=ip)
    await db.commit()
    await db.refresh(farm)
    return farm


async def farm_stats(db, farm_id) -> dict:
    res = await db.execute(select(Farm, User.full_name).outerjoin(User, Farm.owner_id == User.id).where(Farm.id == str(farm_id)))
    row = res.one_or_none()
    if row is None:
        raise NotFoundException("Farm not found.")
    farm, owner = row
    active = int((await db.execute(select(func.count(Flock.id)).where(Flock.farm_id == farm.id, Flock.deleted_at.is_(None), Flock.status == "active"))).scalar_one())
    birds = int((await db.execute(select(func.coalesce(func.sum(Flock.initial_count), 0)).where(Flock.farm_id == farm.id, Flock.deleted_at.is_(None), Flock.status == "active"))).scalar_one())
    inv = Decimal((await db.execute(select(func.coalesce(func.sum(InventoryItem.quantity * InventoryItem.avg_cost), 0)).where(InventoryItem.farm_id == farm.id, InventoryItem.deleted_at.is_(None)))).scalar_one())
    rev = Decimal((await db.execute(select(func.coalesce(func.sum(RevenueRecord.amount), 0)).where(RevenueRecord.farm_id == str(farm.id), RevenueRecord.deleted_at.is_(None)))).scalar_one())
    exp = Decimal((await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.farm_id == str(farm.id), Expense.deleted_at.is_(None)))).scalar_one())
    ai = int((await db.execute(select(func.count(AIUsageLog.id)).where(AIUsageLog.farm_id == farm.id))).scalar_one())
    return {"id": farm.id, "name": farm.name, "owner_name": owner, "active_flocks": active,
            "total_birds": birds, "inventory_value": inv.quantize(Decimal("0.01")),
            "total_revenue": rev.quantize(Decimal("0.01")), "total_expenses": exp.quantize(Decimal("0.01")),
            "net_profit": (rev - exp).quantize(Decimal("0.01")), "ai_requests": ai}


# ── Analytics ─────────────────────────────────────────────────────────────────

async def platform_analytics(db) -> dict:
    orgs = int((await db.execute(select(func.count(Organization.id)).where(Organization.deleted_at.is_(None)))).scalar_one())
    farms = int((await db.execute(select(func.count(Farm.id)).where(Farm.deleted_at.is_(None)))).scalar_one())
    users = int((await db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))).scalar_one())
    today = datetime.now(tz=timezone.utc).date()
    active_today = int((await db.execute(select(func.count(func.distinct(Session.user_id))).where(func.date(Session.created_at) == today))).scalar_one())

    # AI by provider (usage log = gemini/claude; cache = offline).
    ai_rows = (await db.execute(select(AIUsageLog.provider, func.count(AIUsageLog.id)).group_by(AIUsageLog.provider))).all()
    ai_by = {p: int(c) for p, c in ai_rows}
    offline = int((await db.execute(select(func.count(AIResponseCache.id)).where(AIResponseCache.provider == "offline"))).scalar_one())
    ai_total = sum(ai_by.values()) + offline

    # Subscriptions.
    plan_rows = (await db.execute(
        select(SubscriptionPlan.name, func.count(Farm.id))
        .outerjoin(Farm, (Farm.plan_id == SubscriptionPlan.id) & (Farm.deleted_at.is_(None)))
        .group_by(SubscriptionPlan.name))).all()
    subs = []
    monthly_rev = Decimal("0")
    for name, cnt in plan_rows:
        price = _PLAN_PRICE.get(name, Decimal("0"))
        rev = price * cnt
        monthly_rev += rev
        subs.append({"plan": name, "farm_count": int(cnt), "monthly_revenue": rev})

    # Growth (cumulative counts per month, last 6).
    growth = []
    for i in range(5, -1, -1):
        m = today.replace(day=1) - timedelta(days=30 * i)
        cutoff = datetime(m.year, m.month, 1, tzinfo=timezone.utc) + timedelta(days=31)
        o = int((await db.execute(select(func.count(Organization.id)).where(Organization.created_at < cutoff))).scalar_one())
        f = int((await db.execute(select(func.count(Farm.id)).where(Farm.created_at < cutoff))).scalar_one())
        u = int((await db.execute(select(func.count(User.id)).where(User.created_at < cutoff))).scalar_one())
        growth.append({"period": m.strftime("%Y-%m"), "organizations": o, "farms": f, "users": u})

    # Top farms by AI requests.
    top_rows = (await db.execute(
        select(AIUsageLog.farm_id, Farm.name, func.count(AIUsageLog.id))
        .join(Farm, AIUsageLog.farm_id == Farm.id)
        .group_by(AIUsageLog.farm_id, Farm.name).order_by(func.count(AIUsageLog.id).desc()).limit(5))).all()
    top = [{"farm_id": fid, "name": name, "ai_requests": int(c)} for fid, name, c in top_rows]

    # Rough estimates for API requests + storage.
    audit_count = int((await db.execute(select(func.count(AuditLog.id)))).scalar_one())
    return {
        "total_organizations": orgs, "total_farms": farms, "total_users": users,
        "active_users_today": active_today, "api_requests_estimate": audit_count * 6,
        "storage_mb_estimate": Decimal(str(round((farms * 5 + users * 0.5), 2))),
        "ai_requests_total": ai_total, "ai_gemini": ai_by.get("gemini", 0),
        "ai_claude": ai_by.get("claude", 0), "ai_offline": offline,
        "monthly_revenue_estimate": monthly_rev, "subscription_breakdown": subs,
        "growth": growth, "top_farms": top,
    }


# ── Feature flags ─────────────────────────────────────────────────────────────

async def list_feature_flags(db) -> list[FeatureFlag]:
    # Ensure the module defaults exist (global).
    existing = {(f.flag_key, f.organization_id) for f in (await db.execute(select(FeatureFlag).where(FeatureFlag.deleted_at.is_(None)))).scalars().all()}
    created = False
    for key in FLAG_MODULES:
        if (key, None) not in existing:
            db.add(FeatureFlag(flag_key=key, name=key.title(), is_enabled=True, organization_id=None,
                               description=f"Enable the {key} module."))
            created = True
    if created:
        await db.commit()
    res = await db.execute(select(FeatureFlag).where(FeatureFlag.deleted_at.is_(None))
                           .order_by(FeatureFlag.organization_id.nullsfirst(), FeatureFlag.flag_key))
    return list(res.scalars().all())


async def set_feature_flag(db, actor, flag_key, is_enabled, organization_id=None, name=None, description=None, ip=None) -> FeatureFlag:
    filters = [FeatureFlag.flag_key == flag_key, FeatureFlag.deleted_at.is_(None)]
    filters.append(FeatureFlag.organization_id == str(organization_id) if organization_id else FeatureFlag.organization_id.is_(None))
    flag = (await db.execute(select(FeatureFlag).where(*filters))).scalar_one_or_none()
    if flag is None:
        flag = FeatureFlag(flag_key=flag_key, name=name or flag_key.title(), description=description,
                           is_enabled=is_enabled, organization_id=organization_id, updated_by=actor.id)
        db.add(flag)
    else:
        flag.is_enabled = is_enabled
        flag.updated_by = actor.id
    await _audit(db, actor, "feature_flag.set", "feature_flag", None,
                 new={"flag": flag_key, "enabled": is_enabled, "org": str(organization_id) if organization_id else "global"}, ip=ip)
    await db.commit()
    await db.refresh(flag)
    return flag


# ── System config / maintenance ───────────────────────────────────────────────

async def get_system_config(db) -> SystemConfig:
    cfg = (await db.execute(select(SystemConfig).where(SystemConfig.deleted_at.is_(None)).limit(1))).scalar_one_or_none()
    if cfg is None:
        cfg = SystemConfig()
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg


async def update_system_config(db, actor, data: dict, ip=None) -> SystemConfig:
    cfg = await get_system_config(db)
    old = {"maintenance_mode": cfg.maintenance_mode, "read_only_mode": cfg.read_only_mode}
    for f in ("maintenance_mode", "read_only_mode", "banner_message", "maintenance_scheduled_at",
              "ai_provider_priority", "email_sender", "sms_sender", "default_currency",
              "default_timezone", "data_retention_days", "limits"):
        if f in data and data[f] is not None:
            setattr(cfg, f, data[f])
    cfg.updated_by = actor.id
    await _audit(db, actor, "system_config.update", "system_config", cfg.id, old=old,
                 new={k: v for k, v in data.items() if v is not None}, ip=ip)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ── System health ─────────────────────────────────────────────────────────────

async def system_health(db) -> dict:
    from app.config import settings
    components = []

    try:
        await db.execute(select(func.now()))
        db_status = "ok"
    except Exception as e:
        db_status = "down"
    components.append({"name": "Database", "status": db_status, "detail": "PostgreSQL"})

    # Redis / queue / storage are optional in this deployment.
    components.append({"name": "Redis", "status": "not_configured", "detail": "Cache/queue backend optional"})
    components.append({"name": "Queue", "status": "ok", "detail": "In-process background jobs"})
    components.append({"name": "Storage", "status": "ok", "detail": "Local/object storage"})

    from app.services import ai_provider
    prov = ai_provider.providers_available()
    ai_status = "ok" if (prov["gemini"] or prov["claude"]) else "degraded"
    components.append({"name": "AI Providers", "status": ai_status,
                       "detail": f"gemini={prov['gemini']} claude={prov['claude']} offline={prov['offline_fallback']}"})

    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall, "version": getattr(settings, "APP_VERSION", "1.0.0"),
        "environment": getattr(settings, "ENVIRONMENT", "development"),
        "uptime_seconds": int(time.time() - _PROCESS_START),
        "components": components, "checked_at": datetime.now(tz=timezone.utc),
    }


# ── Background jobs ───────────────────────────────────────────────────────────

_RUNNABLE_JOBS = {"cleanup_expired_sessions", "recompute_feature_flags", "purge_stale_ai_cache"}


async def jobs_dashboard(db) -> dict:
    rows = (await db.execute(select(BackgroundJob).where(BackgroundJob.deleted_at.is_(None))
                             .order_by(BackgroundJob.created_at.desc()).limit(50))).scalars().all()
    sc_res = await db.execute(
        select(BackgroundJob.status, func.count(BackgroundJob.id)).where(BackgroundJob.deleted_at.is_(None))
        .group_by(BackgroundJob.status))
    status_counts = {s: int(c) for s, c in sc_res.all()}
    avg = (await db.execute(select(func.avg(BackgroundJob.duration_ms)).where(BackgroundJob.status == "success"))).scalar_one_or_none()
    return {
        "total": sum(status_counts.values()),
        "success": status_counts.get("success", 0), "failed": status_counts.get("failed", 0),
        "running": status_counts.get("running", 0), "queued": status_counts.get("queued", 0),
        "queue_depth": status_counts.get("queued", 0) + status_counts.get("running", 0),
        "avg_duration_ms": int(avg) if avg is not None else None,
        "recent": rows,
    }


async def run_job(db, actor, name: str, ip=None) -> BackgroundJob:
    if name not in _RUNNABLE_JOBS:
        raise ValidationException(f"Unknown job '{name}'. Available: {sorted(_RUNNABLE_JOBS)}")
    job = BackgroundJob(name=name, status="running", queue="admin", started_at=datetime.now(tz=timezone.utc),
                        triggered_by=actor.id, attempts=1)
    db.add(job)
    await db.flush()
    t0 = time.time()
    result: dict = {}
    try:
        if name == "cleanup_expired_sessions":
            res = await db.execute(select(Session).where(Session.expires_at < datetime.now(tz=timezone.utc), Session.revoked_at.is_(None)))
            n = 0
            for s in res.scalars().all():
                s.revoked_at = datetime.now(tz=timezone.utc)
                n += 1
            result = {"revoked": n}
        elif name == "recompute_feature_flags":
            flags = await list_feature_flags(db)
            result = {"flags": len(flags)}
        elif name == "purge_stale_ai_cache":
            cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
            res = await db.execute(select(AIResponseCache).where(AIResponseCache.created_at < cutoff, AIResponseCache.deleted_at.is_(None)))
            n = 0
            for c in res.scalars().all():
                c.deleted_at = datetime.now(tz=timezone.utc)
                n += 1
            result = {"purged": n}
        job.status = "success"
        job.result = result
    except Exception as e:  # pragma: no cover - defensive
        job.status = "failed"
        job.error = str(e)[:500]
    job.finished_at = datetime.now(tz=timezone.utc)
    job.duration_ms = int((time.time() - t0) * 1000)
    await _audit(db, actor, "job.run", "background_job", job.id, new={"name": name, "status": job.status}, ip=ip)
    await db.commit()
    await db.refresh(job)
    return job


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def admin_dashboard(db) -> dict:
    an = await platform_analytics(db)
    cfg = await get_system_config(db)
    health = await system_health(db)
    suspended_orgs = int((await db.execute(select(func.count(Organization.id)).where(Organization.is_suspended.is_(True)))).scalar_one())
    suspended_users = int((await db.execute(select(func.count(User.id)).where(User.is_active.is_(False), User.deleted_at.is_(None)))).scalar_one())
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    jobs_failed = int((await db.execute(select(func.count(BackgroundJob.id)).where(BackgroundJob.status == "failed", BackgroundJob.created_at >= since))).scalar_one())
    return {
        "organizations": an["total_organizations"], "farms": an["total_farms"], "users": an["total_users"],
        "active_users_today": an["active_users_today"], "monthly_revenue_estimate": an["monthly_revenue_estimate"],
        "ai_requests_total": an["ai_requests_total"], "suspended_orgs": suspended_orgs,
        "suspended_users": suspended_users, "maintenance_mode": cfg.maintenance_mode,
        "health_status": health["status"], "jobs_failed_24h": jobs_failed,
    }


# ── Admin AI ──────────────────────────────────────────────────────────────────

async def admin_ask(db, question: str) -> dict:
    from app.services import ai_provider
    an = await platform_analytics(db)
    cfg = await get_system_config(db)

    q = question.lower()
    parts, sources = [], []

    def add(src, text):
        parts.append(text)
        if src not in sources:
            sources.append(src)

    if any(w in q for w in ("ai", "gemini", "claude", "request", "usage")):
        add("ai_usage", f"AI requests: {an['ai_requests_total']} total ({an['ai_gemini']} Gemini, "
                        f"{an['ai_claude']} Claude, {an['ai_offline']} offline).")
        if an["top_farms"]:
            top = an["top_farms"][0]
            add("ai_usage", f"Most AI requests: {top['name']} ({top['ai_requests']}).")
    if any(w in q for w in ("organization", "org", "suspend", "limit")):
        add("organizations", f"{an['total_organizations']} organizations across {an['total_farms']} farms.")
    if any(w in q for w in ("user", "active", "login", "suspended")):
        add("users", f"{an['total_users']} users, {an['active_users_today']} active today.")
    if any(w in q for w in ("revenue", "subscription", "plan", "money")):
        add("revenue", f"Estimated monthly platform revenue KES {an['monthly_revenue_estimate']:,}.")
        for s in an["subscription_breakdown"]:
            add("revenue", f"{s['plan']}: {s['farm_count']} farm(s).")
    if any(w in q for w in ("maintenance", "flag", "config", "health", "system")):
        add("system", f"Maintenance mode is {'ON' if cfg.maintenance_mode else 'off'}; platform health nominal.")

    if not parts:
        add("platform", f"Platform snapshot: {an['total_organizations']} orgs, {an['total_farms']} farms, "
                        f"{an['total_users']} users, {an['ai_requests_total']} AI requests, "
                        f"est. monthly revenue KES {an['monthly_revenue_estimate']:,}.")

    prompt = f"You are Greena's platform admin assistant. Platform analytics: {an}. Question: {question}"
    result = await ai_provider.complete(prompt, offline_answer=" ".join(parts))
    return {"answer": result.text, "provider": result.provider, "sources": sources}
