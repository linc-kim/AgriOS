"""
Greena — Small Ruminant ARIA Service (Modules 18/19, Milestone 10)

ARIA for goat and sheep management. It **explains, summarises, recommends and
answers** — it is never the source of truth and never modifies a plan or record
(frozen PD-07/08). Reuses the platform AI router (`ai_provider`, offline-grounded)
and `ai_settings_service`; no parallel AI, no species-specific AI perms.

Deterministic-first (frozen AR-01/AR-04): factual questions are answered directly
from recorded facts / deterministic engine outputs with **no LLM**; only open
explanation routes to the provider, always with a grounded offline fallback. The
LLM sees only a bounded context snapshot — never the database. Every answer cites
``sources`` and carries an honesty ``fact_type``. ARIA never diagnoses disease
(frozen §4.4) — health answers are patterns with a disclaimer.
"""

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.farm import Farm
from app.services import ai_provider, ai_settings_service
from app.services import growth_planner_service, small_ruminant_reporting_service
from app.services import small_ruminant_species_config as cfg

RECORDED = "recorded"
CALCULATED = "calculated"
FORECAST = "forecast"
AI_SUGGESTION = "ai_suggestion"
UNAVAILABLE = "unavailable"


def _v(x):
    return x.get("value") if isinstance(x, dict) else x


async def compile_context(db: AsyncSession, farm: Farm, species: str) -> dict:
    """A compact, bounded snapshot composing the deterministic engines via the
    executive dashboard + the Growth Planner's recorded progress (AR-01). Every
    figure keeps the honesty label its engine assigned; nothing is recomputed."""
    dash = await small_ruminant_reporting_service.executive_dashboard(db, farm.id, species)
    pop = dash["population"]
    repro = dash["reproduction"]
    health = dash["health"]
    pnl = dash["finance"]["pnl"]
    housing = dash["housing"]
    forecast = dash["forecast"]
    bottlenecks = dash["bottlenecks"]
    cfgd = cfg.get_config(species)
    growth_pct = await growth_planner_service.primary_overall_progress(db, farm.id, species)

    ctx = {
        "farm": farm.name,
        "species": species,
        "collective_noun": cfgd["collective_noun"],
        "total_animals": _v(pop["total_ever"]),
        "active_animals": _v(pop["active"]),
        "total_births": _v(repro.get("total_births")),
        "birth_rate_pct": _v(repro.get("birth_rate_pct")),
        "avg_litter_size": _v(repro.get("avg_litter_size")),
        "offspring_survival_pct": _v(repro.get("offspring_survival_pct")),
        "mortality_rate_pct": _v(health.get("mortality_rate_pct")),
        "revenue": _v(pnl.get("revenue")),
        "gross_margin": _v(pnl.get("gross_margin")),
        "gross_margin_pct": _v(pnl.get("gross_margin_pct")),
        "overcrowded_locations": len(housing.get("overcrowded_pens", []))
        + len(housing.get("overcrowded_pastures", [])),
        "projected_head": _v((forecast.get("projected_head") or {})),
        "top_bottleneck": (bottlenecks[0]["area"] if bottlenecks else None),
        "growth_progress_pct": growth_pct,
    }
    if cfg.produces_milk(species):
        ctx["milk_total_recorded_l"] = _v((dash.get("dairy", {}) or {}).get("total_recorded_yield_l"))
    if cfg.produces_wool(species):
        ctx["wool_total_greasy_kg"] = _v((dash.get("wool", {}) or {}).get("total_greasy_kg"))
    return ctx


