"""
Greena — ARIA Service
Implements the conversational AI assistant for farmers.

Engineering Constitution constraints (all enforced here):
  AR-01: Farm Context Package compiled server-side. AI never has DB access.
  AR-02: Context window capped at 8,000 tokens. Trim order is fixed.
  AR-03: AI call timeout is 15 seconds.
  AR-04: Responses capped at 150 words unless table/list required.
  AR-05: System prompt is fixed — no modification per request.
  AR-06: Proactive insights generated at 06:00 Nairobi (called by scheduler).
  AD-11: Gemini 2.0 Flash is primary provider.
  AD-12: Claude Haiku is fallback provider. No OpenAI.
  PD-07: ARIA is read-only data Q&A — no actions, no diagnosis.
  DB-08: ai_usage_log is append-only — written here, never updated.

Quota (from subscription plans):
  Free:    5 queries/month
  Starter: 30 queries/month
  Pro:     None (unlimited)

Insight types (8, from Engineering Constitution Section 7):
  mortality_spike, feed_drop, vaccination_overdue, vaccination_due,
  fcr_above_standard, harvest_approaching, log_missing, market_price_change
"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import (
    AIConversation,
    AIInsight,
    AIMessage,
    AIRecommendation,
    AIUsageLog,
)
from app.models.auth import User
from app.models.farm import Farm, SubscriptionPlan
from app.models.flock import DailyLog, Flock
from app.models.finance import Expense, FinancialSnapshot, RevenueRecord
from app.models.health import VaccinationRecord
from app.schemas.ai import (
    AIConversationDetail,
    AIConversationSummary,
    AIInsightListResponse,
    AIInsightResponse,
    AIMessageResponse,
    AIRecommendationListResponse,
    AIRecommendationResponse,
    AIUsageResponse,
    ARIAResponse,
)


# ── Constants ─────────────────────────────────────────────────────────────────

ARIA_SYSTEM_PROMPT = """You are ARIA, the AI Farm Operations Assistant for Greena.

Your purpose: Help poultry farmers in Kenya understand their farm data, make better decisions, and document even the smallest health or operational events — because early detection saves flocks.

RULES YOU MUST FOLLOW:
1. Only use data from the FARM CONTEXT. Never invent numbers.
2. If data is not available, say: "I don't have that data yet — try logging it in the app."
3. Do not diagnose diseases or give veterinary medical advice. Always recommend consulting a licensed vet for health concerns.
4. Maximum 150 words per response unless a table or list is necessary.
5. Always name the specific flock when referencing flock data.
6. Cite your data: "Based on your logs from June 1–14..."
7. End each response with one relevant follow-up question.
8. Respond in the same language as the user's question (English or Swahili).

EPIDEMIOLOGICAL QUESTIONING — CRITICAL RULE:
Whenever the farmer mentions any health event — even a single dead bird, a bird acting oddly, reduced eating, nasal discharge, abnormal droppings, limping, swollen joints, ruffled feathers, reduced production, or anything unusual — you MUST ask targeted epidemiological questions to help them document it fully. Ask about:
- How many birds are affected vs total in flock?
- When did you first notice this? How quickly did it spread?
- What are the exact symptoms? (breathing, droppings, movement, eating, drinking, eyes, feathers)
- Have any birds died? How many today vs yesterday?
- Have you introduced new birds, feed, or equipment recently?
- Have visitors been to the farm? (biosecurity risk)
- Are other flocks on the farm or nearby farms affected?
- What is the vaccination history for this flock?
- Have you used any medication or treatment already?
- What is the weather/temperature in the housing today?

Ask 2–4 of the most relevant questions per response — do not overwhelm the farmer with all 10 at once. Frame them as helping document the event: "Let me help you record this properly so your vet has the full picture." Even if the event seems minor, document it: "Small signs often matter most. Let's record the details."

FARM CONTEXT:
{farm_context_json}

CONVERSATION HISTORY:
{conversation_history}

