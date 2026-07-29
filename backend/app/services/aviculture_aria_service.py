"""
Greena — Aviculture ARIA Service (Module 15, Part 10)

Extends the EXISTING Greena ARIA / AI architecture to the aviculture domain — it
does not replace it. It reuses ``ai_provider.complete`` (the deterministic-first
LLM call with a mandatory offline fallback) and ``ai_settings_service`` (offline
mode, usage), and preserves the frozen ARIA guarantees:

  * AR-01 — the LLM only ever sees a bounded JSON context this service compiles;
    it never touches the database. "Never invents data" stays enforceable.
  * Doc 07 §12 / master-context §4.4 — ARIA NEVER diagnoses disease. Diagnosis
    questions are refused deterministically with a veterinary referral.
  * Doc 07 §15 — every answer is honesty-labelled (recorded fact / calculated /
    ai suggestion / unavailable), carries its evidence, and states confidence.
  * ARIA explains; it never calculates. All figures come from the Part 3-9
    deterministic engines (via the reporting dashboard) — ARIA only reads them.

Deterministic-first: factual questions about the collection are answered from the
recorded facts with NO LLM call; only open explanation/education is routed to the
provider, always with the deterministic answer as the offline fallback.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.aviculture import AviSpecies
from app.services import (
    ai_provider, ai_settings_service, aviculture_reporting_service,
    aviculture_automation_service,
)

# Honesty labels (shared vocabulary with the engines).
RECORDED = "recorded_fact"
CALCULATED = "calculated"
AI_SUGGESTION = "ai_suggestion"
UNAVAILABLE = "unavailable"

_MAX_WORDS = 150  # AR-04 response cap, preserved.

# Disease-diagnosis intent — refused deterministically (frozen §4.4).
_DIAGNOSIS_TERMS = (
    "diagnose", "diagnosis", "what disease", "what's wrong with", "whats wrong with",
    "what is wrong with", "what illness", "what sickness", "why is my bird sick",
    "what does my bird have", "is it sick with", "cure for", "what should i treat",
)
_DIAGNOSIS_REFUSAL = (
    "I can't diagnose disease — that needs a licensed avian veterinarian. I can help "
    "you record the symptoms you observe, explain preventive care and biosecurity, and "
    "surface the bird's recorded health history. Please consult a vet for any diagnosis "
    "or treatment decision."
)


def _clamp_words(text: str) -> str:
    words = text.split()
    return text if len(words) <= _MAX_WORDS else " ".join(words[:_MAX_WORDS]) + "…"


def _is_diagnosis(q: str) -> bool:
    n = q.lower()
    return any(t in n for t in _DIAGNOSIS_TERMS)


# ── Bounded context (AR-01) ───────────────────────────────────────────────────

async def compile_context(db: AsyncSession, farm: Farm) -> dict:
    """A compact, bounded snapshot of the collection — the only data the LLM sees
    (AR-01). Composes the Part 3-9 deterministic engines via the reporting
    dashboard; every figure keeps the honesty label its engine assigned."""
    dash = await aviculture_reporting_service.dashboard(db, farm)
    due = await aviculture_automation_service.preview(db, farm)
    coll = dash["collection"]
    fin = dash["finance"]
    return {
        "farm": farm.name,
        "birds_total": coll["total"]["value"],
        "by_species": coll["by_species"],
        "by_status": coll["by_status"],
        "active_pairs": dash["breeding"]["active_pairs"],
        "active_breeding_programs": dash["breeding"]["active_programs"],
        "active_incubation_batches": dash["incubation"]["active_batches"],
        "hatch_rate_pct": dash["incubation"]["statistics"]["hatch_rate_pct"],
        "mortality_rate_pct": dash["health"]["mortality_rate_pct"],
        "vaccination_coverage_pct": dash["health"]["vaccination_coverage_pct"],
        "active_quarantines": dash["health"]["active_quarantines"],
        "active_disease_events": dash["health"]["active_disease_events"],
        "collection_value": fin.get("collection_value"),
        "sale_income": fin["sale_income"],
        "operational_expenses": fin["operational_expenses"],
        "tasks_due": len(due),
    }


# ── Species knowledge (Doc 16) ────────────────────────────────────────────────

async def species_knowledge(db: AsyncSession, farm: Farm, species_id) -> dict:
    sp = (await db.execute(select(AviSpecies).where(
        AviSpecies.id == species_id, AviSpecies.deleted_at.is_(None)))).scalar_one_or_none()
    if sp is None:
        raise NotFoundException("Species not found.")
    profile = sp.profile or {}
    return {
        "species": sp.common_name,
        "scientific_name": sp.scientific_name,
        "group": sp.species_group,
        "conservation_status": sp.conservation_status,
        # Recorded husbandry knowledge from the data-driven catalog (Doc 16 §4).
        "profile": profile,
        "label": RECORDED if profile else UNAVAILABLE,
        "detail": ("Recorded species profile from the catalog." if profile
                   else "No husbandry profile recorded for this species yet."),
        "disclaimer": "Established best practice — not a substitute for species-specific "
                      "expertise or veterinary advice.",
    }


# ── Deterministic-first Q&A ───────────────────────────────────────────────────

# Factual patterns answerable directly from recorded facts (no LLM).
def _factual_answer(q: str, ctx: dict) -> tuple[str, str, list[str]] | None:
    n = q.lower()

    def val(labelled):
        return labelled.get("value") if isinstance(labelled, dict) else labelled

    if re.search(r"how many .*bird|bird count|total birds|size of .*collection", n):
        return f"You have {ctx['birds_total']} bird(s) recorded across {len(ctx['by_species'])} species.", RECORDED, ["collection.total"]
    if re.search(r"how many .*pair|breeding pair", n):
        return f"There are {ctx['active_pairs']} active breeding pair(s).", RECORDED, ["breeding.active_pairs"]
    if re.search(r"incubat|hatch(ing)? batch|eggs? incubat", n):
        hr = val(ctx["hatch_rate_pct"])
        hr_txt = f" Recorded hatch rate is {hr}%." if hr is not None else " Not enough recorded data for a hatch rate yet."
        return f"There are {ctx['active_incubation_batches']} active incubation batch(es).{hr_txt}", CALCULATED, ["incubation"]
    if re.search(r"collection value|worth|valuation", n):
        cv = val(ctx.get("collection_value"))
        return (f"The recorded collection value is KES {cv}." if cv is not None
                else "No collection valuation has been recorded yet."), (RECORDED if cv is not None else UNAVAILABLE), ["finance.collection_value"]
    if re.search(r"mortality|death rate", n):
        mr = val(ctx["mortality_rate_pct"])
        return (f"The recorded mortality rate is {mr}%." if mr is not None
                else "Not enough recorded data to compute a mortality rate."), (CALCULATED if mr is not None else UNAVAILABLE), ["health.mortality_rate_pct"]
    if re.search(r"vaccinat", n):
        vc = val(ctx["vaccination_coverage_pct"])
        return (f"Vaccination coverage is {vc}% of active birds." if vc is not None
                else "Not enough recorded data to compute vaccination coverage."), (CALCULATED if vc is not None else UNAVAILABLE), ["health.vaccination_coverage_pct"]
    if re.search(r"task|due|reminder|to.?do", n):
        return f"There are {ctx['tasks_due']} operational task(s) due within the horizon.", CALCULATED, ["automation.tasks_due"]
    if re.search(r"quarantine|disease|outbreak", n):
        return (f"{ctx['active_quarantines']} bird(s) in active quarantine and "
                f"{ctx['active_disease_events']} active disease event(s) recorded."), RECORDED, ["health"]
    return None


def _summary_offline(ctx: dict) -> str:
    return (f"Your collection has {ctx['birds_total']} bird(s) across {len(ctx['by_species'])} species, "
            f"{ctx['active_pairs']} active pair(s) and {ctx['active_incubation_batches']} incubation batch(es). "
            f"{ctx['tasks_due']} task(s) are due. Ask me about breeding, incubation, health, species care, "
            f"or your figures — I explain from your recorded data and never guess.")


def _build_prompt(question: str, ctx: dict, species: dict | None) -> str:
    import json
    parts = [
        "You are ARIA, an assistant for an aviculture (ornamental & specialty bird) collection.",
        "Rules: Explain clearly; NEVER invent data; use ONLY the FACTS provided and say so if a fact "
        "is missing. NEVER diagnose disease — recommend a licensed avian vet. Do not guarantee breeding, "
        "hatch or health outcomes. Keep the answer under 150 words.",
        f"FACTS (recorded/computed from the farm's data):\n{json.dumps(ctx, default=str)}",
    ]
    if species:
        parts.append(f"SPECIES KNOWLEDGE:\n{json.dumps(species.get('profile', {}), default=str)}")
    parts.append(f"QUESTION: {question}")
    return "\n\n".join(parts)


async def ask(db: AsyncSession, farm: Farm, user: User, question: str) -> dict:
    """Answer an aviculture question, deterministic-first and honesty-labelled."""
    settings = await ai_settings_service.get_or_create(db, farm.id)
    ai_on = ai_settings_service.effective_ai_enabled(settings)

    # 1. Frozen diagnosis ban (§4.4).
    if _is_diagnosis(question):
        return {"provider": "deterministic", "engine": "deterministic", "fact_type": AI_SUGGESTION,
                "answer": _DIAGNOSIS_REFUSAL, "sources": [], "safety": ["no_diagnosis"],
                "confidence": "high", "ai_enabled": ai_on}

    ctx = await compile_context(db, farm)

    # 2. Deterministic factual answer — no LLM needed.
    fact = _factual_answer(question, ctx)
    if fact is not None:
        answer, ftype, sources = fact
        return {"provider": "deterministic", "engine": "deterministic", "fact_type": ftype,
                "answer": answer, "sources": sources, "safety": [], "confidence": "high", "ai_enabled": ai_on}

    # 3. Open explanation / education — grounded LLM with deterministic fallback.
    offline = _summary_offline(ctx)
    if not ai_on:
        return {"provider": "offline", "engine": "deterministic", "fact_type": UNAVAILABLE,
                "answer": offline, "sources": ["collection"], "safety": [],
                "confidence": "medium", "ai_enabled": False}

    prompt = _build_prompt(question, ctx, None)
    result = await ai_provider.complete(prompt, offline_answer=offline)
    # Only real provider calls are billable/logged (the usage-log provider enum is
    # gemini|claude); the offline fallback is free and not recorded.
    if result.provider in ("gemini", "claude"):
        await ai_settings_service.record_usage(
            db, farm_id=farm.id, user_id=user.id, provider=result.provider, model=settings.model,
            prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            cost_usd=result.cost_usd, call_type="aviculture_ask")
    return {"provider": result.provider, "engine": "ai_router",
            "fact_type": AI_SUGGESTION if result.provider != "offline" else UNAVAILABLE,
            "answer": _clamp_words(result.text), "sources": ["collection"], "safety": [],
            "confidence": "medium", "ai_enabled": True}
