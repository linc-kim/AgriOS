"""
Greena — Security Utilities
Handles: JWT creation/validation, bcrypt PIN hashing, OTP generation.
All security parameters come from Settings — never hardcoded.
"""

import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
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


# ── Account Passwords (Argon2id) ──────────────────────────────────────────────
# Argon2id is the primary hasher for account passwords: memory-hard, timing-safe,
# and passphrase-friendly (no bcrypt 72-byte truncation). PIN/OTP hashing above
# stays on bcrypt via passlib — this is intentionally separate.

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash an account password with Argon2id."""
    return _password_hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Timing-safe verification of a password against its Argon2id hash."""
    try:
        return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def password_needs_rehash(hashed: str) -> bool:
    """True if the stored hash should be upgraded to current Argon2 parameters."""
    try:
        return _password_hasher.check_needs_rehash(hashed)
    except InvalidHash:
        return True


# Common passwords are rejected outright; the list stays intentionally small
# (a full breach check via HaveIBeenPwned can be layered in later).
_COMMON_PASSWORDS = frozenset(
    {
        "password", "passw0rd", "12345678", "123456789", "1234567890",
        "qwertyuiop", "letmein123", "iloveyou123", "adminadmin",
        "welcome123", "changeme123", "greena123456", "password1234",
    }
)


def validate_password_strength(password: str) -> None:
    """
    Modern, length-first password policy (NIST-aligned): require length, reject
    obviously weak or common secrets, but do not impose brittle composition rules.
    Raises ValidationException on failure.
    """
    from app.config import settings
    from app.exceptions import ValidationException

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValidationException(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."
        )
    if len(password) > 200:
        raise ValidationException("Password must be at most 200 characters.")
    if password.lower() in _COMMON_PASSWORDS:
        raise ValidationException("That password is too common. Choose a stronger one.")
    if len(set(password)) < 5:
        raise ValidationException("Password is too repetitive. Choose a stronger one.")


# ── Opaque Tokens (refresh, email verification, reset) ────────────────────────

def generate_url_token(nbytes: int = 32) -> str:
    """Generate a high-entropy, URL-safe opaque token to email or set in a cookie."""
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str) -> str:
    """
    SHA-256 hex digest for indexing high-entropy tokens (refresh `token_lookup`,
    email-token `token_lookup`). High entropy means a fast hash is safe here — the
    value is not guessable, so no salt/slow-hash is needed, and it enables O(1)
    indexed lookups.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
