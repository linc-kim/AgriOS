"""
Greena — AI Provider Manager (Gate 4).

The single service every AI completion flows through. It owns provider selection,
per-key round-robin rotation, health tracking and failover, so ARIA and every
module call one abstraction and never talk to a model (or hold a key) directly:

        AI Provider Manager
                │
                ├── Gemini  (Key A, Key B, … round-robin + failover)
                ├── Claude  (fallback)
                └── (future: OpenAI, others — just register a provider)

Adding another Gemini key, or a whole new provider, is a registration — not a
rewrite of ARIA. All keys stay backend-only (Doc 3 §17). When every provider is
unavailable the manager returns a grounded ``offline`` completion so the assistant
stays honest and the product stays demonstrable.
"""

from __future__ import annotations

import base64
import dataclasses
import enum
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx

logger = logging.getLogger("greena.ai.manager")

# Manager contract version — surfaced in diagnostics; bump on behavioural changes.
MANAGER_VERSION = "1.0"

# Pricing (USD/token) — mirrors aria_service so the manager is self-contained.
_GEMINI_IN, _GEMINI_OUT = 0.000000075, 0.0000003
_CLAUDE_IN, _CLAUDE_OUT = 0.00000025, 0.00000125
_DEFAULT_TIMEOUT = 15


# ── Result + error taxonomy ───────────────────────────────────────────────────


@dataclass
class Completion:
    text: str
    provider: str  # "gemini" | "claude" | "offline"
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    key_index: int | None = None  # which key served it (observability)
    confidence: str = "medium"  # explainability metadata for callers/UI


class ErrorKind(str, enum.Enum):
    RATE_LIMIT = "rate_limit"  # 429 — back off this key, try the next
    QUOTA = "quota"  # quota exhausted — long cooldown
    TRANSIENT = "transient"  # 5xx / timeout / network — try the next
    FATAL = "fatal"  # 4xx auth/bad-request — key/model misconfig


class ProviderCallError(Exception):
    def __init__(self, message: str, kind: ErrorKind) -> None:
        super().__init__(message)
        self.kind = kind


