"""
AGRIOS — Request Middleware
Handles: request ID injection, timing, security headers.

Sprint 10: SecurityHeadersMiddleware added for production hardening.
"""

import time
import uuid

from fastapi import Request, Response
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
