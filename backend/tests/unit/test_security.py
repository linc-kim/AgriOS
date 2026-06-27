"""
AGRIOS — Security Unit Tests
Tests: OTP generation, JWT creation/validation, PIN hashing.
"""

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    generate_otp_code,
    hash_secret,
    verify_secret,
)


class TestOTPGeneration:

    def test_otp_is_6_digits(self):
        code = generate_otp_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_otp_codes_are_unique(self):
        codes = {generate_otp_code() for _ in range(100)}
        # With 10^6 possibilities, 100 codes should almost never collide
        assert len(codes) > 90


class TestSecretHashing:

    def test_hash_and_verify_pin(self):
        pin = "1234"
        hashed = hash_secret(pin)
        assert verify_secret(pin, hashed) is True

    def test_wrong_pin_does_not_verify(self):
        hashed = hash_secret("1234")
        assert verify_secret("5678", hashed) is False

    def test_hash_is_not_plaintext(self):
        pin = "1234"
        hashed = hash_secret(pin)
        assert pin not in hashed


class TestJWT:

    def test_access_token_can_be_decoded(self):
        token = create_access_token(subject="user-uuid-123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user-uuid-123"
        assert payload["type"] == "access"

    def test_access_token_with_additional_claims(self):
        token = create_access_token(
            subject="user-uuid-123",
            additional_claims={"role": "farm_owner"},
        )
        payload = decode_access_token(token)
        assert payload["role"] == "farm_owner"

    def test_tampered_token_raises_jwt_error(self):
        token = create_access_token(subject="user-uuid-123")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(JWTError):
            decode_access_token(tampered)

    def test_refresh_token_returns_three_values(self):
        raw, hashed, expiry = create_refresh_token()
        assert len(raw) > 20
        assert verify_secret(raw, hashed) is True
        assert expiry is not None
