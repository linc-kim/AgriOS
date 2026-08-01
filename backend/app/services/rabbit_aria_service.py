"""
Greena — Rabbit ARIA Service (Module 17, Milestone 9)

ARIA for rabbit management. It **explains, summarises, recommends and answers** —
it is never the source of truth and it never modifies a plan or record (Spec
Part 6 §4-8; frozen PD-07/08). Reuses the platform AI router (`ai_provider`,
offline-grounded) and `ai_settings_service`; no parallel AI system.

Deterministic-first (frozen AR-01/AR-04): factual questions are answered directly
from recorded facts / deterministic engine outputs with **no LLM**; only open
explanation routes to the provider, always with a grounded offline fallback. The
LLM sees only a bounded context snapshot — never the database. Every answer cites
its ``sources`` and carries an honesty ``fact_type``. ARIA never diagnoses disease
(frozen §4.4) — health answers are patterns with a disclaimer.
"""

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.services import ai_provider, ai_settings_service
from app.services import growth_planner_service, rabbit_reporting_service

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
AI_SUGGESTION = "ai_suggestion"
UNAVAILABLE = "unavailable"


def _v(x):
    return x.get("value") if isinstance(x, dict) else x


# ── Bounded context (the only data the LLM sees — AR-01) ──────────────────────

async def compile_context(db: AsyncSession, farm: Farm) -> dict:
    """A compact, bounded snapshot composing the rabbit deterministic engines via
    the executive dashboard + the Growth Planner's recorded progress. Every figure
    keeps the honesty label its engine assigned; nothing is recomputed here."""
    dash = await rabbit_reporting_service.executive_dashboard(db, farm.id)
    pop = dash["recorded_facts"]["population"]
    repro = dash["reproduction"]
    health = dash["health"]
    pnl = dash["finance"]["pnl"]
    housing = dash["housing"]
    forecast = dash["forecast"]
    bottlenecks = dash["bottlenecks"]
    growth_pct = await growth_planner_service.primary_overall_progress(db, farm.id, "rabbit")
    return {
        "farm": farm.name,
        "total_rabbits": _v(pop["total_rabbits"]),
        "bucks": _v(pop["bucks"]),
        "does": _v(pop["does"]),
        "kits": _v(pop["kits"]),
        "total_litters": _v(repro.get("total_litters")),
        "kindling_rate_pct": _v(repro.get("kindling_rate_pct")),
        "avg_litter_size": _v(repro.get("avg_litter_size")),
        "kit_survival_pct": _v(repro.get("kit_survival_pct")),
        "mortality_rate_pct": _v(health.get("mortality_rate_pct")),
        "revenue": _v(pnl.get("revenue")),
        "gross_profit": _v(pnl.get("gross_profit")),
        "gross_margin_pct": _v(pnl.get("gross_margin_pct")),
        "overcrowded_cages": len(housing.get("overcrowded_cages", [])),
        "herd_forecast_30d": _v((forecast.get("herd_size") or {}).get("forecast")),
        "revenue_forecast": _v((forecast.get("revenue") or {}).get("forecast")),
        "top_bottleneck": (bottlenecks[0]["constraint"] if bottlenecks else None),
        "growth_progress_pct": growth_pct,
    }


# ── Deterministic-first Q&A ───────────────────────────────────────────────────