class KeyState(str, enum.Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    FAILED = "failed"


# Cooldown (seconds) before a non-available key is retried.
_COOLDOWN: dict[KeyState, int] = {
    KeyState.RATE_LIMITED: 60,
    KeyState.QUOTA_EXHAUSTED: 3600,
    KeyState.FAILED: 120,
}

_STATE_FOR_KIND: dict[ErrorKind, KeyState] = {
    ErrorKind.RATE_LIMIT: KeyState.RATE_LIMITED,
    ErrorKind.QUOTA: KeyState.QUOTA_EXHAUSTED,
    ErrorKind.TRANSIENT: KeyState.FAILED,
    ErrorKind.FATAL: KeyState.FAILED,
}


@dataclass
class _Key:
    value: str
    index: int
    state: KeyState = KeyState.AVAILABLE
    cooldown_until: float = 0.0
    requests: int = 0  # total attempts routed to this key
    successes: int = 0
    failures: int = 0
    prompt_tokens: int = 0  # cumulative usage (observability)
    completion_tokens: int = 0
    last_used_at: float | None = None

    def usable(self, now: float) -> bool:
        if self.state is KeyState.AVAILABLE:
            return True
        if now >= self.cooldown_until:
            self.state = KeyState.AVAILABLE  # cooldown elapsed — give it another chance
            return True
        return False

    def cooldown_remaining(self, now: float) -> float:
        if self.state is KeyState.AVAILABLE:
            return 0.0
        return max(0.0, self.cooldown_until - now)

    def record_attempt(self, now: float) -> None:
        self.requests += 1
        self.last_used_at = now

    def mark_ok(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.state = KeyState.AVAILABLE
        self.cooldown_until = 0.0
        self.successes += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def mark_bad(self, kind: ErrorKind, now: float) -> None:
        self.failures += 1
        state = _STATE_FOR_KIND[kind]
        self.state = state
        self.cooldown_until = now + _COOLDOWN.get(state, 60)

    def snapshot(self, now: float) -> dict:
        return {
            "index": self.index,
            "state": self.state.value,
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "cooldown_remaining": round(self.cooldown_remaining(now), 1),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "last_used_at": self.last_used_at,
        }


def _classify_status(status: int) -> ErrorKind:
    if status == 429:
        return ErrorKind.RATE_LIMIT
    if status in (500, 502, 503, 504):
        return ErrorKind.TRANSIENT
    if status in (400, 401, 403):
        return ErrorKind.FATAL
    return ErrorKind.TRANSIENT


# ── Routing policy (configurable — not hardcoded) ─────────────────────────────


class RoutingPolicy(str, enum.Enum):
    ROUND_ROBIN = "round_robin"  # spread load evenly across keys (default)
    PRIMARY = "primary"  # sticky: prefer the lowest-index usable key
    LEAST_FAILURES = "least_failures"  # prefer the healthiest usable key


def _resolve_policy(value: str | RoutingPolicy | None) -> RoutingPolicy:
    if isinstance(value, RoutingPolicy):
        return value
    try:
        return RoutingPolicy((value or "round_robin").strip().lower())
    except ValueError:
        logger.warning("Unknown AI routing policy %r; using round_robin", value)
        return RoutingPolicy.ROUND_ROBIN


# ── Provider protocol ─────────────────────────────────────────────────────────


@runtime_checkable
class AIProvider(Protocol):
    name: str

    def available(self) -> bool: ...
    async def complete(self, prompt: str) -> Completion: ...


# ── Gemini (multi-key, round-robin + failover) ────────────────────────────────


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        keys: list[str],
        *,
        model: str = "gemini-2.0-flash",
        timeout: int = _DEFAULT_TIMEOUT,
        policy: str | RoutingPolicy = RoutingPolicy.ROUND_ROBIN,
    ) -> None:
        self._keys = [_Key(value=k, index=i) for i, k in enumerate(keys) if k]
        self._model = model
        self._timeout = timeout
        self._policy = _resolve_policy(policy)
        self._cursor = 0

    @property
    def policy(self) -> RoutingPolicy:
        return self._policy

    def available(self) -> bool:
        now = time.monotonic()
        return any(k.usable(now) for k in self._keys)

    def key_health(self) -> list[dict]:
        now = time.monotonic()
        return [k.snapshot(now) for k in self._keys]

    def _try_order(self) -> list[int]:
        """Indices into ``self._keys`` in the order the policy wants them tried."""
        n = len(self._keys)
        if self._policy is RoutingPolicy.PRIMARY:
            return list(range(n))
        if self._policy is RoutingPolicy.LEAST_FAILURES:
            return sorted(range(n), key=lambda i: (self._keys[i].failures, i))
        # ROUND_ROBIN: start at the cursor and wrap.
        return [(self._cursor + off) % n for off in range(n)]

    async def complete(self, prompt: str) -> Completion:
        return await self._rotate(lambda key: self._call(prompt, key))

    async def complete_vision(
        self, prompt: str, image_bytes: bytes, mime: str
    ) -> Completion:
        return await self._rotate(
            lambda key: self._call_vision(prompt, image_bytes, mime, key)
        )

    async def _rotate(self, call_fn) -> Completion:
        """Try keys in policy order; on rate-limit/quota/transient, fail over."""
        if not self._keys:
            raise ProviderCallError("no gemini keys configured", ErrorKind.FATAL)
        now = time.monotonic()
        last: ProviderCallError | None = None
        for idx in self._try_order():
            key = self._keys[idx]
            if not key.usable(now):
                continue
            key.record_attempt(now)
            try:
                comp = await call_fn(key)
            except ProviderCallError as exc:
                key.mark_bad(exc.kind, now)
                last = exc
                logger.warning(
                    "Gemini key %d failed (%s); failing over", key.index, exc.kind.value
                )
                continue
            key.mark_ok(comp.prompt_tokens, comp.completion_tokens)
            # Round-robin advances the cursor past the key that served this call.
            if self._policy is RoutingPolicy.ROUND_ROBIN:
                self._cursor = (idx + 1) % len(self._keys)
            comp.key_index = key.index
            return comp
        raise last or ProviderCallError(
            "all gemini keys unavailable", ErrorKind.TRANSIENT
        )

    async def _call(self, prompt: str, key: _Key) -> Completion:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={key.value}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 512, "temperature": 0.3},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderCallError("gemini timeout", ErrorKind.TRANSIENT) from exc
        except httpx.HTTPError as exc:
            raise ProviderCallError(
                f"gemini network error: {exc}", ErrorKind.TRANSIENT
            ) from exc

        if resp.status_code >= 400:
            raise ProviderCallError(
                f"gemini HTTP {resp.status_code}", _classify_status(resp.status_code)
            )

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderCallError(
                "gemini returned no content", ErrorKind.TRANSIENT
            ) from exc

        usage = data.get("usageMetadata", {})
        pt = usage.get("promptTokenCount", 0)
        ct = usage.get("candidatesTokenCount", 0)
        return Completion(text, "gemini", pt, ct, pt * _GEMINI_IN + ct * _GEMINI_OUT)

    async def _call_vision(
        self, prompt: str, image_bytes: bytes, mime: str, key: _Key
    ) -> Completion:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={key.value}"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime or "image/jpeg",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 512, "temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderCallError(
                "gemini vision timeout", ErrorKind.TRANSIENT
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderCallError(
                f"gemini vision network error: {exc}", ErrorKind.TRANSIENT
            ) from exc
        if resp.status_code >= 400:
            raise ProviderCallError(
                f"gemini vision HTTP {resp.status_code}",
                _classify_status(resp.status_code),
            )
        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderCallError(
                "gemini vision returned no content", ErrorKind.TRANSIENT
            ) from exc
        usage = data.get("usageMetadata", {})
        pt = usage.get("promptTokenCount", 0)
        ct = usage.get("candidatesTokenCount", 0)
        return Completion(text, "gemini", pt, ct, pt * _GEMINI_IN + ct * _GEMINI_OUT)


# ── Claude (single key, fallback) ─────────────────────────────────────────────


class ClaudeProvider:
    name = "claude"

    def __init__(
        self,
        key: str,
        *,
        model: str = "claude-haiku-4-5-20251001",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._key = key
        self._model = model
        self._timeout = timeout
        self._key_state = _Key(value=key, index=0)

    def available(self) -> bool:
        if not self._key:
            return False
        return self._key_state.usable(time.monotonic())

    def key_health(self) -> list[dict]:
        return [self._key_state.snapshot(time.monotonic())]

    async def complete(self, prompt: str) -> Completion:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self._key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "messages": [{"role": "user", "content": prompt}],
        }
        now = time.monotonic()
        self._key_state.record_attempt(now)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            self._key_state.mark_bad(ErrorKind.TRANSIENT, now)
            raise ProviderCallError(
                f"claude network error: {exc}", ErrorKind.TRANSIENT
            ) from exc

        if resp.status_code >= 400:
            kind = _classify_status(resp.status_code)
            self._key_state.mark_bad(kind, now)
            raise ProviderCallError(f"claude HTTP {resp.status_code}", kind)

        data = resp.json()
        try:
            text = data["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderCallError(
                "claude returned no content", ErrorKind.TRANSIENT
            ) from exc
        usage = data.get("usage", {})
        pt = usage.get("input_tokens", 0)
        ct = usage.get("output_tokens", 0)
        self._key_state.mark_ok(pt, ct)
        return Completion(text, "claude", pt, ct, pt * _CLAUDE_IN + ct * _CLAUDE_OUT)


# ── The manager ───────────────────────────────────────────────────────────────


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class AIProviderManager:
    """Routes a completion through registered providers in priority order."""

    def __init__(
        self, providers: list[AIProvider] | None = None, *, cache_ttl: int = 0
    ) -> None:
        self._providers: list[AIProvider] = list(providers or [])
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, Completion]] = {}

    def register(self, provider: AIProvider) -> None:
        self._providers.append(provider)

    @property
    def providers(self) -> list[AIProvider]:
        return list(self._providers)

    def _offline(self, prompt: str, offline_answer: str) -> Completion:
        return Completion(
            offline_answer,
            "offline",
            _estimate_tokens(prompt),
            _estimate_tokens(offline_answer),
            0.0,
            confidence="offline",
        )

    def _cache_get(self, key: str) -> Completion | None:
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            # A cache hit is not new spend — zero the cost and mark it cached.
            return dataclasses.replace(hit[1], cost_usd=0.0, confidence="cached")
        if hit:
            del self._cache[key]
        return None

    def _cache_put(self, key: str, comp: Completion) -> None:
        if (
            len(self._cache) >= 512
        ):  # crude bound; identical-prompt keys are low-cardinality
            self._cache.clear()
        self._cache[key] = (time.monotonic() + self._cache_ttl, comp)

    async def complete(
        self, prompt: str, *, offline_answer: str, use_cache: bool = True
    ) -> Completion:
        cache_key: str | None = None
        if self._cache_ttl > 0 and use_cache:
            cache_key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        result = await self._run(prompt, offline_answer)

        # Never cache the offline fallback — a transient outage must not stick.
        if cache_key is not None and result.provider != "offline":
            self._cache_put(cache_key, result)
        return result

    async def _run(self, prompt: str, offline_answer: str) -> Completion:
        for provider in self._providers:
            try:
                if not provider.available():
                    continue
                return await provider.complete(prompt)
            except ProviderCallError as exc:
                logger.warning(
                    "Provider %s unavailable (%s); trying next",
                    provider.name,
                    exc.kind.value,
                )
                continue
            except Exception as exc:  # never let a provider bug break the request
                logger.warning(
                    "Provider %s errored: %s; trying next", provider.name, exc
                )
                continue
        return self._offline(prompt, offline_answer)

    async def complete_vision(
        self, prompt: str, image_bytes: bytes, mime: str, *, offline_answer: str
    ) -> Completion:
        """Vision completion through any provider that supports it (Gemini today)."""
        for provider in self._providers:
            call_vision = getattr(provider, "complete_vision", None)
            if not callable(call_vision) or not provider.available():
                continue
            try:
                return await call_vision(prompt, image_bytes, mime)
            except ProviderCallError as exc:
                logger.warning(
                    "Vision provider %s unavailable (%s); trying next",
                    provider.name,
                    exc.kind.value,
                )
                continue
            except Exception as exc:
                logger.warning(
                    "Vision provider %s errored: %s; trying next", provider.name, exc
                )
                continue
        return self._offline(prompt, offline_answer)

    def health(self) -> dict:
        out: dict = {}
        for provider in self._providers:
            key_health = getattr(provider, "key_health", None)
            entry: dict = {
                "available": provider.available(),
                "keys": key_health() if callable(key_health) else None,
            }
            policy = getattr(provider, "policy", None)
            if policy is not None:
                entry["policy"] = policy.value
            out[provider.name] = entry
        return out

    def config(self) -> dict:
        """Non-secret manager configuration for diagnostics (no key values)."""
        gemini = next((p for p in self._providers if p.name == "gemini"), None)
        return {
            "version": MANAGER_VERSION,
            "registered_providers": [p.name for p in self._providers],
            "routing_policy": (gemini.policy.value if gemini is not None else None),
            "cache": {
                "enabled": self._cache_ttl > 0,
                "ttl_seconds": self._cache_ttl,
                "entries": len(self._cache),
            },
        }

    def usage(self) -> dict:
        """Aggregate request / success / failure / token counters across all keys."""
        agg = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
        for provider in self._providers:
            key_health = getattr(provider, "key_health", None)
            if not callable(key_health):
                continue
            for key in key_health():
                for field_name in agg:
                    agg[field_name] += key.get(field_name, 0)
        return agg


# ── Singleton wired from settings ─────────────────────────────────────────────

_manager: AIProviderManager | None = None


def build_manager() -> AIProviderManager:
    """Construct a manager from current settings — Gemini (N keys) then Claude."""
    from app.config import settings

    manager = AIProviderManager(cache_ttl=settings.AI_RESPONSE_CACHE_TTL_SECONDS)
    keys = settings.gemini_api_keys
    if keys:
        manager.register(
            GeminiProvider(
                keys,
                model=settings.GEMINI_MODEL,
                timeout=settings.AI_CALL_TIMEOUT_SECONDS,
                policy=settings.AI_KEY_ROUTING,
            )
        )
    if settings.CLAUDE_API_KEY.strip():
        manager.register(
            ClaudeProvider(
                settings.CLAUDE_API_KEY.strip(),
                model=settings.CLAUDE_MODEL,
                timeout=settings.AI_CALL_TIMEOUT_SECONDS,
            )
        )
    return manager


def get_manager() -> AIProviderManager:
    global _manager
    if _manager is None:
        _manager = build_manager()
    return _manager


def reset_manager() -> None:
    """Rebuild the manager from current settings (used by tests and key rotation)."""
    global _manager
    _manager = None
