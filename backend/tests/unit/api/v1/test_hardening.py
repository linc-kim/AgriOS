"""
Sprint 10 — Production Hardening Unit Tests (Backend)
Tests: SecurityHeadersMiddleware, VERSION=1.0.0, Settings config, OTP rate-limit
config, CSP values, HSTS production-only behaviour, middleware ordering.
All tests run without I/O — pure in-process assertions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import settings
from app.core.middleware import SecurityHeadersMiddleware


# ── 1. VERSION ────────────────────────────────────────────────────────────────

class TestVersionBump:
    def test_version_is_1_0_0(self):
        assert settings.VERSION == "1.0.0"

    def test_version_is_string(self):
        assert isinstance(settings.VERSION, str)

    def test_version_has_three_parts(self):
        parts = settings.VERSION.split(".")
        assert len(parts) == 3

    def test_version_parts_are_integers(self):
        major, minor, patch = settings.VERSION.split(".")
        assert int(major) == 1
        assert int(minor) == 0
        assert int(patch) == 0


# ── 2. Settings Configuration ─────────────────────────────────────────────────

class TestSettingsConfig:
    def test_otp_max_requests_per_phone(self):
        """Engineering Constitution: max 3 OTP requests per phone per window."""
        assert settings.OTP_MAX_REQUESTS_PER_PHONE == 3

    def test_otp_request_window_is_10_minutes(self):
        """Engineering Constitution: 10-minute OTP rate-limit window."""
        assert settings.OTP_REQUEST_WINDOW_MINUTES == 10

    def test_otp_max_attempts(self):
        """Engineering Constitution: 3 wrong attempts locks the OTP."""
        assert settings.OTP_MAX_ATTEMPTS == 3

    def test_otp_expire_minutes(self):
        """Engineering Constitution: OTP expires after 10 minutes."""
        assert settings.OTP_EXPIRE_MINUTES == 10

    def test_jwt_expire_minutes_sensible(self):
        """Access tokens should expire quickly (short-lived)."""
        assert settings.JWT_EXPIRE_MINUTES <= 60

    def test_refresh_token_expire_days_sensible(self):
        """Refresh tokens are long-lived (max 90 days)."""
        assert 1 <= settings.REFRESH_TOKEN_EXPIRE_DAYS <= 90

    def test_ai_context_max_tokens(self):
        """AI context budget is locked at 8000 tokens."""
        assert settings.AI_CONTEXT_MAX_TOKENS == 8000

    def test_ai_response_max_words(self):
        """ARIA responses capped at 150 words to control cost."""
        assert settings.AI_RESPONSE_MAX_WORDS == 150


# ── 3. SecurityHeadersMiddleware — header values ──────────────────────────────

class TestSecurityHeadersValues:
    """Verify static header values without running the middleware's dispatch."""

    def test_csp_api_has_default_src_none(self):
        csp = SecurityHeadersMiddleware._CSP_API
        assert "default-src 'none'" in csp

    def test_csp_api_denies_frame_ancestors(self):
        csp = SecurityHeadersMiddleware._CSP_API
        assert "frame-ancestors 'none'" in csp

    def test_hsts_max_age_is_one_year(self):
        hsts = SecurityHeadersMiddleware._HSTS
        assert "max-age=31536000" in hsts

    def test_hsts_includes_subdomains(self):
        hsts = SecurityHeadersMiddleware._HSTS
        assert "includeSubDomains" in hsts


# ── 4. SecurityHeadersMiddleware — dispatch behaviour ─────────────────────────

class TestSecurityHeadersDispatch:
    """Integration-style tests using mock request/response objects."""

    def _make_middleware(self):
        app_mock = MagicMock()
        return SecurityHeadersMiddleware(app_mock)

    @pytest.mark.asyncio
    async def test_x_content_type_options_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert result.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_x_frame_options_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert result.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_x_xss_protection_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert result.headers["X-XSS-Protection"] == "1; mode=block"

    @pytest.mark.asyncio
    async def test_referrer_policy_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert result.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_permissions_policy_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert "camera=()" in result.headers["Permissions-Policy"]

    @pytest.mark.asyncio
    async def test_csp_header_set(self):
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert "Content-Security-Policy" in result.headers

    @pytest.mark.asyncio
    async def test_hsts_not_set_in_development(self, monkeypatch):
        """HSTS must not be sent in development (no HTTPS locally)."""
        # is_production is a read-only property derived from ENVIRONMENT; drive it
        # via ENVIRONMENT, which the middleware reads live per request.
        monkeypatch.setattr("app.core.middleware.settings.ENVIRONMENT", "development")
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert "Strict-Transport-Security" not in result.headers

    @pytest.mark.asyncio
    async def test_hsts_set_in_production(self, monkeypatch):
        """HSTS must be sent in production."""
        monkeypatch.setattr("app.core.middleware.settings.ENVIRONMENT", "production")
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        assert "Strict-Transport-Security" in result.headers
        assert "max-age=31536000" in result.headers["Strict-Transport-Security"]

    @pytest.mark.asyncio
    async def test_all_six_non_hsts_headers_present(self):
        """All security headers (excluding HSTS) are always present."""
        middleware = self._make_middleware()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_request = MagicMock()

        async def call_next(_req):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)
        required = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
            "Content-Security-Policy",
        ]
        for header in required:
            assert header in result.headers, f"Missing header: {header}"