def _factual_answer(q: str, ctx: dict):
    """Return (answer, fact_type, sources) for a factual question, else None."""
    n = q.lower()

    if re.search(r"how many .*rabbit|herd size|total rabbit|population", n):
        return (f"You have {ctx['total_rabbits']} active rabbits "
                f"({ctx['bucks']} bucks, {ctx['does']} does, {ctx['kits']} kits).",
                RECORDED, ["reports.recorded_facts.population"])
    if re.search(r"how many .*doe|number of doe|breeding doe", n):
        return (f"You have {ctx['does']} active does.", RECORDED, ["reports.recorded_facts.population.does"])
    if re.search(r"how many .*buck", n):
        return (f"You have {ctx['bucks']} active bucks.", RECORDED, ["reports.recorded_facts.population.bucks"])
    if re.search(r"litter|kits born|kindling", n):
        lr, ls = ctx["kindling_rate_pct"], ctx["avg_litter_size"]
        return (f"Recorded litters: {ctx['total_litters']}."
                + (f" Kindling rate {lr}%." if lr is not None else "")
                + (f" Average litter size {ls}." if ls is not None else ""),
                CALCULATED, ["reports.reproduction"])
    if re.search(r"revenue|income|sales", n):
        return (f"Recorded sale revenue totals {ctx['revenue']}.",
                RECORDED, ["reports.finance.pnl.revenue"])
    if re.search(r"profit|margin", n):
        gp, gm = ctx["gross_profit"], ctx["gross_margin_pct"]
        if gp is None:
            return ("No recorded revenue/cost yet to compute profit.", UNAVAILABLE, ["reports.finance.pnl"])
        return (f"Calculated gross profit is {gp}" + (f" ({gm}% margin)." if gm is not None else "."),
                CALCULATED, ["reports.finance.pnl.gross_profit"])
    if re.search(r"mortality|survival|death|deaths", n):
        mr, ks = ctx["mortality_rate_pct"], ctx["kit_survival_pct"]
        if mr is None and ks is None:
            return ("Not enough recorded data for mortality/survival.", UNAVAILABLE, ["reports.health"])
        return (f"Recorded mortality rate {mr}%; kit survival {ks}%. This is a pattern, not a diagnosis.",
                CALCULATED, ["reports.health.mortality_rate_pct", "reports.reproduction.kit_survival_pct"])
    if re.search(r"overcrowd|housing|cage.*full|capacity", n):
        oc = ctx["overcrowded_cages"]
        return ((f"{oc} cage(s) are over recorded capacity." if oc else "No cages are over capacity."),
                CALCULATED, ["reports.housing.overcrowded_cages"])
    if re.search(r"bottleneck|constraint|limiting|what.?s slowing|problem", n):
        tb = ctx["top_bottleneck"]
        return ((f"The top deterministic bottleneck is '{tb}'." if tb
                 else "No significant bottleneck is currently flagged."),
                CALCULATED, ["reports.bottlenecks"])
    if re.search(r"forecast|projection|project|expect|next month", n):
        hf, rf = ctx["herd_forecast_30d"], ctx["revenue_forecast"]
        if hf is None and rf is None:
            return ("Not enough recorded history to project yet.", UNAVAILABLE, ["reports.forecast"])
        return (f"Projected herd ~{hf} rabbits and revenue ~{rf} over the horizon — forecasts, not guarantees.",
                FORECAST, ["reports.forecast.herd_size", "reports.forecast.revenue"])
    if re.search(r"growth|goal|progress|on track|roadmap|target", n):
        gp = ctx["growth_progress_pct"]
        return ((f"Recorded progress toward your primary growth goal is {gp}%." if gp is not None
                 else "No active growth plan with a recorded actual yet. I can suggest one — you decide."),
                CALCULATED if gp is not None else UNAVAILABLE, ["growth.overall_percent"])
    return None


def _summary_offline(ctx: dict) -> str:
    return (f"You have {ctx['total_rabbits']} active rabbits ({ctx['does']} does, {ctx['bucks']} bucks), "
            f"{ctx['total_litters']} recorded litters and revenue of {ctx['revenue']}. I explain from your "
            f"recorded data and the deterministic engines — I never guess, and I never change your plans for you.")


def _build_prompt(question: str, ctx: dict) -> str:
    return "\n\n".join([
        "You are ARIA, an assistant for a rabbit farming operation.",
        "Rules: Explain clearly; use ONLY the FACTS provided and say so when a fact is missing; NEVER invent "
        "data or numbers; do not diagnose disease; never guarantee production, biological or financial "
        "outcomes; you may recommend actions but you must NOT claim to change any plan or record. Under 150 words.",
        f"FACTS (recorded/computed by the deterministic engines):\n{json.dumps(ctx, default=str)}",
        f"QUESTION: {question}",
    ])


async def ask(db: AsyncSession, farm: Farm, user: User, question: str) -> dict:
    """Answer a rabbit question, deterministic-first and honesty-labelled."""
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
            cost_usd=result.cost_usd, call_type="rabbit_ask")
    return {"provider": result.provider, "engine": "ai_router",
            "fact_type": AI_SUGGESTION if result.provider != "offline" else UNAVAILABLE,
            "answer": result.text, "sources": ["reports.dashboard"],
            "confidence": "medium" if result.provider != "offline" else "low", "ai_enabled": True}
