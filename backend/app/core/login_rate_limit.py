"""
Greena — login brute-force throttle.

A small in-memory sliding-window limiter for the email/password login endpoint.
Failed attempts are counted per client IP; once the threshold is crossed inside
the window the endpoint returns 429 until the window drains. A successful login
clears the counter.

Scope: the production service runs a single worker (see render.yaml), so an
in-process store is correct and has zero external dependencies. If the API is
ever scaled to multiple instances, move this to a shared store (e.g. Redis) so
the window is enforced across them — the interface here is deliberately small so
that swap is contained.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.config import settings


class LoginRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _window(self) -> float:
        return settings.LOGIN_ATTEMPT_WINDOW_MINUTES * 60

    def _prune(self, key: str, now: float) -> None:
        window = self._window()
        dq = self._hits[key]
        while dq and now - dq[0] > window:
            dq.popleft()
        if not dq:
            self._hits.pop(key, None)

    def is_blocked(self, key: str) -> bool:
        """True if this key has already used up its attempts in the window."""
        if not key:
            return False
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            return len(self._hits.get(key, ())) >= settings.LOGIN_MAX_ATTEMPTS

    def record_failure(self, key: str) -> None:
        if not key:
            return
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        if not key:
            return
        with self._lock:
            self._hits.pop(key, None)


login_rate_limiter = LoginRateLimiter()
