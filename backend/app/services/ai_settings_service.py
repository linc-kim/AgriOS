"""
ARIA — AI settings and the usage/cost dashboard (Module 13 Part 8).

A farm's AI configuration: whether AI is on at all, which model it may use
(Gemini Flash, Gemini Pro, or offline-deterministic-only), the temperature and
token ceiling, and whether images and documents may be sent to a model. Plus the
usage and cost dashboard, read from the immutable `ai_usage_log`.

Settings are created lazily with safe defaults, so a farm that has never opened
the settings screen still has a coherent, honest configuration.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AIUsageLog
from app.models.ai_assistant import AI_MODELS, AISettings


async def get_or_create(db: AsyncSession, farm_id: uuid.UUID) -> AISettings:
    row = (
        await db.execute(
            select(AISettings).where(
                AISettings.farm_id == farm_id, AISettings.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = AISettings(farm_id=farm_id)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update(
    db: AsyncSession, farm_id: uuid.UUID, changes: dict, user_id: uuid.UUID
) -> AISettings:
    row = await get_or_create(db, farm_id)
    if "model" in changes and changes["model"] not in AI_MODELS:
        raise ValueError(f"model must be one of {AI_MODELS}")
    if "temperature" in changes:
        t = float(changes["temperature"])
        if not 0.0 <= t <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
    if "max_output_tokens" in changes:
        n = int(changes["max_output_tokens"])
        if not 16 <= n <= 4096:
            raise ValueError("max_output_tokens must be between 16 and 4096")

    for field in ("ai_enabled", "model", "temperature", "max_output_tokens",
                  "allow_vision", "allow_documents", "monthly_budget_usd"):
        if field in changes and changes[field] is not None:
            setattr(row, field, changes[field])
    row.updated_by = user_id
    row.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


def effective_ai_enabled(settings: AISettings) -> bool:
    """AI is on only when the farm enabled it *and* didn't pick offline-only."""
    return bool(settings.ai_enabled) and settings.model != "offline"


async def usage_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """
    The cost dashboard: totals, this-month spend, and a per-provider breakdown,
    read from the append-only usage log so it can never disagree with billing.
    """
    # ai_usage_log.created_at is a naive UTC timestamp, so compare against a
    # naive boundary to avoid mixing offset-aware and naive datetimes.
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def _agg(*extra):
        q = select(
            func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
            func.coalesce(func.sum(AIUsageLog.cost_usd), 0),
            func.count(AIUsageLog.id),
        ).where(AIUsageLog.farm_id == farm_id, *extra)
        tokens, cost, calls = (await db.execute(q)).one()
        return {"tokens": int(tokens), "cost_usd": float(cost), "calls": int(calls)}

    total = await _agg()
    month = await _agg(AIUsageLog.created_at >= month_start)

    provider_rows = (
        await db.execute(
            select(
                AIUsageLog.provider,
                func.count(AIUsageLog.id),
                func.coalesce(func.sum(AIUsageLog.cost_usd), 0),
                func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
            )
            .where(AIUsageLog.farm_id == farm_id)
            .group_by(AIUsageLog.provider)
        )
    ).all()
    by_provider = [
        {"provider": p, "calls": int(c), "cost_usd": float(cost), "tokens": int(tok)}
        for p, c, cost, tok in provider_rows
    ]

    return {
        "total": total,
        "this_month": month,
        "by_provider": by_provider,
    }


async def record_usage(
    db: AsyncSession,
    *,
    farm_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    call_type: str,
    success: bool = True,
) -> None:
    """Append one immutable usage row (DB-08: append-only)."""
    db.add(AIUsageLog(
        farm_id=farm_id, user_id=user_id, provider=provider, model=model,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens, cost_usd=cost_usd,
        call_type=call_type, success=success,
    ))
    await db.commit()
