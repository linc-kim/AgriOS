"""
Sprint 10 — Production Hardening Integration Tests (Backend)
Tests: /health endpoint, security headers on live responses, CORS preflight,
RequestID/Timing middleware, OTP rate limiting (service-layer), response shape.
All tests run against the test database via client fixture from conftest.py.
"""

import pytest
from unittest.mock import AsyncMock, patch


# ── 1. Health Check endpoint ──────────────────────────────────────────────────

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """GET /health is reachable without authentication."""
        resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_has_status_key(self, client):
        resp = await client.get("/health")
        assert "status" in resp.json()

    @pytest.mark.asyncio
    async def test_health_response_has_version(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "version" in data
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_response_has_environment(self, client):
        resp = await client.get("/health")
        data = resp.json()
        assert "environment" in data
        assert data["environment"] in ("development", "staging", "production")

    @pytest.mark.asyncio
    async def test_health_response_has_db_key(self, client):
        resp = await client.get("/health")
        assert "db" in resp.json()

    @pytest.mark.asyncio
    async def test_health_db_connected(self, client):
        """Test database is reachable during integration test run."""
        resp = await client.get("/health")
        data = resp.json()
        # In CI, the test DB is up, so this must be connected
        assert data["db"] == "connected"
        assert data["status"] == "ok"


# ── 2. Security Headers (via SecurityHeadersMiddleware) ───────────────────────

class TestSecurityHeaders:

    @pytest.mark.asyncio
    async def test_health_response_has_x_content_type_options(self, client):
        resp = await client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_health_response_has_x_frame_options(self, client):
        resp = await client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_health_response_has_xss_protection(self, client):
        resp = await client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    @pytest.mark.asyncio
    async def test_health_response_has_referrer_policy(self, client):
        resp = await client.get("/health")
        assert "referrer-policy" in resp.headers

    @pytest.mark.asyncio
    async def test_health_response_has_permissions_policy(self, client):
        resp = await client.get("/health")
        assert "permissions-policy" in resp.headers

    @pytest.mark.asyncio
    async def test_health_response_has_csp(self, client):
        resp = await client.get("/health")
        assert "content-security-policy" in resp.headers

    @pytest.mark.asyncio
    async def test_api_response_has_security_headers(self, client, seeded_roles):
        """Security headers present on unauthenticated API endpoints too."""
        resp = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+254799999901"},
        )
        # Even on a rejection (422/429/200), headers must be present
        assert "x-content-type-options" in resp.headers


# ── 3. RequestID + Timing Middleware ─────────────────────────────────────────

class TestRequestMiddleware:

    @pytest.mark.asyncio
    async def test_x_request_id_present(self, client):
        resp = await client.get("/health")
        assert "x-request-id" in resp.headers

    @pytest.mark.asyncio
    async def test_x_request_id_is_uuid_format(self, client):
        import uuid
        resp = await client.get("/health")
        request_id = resp.headers.get("x-request-id")
        assert request_id is not None
        # Must be a valid UUID
        parsed = uuid.UUID(request_id)
        assert str(parsed) == request_id

    @pytest.mark.asyncio
    async def test_x_process_time_present(self, client):
        resp = await client.get("/health")
        assert "x-process-time" in resp.headers

    @pytest.mark.asyncio
    async def test_x_process_time_is_numeric_seconds(self, client):
        resp = await client.get("/health")
        timing = resp.headers.get("x-process-time")
        assert timing is not None
        # Should end with 's' and be parseable as float
        assert timing.endswith("s")
        value = float(timing[:-1])
        assert value >= 0


# ── 4. OTP Rate Limiting (service-layer, Engineering Constitution) ────────────

class TestOTPRateLimiting:

    @pytest.mark.asyncio
    async def test_fourth_otp_request_is_rate_limited(self, client, seeded_roles):
        """
        Engineering Constitution SD-06: max 3 OTP requests per phone per 10 min.
        The 4th request for the same phone must return HTTP 429.
        """
        phone = "+254711111990"
        for _ in range(3):
            resp = await client.post(
                "/api/v1/auth/request-otp",
                json={"phone": phone},
            )
            assert resp.status_code == 200

        resp = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone},
        )
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "RATE_LIMITED"

    @pytest.mark.asyncio
    async def test_different_phones_are_not_rate_limited_together(self, client, seeded_roles):
        """Rate limit is per phone — a new phone number gets its own quota."""
        phone_a = "+254711111991"
        phone_b = "+254711111992"

        # Exhaust quota for phone_a
        for _ in range(3):
            await client.post("/api/v1/auth/request-otp", json={"phone": phone_a})

        # phone_b should still succeed
        resp = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone_b},
        )
        assert resp.status_code == 200
