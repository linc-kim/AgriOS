"""
Greena — AI Model Abstraction (Module 9).

A single entry point for LLM completion that degrades gracefully:

    Gemini (primary)  →  Claude (secondary)  →  offline deterministic fallback

The offline fallback is grounded: it answers from the structured farm context we
already build, so the assistant remains useful (and the product remains
demonstrable) even with no API keys or no connectivity. Every path returns the
same shape, so callers never branch on provider.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("greena.ai.provider")


@dataclass
class AIResult:
    text: str
    provider: str  # gemini | claude | offline
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    confidence: str = "medium"  # explainability: medium | offline | cached


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def complete(prompt: str, *, offline_answer: str) -> AIResult:
    """
    Complete a prompt through the AI Provider Manager (Gate 4).

    All provider selection, Gemini multi-key round-robin, failover and health
    tracking live in the manager now — this stays as the stable façade every
    caller already imports. ``offline_answer`` is a deterministic, context-
    grounded response the caller precomputes from farm data; the manager returns
    it verbatim when no provider is available or all providers fail.
    """
    from app.services.ai_provider_manager import get_manager

    completion = await get_manager().complete(prompt, offline_answer=offline_answer)
    return AIResult(
        completion.text,
        completion.provider,
        completion.prompt_tokens,
        completion.completion_tokens,
        completion.cost_usd,
        completion.confidence,
    )


def providers_available() -> dict:
    return {
        "gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "claude": bool(os.environ.get("CLAUDE_API_KEY", "").strip()),
        "offline_fallback": True,
    }


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


# ── Multimodal (Module 13 Part 8) ─────────────────────────────────────────────
#
# Vision and document understanding. Both degrade to a grounded offline message
# when no Gemini key is configured, so the assistant stays honest — it says it
# cannot read the image rather than inventing what is in it.

_VISION_OFFLINE = (
    "I can't analyse images right now — AI vision isn't enabled on this farm. "
    "You can still describe what you see and I'll help you record it, and for any "
    "sign of illness please consult a licensed vet."
)


async def analyze_image(
    prompt: str, image_bytes: bytes, mime: str, *, offline_answer: str | None = None
) -> AIResult:
    """
    Describe an uploaded image with Gemini Vision, or say so honestly offline.

    Medical safety is caller-enforced: the prompt handed in must already carry
    the never-diagnose instruction (§4.4). This function only transports it.
    """
    from app.services.ai_provider_manager import get_manager

    fallback = offline_answer or _VISION_OFFLINE
    completion = await get_manager().complete_vision(
        prompt, image_bytes, mime, offline_answer=fallback
    )
    return AIResult(
        completion.text,
        completion.provider,
        completion.prompt_tokens,
        completion.completion_tokens,
        completion.cost_usd,
        completion.confidence,
    )


async def summarize(prompt: str, *, offline_answer: str) -> AIResult:
    """A thin alias over `complete` for document/report summarisation."""
    return await complete(prompt, offline_answer=offline_answer)


# ── Safety ────────────────────────────────────────────────────────────────────

# Environment variables that must never leak into a prompt or a response.
_SECRET_MARKERS = (
    "api_key",
    "api key",
    "gemini_api_key",
    "claude_api_key",
    "secret_key",
    "database_url",
    "password",
    "authorization",
    "bearer ",
    "jwt",
)


def redact_secrets(text: str) -> str:
    """
    Defensive scrub: never echo anything that looks like a secret.

    The prompts ARIA builds are assembled from bounded farm context, not from the
    environment, so this should never fire — it exists so that if a value ever
    reaches a prompt by mistake, it is masked rather than sent onward.
    """
    if not text:
        return text
    out = text
    for key, val in os.environ.items():
        if val and len(val) >= 8 and val in out:
            out = out.replace(val, "«redacted»")
    lowered = out.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        # Mask obvious key=value secret patterns.
        import re

        out = re.sub(
            r"(?i)(api[_ ]?key|secret|password|bearer|token)\s*[:=]\s*\S+",
            r"\1: «redacted»",
            out,
        )
    return out
