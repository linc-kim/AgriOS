"""
Greena — Swine ARIA Service (Module 20, Milestone 10)

ARIA for pig management. It **explains, summarises, recommends and answers** — it is
never the source of truth and never modifies a record or plan (frozen PD-07/08, and
rule 6: no writes). Reuses the platform AI router (``ai_provider``, offline-grounded)
and ``ai_settings_service``; no parallel AI, no swine-specific AI perms. This module
is a thin ADAPTER — swine context + prompts — over the shared ARIA architecture, so
the same framework serves every livestock module (rule 8).

Deterministic-first (frozen AR-01/AR-04): factual questions are answered directly
from the Milestone-9 analytics with **no LLM**; only open explanation routes to the
provider, always with a grounded offline fallback. The LLM sees only a bounded
context snapshot — never the database (AR-01). Every answer cites ``sources`` and
carries an honesty ``fact_type``; missing data is reported as unavailable, never
invented (rule 4). ARIA never diagnoses disease (frozen §4.4, rule 5) — health
answers are patterns that recommend veterinary consultation.
"""

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.services import ai_provider, ai_settings_service
from app.services import swine_intelligence, swine_reporting_service

RECORDED = "recorded"
CALCULATED = "calculated"
AI_SUGGESTION = "ai_suggestion"
UNAVAILABLE = "unavailable"


def _v(x):
    return x.get("value") if isinstance(x, dict) else x


async def compile_context(db: AsyncSession, farm: Farm) -> dict:
    """A compact, bounded snapshot composing the deterministic engines via the farm
    dashboard (AR-01). Every figure keeps the honesty label its engine assigned;
    nothing is recomputed here — ARIA only interprets (rule 1)."""
    dash = await swine_reporting_service.farm_dashboard(db, farm.id)
    repro = dash["reproduction"]
    farrowing = dash["farrowing"]
    health = dash["health"]
    pnl = dash["finance"]["pnl"]
    econ = dash["finance"]["unit_economics"]
    feed = dash["feed"]
    growth = dash["growth"].get("herd", {})
    housing = dash["housing"]
    return {
        "farm": farm.name,
        "active_pigs": _v(dash["population"]),
        "total_services": _v(repro.get("total_services")),
        "conception_rate_pct": _v(repro.get("conception_rate_pct")),
        "total_farrowings": _v(farrowing.get("total_farrowings")),
        "avg_litter_size": _v(farrowing.get("avg_litter_size")),
        "pre_wean_survival_pct": _v(farrowing.get("pre_wean_survival_pct")),
        "mortality_rate_pct": _v(health.get("mortality_rate_pct")),
        "open_disease_cases": _v(health.get("open_disease_cases")),
        "active_withdrawals": _v(health.get("active_withdrawals")),
        "vaccinations": _v(health.get("vaccinations")),
        "total_feed_kg": _v(feed.get("total_feed_kg")),
        "avg_daily_gain_kg": _v(growth.get("avg_daily_gain_kg")),
        "revenue": _v(pnl.get("revenue")),
        "gross_margin": _v(pnl.get("gross_margin")),
        "gross_margin_pct": _v(pnl.get("gross_margin_pct")),
        "cost_per_pig": _v(econ.get("cost_per_pig")),
        "cost_per_kg_sold": _v(econ.get("cost_per_kg_sold")),
        "overcrowded_pens": len(housing.get("overcrowded_pens", []) or []),
    }


def _factual_answer(q: str, ctx: dict):
    """Return (answer, fact_type, sources) for a factual question, else None. No LLM
    is used for any of these — deterministic engines answer first (rule 2)."""
    n = q.lower()
    if re.search(r"how many|herd size|population|total pig|number of pig", n):
        return (f"You have {ctx['active_pigs']} active pigs recorded.", RECORDED, ["reports.population"])
    if re.search(r"feed|consum|ration", n):
        return (f"Recorded feed consumption totals {ctx['total_feed_kg']} kg.", RECORDED, ["reports.feed"])
    if re.search(r"adg|daily gain|growth rate", n):
        adg = ctx["avg_daily_gain_kg"]
        return ((f"Herd average daily gain is {adg} kg/day." if adg is not None
                 else "No weight history yet to compute average daily gain."),
                CALCULATED if adg is not None else UNAVAILABLE, ["reports.growth.herd"])
    if re.search(r"cost per pig", n):
        cp = ctx["cost_per_pig"]
        return ((f"Calculated cost per pig is {cp}." if cp is not None
                 else "Not enough recorded cost data to compute cost per pig."),
                CALCULATED if cp is not None else UNAVAILABLE, ["reports.finance.unit_economics.cost_per_pig"])
    if re.search(r"cost per (kg|kilo)", n):
        ck = ctx["cost_per_kg_sold"]
        return ((f"Calculated cost per kg sold is {ck}." if ck is not None
                 else "No sold weight recorded yet to compute cost per kg."),
                CALCULATED if ck is not None else UNAVAILABLE, ["reports.finance.unit_economics.cost_per_kg_sold"])
    if re.search(r"profit|margin|roi", n):
        gm, gmp = ctx["gross_margin"], ctx["gross_margin_pct"]
        if gm is None:
            return ("No recorded revenue/cost yet to compute margin.", UNAVAILABLE, ["reports.finance.pnl"])
        return (f"Calculated gross margin is {gm}" + (f" ({gmp}%)." if gmp is not None else "."),
                CALCULATED, ["reports.finance.pnl.gross_margin"])
    if re.search(r"revenue|income|sales", n):
        return (f"Recorded sale revenue totals {ctx['revenue']}.", RECORDED, ["reports.finance.pnl.revenue"])
    if re.search(r"pregnan|conception|in.?pig|served", n):
        cr = ctx["conception_rate_pct"]
        return (f"Recorded services: {ctx['total_services']}."
                + (f" Conception rate {cr}%." if cr is not None else " Conception rate not computable yet."),
                CALCULATED, ["reports.reproduction"])
    if re.search(r"litter|farrow|born|piglet", n):
        ls = ctx["avg_litter_size"]
        return (f"Recorded farrowings: {ctx['total_farrowings']}."
                + (f" Average litter size {ls}." if ls is not None else ""),
                CALCULATED, ["reports.farrowing"])
    if re.search(r"vaccinat|vaccine", n):
        return (f"Recorded vaccinations: {ctx['vaccinations']}.", RECORDED, ["reports.health.vaccinations"])
    if re.search(r"withdrawal|withhold|market ready|sell now", n):
        wd = ctx["active_withdrawals"]
        return ((f"{wd} treatment(s) are within a meat withdrawal period — those pigs must not go to market yet."
                 if wd else "No active meat-withdrawal periods are recorded."),
                RECORDED, ["reports.health.active_withdrawals"])
    if re.search(r"mortality|death|survival", n):
        mr = ctx["mortality_rate_pct"]
        if mr is None:
            return ("Not enough recorded data for a mortality rate.", UNAVAILABLE, ["reports.health"])
        return (f"Recorded mortality rate is {mr}%. A pattern, not a diagnosis — consult your vet for causes.",
                CALCULATED, ["reports.health.mortality_rate_pct"])
    if re.search(r"disease|sick|ill|health", n):
        oc = ctx["open_disease_cases"]
        return (f"{oc} open disease case(s) recorded. I summarise records and recommend a vet — I do not diagnose.",
                RECORDED, ["reports.health.open_disease_cases"])
    if re.search(r"overcrowd|housing|capacity|pen", n):
        oc = ctx["overcrowded_pens"]
        return ((f"{oc} pen(s) are over recorded capacity." if oc else "No pens are over capacity."),
                CALCULATED, ["reports.housing"])
    return None


