"""
Greena — Admin Service (Sprint 8)
Platform administration: stats, user management, farm oversight, AI usage.
All functions are super_admin-only via endpoint permission checks.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIUsageLog
from app.models.auth import User, UserRole, Role
from app.models.farm import Farm, FarmMember, SubscriptionPlan
from app.models.flock import Flock, DailyLog
from app.models.finance import Expense, RevenueRecord
from app.models.health import DiseaseAlert
from app.models.platform import MarketPrice, Notification
from app.schemas.admin import (
    AdminAIUsageDay,
    AdminAIUsageResponse,
    AdminFarmDetail,
    AdminFarmListResponse,
    AdminFarmPlanOverride,
    AdminFarmSummary,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
    PlatformStats,
    SubscriptionPlanSummary,
)

logger = logging.getLogger(__name__)


# ── Platform Stats (A-01) ─────────────────────────────────────────────────────

async def get_platform_stats(db: AsyncSession) -> PlatformStats:
    """Return platform-wide KPIs for the admin overview dashboard."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Total users
    total_users = (await db.scalar(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    )) or 0

    # Active users (signed in / created within 30 days — use created_at as proxy in V1)
    active_users_30d = (await db.scalar(
        select(func.count(User.id)).where(
            User.deleted_at.is_(None),
            User.created_at >= thirty_days_ago,
        )
    )) or 0

    # Total farms
    total_farms = (await db.scalar(
        select(func.count(Farm.id)).where(Farm.deleted_at.is_(None))
    )) or 0

    # Active farms (had a daily log in 30 days)
    active_farms_30d = (await db.scalar(
        select(func.count(distinct(Flock.farm_id))).join(
            DailyLog, DailyLog.flock_id == Flock.id
        ).where(
            DailyLog.deleted_at.is_(None),
            DailyLog.log_date >= (date.today() - timedelta(days=30)),
        )
    )) or 0

    # Total flocks (all time)
    total_flocks = (await db.scalar(
        select(func.count(Flock.id)).where(Flock.deleted_at.is_(None))
    )) or 0

    # Active flocks (status = 'active')
    active_flocks = (await db.scalar(
        select(func.count(Flock.id)).where(
            Flock.deleted_at.is_(None),
            Flock.status == "active",
        )
    )) or 0

    # AI queries last 30 days
    total_ai_queries_30d = (await db.scalar(
        select(func.count(AIUsageLog.id)).where(
            AIUsageLog.created_at >= thirty_days_ago,
        )
    )) or 0

    # AI cost last 30 days
    total_ai_cost_usd_30d = float((await db.scalar(
        select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0)).where(
            AIUsageLog.created_at >= thirty_days_ago,
        )
    )) or 0)

    # Notifications sent last 30 days (total created)
    total_notifications_sent_30d = (await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.deleted_at.is_(None),
            Notification.created_at >= thirty_days_ago,
        )
    )) or 0

    # Active disease alerts
    total_disease_alerts_active = (await db.scalar(
        select(func.count(DiseaseAlert.id)).where(
            DiseaseAlert.deleted_at.is_(None),
            DiseaseAlert.status == "active",
        )
    )) or 0

    # Total market prices
    total_market_prices = (await db.scalar(
        select(func.count(MarketPrice.id))
    )) or 0

    return PlatformStats(
        total_users=total_users,
        active_users_30d=active_users_30d,
        total_farms=total_farms,
        active_farms_30d=active_farms_30d,
        total_flocks=total_flocks,
        active_flocks=active_flocks,
        total_ai_queries_30d=total_ai_queries_30d,
        total_ai_cost_usd_30d=round(total_ai_cost_usd_30d, 4),
        total_notifications_sent_30d=total_notifications_sent_30d,
        total_disease_alerts_active=total_disease_alerts_active,
        total_market_prices=total_market_prices,
    )


# ── User Management (A-02) ────────────────────────────────────────────────────

