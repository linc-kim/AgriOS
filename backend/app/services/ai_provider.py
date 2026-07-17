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
    provider: str            # gemini | claude | offline
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def complete(prompt: str, *, offline_answer: str) -> AIResult:
    """
    Try the configured providers in order; fall back to a grounded offline answer.

    ``offline_answer`` is a deterministic, context-grounded response the caller
    precomputes from the farm data — used verbatim when no provider is available
    or all providers fail.
    """
    from app.services import aria_service

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    claude_key = os.environ.get("CLAUDE_API_KEY", "").strip()

    if gemini_key:
        try:
            content, pt, ct, tt, _dur = await aria_service._call_gemini(prompt)
            if content:
                return AIResult(content, "gemini", pt, ct, aria_service._compute_cost("gemini", pt, ct))
        except Exception as e:  # timeout / quota / network → try next
            logger.warning("Gemini call failed, falling back: %s", e)

    if claude_key:
        try:
            content, pt, ct, tt, _dur = await aria_service._call_claude(prompt)
            if content:
                return AIResult(content, "claude", pt, ct, aria_service._compute_cost("claude", pt, ct))
        except Exception as e:
            logger.warning("Claude call failed, falling back: %s", e)

    # Offline-safe deterministic fallback.
    return AIResult(offline_answer, "offline", _estimate_tokens(prompt), _estimate_tokens(offline_answer), 0.0)


def providers_available() -> dict:
    return {
        "gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "claude": bool(os.environ.get("CLAUDE_API_KEY", "").strip()),
        "offline_fallback": True,
    }
