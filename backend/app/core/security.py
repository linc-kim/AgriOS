"""
AGRIOS — Security Utilities
Handles: JWT creation/validation, bcrypt PIN hashing, OTP generation.
All security parameters come from Settings — never hardcoded.
"""

import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password / PIN Context ────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_secret(secret: str) -> str:
    """Hash a PIN, OTP code, or refresh token using bcrypt."""
    return pwd_context.hash(secret)


def verify_secret(plain: str, hashed: str) -> bool:
    """Verify a plain value against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ── OTP ───────────────────────────────────────────────────────────────────────

def generate_otp_code() -> str:
    """
    Generate a 6-digit OTP code.
    Uses secrets.choice for cryptographic randomness.
    """
    return "".join(secrets.choice(string.digits) for _ in range(6))


def get_otp_expiry() -> datetime:
    """Return the expiry datetime for a new OTP."""
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.OTP_EXPIRE_MINUTES
    )


# ── JWT ───────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def create_access_token(
    subject: str,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create a short-lived JWT access token.
    Subject is the user's UUID as a string.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Create a refresh token.
    Returns: (raw_token, hashed_token, expiry_datetime)
    The raw token is sent to the client (httpOnly cookie).
    The hashed token is stored in the database.
    """
    raw_token = secrets.token_urlsafe(64)
    hashed_token = hash_secret(raw_token)
    expiry = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return raw_token, hashed_token, expiry


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises JWTError if the token is invalid or expired.
    """
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise JWTError("Invalid token type")

    return payload


def extract_user_id(token: str) -> str:
    """
    Extract the user UUID from a valid access token.
    Raises JWTError on any validation failure.
    """
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if not subject:
        raise JWTError("Token missing subject")
    return subject