async def list_users(
    db: AsyncSession,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminUserListResponse:
    """List all platform users with admin summary data."""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    stmt = (
        select(
            User,
            func.count(distinct(FarmMember.farm_id)).label("farm_count"),
            func.count(AIUsageLog.id).filter(
                AIUsageLog.created_at >= thirty_days_ago
            ).label("ai_queries_this_month"),
        )
        .outerjoin(FarmMember, FarmMember.user_id == User.id)
        .outerjoin(AIUsageLog, AIUsageLog.user_id == User.id)
        .where(User.deleted_at.is_(None))
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )

    if search:
        stmt = stmt.where(
            User.phone_number.ilike(f"%{search}%")
            | User.name.ilike(f"%{search}%")
        )

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    # Total count
    count_stmt = select(func.count(User.id)).where(User.deleted_at.is_(None))
    if search:
        count_stmt = count_stmt.where(
            User.phone_number.ilike(f"%{search}%")
            | User.name.ilike(f"%{search}%")
        )
    if is_active is not None:
        count_stmt = count_stmt.where(User.is_active == is_active)

    total = (await db.scalar(count_stmt)) or 0

    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()

    items = [
        AdminUserSummary(
            id=row.User.id,
            phone_number=row.User.phone_number,
            name=row.User.name,
            is_active=row.User.is_active,
            is_verified=row.User.is_verified,
            farm_count=row.farm_count or 0,
            ai_queries_this_month=row.ai_queries_this_month or 0,
            created_at=row.User.created_at,
        )
        for row in rows
    ]

    return AdminUserListResponse(items=items, total=total)


async def get_user_detail(db: AsyncSession, user_id: UUID) -> Optional[AdminUserDetail]:
    """Get full user detail for admin inspection."""
    user = await db.get(User, user_id)
    if not user or user.deleted_at:
        return None

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    # Farm memberships
    farm_rows = (await db.execute(
        select(Farm.id, Farm.name, FarmMember.role_id)
        .join(FarmMember, FarmMember.farm_id == Farm.id)
        .where(FarmMember.user_id == user_id, Farm.deleted_at.is_(None))
    )).all()

    farms = [{"id": str(r.id), "name": r.name} for r in farm_rows]

    # Role names
    role_rows = (await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )).scalars().all()

    # AI usage
    ai_30d = (await db.scalar(
        select(func.count(AIUsageLog.id)).where(
            AIUsageLog.user_id == user_id,
            AIUsageLog.created_at >= thirty_days_ago,
        )
    )) or 0

    ai_all = (await db.scalar(
        select(func.count(AIUsageLog.id)).where(AIUsageLog.user_id == user_id)
    )) or 0

    return AdminUserDetail(
        id=user.id,
        phone_number=user.phone_number,
        name=user.name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        farms=farms,
        roles=list(role_rows),
        ai_queries_this_month=ai_30d,
        ai_queries_all_time=ai_all,
    )


async def suspend_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """Suspend a user account (sets is_active=False)."""
    user = await db.get(User, user_id)
    if not user or user.deleted_at:
        return None
    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


async def restore_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """Restore a suspended user account."""
    user = await db.get(User, user_id)
    if not user or user.deleted_at:
        return None
    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


async def override_user_quota(
    db: AsyncSession,
    user_id: UUID,
    monthly_limit: Optional[int],
) -> Optional[User]:
    """
    Store a quota override in user metadata_.
    The ARIA service reads user.metadata_.get('quota_override') to apply it.
    """
    user = await db.get(User, user_id)
    if not user or user.deleted_at:
        return None

    meta = dict(user.metadata_ or {})
    if monthly_limit is None:
        meta.pop("quota_override", None)
    else:
        meta["quota_override"] = monthly_limit

    user.metadata_ = meta
    await db.commit()
    await db.refresh(user)
    return user


# ── Farm Management (A-03/A-04) ──────────────────────────────────────────────

async def list_farms(
    db: AsyncSession,
    search: Optional[str] = None,
    plan_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> AdminFarmListResponse:
    """List all farms with admin summary data."""
    stmt = (
        select(
            Farm,
            SubscriptionPlan.name.label("plan_name"),
            func.count(distinct(FarmMember.user_id)).label("member_count"),
            func.count(
                distinct(Flock.id)
            ).filter(Flock.status == "active").label("active_flock_count"),
        )
        .join(SubscriptionPlan, SubscriptionPlan.id == Farm.plan_id)
        .outerjoin(FarmMember, FarmMember.farm_id == Farm.id)
        .outerjoin(
            Flock,
            (Flock.farm_id == Farm.id) & (Flock.deleted_at.is_(None)),
        )
        .where(Farm.deleted_at.is_(None))
        .group_by(Farm.id, SubscriptionPlan.name)
        .order_by(Farm.created_at.desc())
    )

    if search:
        stmt = stmt.where(Farm.name.ilike(f"%{search}%"))

    if plan_name:
        stmt = stmt.where(SubscriptionPlan.name == plan_name)

    count_stmt = select(func.count(Farm.id)).where(Farm.deleted_at.is_(None))
    if search:
        count_stmt = count_stmt.where(Farm.name.ilike(f"%{search}%"))

    total = (await db.scalar(count_stmt)) or 0
    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()

    items = [
        AdminFarmSummary(
            id=row.Farm.id,
            name=row.Farm.name,
            owner_phone=None,   # Resolved separately for performance
            owner_name=None,
            subscription_plan=row.plan_name,
            member_count=row.member_count or 0,
            active_flock_count=row.active_flock_count or 0,
            last_log_date=None,
            created_at=row.Farm.created_at,
        )
        for row in rows
    ]

    return AdminFarmListResponse(items=items, total=total)


async def override_farm_plan(
    db: AsyncSession,
    farm_id: UUID,
    payload: AdminFarmPlanOverride,
) -> Optional[Farm]:
    """Override the subscription plan for a farm."""
    farm = await db.get(Farm, farm_id)
    if not farm or farm.deleted_at:
        return None

    plan = (await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == payload.plan_name)
    )).scalar_one_or_none()

    if not plan:
        return None

    farm.plan_id = plan.id
    meta = dict(farm.metadata_ or {})
    meta["plan_override_reason"] = payload.reason
    meta["plan_override_at"] = datetime.utcnow().isoformat()
    farm.metadata_ = meta
    await db.commit()
    await db.refresh(farm)
    return farm