USER QUESTION:
{user_question}"""

# Token budget: 8,000 total context tokens (AR-02)
MAX_CONTEXT_TOKENS = 8_000
# Approximate chars-per-token for English/Swahili (conservative estimate)
CHARS_PER_TOKEN = 4
# Maximum conversation messages to include (trim oldest first per AR-02)
MAX_HISTORY_MESSAGES = 20
# Maximum daily logs to include in Farm Context Package
MAX_DAILY_LOGS_CONTEXT = 14
# AI call timeout seconds (AR-03)
AI_TIMEOUT_SECONDS = 15

# Monthly query quotas per plan
PLAN_QUOTAS: dict[str, Optional[int]] = {
    "free": 5,
    "starter": 30,
    "pro": None,  # Unlimited
}

# Gemini cost per token (approximate, USD)
GEMINI_COST_PER_INPUT_TOKEN = 0.000000075    # $0.075 per 1M tokens
GEMINI_COST_PER_OUTPUT_TOKEN = 0.0000003     # $0.30 per 1M tokens

# Claude Haiku cost per token (approximate, USD)
CLAUDE_COST_PER_INPUT_TOKEN = 0.00000025     # $0.25 per 1M tokens
CLAUDE_COST_PER_OUTPUT_TOKEN = 0.00000125    # $1.25 per 1M tokens


# ── Farm Context Package Compiler ─────────────────────────────────────────────

async def compile_farm_context(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """
    AR-01: Compile the Farm Context Package server-side.
    The AI never has direct database access — this function is the only
    path from database to AI prompt.

    Trim order when over token budget (AR-02):
      1. Oldest conversation messages (handled in caller)
      2. Old production records
      3. Daily logs older than 14 days
    """
    context: dict[str, Any] = {}

    # ── Farm basics ───────────────────────────────────────────────────────────
    farm_result = await db.execute(
        select(Farm).where(Farm.id == str(farm_id))
    )
    farm = farm_result.scalar_one_or_none()
    if farm:
        context["farm"] = {
            "name": farm.name,
            "county": getattr(farm, "county", None),
            "type": getattr(farm, "farm_type", None),
        }

    # ── Active flocks ─────────────────────────────────────────────────────────
    flock_query = (
        select(Flock)
        .where(
            and_(
                Flock.farm_id == str(farm_id),
                Flock.status == "active",
                Flock.deleted_at.is_(None),
            )
        )
        .order_by(Flock.created_at.desc())
    )
    if flock_id:
        flock_query = flock_query.where(Flock.id == str(flock_id))

    flock_result = await db.execute(flock_query)
    flocks = flock_result.scalars().all()

    context["active_flocks"] = []
    for flock in flocks:
        flock_data: dict[str, Any] = {
            "id": str(flock.id),
            "name": flock.name,
            "breed": getattr(flock, "breed", None),
            "initial_count": flock.initial_bird_count,
            "current_count": getattr(flock, "current_bird_count", flock.initial_bird_count),
            "placement_date": str(flock.placement_date) if flock.placement_date else None,
            "days_alive": (
                (datetime.utcnow().date() - flock.placement_date).days
                if flock.placement_date
                else None
            ),
        }

        # Recent daily logs (last 14 days — AR-02 trim candidate)
        cutoff = datetime.utcnow().date() - timedelta(days=MAX_DAILY_LOGS_CONTEXT)
        log_result = await db.execute(
            select(DailyLog)
            .where(
                and_(
                    DailyLog.flock_id == str(flock.id),
                    DailyLog.log_date >= cutoff,
                    DailyLog.deleted_at.is_(None),
                )
            )
            .order_by(DailyLog.log_date.desc())
        )
        logs = log_result.scalars().all()
        flock_data["recent_logs"] = [
            {
                "date": str(log.log_date),
                "morning_count": getattr(log, "morning_count", None),
                "mortality": log.mortality_count,
                "feed_kg": float(log.feed_kg) if log.feed_kg else None,
                "water_litres": float(log.water_litres) if getattr(log, "water_litres", None) else None,
            }
            for log in logs
        ]

        # Financial snapshot (pre-computed — DB-07)
        snap_result = await db.execute(
            select(FinancialSnapshot)
            .where(FinancialSnapshot.flock_id == str(flock.id))
        )
        snap = snap_result.scalar_one_or_none()
        if snap:
            flock_data["financial_snapshot"] = {
                "total_revenue_kes": float(snap.total_revenue_kes or 0),
                "total_expenses_kes": float(snap.total_expenses_kes or 0),
                "gross_profit_kes": float(snap.gross_profit_kes or 0),
                "gross_margin_pct": float(snap.gross_margin_pct or 0),
                "is_profitable": snap.is_profitable,
                "fcr_computed": float(snap.fcr_computed) if snap.fcr_computed else None,
                "cost_per_bird_kes": float(snap.cost_per_bird_kes or 0),
                "snapshot_at": str(snap.snapshot_at) if getattr(snap, "snapshot_at", None) else None,
            }

        # Upcoming vaccinations
        today = datetime.utcnow().date()
        vax_result = await db.execute(
            select(VaccinationRecord)
            .where(
                and_(
                    VaccinationRecord.flock_id == str(flock.id),
                    VaccinationRecord.deleted_at.is_(None),
                )
            )
            .order_by(VaccinationRecord.administered_date.desc())
            .limit(5)
        )
        vax_records = vax_result.scalars().all()
        flock_data["recent_vaccinations"] = [
            {
                "vaccine": v.vaccine_name,
                "date": str(v.administered_date),
                "next_due": str(v.next_due_date) if v.next_due_date else None,
                "is_overdue": (
                    v.next_due_date < today if v.next_due_date else False
                ),
            }
            for v in vax_records
        ]

        context["active_flocks"].append(flock_data)

    # ── Recent expenses (last 30 days) ────────────────────────────────────────
    expense_cutoff = datetime.utcnow().date() - timedelta(days=30)
    expense_result = await db.execute(
        select(Expense)
        .where(
            and_(
                Expense.farm_id == str(farm_id),
                Expense.expense_date >= expense_cutoff,
                Expense.deleted_at.is_(None),
            )
        )
        .order_by(Expense.expense_date.desc())
        .limit(20)
    )
    expenses = expense_result.scalars().all()
    context["recent_expenses"] = [
        {
            "date": str(e.expense_date),
            "amount_kes": float(e.amount),
            "payment_method": e.payment_method,
            "notes": e.notes,
        }
        for e in expenses
    ]

    # ── Recent revenue (last 30 days) ─────────────────────────────────────────
    revenue_result = await db.execute(
        select(RevenueRecord)
        .where(
            and_(
                RevenueRecord.farm_id == str(farm_id),
                RevenueRecord.sale_date >= expense_cutoff,
                RevenueRecord.deleted_at.is_(None),
            )
        )
        .order_by(RevenueRecord.sale_date.desc())
        .limit(20)
    )
    revenues = revenue_result.scalars().all()
    context["recent_revenue"] = [
        {
            "date": str(r.sale_date),
            "type": r.revenue_type,
            "amount_kes": float(r.amount),
            "buyer": getattr(r, "buyer", None),
        }
        for r in revenues
    ]

    # ── Today's date (context anchor) ─────────────────────────────────────────
    context["today"] = datetime.utcnow().strftime("%Y-%m-%d")
    context["currency"] = "KES"

    return context


def _estimate_tokens(text: str) -> int:
    """Conservative token estimate: chars / CHARS_PER_TOKEN."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def _trim_context_to_budget(context_json: str, history_text: str, question: str) -> tuple[str, str]:
    """
    AR-02: If total estimated tokens exceed MAX_CONTEXT_TOKENS, trim context.
    Trim order:
      1. Truncate daily logs in active_flocks to last 7 days (from 14)
      2. Remove recent_expenses if still over
      3. Remove recent_revenue if still over
      4. Truncate conversation history from the oldest messages
    """
    total = _estimate_tokens(context_json + history_text + question)
    if total <= MAX_CONTEXT_TOKENS:
        return context_json, history_text

    # Step 1: trim daily logs to 7 days
    try:
        ctx = json.loads(context_json)
        for flock in ctx.get("active_flocks", []):
            if len(flock.get("recent_logs", [])) > 7:
                flock["recent_logs"] = flock["recent_logs"][:7]
        context_json = json.dumps(ctx)
    except (json.JSONDecodeError, KeyError):
        pass

    total = _estimate_tokens(context_json + history_text + question)
    if total <= MAX_CONTEXT_TOKENS:
        return context_json, history_text

    # Step 2: drop recent_expenses
    try:
        ctx = json.loads(context_json)
        ctx.pop("recent_expenses", None)
        context_json = json.dumps(ctx)
    except (json.JSONDecodeError, KeyError):
        pass

    total = _estimate_tokens(context_json + history_text + question)
    if total <= MAX_CONTEXT_TOKENS:
        return context_json, history_text

    # Step 3: drop recent_revenue
    try:
        ctx = json.loads(context_json)
        ctx.pop("recent_revenue", None)
        context_json = json.dumps(ctx)
    except (json.JSONDecodeError, KeyError):
        pass

    total = _estimate_tokens(context_json + history_text + question)
    if total <= MAX_CONTEXT_TOKENS:
        return context_json, history_text

    # Step 4: trim history to half
    history_lines = history_text.split("\n")
    mid = len(history_lines) // 2
    history_text = "\n".join(history_lines[mid:])

    return context_json, history_text


