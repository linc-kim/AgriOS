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
    import base64

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return AIResult(offline_answer or _VISION_OFFLINE, "offline",
                        _estimate_tokens(prompt), _estimate_tokens(offline_answer or _VISION_OFFLINE), 0.0)

    import httpx

    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={gemini_key}")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": mime or "image/jpeg", "data": b64}},
        ]}],
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        pt = usage.get("promptTokenCount", 0)
        ct = usage.get("candidatesTokenCount", 0)
        from app.services import aria_service
        return AIResult(text, "gemini", pt, ct, aria_service._compute_cost("gemini", pt, ct))
    except Exception as e:
        logger.warning("Gemini Vision failed, offline fallback: %s", e)
        return AIResult(offline_answer or _VISION_OFFLINE, "offline",
                        _estimate_tokens(prompt), _estimate_tokens(offline_answer or _VISION_OFFLINE), 0.0)


async def summarize(prompt: str, *, offline_answer: str) -> AIResult:
    """A thin alias over `complete` for document/report summarisation."""
    return await complete(prompt, offline_answer=offline_answer)


# ── Safety ────────────────────────────────────────────────────────────────────

# Environment variables that must never leak into a prompt or a response.
_SECRET_MARKERS = (
    "api_key", "api key", "gemini_api_key", "claude_api_key", "secret_key",
    "database_url", "password", "authorization", "bearer ", "jwt",
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
        out = re.sub(r"(?i)(api[_ ]?key|secret|password|bearer|token)\s*[:=]\s*\S+",
                     r"\1: «redacted»", out)
    return out