# ── AI Usage (A-07) ──────────────────────────────────────────────────────────

async def get_ai_usage(
    db: AsyncSession,
    period_days: int = 30,
) -> AdminAIUsageResponse:
    """Return AI usage and cost summary for the admin dashboard."""
    since = datetime.utcnow() - timedelta(days=period_days)

    # Totals
    total_queries = (await db.scalar(
        select(func.count(AIUsageLog.id)).where(AIUsageLog.created_at >= since)
    )) or 0

    total_tokens = int((await db.scalar(
        select(func.coalesce(func.sum(AIUsageLog.total_tokens), 0))
        .where(AIUsageLog.created_at >= since)
    )) or 0)

    total_cost_usd = float((await db.scalar(
        select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0))
        .where(AIUsageLog.created_at >= since)
    )) or 0.0)

    unique_users = (await db.scalar(
        select(func.count(distinct(AIUsageLog.user_id)))
        .where(AIUsageLog.created_at >= since)
    )) or 0

    # Top model
    model_row = (await db.execute(
        select(AIUsageLog.provider, func.count(AIUsageLog.id).label("cnt"))
        .where(AIUsageLog.created_at >= since)
        .group_by(AIUsageLog.provider)
        .order_by(func.count(AIUsageLog.id).desc())
        .limit(1)
    )).first()
    top_model = model_row.provider if model_row else None

    # Fallback rate — logs where model_used contains "claude" or "fallback"
    fallback_count = (await db.scalar(
        select(func.count(AIUsageLog.id)).where(
            AIUsageLog.created_at >= since,
            AIUsageLog.provider == 'claude',  # claude = fallback provider in V1
        )
    )) or 0
    fallback_rate = round((fallback_count / total_queries * 100) if total_queries > 0 else 0.0, 1)

    # Daily breakdown
    daily_rows = (await db.execute(
        select(
            func.date(AIUsageLog.created_at).label("day"),
            func.count(AIUsageLog.id).label("query_count"),
            func.coalesce(func.sum(AIUsageLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0.0).label("cost_usd"),
            func.count(distinct(AIUsageLog.user_id)).label("unique_users"),
        )
        .where(AIUsageLog.created_at >= since)
        .group_by(func.date(AIUsageLog.created_at))
        .order_by(func.date(AIUsageLog.created_at).desc())
    )).all()

    daily_breakdown = [
        AdminAIUsageDay(
            date=str(row.day),
            query_count=row.query_count,
            total_tokens=int(row.total_tokens),
            cost_usd=float(row.cost_usd),
            unique_users=row.unique_users,
        )
        for row in daily_rows
    ]

    return AdminAIUsageResponse(
        period_days=period_days,
        total_queries=total_queries,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost_usd, 4),
        unique_users=unique_users,
        daily_breakdown=daily_breakdown,
        top_model=top_model,
        fallback_rate_pct=fallback_rate,
    )


# ── Subscription Plans (A-04) ─────────────────────────────────────────────────

async def list_subscription_plans(
    db: AsyncSession,
) -> list[SubscriptionPlanSummary]:
    """Return all subscription plans with farm count per plan."""
    rows = (await db.execute(
        select(
            SubscriptionPlan,
            func.count(Farm.id).label("farm_count"),
        )
        .outerjoin(Farm, (Farm.plan_id == SubscriptionPlan.id) & (Farm.deleted_at.is_(None)))
        .group_by(SubscriptionPlan.id)
        .order_by(SubscriptionPlan.price_kes)
    )).all()

    return [
        SubscriptionPlanSummary(
            id=row.SubscriptionPlan.id,
            name=row.SubscriptionPlan.name,
            display_name=row.SubscriptionPlan.display_name,
            price_kes=str(row.SubscriptionPlan.price_kes),
            farm_count=row.farm_count or 0,
        )
        for row in rows
    ]