def _factual_answer(q: str, ctx: dict, species: str):
    """Return (answer, fact_type, sources) for a factual question, else None."""
    n = q.lower()
    noun = ctx["collective_noun"]

    if re.search(r"how many|herd size|flock size|population|total", n):
        return (f"You have {ctx['active_animals']} active {species}s "
                f"(of {ctx['total_animals']} ever recorded in the {noun}).",
                RECORDED, ["reports.population"])
    if re.search(r"birth|kidding|lambing|offspring|litter", n):
        br, ls = ctx["birth_rate_pct"], ctx["avg_litter_size"]
        return (f"Recorded births: {ctx['total_births']}."
                + (f" Birth rate {br}%." if br is not None else "")
                + (f" Average litter size {ls}." if ls is not None else ""),
                CALCULATED, ["reports.reproduction"])
    if re.search(r"revenue|income|sales", n):
        return (f"Recorded sale revenue totals {ctx['revenue']}.", RECORDED, ["reports.finance.pnl.revenue"])
    if re.search(r"profit|margin", n):
        gm, gmp = ctx["gross_margin"], ctx["gross_margin_pct"]
        if gm is None:
            return ("No recorded revenue/cost yet to compute margin.", UNAVAILABLE, ["reports.finance.pnl"])
        return (f"Calculated gross margin is {gm}" + (f" ({gmp}%)." if gmp is not None else "."),
                CALCULATED, ["reports.finance.pnl.gross_margin"])
    if re.search(r"mortality|survival|death", n):
        mr, ss = ctx["mortality_rate_pct"], ctx["offspring_survival_pct"]
        if mr is None and ss is None:
            return ("Not enough recorded data for mortality/survival.", UNAVAILABLE, ["reports.health"])
        return (f"Recorded mortality rate {mr}%; offspring survival {ss}%. A pattern, not a diagnosis.",
                CALCULATED, ["reports.health.mortality_rate_pct"])
    if re.search(r"milk|lactation|dairy", n) and cfg.produces_milk(species):
        return (f"Total recorded milk is {ctx.get('milk_total_recorded_l')} litres.",
                RECORDED, ["reports.dairy.total_recorded_yield_l"])
    if re.search(r"wool|fleece|shear", n) and cfg.produces_wool(species):
        return (f"Total recorded greasy wool is {ctx.get('wool_total_greasy_kg')} kg.",
                RECORDED, ["reports.wool.total_greasy_kg"])
    if re.search(r"overcrowd|housing|capacity|pen|pasture", n):
        oc = ctx["overcrowded_locations"]
        return ((f"{oc} location(s) are over recorded capacity." if oc else "No locations are over capacity."),
                CALCULATED, ["reports.housing"])
    if re.search(r"bottleneck|constraint|limiting|problem", n):
        tb = ctx["top_bottleneck"]
        return ((f"The top deterministic bottleneck is '{tb}'." if tb
                 else "No significant bottleneck is currently flagged."),
                CALCULATED, ["reports.bottlenecks"])
    if re.search(r"forecast|project|expect|next month", n):
        ph = ctx["projected_head"]
        return ((f"Projected head is ~{ph} — a forecast, not a guarantee." if ph is not None
                 else "Not enough recorded history to project yet."),
                FORECAST if ph is not None else UNAVAILABLE, ["reports.forecast.projected_head"])
    if re.search(r"growth|goal|progress|on track|roadmap|target", n):
        gp = ctx["growth_progress_pct"]
        return ((f"Recorded progress toward your primary growth goal is {gp}%." if gp is not None
                 else "No active growth plan with a recorded actual yet. I can suggest one — you decide."),
                CALCULATED if gp is not None else UNAVAILABLE, ["growth.overall_percent"])
    return None


def _summary_offline(ctx: dict, species: str) -> str:
    return (f"You have {ctx['active_animals']} active {species}s, {ctx['total_births']} recorded births and "
            f"revenue of {ctx['revenue']}. I explain from your recorded data and the deterministic engines — "
            f"I never guess, and I never change your plans for you.")


def _build_prompt(question: str, ctx: dict, species: str) -> str:
    return "\n\n".join([
        f"You are ARIA, an assistant for a {species} farming operation.",
        "Rules: Explain clearly; use ONLY the FACTS provided and say so when a fact is missing; NEVER invent "
        "data or numbers; do not diagnose disease; never guarantee production, biological or financial "
        "outcomes; you may recommend actions but you must NOT claim to change any plan or record. Under 150 words.",
        f"FACTS (recorded/computed by the deterministic engines):\n{json.dumps(ctx, default=str)}",
        f"QUESTION: {question}",
    ])


async def ask(db: AsyncSession, farm: Farm, species: str, user: User, question: str) -> dict:
    """Answer a goat/sheep question, deterministic-first and honesty-labelled."""
    settings = await ai_settings_service.get_or_create(db, farm.id)
    ai_on = ai_settings_service.effective_ai_enabled(settings)
    ctx = await compile_context(db, farm, species)

    fact = _factual_answer(question, ctx, species)
    if fact is not None:
        answer, ftype, sources = fact
        return {"provider": "deterministic", "engine": "deterministic", "fact_type": ftype,
                "answer": answer, "sources": sources, "confidence": "high", "ai_enabled": ai_on}

    offline = _summary_offline(ctx, species)
    if not ai_on:
        return {"provider": "offline", "engine": "deterministic", "fact_type": UNAVAILABLE,
                "answer": offline, "sources": ["reports.dashboard"], "confidence": "medium", "ai_enabled": False}

    result = await ai_provider.complete(_build_prompt(question, ctx, species), offline_answer=offline)
    if result.provider in ("gemini", "claude"):
        await ai_settings_service.record_usage(
            db, farm_id=farm.id, user_id=user.id, provider=result.provider, model=settings.model,
            prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd, call_type=f"{species}_ask")
    return {"provider": result.provider, "engine": "ai_router",
            "fact_type": AI_SUGGESTION if result.provider != "offline" else UNAVAILABLE,
            "answer": result.text, "sources": ["reports.dashboard"],
            "confidence": "medium" if result.provider != "offline" else "low", "ai_enabled": True}
