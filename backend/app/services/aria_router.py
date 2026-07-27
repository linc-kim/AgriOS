"""
ARIA — the AI router.

This is the piece Part 8 is built around, and the one rule it enforces above all
others: *deterministic systems answer whenever they can; Gemini is consulted only
when they cannot.* Every request — a typed question, a spoken sentence, an
uploaded image, a document — passes through here first, and the router decides
which engine handles it before a single token is sent anywhere.

It is pure by construction, like every ARIA engine before it. It takes the text,
the metadata of any attachments, and a small capability flag set, and returns a
`RouteDecision` — the target engine, whether Gemini is required, the detected
language, the safety rules that apply, and the reasoning. It performs no I/O and
calls no model. That is what makes the routing itself testable exhaustively, and
what lets the honesty rules be *checked* rather than hoped for:

- **Structured farm calculations never go to Gemini.** Records, aggregate farm
  questions, knowledge lookups and decisions route to deterministic engines. When
  a report or a simulation is explained, only the already-computed deterministic
  *output* is handed to Gemini as prose to rephrase — never the inputs to compute.
- **Disease is never diagnosed.** Any health-symptom language attaches a
  vet-referral safety rule and is kept away from a diagnostic path (§4.4).
- **Out-of-scope stays out.** "Ngombe sio module hii" — cattle, goats, crops are
  declined deterministically, not passed to a model to guess at.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.services import aria_nlu
from app.services.aria_language import LanguageResult, detect_language


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"


class RouteTarget(str, Enum):
    RECORD = "record"                     # deterministic NLU record pipeline
    FARM_CHAT = "farm_chat"               # deterministic aggregate Q&A
    KNOWLEDGE = "knowledge"               # deterministic knowledge base / decision
    REPORT_EXPLAIN = "report_explain"     # deterministic values + Gemini prose
    SIMULATION = "simulation"             # deterministic simulator + Gemini prose
    DOCUMENT_EXTRACT = "document_extract" # deterministic CSV/XLSX/TXT parse
    DOCUMENT_AI = "document_ai"           # PDF/DOCX → Gemini summary
    VISION = "vision"                     # image → Gemini Vision
    GENERAL_CHAT = "general_chat"         # freeform → Gemini (offline fallback)
    OUT_OF_SCOPE = "out_of_scope"         # not this domain — declined


class Engine(str, Enum):
    DETERMINISTIC = "deterministic"
    GEMINI = "gemini"
    HYBRID = "hybrid"                     # deterministic result, Gemini prose


#: Safety rules the router can attach to a decision.
class Safety(str, Enum):
    NO_DIAGNOSIS = "no_diagnosis"                 # §4.4 — vet referral, never diagnose
    NO_CALC_TO_GEMINI = "no_calculations_to_gemini"
    PERMISSION_SCOPED = "permission_scoped"
    OFFLINE_CAPABLE = "offline_capable"           # works with no AI provider


@dataclass
class Attachment:
    """Metadata only — the router never reads file contents."""

    filename: str
    mime: str
    size_bytes: int = 0

    @property
    def modality(self) -> Modality:
        m = (self.mime or "").lower()
        name = (self.filename or "").lower()
        if m.startswith("image/") or name.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
            return Modality.IMAGE
        if m.startswith("audio/") or name.endswith((".mp3", ".wav", ".m4a", ".ogg", ".webm")):
            return Modality.AUDIO
        return Modality.DOCUMENT

    @property
    def is_deterministic_document(self) -> bool:
        name = (self.filename or "").lower()
        m = (self.mime or "").lower()
        return (
            name.endswith((".csv", ".tsv", ".xlsx", ".xls", ".txt"))
            or "csv" in m or "spreadsheet" in m or "excel" in m or m == "text/plain"
        )


@dataclass
class RouteDecision:
    target: RouteTarget
    engine: Engine
    modality: Modality
    needs_gemini: bool
    language: LanguageResult
    reason: str
    safety: list[Safety] = field(default_factory=list)
    confidence: float = 1.0
    #: Populated for text records so the caller can skip re-parsing.
    intent: str | None = None

    @property
    def deterministic_first(self) -> bool:
        return self.engine in (Engine.DETERMINISTIC, Engine.HYBRID)


# ── Signal vocabularies ───────────────────────────────────────────────────────

#: Species that are not part of the poultry product. Declined deterministically.
_OUT_OF_SCOPE = (
    "ngombe", "ng'ombe", "cow", "cows", "cattle", "maziwa", "dairy",
    "mbuzi", "goat", "goats", "kondoo", "sheep", "nguruwe", "pig", "pigs",
    "samaki", "fish", "mahindi", "maize", "crop", "crops", "mimea",
)

#: Report-explanation requests. The report itself is computed deterministically;
#: only its prose is a job for Gemini.
_EXPLAIN = (
    "explain", "eleza", "nini maana", "what does this mean", "break down",
    "simplify", "rahisisha", "help me understand", "walk me through",
    "explain this report", "explain the report", "explain my",
)

#: What-if planning. Routed to the deterministic simulator; Gemini only narrates.
_SIMULATE = (
    "what if", "what happens if", "vipi kama", "ikiwa", "suppose", "scenario",
    "simulate", "would happen", "if feed", "if prices", "if i", "double",
)

#: Aggregate farm questions with deterministic answers (capability 12).
_FARM_CHAT = (
    "how many", "how much", "which flock", "which farm", "best performing",
    "worst", "overdue", "need attention", "needs attention", "this month",
    "this week", "total", "average", "wangapi", "ngapi", "ni gani",
    "died", "mortality", "production", "reminders", "compare",
)

#: Health-symptom language — attaches the no-diagnosis safety rule (§4.4).
_HEALTH_SYMPTOMS = (
    "sick", "cough", "coughing", "kukohoa", "sneez", "diarr", "droppings",
    "swollen", "limping", "paralys", "discharge", "not eating", "dying",
    "disease", "ugonjwa", "wameanza kukohoa", "wanakohoa", "symptom", "wugua",
    "mgonjwa", "wagonjwa",
)


def _has(text: str, terms: tuple[str, ...]) -> bool:
    return any(t in text for t in terms)


# ── The router ────────────────────────────────────────────────────────────────


def route(
    text: str,
    *,
    attachments: list[Attachment] | None = None,
    ai_enabled: bool = True,
) -> RouteDecision:
    """
    Decide how one request should be handled.

    Deterministic-first: attachments and text are checked against the
    deterministic paths before any Gemini path is considered, and `ai_enabled`
    (the org's "offline deterministic only" switch) forces every would-be Gemini
    route to its deterministic or offline counterpart.
    """
    attachments = attachments or []
    text = text or ""
    norm = aria_nlu.normalise(text)
    lang = detect_language(text)

    base_safety = [Safety.PERMISSION_SCOPED]
    if _has(norm, _HEALTH_SYMPTOMS):
        base_safety.append(Safety.NO_DIAGNOSIS)

    # ── Attachments take precedence — modality decides the path ────────────────
    if attachments:
        a = attachments[0]
        mod = a.modality
        if mod is Modality.IMAGE:
            # An uploaded bird/carcass photo invites diagnosis — always attach the
            # no-diagnosis rule, even when the caption carried no symptom words.
            img_safety = list(base_safety)
            if Safety.NO_DIAGNOSIS not in img_safety:
                img_safety.append(Safety.NO_DIAGNOSIS)
            return RouteDecision(
                target=RouteTarget.VISION, engine=Engine.GEMINI, modality=mod,
                needs_gemini=True, language=lang,
                reason="Image content can only be read by vision — Gemini Vision handles it.",
                safety=img_safety, confidence=0.9,
            )
        if mod is Modality.DOCUMENT:
            if a.is_deterministic_document:
                return RouteDecision(
                    target=RouteTarget.DOCUMENT_EXTRACT, engine=Engine.DETERMINISTIC,
                    modality=mod, needs_gemini=False, language=lang,
                    reason="Structured document (CSV/Excel/text) — extracted deterministically, no model needed.",
                    safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=0.95,
                )
            return RouteDecision(
                target=RouteTarget.DOCUMENT_AI, engine=Engine.GEMINI, modality=mod,
                needs_gemini=True, language=lang,
                reason="Unstructured document (PDF/DOCX) — Gemini summarises it; contents are never invented.",
                safety=base_safety, confidence=0.85,
            )
        if mod is Modality.AUDIO:
            # Audio is transcribed client-side (Web Speech) into `text`; a bare
            # audio blob with no transcript needs server transcription (Gemini).
            if norm.strip():
                pass  # fall through and route the transcript text below
            else:
                return RouteDecision(
                    target=RouteTarget.GENERAL_CHAT, engine=Engine.GEMINI, modality=mod,
                    needs_gemini=True, language=lang,
                    reason="Audio with no transcript needs speech-to-text — handled by the model.",
                    safety=base_safety, confidence=0.6,
                )

    # ── Out of scope — declined deterministically, never guessed at ────────────
    if _has(norm, _OUT_OF_SCOPE) and not _is_record(text):
        return RouteDecision(
            target=RouteTarget.OUT_OF_SCOPE, engine=Engine.DETERMINISTIC,
            modality=Modality.TEXT, needs_gemini=False, language=lang,
            reason="Outside the poultry domain — declined deterministically.",
            safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=0.8,
        )

    # ── Deterministic write: a record ──────────────────────────────────────────
    parsed = aria_nlu.parse(text)
    if parsed.is_actionable:
        return RouteDecision(
            target=RouteTarget.RECORD, engine=Engine.DETERMINISTIC, modality=Modality.TEXT,
            needs_gemini=False, language=lang,
            reason=f"Recognised a record ({parsed.intent.value}) — handled by the deterministic pipeline.",
            safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=parsed.confidence,
            intent=parsed.intent.value,
        )

    # ── Report explanation: deterministic values, Gemini prose ─────────────────
    if _has(norm, _EXPLAIN) and _mentions_analytic(norm):
        return RouteDecision(
            target=RouteTarget.REPORT_EXPLAIN,
            engine=Engine.HYBRID if ai_enabled else Engine.DETERMINISTIC,
            modality=Modality.TEXT, needs_gemini=ai_enabled, language=lang,
            reason="Report explanation — figures come from the deterministic engine; only the wording is Gemini's.",
            safety=base_safety + [Safety.NO_CALC_TO_GEMINI, Safety.OFFLINE_CAPABLE],
            confidence=0.8,
        )

    # ── Simulation: deterministic simulator, Gemini narrates ───────────────────
    if _has(norm, _SIMULATE):
        return RouteDecision(
            target=RouteTarget.SIMULATION,
            engine=Engine.HYBRID if ai_enabled else Engine.DETERMINISTIC,
            modality=Modality.TEXT, needs_gemini=ai_enabled, language=lang,
            reason="What-if — the deterministic simulator computes it; Gemini only explains the result.",
            safety=base_safety + [Safety.NO_CALC_TO_GEMINI, Safety.OFFLINE_CAPABLE],
            confidence=0.75,
        )

    # ── Aggregate farm question: deterministic Q&A ─────────────────────────────
    if _has(norm, _FARM_CHAT):
        return RouteDecision(
            target=RouteTarget.FARM_CHAT, engine=Engine.DETERMINISTIC, modality=Modality.TEXT,
            needs_gemini=False, language=lang,
            reason="Aggregate farm question — answered deterministically from records.",
            safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=0.8,
        )

    # ── Knowledge / decision: deterministic ────────────────────────────────────
    if _looks_like_knowledge(norm):
        return RouteDecision(
            target=RouteTarget.KNOWLEDGE, engine=Engine.DETERMINISTIC, modality=Modality.TEXT,
            needs_gemini=False, language=lang,
            reason="Husbandry knowledge or a decision — the local knowledge base answers it.",
            safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=0.65,
        )

    # ── Everything else: general chat (Gemini, offline fallback) ───────────────
    return RouteDecision(
        target=RouteTarget.GENERAL_CHAT,
        engine=Engine.GEMINI if ai_enabled else Engine.DETERMINISTIC,
        modality=Modality.TEXT, needs_gemini=ai_enabled, language=lang,
        reason=("Open question with no deterministic answer — Gemini assists, grounded in farm context."
                if ai_enabled else
                "Open question, AI disabled — answered from farm context offline."),
        safety=base_safety + [Safety.OFFLINE_CAPABLE], confidence=0.5,
    )


def _is_record(text: str) -> bool:
    return aria_nlu.parse(text).is_actionable


def _mentions_analytic(norm: str) -> bool:
    return _has(norm, (
        "report", "ripoti", "health", "afya", "production", "budget", "bajeti",
        "forecast", "utabiri", "alert", "score", "summary", "muhtasari", "operations",
    ))


_KNOWLEDGE_MARKERS = (
    "how do i", "how to", "how should", "when should", "what is", "what are",
    "why do", "why is", "should i", "is it", "vaccinate", "temperature", "brooding",
    "how many days", "at what age", "recommended", "best practice", "namna gani",
    "je ni", "ninafaa", "lini", "kwa nini",
)


def _looks_like_knowledge(norm: str) -> bool:
    return _has(norm, _KNOWLEDGE_MARKERS)