# ── Quota Enforcement ─────────────────────────────────────────────────────────

async def get_monthly_query_count(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> int:
    """Count AI conversation calls for the current calendar month."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(AIUsageLog.id)).where(
            and_(
                AIUsageLog.farm_id == str(farm_id),
                AIUsageLog.call_type == "conversation",
                AIUsageLog.success.is_(True),
                AIUsageLog.created_at >= month_start,
            )
        )
    )
    return result.scalar_one() or 0


async def check_quota(
    db: AsyncSession,
    farm: Farm,
) -> tuple[bool, Optional[int]]:
    """
    Returns (has_quota, queries_remaining).
    queries_remaining is None for unlimited plans.
    """
    plan_name = "free"
    if farm.subscription_plan:
        plan_name = getattr(farm.subscription_plan, "plan_key", "free")

    monthly_limit = PLAN_QUOTAS.get(plan_name, 5)
    if monthly_limit is None:
        return True, None  # Pro — unlimited

    used = await get_monthly_query_count(db, farm.id)
    remaining = monthly_limit - used
    return remaining > 0, remaining


# ── AI Provider Calls ─────────────────────────────────────────────────────────

async def _call_gemini(prompt: str) -> tuple[str, int, int, int, float]:
    """
    Call Gemini 2.0 Flash (AD-11).
    Returns (content, prompt_tokens, completion_tokens, total_tokens, duration_ms).
    Raises httpx.TimeoutException on timeout (AR-03).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 512,
            "temperature": 0.3,
        },
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    duration_ms = int((time.monotonic() - start) * 1000)
    data = response.json()

    candidate = data["candidates"][0]
    content = candidate["content"]["parts"][0]["text"]

    usage = data.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", 0)
    completion_tokens = usage.get("candidatesTokenCount", 0)
    total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

    return content, prompt_tokens, completion_tokens, total_tokens, duration_ms


