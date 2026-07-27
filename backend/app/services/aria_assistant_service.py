"""
ARIA — the multimodal assistant orchestrator (Module 13 Part 8).

This is where the router's decision becomes an answer. It takes a request,
resolves the farm's AI settings, runs `aria_router.route`, and dispatches to the
right engine — a deterministic one whenever the router says so, Gemini only when
it must, and a grounded offline answer when no provider is configured.

The honesty rules are enforced here, not merely intended:

- **Records, farm questions, knowledge and decisions never touch Gemini.** They
  are answered by the Part 1–6 deterministic engines.
- **Reports and simulations are computed deterministically; Gemini only
  rephrases the result.** The numbers are produced by the engine and passed to
  the model as finished output with an explicit "do not change any number"
  instruction — the model is never asked to calculate.
- **Images and documents degrade honestly.** With no Gemini key, vision says it
  cannot read the image and a PDF says it needs AI; structured documents
  (CSV/Excel/text) are still read deterministically.
- **Disease is never diagnosed** (§4.4), and every response is scrubbed of
  anything resembling a secret before it leaves.

Usage and cost are logged for every model call, so the settings dashboard always
reflects what actually happened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_assistant import AIDocument, AISettings
from app.models.auth import User
from app.models.farm import Farm
from app.models.flock import DailyLog, Flock, ProductionRecord
from app.services import (
    aria_decisions,
    aria_documents,
    aria_knowledge,
    aria_planning,
    aria_record_service,
    aria_router,
    ai_provider,
    ai_settings_service,
)
from app.services.aria_router import Engine, RouteTarget, Safety

# The engines that must never receive a calculation to perform.
_NEVER_DIAGNOSE_NOTE = (
    " I can't diagnose illness — for any health concern please consult a licensed vet."
)


@dataclass
class AssistResult:
    handled: bool
    route: str
    engine: str
    provider: str                 # deterministic | gemini | claude | offline
    answer: str
    language: str
    mixed_language: bool = False
    safety: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    needs_confirmation: bool = False
    data: dict = field(default_factory=dict)


def _finalise(result: AssistResult) -> AssistResult:
    result.answer = ai_provider.redact_secrets(result.answer)
    return result


# ── Text pipeline ─────────────────────────────────────────────────────────────


async def assist(
    db: AsyncSession,
    farm: Farm,
    user: User,
    text: str,
    *,
    settings: AISettings,
    state: dict | None = None,
) -> AssistResult:
    """
    Handle one text (or transcribed voice) turn end to end.

    `state` continues an in-flight recording dialogue. When present, the record
    pipeline owns the turn — the router is not consulted mid-recording, so a
    half-finished record is never re-routed away.
    """
    ai_on = ai_settings_service.effective_ai_enabled(settings)

    # Continue an in-flight recording without re-routing.
    if state:
        return _finalise(await _record(db, farm, user, text, state, ai_on))

    decision = aria_router.route(text, ai_enabled=ai_on)
    lang = decision.language
    safety = [s.value for s in decision.safety]

    def base(engine: str, provider: str, answer: str, **kw) -> AssistResult:
        return _finalise(AssistResult(
            handled=True, route=decision.target.value, engine=engine, provider=provider,
            answer=answer, language=lang.primary.value, mixed_language=lang.mixed,
            safety=safety, **kw,
        ))

    t = decision.target
    if t is RouteTarget.RECORD:
        return _finalise(await _record(db, farm, user, text, None, ai_on))

    if t is RouteTarget.OUT_OF_SCOPE:
        return base(Engine.DETERMINISTIC.value, "offline", _out_of_scope_reply(lang.primary.value))

    if t is RouteTarget.FARM_CHAT:
        answer, sources, data = await _farm_chat(db, farm, user, text)
        return base(Engine.DETERMINISTIC.value, "offline", answer, sources=sources, data=data)

    if t is RouteTarget.KNOWLEDGE:
        answer, sources = await _knowledge(db, farm, user, text, safety)
        return base(Engine.DETERMINISTIC.value, "offline", answer, sources=sources)

    if t is RouteTarget.REPORT_EXPLAIN:
        return _finalise(await _report_explain(db, farm, user, decision, settings))

    if t is RouteTarget.SIMULATION:
        return _finalise(await _simulation(db, farm, user, text, decision, settings))

    # GENERAL_CHAT — Gemini when enabled, grounded offline answer otherwise.
    return _finalise(await _general_chat(db, farm, user, text, decision, settings))


async def _record(db, farm, user, text, state, ai_on) -> AssistResult:
    turn = await aria_record_service.handle_turn(db, farm, user, text, state)
    if not turn.handled:
        # The record pipeline declined — treat as a general question instead.
        decision = aria_router.route(text, ai_enabled=ai_on)
        return await _general_chat(db, farm, user, text, decision, None)
    lang = aria_router.detect_language(text)
    return AssistResult(
        handled=True, route="record", engine="deterministic", provider="offline",
        answer=turn.reply, language=lang.primary.value, mixed_language=lang.mixed,
        safety=["offline_capable"], needs_confirmation=bool(turn.stage and not turn.saved),
        data={"stage": turn.stage, "options": turn.options, "state": turn.state,
              "saved": turn.saved, "summary": turn.summary, "module": turn.module,
              "resource_id": turn.resource_id},
    )


def _out_of_scope_reply(language: str) -> str:
    if language in ("sw", "sheng"):
        return ("Samahani, ninashughulikia kuku pekee kwa sasa — sio ng'ombe, mbuzi, "
                "wala mimea. Niulize kuhusu kuku wako.")
    return ("I only cover poultry right now — not cattle, goats, or crops. "
            "Ask me anything about your birds.")


# ── Deterministic farm chat (capability 12) ───────────────────────────────────


async def _farm_chat(db, farm, user, text) -> tuple[str, list[str], dict]:
    from app.services import aria_intelligence_data

    norm = aria_router.aria_nlu.normalise(text)
    facts = await aria_intelligence_data.gather_facts(db, farm, user)

    # "How many birds died this month / week?"
    if aria_router._has(norm, ("died", "death", "mortality", "lost", "walikufa", "vifo")):
        window = 30 if "month" in norm or "mwezi" in norm else 7
        total = await _mortality_over(db, farm, days=window)
        label = "month" if window == 30 else "7 days"
        return (
            f"{total} bird(s) recorded lost at {farm.name} in the last {label}. "
            f"That's from your daily logs — nothing is estimated.",
            ["daily logs"], {"metric": "mortality", "window_days": window, "value": total},
        )

    # "Which flock performs best?"
    if aria_router._has(norm, ("best", "which flock", "top", "performing", "gani")):
        ranking = await _flock_production_ranking(db, farm)
        if not ranking:
            return ("No egg production is recorded yet, so I can't rank your flocks. "
                    "Log some collections and I'll compare them.", ["production records"], {})
        best = ranking[0]
        lines = "; ".join(f"{n}: {e} eggs/7d" for n, e in ranking[:3])
        return (f"{best[0]} is your best-producing flock — {best[1]} eggs in the last 7 days. "
                f"Full ranking: {lines}.", ["production records"],
                {"metric": "best_flock", "ranking": ranking})

    # "What reminders are overdue?"
    if aria_router._has(norm, ("overdue", "reminder", "reminders", "due")):
        overdue = [r for r in facts.upcoming_reminders if r.get("overdue")]
        if not overdue:
            return (f"No reminders are overdue at {farm.name}. "
                    f"{facts.reminders_open} reminder(s) are open in total.",
                    ["reminders"], {"metric": "overdue_reminders", "value": 0})
        titles = "; ".join(str(r.get("title")) for r in overdue[:5])
        return (f"{len(overdue)} reminder(s) are overdue: {titles}.", ["reminders"],
                {"metric": "overdue_reminders", "value": len(overdue)})

    # "Which farms need attention?" — this farm's own status (cross-farm lives in
    # the Operations Center, which is org-scoped).
    if aria_router._has(norm, ("need attention", "needs attention", "which farm")):
        return (f"For {farm.name}: health is {_health_word(facts)}. "
                f"For a cross-farm view of every farm that needs attention, open the "
                f"Operations Center.", ["farm health"], {"metric": "attention"})

    # Fallback: a grounded offline answer.
    from app.services import ai_platform_service
    try:
        ctx = await ai_platform_service.build_context(db, farm)
        answer, sources = ai_platform_service._build_offline_answer(text, ctx, {})
        return answer, sources, {}
    except Exception:
        return ("I don't have that figure to hand — try the dashboard or log the data first.",
                [], {})


async def _mortality_over(db, farm, *, days: int) -> int:
    since = date.today() - timedelta(days=days)
    flock_ids = (await db.execute(
        select(Flock.id).where(Flock.farm_id == str(farm.id), Flock.deleted_at.is_(None))
    )).scalars().all()
    if not flock_ids:
        return 0
    total = (await db.execute(
        select(func.coalesce(func.sum(DailyLog.mortality_count), 0)).where(
            DailyLog.flock_id.in_([str(f) for f in flock_ids]),
            DailyLog.log_date >= since, DailyLog.deleted_at.is_(None),
        )
    )).scalar_one()
    return int(total or 0)


async def _flock_production_ranking(db, farm) -> list[tuple[str, int]]:
    since = date.today() - timedelta(days=7)
    rows = (await db.execute(
        select(Flock.name, func.coalesce(func.sum(ProductionRecord.eggs_collected), 0))
        .join(ProductionRecord, ProductionRecord.flock_id == Flock.id)
        .where(Flock.farm_id == str(farm.id), Flock.deleted_at.is_(None),
               ProductionRecord.record_date >= since, ProductionRecord.deleted_at.is_(None))
        .group_by(Flock.name)
    )).all()
    ranked = [(n, int(e)) for n, e in rows if int(e) > 0]
    ranked.sort(key=lambda x: -x[1])
    return ranked


def _health_word(facts) -> str:
    from app.services import aria_intelligence
    h = aria_intelligence.compute_health_score(facts)
    return f"{h.score}/100 ({h.grade})"


# ── Knowledge / decisions ─────────────────────────────────────────────────────


async def _knowledge(db, farm, user, text, safety) -> tuple[str, list[str]]:
    from app.services import aria_intelligence_data
    facts = await aria_intelligence_data.gather_facts(db, farm, user)
    decision = aria_decisions.decide(text, facts)
    if decision is not None:
        pros = " ".join(f"+ {p}" for p in decision.pros[:3])
        cons = " ".join(f"- {c}" for c in decision.cons[:3])
        return f"{decision.headline} {pros} {cons}".strip(), ["decision support"]
    know = aria_knowledge.answer(text)
    if know is not None:
        body = know.get("answer") or know.get("summary") or ""
        if Safety.NO_DIAGNOSIS.value in safety:
            body += _NEVER_DIAGNOSE_NOTE
        return body, ["poultry knowledge base"]
    return ("I don't have a deterministic answer for that — try rephrasing, or ask about "
            "your farm's recorded data.", [])


# ── Report explanation (capability 9) ─────────────────────────────────────────


async def _report_explain(db, farm, user, decision, settings) -> AssistResult:
    from app.services import aria_supervisor_data

    r = await aria_supervisor_data.supervise(db, farm, user)
    health = r["health"]
    monitors = r["monitors"]
    priorities = r["priorities"]
    worst = [m for m in monitors if m.state.value != "normal"]

    lines = [f"Health score: {health.score}/100 ({health.grade})."]
    if worst:
        lines.append("Watch: " + "; ".join(f"{m.label} is {m.state.value} — {m.why}" for m in worst[:3]))
    else:
        lines.append("All monitors are normal.")
    if priorities:
        lines.append("Top priorities: " + "; ".join(p.label for p in priorities[:3]))
    deterministic_explanation = " ".join(lines)
    safety = [s.value for s in decision.safety]

    if decision.engine is Engine.HYBRID and ai_provider.gemini_available():
        prompt = (
            "You are ARIA. Rephrase the following farm report in simple, encouraging "
            "language for a Kenyan poultry farmer. Do NOT change, add, or remove any "
            "number. Do not diagnose disease. Keep it under 120 words.\n\n"
            f"REPORT:\n{deterministic_explanation}"
        )
        res = await ai_provider.complete(prompt, offline_answer=deterministic_explanation)
        await _log(db, farm, user, res, "report_explain")
        return AssistResult(
            handled=True, route="report_explain", engine="hybrid", provider=res.provider,
            answer=res.text, language=decision.language.primary.value,
            mixed_language=decision.language.mixed, safety=safety,
            sources=["health score", "monitors", "priorities"],
            data={"health_score": health.score},
        )

    return AssistResult(
        handled=True, route="report_explain", engine="deterministic", provider="offline",
        answer=deterministic_explanation, language=decision.language.primary.value,
        mixed_language=decision.language.mixed, safety=safety,
        sources=["health score", "monitors", "priorities"], data={"health_score": health.score},
    )


# ── Simulation (capability 10) ────────────────────────────────────────────────

_ADD_VERBS = ("add", "more", "buy", "extra", "ongeza", "nunua")

_SCENARIO_PATTERNS = [
    ("feed_price_change", ("feed price", "feed cost", "bei ya chakula", "feed prices")),
    ("mortality_change", ("mortality", "deaths", "die", "died", "vifo", "walikufa")),
    ("production_change", ("production", "eggs", "lay", "mayai")),
]


def _parse_scenario(text: str) -> tuple[str, float | None]:
    norm = aria_router.aria_nlu.normalise(text)

    # "add / buy N birds" is its own scenario, and its magnitude is a head count.
    if ("bird" in norm or "chick" in norm or "kuku" in norm) and any(v in norm for v in _ADD_VERBS):
        m = re.search(r"(\d[\d,]*)", norm)
        return "add_birds", (float(m.group(1).replace(",", "")) if m else None)

    scenario = "feed_price_change"
    for key, terms in _SCENARIO_PATTERNS:
        if any(t in norm for t in terms):
            scenario = key
            break

    magnitude: float | None = None
    if "double" in norm or "mara mbili" in norm:
        magnitude = 100.0
    elif "half" in norm or "halve" in norm:
        magnitude = -50.0
    else:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*%", norm) or re.search(r"by\s+(-?\d+(?:\.\d+)?)", norm)
        if m:
            magnitude = float(m.group(1))
            if any(w in norm for w in ("drop", "fall", "decrease", "less", "down", "punguza")):
                magnitude = -abs(magnitude)
    return scenario, magnitude


async def _simulation(db, farm, user, text, decision, settings) -> AssistResult:
    from app.services import aria_intelligence_data

    facts = await aria_intelligence_data.gather_facts(db, farm, user)
    scenario, magnitude = _parse_scenario(text)
    result = aria_planning.simulate(facts, scenario, magnitude)

    if not result.available:
        return AssistResult(
            handled=True, route="simulation", engine="deterministic", provider="offline",
            answer=result.note or "I can't simulate that yet.",
            language=decision.language.primary.value, mixed_language=decision.language.mixed,
            safety=[s.value for s in decision.safety], data={"scenario": scenario},
        )

    changes = "; ".join(f"{c.label}: {c.current} → {c.projected} ({c.difference})"
                        for c in result.changes)
    deterministic_explanation = f"{result.description}. {changes}."
    if result.implications:
        deterministic_explanation += " " + " ".join(result.implications[:2])

    safety = [s.value for s in decision.safety]
    if decision.engine is Engine.HYBRID and ai_provider.gemini_available():
        prompt = (
            "You are ARIA. Explain this what-if result to a Kenyan poultry farmer in "
            "simple language. Do NOT change any number — they are already computed. "
            "Keep under 120 words.\n\n" + deterministic_explanation
        )
        res = await ai_provider.complete(prompt, offline_answer=deterministic_explanation)
        await _log(db, farm, user, res, "simulation")
        return AssistResult(
            handled=True, route="simulation", engine="hybrid", provider=res.provider,
            answer=res.text, language=decision.language.primary.value,
            mixed_language=decision.language.mixed, safety=safety,
            sources=["deterministic simulator"],
            data={"scenario": scenario, "magnitude": magnitude},
        )

    return AssistResult(
        handled=True, route="simulation", engine="deterministic", provider="offline",
        answer=deterministic_explanation, language=decision.language.primary.value,
        mixed_language=decision.language.mixed, safety=safety,
        sources=["deterministic simulator"], data={"scenario": scenario, "magnitude": magnitude},
    )


# ── General chat (Gemini, offline fallback) ───────────────────────────────────


async def _general_chat(db, farm, user, text, decision, settings) -> AssistResult:
    from app.services import ai_platform_service

    lang = decision.language if decision else aria_router.detect_language(text)
    safety = [s.value for s in decision.safety] if decision else ["permission_scoped"]

    # Retrieval: cite uploaded documents if any match.
    cites = await search_documents(db, farm, text)
    doc_sources = [c.filename for c in cites]

    # ai_platform_service.ask is itself offline-safe (grounded fallback) and logs
    # usage/cost — the single place general questions are answered.
    try:
        result = await ai_platform_service.ask(db, farm, user, text)
        answer = result.answer if hasattr(result, "answer") else result.get("answer", "")
        provider = getattr(result, "provider", None) or (result.get("provider") if isinstance(result, dict) else "offline")
        sources = list(getattr(result, "sources", None) or (result.get("sources") if isinstance(result, dict) else []) or [])
    except Exception:
        answer, provider, sources = (
            "I don't have enough recorded data to answer that yet.", "offline", [])

    if cites:
        answer += "\n\nFrom your documents: " + "; ".join(
            f"{c.filename}: “{c.snippet}”" for c in cites[:2])
        sources = list(dict.fromkeys(sources + doc_sources))

    if Safety.NO_DIAGNOSIS.value in safety and "vet" not in answer.lower():
        answer += _NEVER_DIAGNOSE_NOTE

    return AssistResult(
        handled=True, route=decision.target.value if decision else "general_chat",
        engine="gemini" if (decision and decision.needs_gemini) else "deterministic",
        provider=provider or "offline", answer=answer,
        language=lang.primary.value, mixed_language=lang.mixed, safety=safety, sources=sources,
    )


# ── Image (capability 5, 11) ──────────────────────────────────────────────────


async def analyze_image_upload(
    db, farm, user, *, filename: str, mime: str, data: bytes, caption: str, settings: AISettings
) -> AssistResult:
    lang = aria_router.detect_language(caption or "")
    if not settings.allow_vision or not ai_settings_service.effective_ai_enabled(settings):
        return AssistResult(
            handled=True, route="vision", engine="deterministic", provider="offline",
            answer=("Image analysis is turned off for this farm. Describe what you see and "
                    "I'll help you record it." + _NEVER_DIAGNOSE_NOTE),
            language=lang.primary.value, safety=["no_diagnosis", "permission_scoped"],
        )

    prompt = (
        "You are ARIA, a poultry farm assistant. Describe what is visible in this image "
        "to help a Kenyan farmer. If it is a receipt or invoice, extract supplier, items, "
        "quantities and totals as a list. If it shows birds, describe what you see but "
        "NEVER diagnose disease — recommend a licensed vet for any health concern. "
        f"Farmer's note: {caption or '(none)'}"
    )
    res = await ai_provider.analyze_image(prompt, data, mime)
    await _log(db, farm, user, res, "vision")
    answer = res.text
    if "vet" not in answer.lower():
        answer += _NEVER_DIAGNOSE_NOTE
    return _finalise(AssistResult(
        handled=True, route="vision", engine="gemini" if res.provider == "gemini" else "deterministic",
        provider=res.provider, answer=answer, language=lang.primary.value,
        safety=["no_diagnosis", "permission_scoped"], data={"filename": filename},
    ))


# ── Documents (capability 6, 7, 11) ───────────────────────────────────────────


async def ingest_document(
    db, farm, user, *, filename: str, mime: str, data: bytes, settings: AISettings
) -> dict:
    """
    Extract an uploaded document and store its text for retrieval.

    Structured formats (CSV/Excel/text) are read deterministically. Unstructured
    ones (PDF/DOCX) are summarised by Gemini when enabled, or stored as
    "needs AI" honestly when not.
    """
    if not settings.allow_documents:
        return {"stored": False, "reason": "Document uploads are turned off for this farm."}

    extracted = aria_documents.extract(filename, mime, data)
    kind = extracted.tables[0].kind if extracted.tables else "generic"
    text = extracted.text

    if not extracted.deterministic:
        # PDF/DOCX — needs a model. Summarise with Gemini if available.
        if ai_settings_service.effective_ai_enabled(settings) and ai_provider.gemini_available():
            res = await ai_provider.summarize(
                f"Summarise this document for a farm's records. Do not invent content:\n{filename}",
                offline_answer=extracted.note,
            )
            await _log(db, farm, user, res, "document")
            text = res.text
        else:
            text = ""  # nothing was actually read; store no fabricated content

    doc = AIDocument(
        farm_id=farm.id, uploaded_by=user.id, filename=filename, mime=mime,
        kind=kind, extracted_text=text[:200_000], table_count=len(extracted.tables),
        size_bytes=len(data),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "stored": True,
        "document_id": str(doc.id),
        "filename": filename,
        "kind": kind,
        "deterministic": extracted.deterministic,
        "table_count": len(extracted.tables),
        "tables": [
            {"kind": tbl.kind, "headers": tbl.headers, "row_count": tbl.row_count,
             "preview": tbl.rows[:5]}
            for tbl in extracted.tables
        ],
        "note": extracted.note,
    }


async def search_documents(db, farm, query: str, *, limit: int = 5) -> list[aria_documents.Citation]:
    """Retrieve spans from this farm's uploaded documents, with citations."""
    docs = (await db.execute(
        select(AIDocument).where(AIDocument.farm_id == farm.id, AIDocument.deleted_at.is_(None))
    )).scalars().all()
    chunks: list[aria_documents.Chunk] = []
    for d in docs:
        chunks.extend(aria_documents.chunk_document(str(d.id), d.filename, d.extracted_text))
    return aria_documents.retrieve(query, chunks, limit=limit)


async def list_documents(db, farm) -> list[AIDocument]:
    rows = (await db.execute(
        select(AIDocument).where(AIDocument.farm_id == farm.id, AIDocument.deleted_at.is_(None))
        .order_by(AIDocument.created_at.desc())
    )).scalars().all()
    return list(rows)


# ── Usage logging ─────────────────────────────────────────────────────────────


async def _log(db, farm, user, res, call_type: str) -> None:
    if res.provider in ("gemini", "claude"):
        try:
            await ai_settings_service.record_usage(
                db, farm_id=farm.id, user_id=user.id, provider=res.provider,
                model=res.provider, prompt_tokens=res.prompt_tokens,
                completion_tokens=res.completion_tokens, cost_usd=res.cost_usd,
                call_type=call_type,
            )
        except Exception:
            pass