def _summary_offline(ctx: dict) -> str:
    return (f"You have {ctx['active_pigs']} active pigs, {ctx['total_farrowings']} recorded farrowings and "
            f"revenue of {ctx['revenue']}. I explain from your recorded data and the deterministic engines — "
            f"I never guess, I never diagnose, and I never change your records for you.")


def _build_prompt(question: str, ctx: dict) -> str:
    return "\n\n".join([
        "You are ARIA, an assistant for a pig (swine) farming operation.",
        "Rules: Explain clearly; use ONLY the FACTS provided and say so when a fact is missing; NEVER invent "
        "data or numbers; NEVER diagnose disease or prescribe medication (recommend a veterinarian instead); "
        "never guarantee production, biological or financial outcomes; you may recommend actions but you must "
        "NOT claim to change any record. Under 150 words.",
        f"FACTS (recorded/computed by the deterministic engines):\n{json.dumps(ctx, default=str)}",
        f"QUESTION: {question}",
    ])


async def ask(db: AsyncSession, farm: Farm, user: User, question: str) -> dict:
    """Answer a swine question, deterministic-first and honesty-labelled."""
    settings = await ai_settings_service.get_or_create(db, farm.id)
    ai_on = ai_settings_service.effective_ai_enabled(settings)
    ctx = await compile_context(db, farm)

    fact = _factual_answer(question, ctx)
    if fact is not None:
        answer, ftype, sources = fact
        return {"provider": "deterministic", "engine": "deterministic", "fact_type": ftype,
                "answer": answer, "sources": sources, "confidence": "high", "ai_enabled": ai_on}

    offline = _summary_offline(ctx)
    if not ai_on:
        return {"provider": "offline", "engine": "deterministic", "fact_type": UNAVAILABLE,
                "answer": offline, "sources": ["reports.farm"], "confidence": "medium", "ai_enabled": False}

    result = await ai_provider.complete(_build_prompt(question, ctx), offline_answer=offline)
    if result.provider in ("gemini", "claude"):
        await ai_settings_service.record_usage(
            db, farm_id=farm.id, user_id=user.id, provider=result.provider, model=settings.model,
            prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd, call_type="swine_ask")
    return {"provider": result.provider, "engine": "ai_router",
            "fact_type": AI_SUGGESTION if result.provider != "offline" else UNAVAILABLE,
            "answer": result.text, "sources": ["reports.farm"],
            "confidence": "medium" if result.provider != "offline" else "low", "ai_enabled": True}


async def recommendations(db: AsyncSession, farm: Farm) -> dict:
    """Explainable, deterministic recommendations (rule 7): each carries the
    recommendation, reason, supporting evidence and a confidence level. Derived from
    the pure intelligence engine over the farm dashboard — ARIA never acts on them."""
    dashboard = await swine_reporting_service.farm_dashboard(db, farm.id)
    briefing = swine_intelligence.build_briefing(dashboard=dashboard)
    return {
        "headline": briefing.headline,
        "recommendations": [
            {"recommendation": i.title, "category": i.category, "severity": i.severity,
             "reason": i.detail, "confidence": i.confidence, "limitations": i.limitations,
             "supporting_data": [{"source": e.source, "value": e.value, "fact_type": e.fact_type}
                                 for e in i.evidence]}
            for i in briefing.insights
        ],
        "priorities": briefing.priorities,
        "note": "ARIA explains and recommends from recorded data; operational changes remain your explicit "
                "workflows — it never edits records or diagnoses disease.",
    }
