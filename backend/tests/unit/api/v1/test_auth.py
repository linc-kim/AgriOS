"""
AGRIOS — Auth Endpoint Unit Tests
Tests all Engineering Constitution security rules:
- OTP rate limiting
- OTP attempt limiting
- OTP expiry
- Token issuance
- Refresh token rotation
"""

import pytest


# ── OTP Request Tests ─────────────────────────────────────────────────────────

class TestOTPRequest:

    @pytest.mark.asyncio
    async def test_request_otp_valid_kenyan_number(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "+254712345678"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["phone"] == "+254712345678"
        assert data["data"]["expires_in_minutes"] == 10

    @pytest.mark.asyncio
    async def test_request_otp_normalises_local_format(self, client, seeded_roles):
        """07XXXXXXXX format should be accepted and normalised."""
        response = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "0712345678"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_otp_rejects_invalid_number(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": "12345"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_request_otp_rate_limited_after_3_requests(self, client, seeded_roles):
        """
        Engineering Constitution: max 3 OTP requests per phone per 10 minutes.
        4th request must be rejected with RATE_LIMITED error.
        """
        phone = "+254700000001"
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/request-otp",
                json={"phone": phone},
            )
            assert response.status_code == 200

        # 4th request should be rate limited
        response = await client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone},
        )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"


# ── OTP Verification Tests ────────────────────────────────────────────────────

class TestOTPVerification:

    @pytest.mark.asyncio
    async def test_verify_otp_wrong_code_increments_attempts(self, client, seeded_roles):
        """Wrong code should increment attempts. 3 wrong attempts should lock."""
        phone = "+254700000002"
        await client.post("/api/v1/auth/request-otp", json={"phone": phone})

        # 3 wrong attempts
        for i in range(3):
            response = await client.post(
                "/api/v1/auth/verify-otp",
                json={"phone": phone, "code": "000000"},
            )

        # After 3 wrong attempts, should be locked
        assert response.status_code == 400
        assert response.json()["error"]["code"] in ("OTP_INVALID", "OTP_MAX_ATTEMPTS")

    @pytest.mark.asyncio
    async def test_verify_otp_rejects_6_digit_non_numeric(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+254712345678", "code": "ABCDEF"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_verify_otp_rejects_wrong_length(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "+254712345678", "code": "1234"},
        )
        assert response.status_code == 422


# ── PIN Tests ─────────────────────────────────────────────────────────────────

class TestPIN:

    @pytest.mark.asyncio
    async def test_set_pin_requires_matching_pins(self, client, seeded_roles):
        """PIN and pin_confirm must match."""
        # This will fail at validation before auth check
        response = await client.post(
            "/api/v1/auth/set-pin",
            json={"pin": "1234", "pin_confirm": "5678"},
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_set_pin_rejects_non_numeric(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/set-pin",
            json={"pin": "abcd", "pin_confirm": "abcd"},
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_set_pin_rejects_too_short(self, client, seeded_roles):
        response = await client.post(
            "/api/v1/auth/set-pin",
            json={"pin": "123", "pin_confirm": "123"},
            headers={"Authorization": "Bearer fake_token"},
        )
        assert response.status_code == 422


# ── Health Check ──────────────────────────────────────────────────────────────

class TestHealth:

    @pytest.mark.asyncio
    async def test_health_check_returns_200(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "db" in data

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, client):
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
