"""Unit tests for the AI Provider Manager (Gate 4) — rotation, failover, health."""

import pytest

from app.services.ai_provider_manager import (
    AIProviderManager,
    Completion,
    ErrorKind,
    GeminiProvider,
    ProviderCallError,
    RoutingPolicy,
)

pytestmark = pytest.mark.asyncio


class _FakeProvider:
    def __init__(self, name, *, available=True, result=None, error=None):
        self.name = name
        self._available = available
        self._result = result
        self._error = error
        self.calls = 0

    def available(self):
        return self._available

    async def complete(self, prompt):
        self.calls += 1
        if self._error:
            raise self._error
        return self._result


# ── Manager routing ───────────────────────────────────────────────────────────

async def test_uses_first_available_provider():
    p1 = _FakeProvider("gemini", result=Completion("hi", "gemini", 1, 1, 0.0))
    p2 = _FakeProvider("claude", result=Completion("hey", "claude", 1, 1, 0.0))
    c = await AIProviderManager([p1, p2]).complete("q", offline_answer="off")
    assert c.provider == "gemini"
    assert p2.calls == 0  # second provider not touched


async def test_fails_over_to_next_provider_on_error():
    p1 = _FakeProvider("gemini", error=ProviderCallError("quota", ErrorKind.QUOTA))
    p2 = _FakeProvider("claude", result=Completion("hey", "claude", 1, 1, 0.0))
    c = await AIProviderManager([p1, p2]).complete("q", offline_answer="off")
    assert c.provider == "claude"


async def test_skips_unavailable_provider():
    p1 = _FakeProvider("gemini", available=False)
    p2 = _FakeProvider("claude", result=Completion("hey", "claude", 1, 1, 0.0))
    c = await AIProviderManager([p1, p2]).complete("q", offline_answer="off")
    assert c.provider == "claude"
    assert p1.calls == 0


async def test_offline_when_all_unavailable():
    c = await AIProviderManager([_FakeProvider("gemini", available=False)]).complete(
        "q", offline_answer="grounded"
    )
    assert c.provider == "offline"
    assert c.text == "grounded"
    assert c.confidence == "offline"


async def test_offline_when_no_providers_registered():
    c = await AIProviderManager([]).complete("q", offline_answer="grounded")
    assert c.provider == "offline"


async def test_provider_exception_is_swallowed_and_next_tried():
    p1 = _FakeProvider("gemini", error=RuntimeError("boom"))  # non-ProviderCallError
    p2 = _FakeProvider("claude", result=Completion("ok", "claude", 1, 1, 0.0))
    c = await AIProviderManager([p1, p2]).complete("q", offline_answer="off")
    assert c.provider == "claude"


# ── Gemini multi-key rotation + failover ──────────────────────────────────────

async def test_gemini_round_robin_across_keys(monkeypatch):
    g = GeminiProvider(["A", "B"])
    served: list[int] = []

    async def fake_call(prompt, key):
        served.append(key.index)
        return Completion("ok", "gemini", 1, 1, 0.0)

    monkeypatch.setattr(g, "_call", fake_call)
    for q in ("1", "2", "3"):
        await g.complete(q)
    assert served == [0, 1, 0]  # round-robin advances each successful call


async def test_gemini_fails_over_and_marks_key(monkeypatch):
    g = GeminiProvider(["A", "B"])

    async def fake_call(prompt, key):
        if key.index == 0:
            raise ProviderCallError("429", ErrorKind.RATE_LIMIT)
        return Completion("ok", "gemini", 1, 1, 0.0)

    monkeypatch.setattr(g, "_call", fake_call)
    c = await g.complete("q")
    assert c.provider == "gemini"
    assert c.key_index == 1
    health = {k["index"]: k["state"] for k in g.key_health()}
    assert health[0] == "rate_limited"
    assert health[1] == "available"


async def test_gemini_all_keys_exhausted_raises_and_unavailable(monkeypatch):
    g = GeminiProvider(["A", "B"])

    async def fake_call(prompt, key):
        raise ProviderCallError("quota", ErrorKind.QUOTA)

    monkeypatch.setattr(g, "_call", fake_call)
    with pytest.raises(ProviderCallError):
        await g.complete("q")
    assert g.available() is False  # both keys in quota cooldown


async def test_gemini_no_keys_is_unavailable():
    g = GeminiProvider([])
    assert g.available() is False


# ── Configurable routing policy ───────────────────────────────────────────────

async def _ok_call(prompt, key):
    return Completion("ok", "gemini", 5, 3, 0.0)


async def test_primary_policy_sticks_to_first_key(monkeypatch):
    g = GeminiProvider(["A", "B"], policy=RoutingPolicy.PRIMARY)
    served: list[int] = []

    async def fake(prompt, key):
        served.append(key.index)
        return Completion("ok", "gemini", 1, 1, 0.0)

    monkeypatch.setattr(g, "_call", fake)
    for q in ("1", "2", "3"):
        await g.complete(q)
    assert served == [0, 0, 0]  # sticky primary — never rotates while key 0 is healthy


async def test_least_failures_policy_prefers_healthiest_key(monkeypatch):
    g = GeminiProvider(["A", "B"], policy=RoutingPolicy.LEAST_FAILURES)
    g._keys[0].failures = 3  # key 0 is unhealthy; key 1 is clean
    served: list[int] = []

    async def fake(prompt, key):
        served.append(key.index)
        return Completion("ok", "gemini", 1, 1, 0.0)

    monkeypatch.setattr(g, "_call", fake)
    await g.complete("q")
    assert served == [1]  # healthiest key chosen first


async def test_unknown_policy_falls_back_to_round_robin():
    assert GeminiProvider(["A"], policy="bogus").policy is RoutingPolicy.ROUND_ROBIN


# ── Per-key metrics + usage aggregate ─────────────────────────────────────────

async def test_key_metrics_are_tracked(monkeypatch):
    g = GeminiProvider(["A"])
    monkeypatch.setattr(g, "_call", _ok_call)
    await g.complete("q")
    k = g.key_health()[0]
    assert k["requests"] == 1 and k["successes"] == 1 and k["failures"] == 0
    assert k["prompt_tokens"] == 5 and k["completion_tokens"] == 3
    assert k["cooldown_remaining"] == 0.0 and k["last_used_at"] is not None


async def test_failure_metrics_and_cooldown(monkeypatch):
    g = GeminiProvider(["A"])

    async def boom(prompt, key):
        raise ProviderCallError("429", ErrorKind.RATE_LIMIT)

    monkeypatch.setattr(g, "_call", boom)
    with pytest.raises(ProviderCallError):
        await g.complete("q")
    k = g.key_health()[0]
    assert k["failures"] == 1 and k["successes"] == 0
    assert k["state"] == "rate_limited" and k["cooldown_remaining"] > 0


async def test_manager_usage_aggregates_across_keys(monkeypatch):
    g = GeminiProvider(["A", "B"])
    monkeypatch.setattr(g, "_call", _ok_call)
    m = AIProviderManager([g])
    await m.complete("1", offline_answer="off")
    await m.complete("2", offline_answer="off")
    usage = m.usage()
    assert usage["successes"] == 2
    assert usage["prompt_tokens"] == 10 and usage["completion_tokens"] == 6
    assert m.health()["gemini"]["policy"] == "round_robin"
