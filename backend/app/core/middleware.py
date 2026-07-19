"""
Greena — Request Middleware
Handles: request ID injection, timing, security headers, metrics, rate limiting.

Sprint 10: SecurityHeadersMiddleware added for production hardening.
Module 11: MetricsMiddleware and RateLimitMiddleware added.
"""

import re
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique X-Request-ID header into every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Adds X-Process-Time header to every response for performance monitoring."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}s"
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security headers into every response.

    Sprint 10 (Production Hardening):
    - X-Content-Type-Options: prevents MIME-type sniffing attacks
    - X-Frame-Options: clickjacking protection (API never rendered in iframes)
    - X-XSS-Protection: legacy XSS filter for older browsers
    - Referrer-Policy: limits referrer leakage on cross-origin requests
    - Permissions-Policy: disables unused browser APIs
    - Content-Security-Policy: restricts resource origins for API responses
    - Strict-Transport-Security: HTTPS enforcement in production only
    """

    # CSP for the JSON API — no scripts, stylesheets, or media
    _CSP_API = (
        "default-src 'none'; "
        "frame-ancestors 'none';"
    )

    # HSTS — only sent in production (31536000s = 1 year)
    _HSTS = "max-age=31536000; includeSubDomains"

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )
        response.headers["Content-Security-Policy"] = self._CSP_API

        if settings.is_production:
            response.headers["Strict-Transport-Security"] = self._HSTS

        return response


# ── Metrics (Module 11) ───────────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_NUMERIC_RE = re.compile(r"/\d+")


def normalise_path(request: Request) -> str:
    """
    Reduce a request path to a low-cardinality template.

    Prometheus label values must be bounded — recording the raw path would
    create a distinct time series per farm id and blow up the registry. The
    matched route template is used when routing resolved; otherwise ids are
    substituted out by pattern so unmatched paths (404s, probes) still collapse.
    """
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
    if path_format:
        return path_format

    path = _UUID_RE.sub("/{id}", request.url.path)
    return _NUMERIC_RE.sub("/{n}", path)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Records request counts, latency and exceptions into the metrics registry.

    Registered innermost so the latency it measures is handler time, excluding
    the other middleware in the stack.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.services.metrics_service import registry

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            registry.record_exception(type(exc).__name__)
            registry.record_request(
                request.method, normalise_path(request), 500, time.perf_counter() - start
            )
            raise

        registry.record_request(
            request.method,
            normalise_path(request),
            response.status_code,
            time.perf_counter() - start,
        )
        return response


# ── Rate limiting (Module 11) ─────────────────────────────────────────────────

# Rate-limit hit log, module-level so it can be inspected and cleared.
# The test suite resets it between tests: the window is shared process state,
# and without a reset a run of auth tests trips the limiter and fails tests that
# have nothing to do with rate limiting.
_rate_limit_hits: dict[str, deque] = defaultdict(deque)
_rate_limit_lock = Lock()


def reset_rate_limits() -> None:
    """Clear the rate-limit window. For tests and administrative recovery."""
    with _rate_limit_lock:
        _rate_limit_hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limit on authentication endpoints.

    Only the auth surface is limited: those endpoints are unauthenticated and
    guessable, so they are what an attacker actually hammers. Everything else
    already requires a valid token and is bounded by plan limits.

    In-process and per-instance, which is the honest scope of a single-process
    deployment (AD-13). Behind multiple replicas this becomes per-replica and
    should move to Redis; the OTP request limits in auth_service remain the
    authoritative per-phone control either way.
    """

    # (max requests, window seconds) per client IP.
    _LIMIT = 20
    _WINDOW = 60
    _PROTECTED_PREFIXES = ("/api/v1/auth/",)
    # Reading your own session is not an attack surface worth limiting.
    _EXEMPT_SUFFIXES = ("/me", "/logout")

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits = _rate_limit_hits
        self._lock = _rate_limit_lock

    def _is_protected(self, path: str) -> bool:
        if not path.startswith(self._PROTECTED_PREFIXES):
            return False
        return not path.endswith(self._EXEMPT_SUFFIXES)

    def _client_ip(self, request: Request) -> str:
        # X-Forwarded-For is set by the platform proxy; take the original client.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._is_protected(request.url.path):
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.monotonic()
        cutoff = now - self._WINDOW

        with self._lock:
            hits = self._hits[ip]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self._LIMIT:
                retry_after = int(self._WINDOW - (now - hits[0])) + 1
                limited = True
            else:
                hits.append(now)
                retry_after = 0
                limited = False

            # Keep the map from growing without bound on a long-lived process.
            if len(self._hits) > 10_000:
                for key in [k for k, v in self._hits.items() if not v]:
                    del self._hits[key]

        if limited:
            from app.services.metrics_service import registry

            registry.record_event("rate_limited")
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please wait and try again.",
                    },
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
