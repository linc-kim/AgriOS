"""
Greena — BSF ARIA Service (Module 16, Part 8)

ARIA for Black Soldier Fly production. It **explains, summarises, recommends and
answers** — it is never the source of truth and it never modifies a plan
(Spec Part 6 §10-11, ARIA/Mission Control Contract). Reuses the platform AI router
(`ai_provider`, offline-grounded) and `ai_settings_service`; no parallel AI system.

Deterministic-first: factual questions are answered directly from recorded
facts / deterministic engine outputs with **no LLM**; only open explanation routes
to the provider, always with a grounded offline fallback. The LLM sees only a
bounded context snapshot — never the database. Every answer cites its ``sources``
and carries an honesty ``fact_type``; uncertainty is surfaced, never hidden.
"""

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.services import ai_provider, ai_settings_service
from app.services import bsf_reporting_service, growth_planner_service

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
AI_SUGGESTION = "ai_suggestion"
UNAVAILABLE = "unavailable"

_MAX_WORDS = 150


def _v(x):
    return x.get("value") if isinstance(x, dict) else x


# ── Bounded context (the only data the LLM sees) ──────────────────────────────

async def compile_context(db: AsyncSession, farm: Farm) -> dict:
    """A compact, bounded snapshot composing the BSF deterministic engines via the
    executive dashboard + the Growth Planner's recorded progress. Every figure
    keeps the honesty label its engine assigned; nothing is recomputed here."""
    dash = await bsf_reporting_service.executive_dashboard(db, farm.id)
    facts = dash["recorded_facts"]
    prod = dash["analytics"]["production"]
    fin = dash["analytics"]["finance"]
    health = dash["analytics"]["health"]
    growth_pct = await growth_planner_service.primary_overall_progress(db, farm.id, "bsf")
    return {
        "farm": farm.name,
        "active_batches": _v(facts["active_batches"]),
        "total_batches": _v(facts["total_batches"]),
        "total_harvest_kg": _v(facts["total_harvest_kg"]),
        "total_revenue": _v(facts["total_revenue"]),
        "total_feed_kg": _v(facts["total_feed_kg"]),
        "feedstock_available_kg": _v(facts["feedstock_available_kg"]),
        "survival_rate_pct": _v(prod.get("survival_rate_pct")),
        "feed_conversion_ratio": _v(prod.get("feed_conversion_ratio")),
        "mortality_rate_pct": _v(health.get("mortality_rate_pct")),
        "gross_profit": _v(fin.get("gross_profit")),
        "gross_margin_pct": _v(fin.get("gross_margin_pct")),
        "harvest_forecast_kg": _v((dash["forecast"].get("harvest_kg") or {}).get("forecast")),
        "top_bottleneck": (dash.get("top_bottleneck") or {}).get("constraint"),
        "growth_progress_pct": growth_pct,
        "business_health_score": _v(dash["scores"]["business_health"]),
    }


# ── Deterministic-first Q&A ───────────────────────────────────────────────────