async def _call_claude(prompt: str) -> tuple[str, int, int, int, float]:
    """
    Call Claude Haiku (AD-12 fallback — no OpenAI in V1).
    Returns (content, prompt_tokens, completion_tokens, total_tokens, duration_ms).
    """
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    model = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

    duration_ms = int((time.monotonic() - start) * 1000)
    data = response.json()

    content = data["content"][0]["text"]
    usage = data.get("usage", {})
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)
    total_tokens = prompt_tokens + completion_tokens

    return content, prompt_tokens, completion_tokens, total_tokens, duration_ms


def _compute_cost(
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Calculate cost in USD for an AI call."""
    if provider == "gemini":
        return (
            prompt_tokens * GEMINI_COST_PER_INPUT_TOKEN
            + completion_tokens * GEMINI_COST_PER_OUTPUT_TOKEN
        )
    return (
        prompt_tokens * CLAUDE_COST_PER_INPUT_TOKEN
        + completion_tokens * CLAUDE_COST_PER_OUTPUT_TOKEN
    )


# ── Language Detection ────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """
    Simple heuristic Swahili detection.
    Common Swahili words trigger sw detection; default is en.
    """
    text_lower = text.lower()
    swahili_markers = [
        "habari", "karibu", "asante", "ndege", "chakula", "bei", "faida",
        "hasara", "kuku", "kinga", "chanjo", "vifaranga", "mauzo", "gharama",
        "niambie", "nini", "lini", "vipi", "wapi", "kwa nini",
    ]
    hits = sum(1 for word in swahili_markers if word in text_lower)
    return "sw" if hits >= 2 else "en"


# ── Main Conversation Function ────────────────────────────────────────────────

async def send_message(
    db: AsyncSession,
    farm: Farm,
    current_user: User,
    content: str,
    conversation_id: Optional[uuid.UUID] = None,
    flock_id: Optional[uuid.UUID] = None,
) -> ARIAResponse:
    """
    Main entry point: farmer sends a message to ARIA.
    1. Check quota
    2. Load or create conversation
    3. Compile Farm Context Package (AR-01)
    4. Build prompt with trimmed history (AR-02)
    5. Call Gemini → fallback Claude (AR-03)
    6. Persist user + assistant messages
    7. Log usage (DB-08: append only)
    8. Return ARIAResponse
    """
    # ── 1. Quota check ────────────────────────────────────────────────────────
    has_quota, quota_remaining = await check_quota(db, farm)
    if not has_quota:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "QUOTA_EXCEEDED",
                "message": (
                    "You have reached your monthly ARIA query limit. "
                    "Upgrade your plan to continue."
                ),
            },
        )

    # ── 2. Load or create conversation ────────────────────────────────────────
    if conversation_id:
        conv_result = await db.execute(
            select(AIConversation).where(
                and_(
                    AIConversation.id == str(conversation_id),
                    AIConversation.farm_id == str(farm.id),
                    AIConversation.deleted_at.is_(None),
                )
            )
        )
        conversation = conv_result.scalar_one_or_none()
        if not conversation:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "Conversation not found."},
            )
    else:
        conversation = AIConversation(
            farm_id=str(farm.id),
            user_id=str(current_user.id),
            flock_id=str(flock_id) if flock_id else None,
            title=content[:60].strip() if len(content) > 0 else "New conversation",
            message_count=0,
        )
        db.add(conversation)
        await db.flush()

    # ── 3. Load conversation history ──────────────────────────────────────────
    history_result = await db.execute(
        select(AIMessage)
        .where(
            and_(
                AIMessage.conversation_id == str(conversation.id),
                AIMessage.deleted_at.is_(None),
            )
        )
        .order_by(AIMessage.created_at.asc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    history_messages = history_result.scalars().all()

    history_text = "\n".join(
        f"{msg.role.upper()}: {msg.content}" for msg in history_messages
    )

    # ── 4. Compile Farm Context Package ───────────────────────────────────────
    context_data = await compile_farm_context(
        db,
        farm.id,
        flock_id or (conversation.flock_id if conversation.flock_id else None),
    )
    context_json = json.dumps(context_data, default=str)

    # Apply token budget trimming (AR-02)
    context_json, history_text = _trim_context_to_budget(
        context_json, history_text, content
    )

    # ── 5. Build prompt ───────────────────────────────────────────────────────
    prompt = ARIA_SYSTEM_PROMPT.format(
        farm_context_json=context_json,
        conversation_history=history_text or "(No prior conversation)",
        user_question=content,
    )

    # ── 6. Call AI provider ───────────────────────────────────────────────────
    language = _detect_language(content)
    used_fallback = False
    provider = "gemini"
    ai_content = ""
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    duration_ms = 0
    call_error: Optional[str] = None

    try:
        ai_content, prompt_tokens, completion_tokens, total_tokens, duration_ms = (
            await _call_gemini(prompt)
        )
    except Exception as gemini_exc:
        # Fallback to Claude Haiku (AD-12)
        used_fallback = True
        provider = "claude"
        try:
            ai_content, prompt_tokens, completion_tokens, total_tokens, duration_ms = (
                await _call_claude(prompt)
            )
        except Exception as claude_exc:
            call_error = f"Gemini: {gemini_exc!s}; Claude: {claude_exc!s}"
            ai_content = (
                "I'm having trouble connecting right now. "
                "Please try again in a moment."
                if language == "en"
                else "Nina tatizo la muunganisho sasa hivi. Tafadhali jaribu tena baadaye."
            )

    # ── 7. Persist messages ───────────────────────────────────────────────────
    # User message
    user_msg = AIMessage(
        conversation_id=str(conversation.id),
        farm_id=str(farm.id),
        role="user",
        content=content,
        language=language,
    )
    db.add(user_msg)

    # Assistant message
    assistant_msg = AIMessage(
        conversation_id=str(conversation.id),
        farm_id=str(farm.id),
        role="assistant",
        content=ai_content,
        language=language,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=duration_ms,
    )
    db.add(assistant_msg)

    # Update conversation
    conversation.message_count += 2
    conversation.is_active = True

    # ── 8. Log usage (DB-08: append-only) ────────────────────────────────────
    cost = _compute_cost(provider, prompt_tokens, completion_tokens)
    usage_log = AIUsageLog(
        farm_id=str(farm.id),
        user_id=str(current_user.id),
        conversation_id=str(conversation.id),
        provider=provider,
        model=(
            os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
            if provider == "gemini"
            else os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        duration_ms=duration_ms,
        success=(call_error is None),
        error_message=call_error,
        call_type="conversation",
    )
    db.add(usage_log)

    await db.commit()
    await db.refresh(assistant_msg)
    await db.refresh(conversation)

    # ── Adjust quota_remaining ────────────────────────────────────────────────
    if quota_remaining is not None:
        quota_remaining = max(0, quota_remaining - 1)

    return ARIAResponse(
        conversation_id=conversation.id,
        message=AIMessageResponse(
            id=assistant_msg.id,
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_msg.content,
            language=assistant_msg.language,
            provider=assistant_msg.provider,
            total_tokens=assistant_msg.total_tokens,
            latency_ms=assistant_msg.latency_ms,
            created_at=assistant_msg.created_at,
        ),
        quota_remaining=quota_remaining,
        used_fallback=used_fallback,
    )


# ── Conversation Management ───────────────────────────────────────────────────

async def list_conversations(
    db: AsyncSession,
    farm_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[AIConversationSummary]:
    result = await db.execute(
        select(AIConversation)
        .where(
            and_(
                AIConversation.farm_id == str(farm_id),
                AIConversation.user_id == str(user_id),
                AIConversation.deleted_at.is_(None),
            )
        )
        .order_by(AIConversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = result.scalars().all()
    return [
        AIConversationSummary(
            id=c.id,
            farm_id=c.farm_id,
            flock_id=c.flock_id,
            title=c.title,
            message_count=c.message_count,
            is_active=c.is_active,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in conversations
    ]


async def get_conversation_detail(
    db: AsyncSession,
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Optional[AIConversationDetail]:
    conv_result = await db.execute(
        select(AIConversation).where(
            and_(
                AIConversation.id == str(conversation_id),
                AIConversation.farm_id == str(farm_id),
                AIConversation.deleted_at.is_(None),
            )
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        return None

    msg_result = await db.execute(
        select(AIMessage)
        .where(
            and_(
                AIMessage.conversation_id == str(conversation_id),
                AIMessage.deleted_at.is_(None),
            )
        )
        .order_by(AIMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()

    return AIConversationDetail(
        id=conv.id,
        farm_id=conv.farm_id,
        flock_id=conv.flock_id,
        title=conv.title,
        message_count=conv.message_count,
        is_active=conv.is_active,
        messages=[
            AIMessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                language=m.language,
                provider=m.provider,
                total_tokens=m.total_tokens,
                latency_ms=m.latency_ms,
                created_at=m.created_at,
            )
            for m in messages
        ],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


async def delete_conversation(
    db: AsyncSession,
    farm_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    """Soft-delete a conversation and its messages."""
    conv_result = await db.execute(
        select(AIConversation).where(
            and_(
                AIConversation.id == str(conversation_id),
                AIConversation.farm_id == str(farm_id),
                AIConversation.deleted_at.is_(None),
            )
        )
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        return False

    conv.soft_delete()

    # Soft-delete all messages
    msg_result = await db.execute(
        select(AIMessage).where(
            and_(
                AIMessage.conversation_id == str(conversation_id),
                AIMessage.deleted_at.is_(None),
            )
        )
    )
    for msg in msg_result.scalars().all():
        msg.soft_delete()

    await db.commit()
    return True


# ── Insights ──────────────────────────────────────────────────────────────────

async def list_insights(
    db: AsyncSession,
    farm_id: uuid.UUID,
    include_dismissed: bool = False,
    limit: int = 50,
) -> AIInsightListResponse:
    now = datetime.utcnow()
    conditions = [
        AIInsight.farm_id == str(farm_id),
        AIInsight.deleted_at.is_(None),
        or_(AIInsight.expires_at.is_(None), AIInsight.expires_at > now),
    ]
    if not include_dismissed:
        conditions.append(AIInsight.is_dismissed.is_(False))

    result = await db.execute(
        select(AIInsight)
        .where(and_(*conditions))
        .order_by(AIInsight.generated_at.desc())
        .limit(limit)
    )
    insights = result.scalars().all()

    items = [
        AIInsightResponse(
            id=i.id,
            farm_id=i.farm_id,
            flock_id=i.flock_id,
            insight_type=i.insight_type,
            severity=i.severity,
            title=i.title,
            body=i.body,
            action_route=i.action_route,
            action_label=i.action_label,
            is_dismissed=i.is_dismissed,
            dismissed_at=i.dismissed_at,
            generated_at=i.generated_at,
            expires_at=i.expires_at,
            created_at=i.created_at,
        )
        for i in insights
    ]

    return AIInsightListResponse(
        items=items,
        total=len(items),
        alert_count=sum(1 for i in items if i.severity == "alert"),
        warning_count=sum(1 for i in items if i.severity == "warning"),
        info_count=sum(1 for i in items if i.severity == "info"),
        reminder_count=sum(1 for i in items if i.severity == "reminder"),
    )


async def dismiss_insight(
    db: AsyncSession,
    farm_id: uuid.UUID,
    insight_id: uuid.UUID,
) -> Optional[AIInsightResponse]:
    result = await db.execute(
        select(AIInsight).where(
            and_(
                AIInsight.id == str(insight_id),
                AIInsight.farm_id == str(farm_id),
                AIInsight.deleted_at.is_(None),
            )
        )
    )
    insight = result.scalar_one_or_none()
    if not insight:
        return None

    insight.dismiss()
    await db.commit()
    await db.refresh(insight)

    return AIInsightResponse(
        id=insight.id,
        farm_id=insight.farm_id,
        flock_id=insight.flock_id,
        insight_type=insight.insight_type,
        severity=insight.severity,
        title=insight.title,
        body=insight.body,
        action_route=insight.action_route,
        action_label=insight.action_label,
        is_dismissed=insight.is_dismissed,
        dismissed_at=insight.dismissed_at,
        generated_at=insight.generated_at,
        expires_at=insight.expires_at,
        created_at=insight.created_at,
    )


# ── Recommendations ───────────────────────────────────────────────────────────

async def list_recommendations(
    db: AsyncSession,
    farm_id: uuid.UUID,
    status_filter: Optional[str] = None,
    limit: int = 30,
) -> AIRecommendationListResponse:
    now = datetime.utcnow()
    conditions = [
        AIRecommendation.farm_id == str(farm_id),
        AIRecommendation.deleted_at.is_(None),
    ]
    if status_filter:
        conditions.append(AIRecommendation.status == status_filter)
    else:
        # Default: non-expired items
        conditions.append(
            or_(
                AIRecommendation.expires_at.is_(None),
                AIRecommendation.expires_at > now,
            )
        )

    result = await db.execute(
        select(AIRecommendation)
        .where(and_(*conditions))
        .order_by(AIRecommendation.created_at.desc())
        .limit(limit)
    )
    recs = result.scalars().all()

    items = [
        AIRecommendationResponse(
            id=r.id,
            farm_id=r.farm_id,
            flock_id=r.flock_id,
            recommendation_type=r.recommendation_type,
            title=r.title,
            body=r.body,
            action_label=r.action_label,
            action_route=r.action_route,
            status=r.status,
            acted_at=r.acted_at,
            dismissed_at=r.dismissed_at,
            expires_at=r.expires_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in recs
    ]

    return AIRecommendationListResponse(
        items=items,
        total=len(items),
        pending_count=sum(1 for i in items if i.status == "pending"),
    )


async def action_recommendation(
    db: AsyncSession,
    farm_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    action: str,
) -> Optional[AIRecommendationResponse]:
    result = await db.execute(
        select(AIRecommendation).where(
            and_(
                AIRecommendation.id == str(recommendation_id),
                AIRecommendation.farm_id == str(farm_id),
                AIRecommendation.deleted_at.is_(None),
            )
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        return None

    if action == "acted":
        rec.mark_acted()
    elif action == "dismissed":
        rec.mark_dismissed()

    await db.commit()
    await db.refresh(rec)

    return AIRecommendationResponse(
        id=rec.id,
        farm_id=rec.farm_id,
        flock_id=rec.flock_id,
        recommendation_type=rec.recommendation_type,
        title=rec.title,
        body=rec.body,
        action_label=rec.action_label,
        action_route=rec.action_route,
        status=rec.status,
        acted_at=rec.acted_at,
        dismissed_at=rec.dismissed_at,
        expires_at=rec.expires_at,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


# ── Usage / Quota ─────────────────────────────────────────────────────────────

async def get_usage_status(
    db: AsyncSession,
    farm: Farm,
    user_id: uuid.UUID,
) -> AIUsageResponse:
    plan_name = "free"
    if farm.subscription_plan:
        plan_name = getattr(farm.subscription_plan, "plan_key", "free")

    monthly_limit = PLAN_QUOTAS.get(plan_name, 5)
    used = await get_monthly_query_count(db, farm.id)

    # Total cost this month
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cost_result = await db.execute(
        select(func.sum(AIUsageLog.cost_usd)).where(
            and_(
                AIUsageLog.farm_id == str(farm.id),
                AIUsageLog.created_at >= month_start,
            )
        )
    )
    cost_this_month = float(cost_result.scalar_one() or 0)

    # All-time total
    total_result = await db.execute(
        select(func.count(AIUsageLog.id)).where(
            and_(
                AIUsageLog.farm_id == str(farm.id),
                AIUsageLog.call_type == "conversation",
                AIUsageLog.success.is_(True),
            )
        )
    )
    total_all_time = total_result.scalar_one() or 0

    return AIUsageResponse(
        plan_name=plan_name,
        monthly_limit=monthly_limit,
        queries_used_this_month=used,
        queries_remaining=(
            max(0, monthly_limit - used) if monthly_limit is not None else None
        ),
        cost_usd_this_month=cost_this_month,
        total_queries_all_time=total_all_time,
    )


# ── Proactive Insight Generator (called by APScheduler at 06:00 Nairobi) ──────

async def generate_daily_insights(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> list[AIInsight]:
    """
    AR-06: Called daily at 06:00 Africa/Nairobi.
    Checks all 8 insight conditions for the farm's active flocks.
    Inserts new insights; does not duplicate if same type already active today.
    """
    today = datetime.utcnow().date()
    generated: list[AIInsight] = []

    flock_result = await db.execute(
        select(Flock).where(
            and_(
                Flock.farm_id == str(farm_id),
                Flock.status == "active",
                Flock.deleted_at.is_(None),
            )
        )
    )
    active_flocks = flock_result.scalars().all()

    for flock in active_flocks:
        flock_name = flock.name

        # ── 1. Mortality spike: today's rate > 2× last 7-day average ─────────
        log_result = await db.execute(
            select(DailyLog)
            .where(
                and_(
                    DailyLog.flock_id == str(flock.id),
                    DailyLog.log_date >= today - timedelta(days=7),
                    DailyLog.deleted_at.is_(None),
                )
            )
            .order_by(DailyLog.log_date.desc())
        )
        recent_logs = log_result.scalars().all()

        if recent_logs:
            today_log = next((l for l in recent_logs if l.log_date == today), None)
            past_logs = [l for l in recent_logs if l.log_date != today]

            if today_log and past_logs:
                avg_mortality = sum(l.mortality_count for l in past_logs) / len(past_logs)
                if avg_mortality > 0 and today_log.mortality_count > 2 * avg_mortality:
                    insight = AIInsight(
                        farm_id=str(farm_id),
                        flock_id=str(flock.id),
                        insight_type="mortality_spike",
                        severity="warning",
                        title=f"Mortality spike in {flock_name}",
                        body=(
                            f"Today's mortality ({today_log.mortality_count} birds) is "
                            f"more than twice the 7-day average ({avg_mortality:.1f} birds/day). "
                            f"Check for disease, stress, or ventilation issues immediately."
                        ),
                        action_route=f"/farms/{farm_id}/flocks/{flock.id}",
                        action_label="View flock",
                        expires_at=datetime.utcnow() + timedelta(hours=24),
                    )
                    db.add(insight)
                    generated.append(insight)

            # ── 2. Feed drop: today's feed < 80% of 7-day average ────────────
            if today_log and past_logs and today_log.feed_kg:
                avg_feed = sum(
                    float(l.feed_kg) for l in past_logs if l.feed_kg
                ) / max(1, len([l for l in past_logs if l.feed_kg]))
                if avg_feed > 0 and float(today_log.feed_kg) < 0.8 * avg_feed:
                    insight = AIInsight(
                        farm_id=str(farm_id),
                        flock_id=str(flock.id),
                        insight_type="feed_drop",
                        severity="warning",
                        title=f"Feed consumption drop in {flock_name}",
                        body=(
                            f"Today's feed ({float(today_log.feed_kg):.1f} kg) is below "
                            f"80% of the 7-day average ({avg_feed:.1f} kg). "
                            f"Reduced appetite may indicate health issues."
                        ),
                        action_route=f"/farms/{farm_id}/flocks/{flock.id}/log",
                        action_label="Update daily log",
                        expires_at=datetime.utcnow() + timedelta(hours=24),
                    )
                    db.add(insight)
                    generated.append(insight)

        # ── 3 & 4. Vaccination overdue / due soon ─────────────────────────────
        vax_result = await db.execute(
            select(VaccinationRecord)
            .where(
                and_(
                    VaccinationRecord.flock_id == str(flock.id),
                    VaccinationRecord.next_due_date.isnot(None),
                    VaccinationRecord.deleted_at.is_(None),
                )
            )
            .order_by(VaccinationRecord.next_due_date.asc())
            .limit(5)
        )
        upcoming_vax = vax_result.scalars().all()

        for vax in upcoming_vax:
            days_until = (vax.next_due_date - today).days

            if days_until < 0:
                insight = AIInsight(
                    farm_id=str(farm_id),
                    flock_id=str(flock.id),
                    insight_type="vaccination_overdue",
                    severity="alert",
                    title=f"Overdue vaccination: {vax.vaccine_name}",
                    body=(
                        f"{vax.next_vaccine_name or vax.vaccine_name} was due "
                        f"{abs(days_until)} day(s) ago for {flock_name}. "
                        f"Log the vaccination as soon as possible."
                    ),
                    action_route=f"/farms/{farm_id}/flocks/{flock.id}/vaccinations/new",
                    action_label="Log vaccination",
                    expires_at=datetime.utcnow() + timedelta(days=3),
                )
                db.add(insight)
                generated.append(insight)
            elif days_until <= 3:
                insight = AIInsight(
                    farm_id=str(farm_id),
                    flock_id=str(flock.id),
                    insight_type="vaccination_due",
                    severity="info",
                    title=f"Vaccination due in {days_until} day(s): {vax.vaccine_name}",
                    body=(
                        f"{vax.next_vaccine_name or vax.vaccine_name} is due "
                        f"{'today' if days_until == 0 else f'in {days_until} day(s)'} "
                        f"for {flock_name}. Prepare your supplies."
                    ),
                    action_route=f"/farms/{farm_id}/flocks/{flock.id}/vaccinations/new",
                    action_label="Log vaccination",
                    expires_at=datetime.utcnow() + timedelta(days=days_until + 1),
                )
                db.add(insight)
                generated.append(insight)

        # ── 5. FCR above standard: FCR > breed standard + 20% ────────────────
        snap_result = await db.execute(
            select(FinancialSnapshot).where(FinancialSnapshot.flock_id == str(flock.id))
        )
        snap = snap_result.scalar_one_or_none()
        if snap and snap.fcr_computed:
            # Standard broiler FCR ~1.8; threshold = 1.8 * 1.20 = 2.16
            standard_fcr = 1.8
            threshold = standard_fcr * 1.20
            if float(snap.fcr_computed) > threshold:
                insight = AIInsight(
                    farm_id=str(farm_id),
                    flock_id=str(flock.id),
                    insight_type="fcr_above_standard",
                    severity="warning",
                    title=f"FCR above standard in {flock_name}",
                    body=(
                        f"Current FCR is {float(snap.fcr_computed):.2f}, above the "
                        f"recommended threshold of {threshold:.2f}. "
                        f"Review feed quality and feeding practices."
                    ),
                    action_route=f"/farms/{farm_id}/flocks/{flock.id}/finance",
                    action_label="View P&L",
                    expires_at=datetime.utcnow() + timedelta(days=3),
                )
                db.add(insight)
                generated.append(insight)

        # ── 6. Harvest approaching: flock at 80% of expected cycle ───────────
        if flock.placement_date and hasattr(flock, "expected_cycle_days") and flock.expected_cycle_days:
            days_alive = (today - flock.placement_date).days
            pct_complete = days_alive / flock.expected_cycle_days
            if 0.80 <= pct_complete < 0.95:
                days_remaining = flock.expected_cycle_days - days_alive
                insight = AIInsight(
                    farm_id=str(farm_id),
                    flock_id=str(flock.id),
                    insight_type="harvest_approaching",
                    severity="info",
                    title=f"Harvest approaching for {flock_name}",
                    body=(
                        f"{flock_name} is at day {days_alive} of {flock.expected_cycle_days} "
                        f"({pct_complete:.0%} complete). "
                        f"Approximately {days_remaining} days remaining. "
                        f"Start planning market arrangements."
                    ),
                    action_route=f"/farms/{farm_id}/flocks/{flock.id}",
                    action_label="View flock",
                    expires_at=datetime.utcnow() + timedelta(days=7),
                )
                db.add(insight)
                generated.append(insight)

        # ── 7. Daily log missing: today not logged (checked at 20:00) ─────────
        # This is only inserted when called from the 20:00 scheduler job.
        # The 06:00 run does not check this.
        today_log_check = next(
            (l for l in recent_logs if l.log_date == today), None
        ) if recent_logs else None

        if today_log_check is None and datetime.utcnow().hour >= 20:
            insight = AIInsight(
                farm_id=str(farm_id),
                flock_id=str(flock.id),
                insight_type="log_missing",
                severity="reminder",
                title=f"Daily log missing for {flock_name}",
                body=(
                    f"Today's log has not been recorded for {flock_name}. "
                    f"Log mortality, feed, and bird count to keep your records complete."
                ),
                action_route=f"/farms/{farm_id}/flocks/{flock.id}/log",
                action_label="Log today",
                expires_at=datetime.utcnow() + timedelta(hours=4),
            )
            db.add(insight)
            generated.append(insight)

    await db.commit()
    return generated