def _factual_answer(q: str, ctx: dict):
    """Return (answer, fact_type, sources) for a factual question, else None."""
    n = q.lower()

    if re.search(r"how many .*batch|batch count|active batch", n):
        return (f"You have {ctx['active_batches']} active batch(es) of {ctx['total_batches']} total.",
                RECORDED, ["reports.recorded_facts.active_batches"])
    if re.search(r"harvest|produced|production .*kg|total .*kg", n):
        return (f"Recorded total harvest is {ctx['total_harvest_kg']} kg.",
                RECORDED, ["reports.recorded_facts.total_harvest_kg"])
    if re.search(r"revenue|income|sales", n):
        return (f"Recorded harvest revenue totals {ctx['total_revenue']}.",
                RECORDED, ["reports.recorded_facts.total_revenue"])
    if re.search(r"profit|margin", n):
        gp, gm = ctx["gross_profit"], ctx["gross_margin_pct"]
        if gp is None:
            return ("No recorded revenue/cost yet to compute profit.", UNAVAILABLE, ["reports.analytics.finance"])
        return (f"Calculated gross profit is {gp}" + (f" ({gm}% margin)." if gm is not None else "."),
                CALCULATED, ["reports.analytics.finance.gross_profit"])
    if re.search(r"fcr|feed conversion|conversion ratio", n):
        fcr = ctx["feed_conversion_ratio"]
        return ((f"Calculated feed conversion ratio is {fcr} (feed ÷ harvested biomass)." if fcr is not None
                 else "Not enough recorded feeding/harvest data for an FCR yet."),
                CALCULATED if fcr is not None else UNAVAILABLE, ["reports.analytics.production.feed_conversion_ratio"])
    if re.search(r"mortality|survival|death", n):
        mr, sr = ctx["mortality_rate_pct"], ctx["survival_rate_pct"]
        if mr is None and sr is None:
            return ("Not enough recorded data for mortality/survival.", UNAVAILABLE, ["reports.analytics"])
        return (f"Recorded survival is {sr}%; cumulative mortality {mr}%. This is a pattern, not a diagnosis.",
                CALCULATED, ["reports.analytics.production.survival_rate_pct", "reports.analytics.health"])
    if re.search(r"feedstock|feed .*left|feed .*available|substrate", n):
        return (f"There is {ctx['feedstock_available_kg']} kg of feedstock on hand.",
                RECORDED, ["reports.recorded_facts.feedstock_available_kg"])
    if re.search(r"bottleneck|constraint|limiting|what.?s slowing", n):
        tb = ctx["top_bottleneck"]
        return ((f"The top deterministic bottleneck is '{tb}'." if tb
                 else "No significant bottleneck is currently flagged."),
                CALCULATED, ["reports.bottlenecks"])
    if re.search(r"forecast|projection|project|expect.*harvest|next month", n):
        fc = ctx["harvest_forecast_kg"]
        return ((f"Projected harvest is ~{fc} kg over the horizon — a forecast, not a guarantee." if fc is not None
                 else "Not enough recorded history to project harvest yet."),
                FORECAST if fc is not None else UNAVAILABLE, ["reports.forecast.harvest_kg"])
    if re.search(r"growth|goal|progress|on track|roadmap", n):
        gp = ctx["growth_progress_pct"]
        return ((f"Recorded progress toward your primary growth goal is {gp}%." if gp is not None
                 else "No active growth plan with a recorded actual yet. I can suggest one — you decide."),
                CALCULATED if gp is not None else UNAVAILABLE, ["growth.overall_percent"])
    return None


def _summary_offline(ctx: dict) -> str:
    return (f"You have {ctx['active_batches']} active batch(es), {ctx['total_harvest_kg']} kg harvested and "
            f"{ctx['feedstock_available_kg']} kg feedstock on hand. I explain from your recorded data and "
            f"the deterministic engines — I never guess, and I never change your plans for you.")


def _build_prompt(question: str, ctx: dict) -> str:
    return "\n\n".join([
        "You are ARIA, an assistant for a Black Soldier Fly (insect farming) operation.",
        "Rules: Explain clearly; use ONLY the FACTS provided and say so when a fact is missing; NEVER invent "
        "data or numbers; do not diagnose disease; never guarantee production, biological or financial "
        "outcomes; you may recommend actions but you must NOT claim to change any plan. Under 150 words.",
        f"FACTS (recorded/computed by the deterministic engines):\n{json.dumps(ctx, default=str)}",
        f"QUESTION: {question}",
    ])


async def ask(db: AsyncSession, farm: Farm, user: User, question: str) -> dict:
    """Answer a BSF question, deterministic-first and honesty-labelled."""
    settings = await ai_settings_service.get_or_create(db, farm.id)
    ai_on = ai_settings_service.effective_ai_enabled(settings)

    ctx = await compile_context(db, farm)

    # 1. Deterministic factual answer — no LLM.
    fact = _factual_answer(question, ctx)
    if fact is not None:
        answer, ftype, sources = fact
        return {"provider": "deterministic", "engine": "deterministic", "fact_type": ftype,
                "answer": answer, "sources": sources, "confidence": "high", "ai_enabled": ai_on}

    # 2. Open explanation — grounded LLM with deterministic fallback.
    offline = _summary_offline(ctx)
    if not ai_on:
        return {"provider": "offline", "engine": "deterministic", "fact_type": UNAVAILABLE,
                "answer": offline, "sources": ["reports.dashboard"], "confidence": "medium", "ai_enabled": False}

    result = await ai_provider.complete(_build_prompt(question, ctx), offline_answer=offline)
    if result.provider in ("gemini", "claude"):
        await ai_settings_service.record_usage(
            db, farm_id=farm.id, user_id=user.id, provider=result.provider, model=settings.model,
            prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd, call_type="bsf_ask")
    return {"provider": result.provider, "engine": "ai_router",
            "fact_type": AI_SUGGESTION if result.provider != "offline" else UNAVAILABLE,
            "answer": result.text, "sources": ["reports.dashboard"],
            "confidence": "medium" if result.provider != "offline" else "low", "ai_enabled": True}
