"""
AGRIOS — Authentication Schemas
Request and response models for all auth endpoints.
Phone format: E.164 (+254XXXXXXXXX for Kenya).
"""

import re
from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

# ── Validators ────────────────────────────────────────────────────────────────

KENYA_PHONE_PATTERN = re.compile(r"^\+254[17]\d{8}$")


def validate_kenyan_phone(phone: str) -> str:
    """
    Validates and normalises a Kenyan phone number to E.164 format.
    Accepts: +254XXXXXXXXX, 254XXXXXXXXX, 07XXXXXXXX, 01XXXXXXXX
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    # Normalise local formats to E.164
    if phone.startswith("07") or phone.startswith("01"):
        phone = "+254" + phone[1:]
    elif phone.startswith("254") and not phone.startswith("+"):
        phone = "+" + phone

    if not KENYA_PHONE_PATTERN.match(phone):
        raise ValueError(
            "Invalid Kenyan phone number. Use format: +254XXXXXXXXX or 07XXXXXXXX"
        )
    return phone


# ── OTP Schemas ───────────────────────────────────────────────────────────────

class OTPRequestIn(AGRIOSSchema):
    """Request body for POST /auth/request-otp"""

    phone: str

    @field_validator("phone")
    @classmethod
    def normalise_phone(cls, v: str) -> str:
        return validate_kenyan_phone(v)


class OTPRequestOut(AGRIOSSchema):
    """Response for POST /auth/request-otp"""

    phone: str
    message: str = "OTP sent successfully"
    expires_in_minutes: int = 10


class OTPVerifyIn(AGRIOSSchema):
    """Request body for POST /auth/verify-otp"""

    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def normalise_phone(cls, v: str) -> str:
        return validate_kenyan_phone(v)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP code must be exactly 6 digits")
        return v


# ── PIN Schemas ───────────────────────────────────────────────────────────────

class PINSetIn(AGRIOSSchema):
    """Request body for POST /auth/set-pin"""

    pin: str
    pin_confirm: str

    @field_validator("pin", "pin_confirm")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or not (4 <= len(v) <= 6):
            raise ValueError("PIN must be 4–6 digits")
        return v

    def model_post_init(self, __context) -> None:
        if self.pin != self.pin_confirm:
            raise ValueError("PINs do not match")


class PINVerifyIn(AGRIOSSchema):
    """Request body for POST /auth/verify-pin"""

    phone: str
    pin: str

    @field_validator("phone")
    @classmethod
    def normalise_phone(cls, v: str) -> str:
        return validate_kenyan_phone(v)

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or not (4 <= len(v) <= 6):
            raise ValueError("PIN must be 4–6 digits")
        return v


# ── Token Schemas ─────────────────────────────────────────────────────────────

class TokenOut(AGRIOSSchema):
    """
    Response for successful OTP verification or PIN login.
    Access token is returned in body.
    Refresh token is set as an httpOnly cookie by the endpoint handler.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds until access token expiry
    is_new_user: bool = False
    has_pin: bool = False


class RefreshOut(AGRIOSSchema):
    """Response for POST /auth/refresh"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


# ── User Profile Schemas ──────────────────────────────────────────────────────

class RoleOut(AGRIOSSchema):
    """Embedded role representation"""

    id: UUID
    name: str
    display_name: str


class UserRoleOut(AGRIOSSchema):
    """A user's role, optionally scoped to a farm"""

    role: RoleOut
    farm_id: UUID | None = None


class UserOut(TimestampedSchema):
    """Public user profile"""

    phone: str
    email: str | None = None
    full_name: str | None = None
    language: str
    is_phone_verified: bool
    has_pin: bool
    sms_notifications_enabled: bool = True  # derived from metadata_
    user_roles: list[UserRoleOut] = []

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # type: ignore[override]
        instance = super().model_validate(obj, *args, **kwargs)
        if hasattr(obj, "metadata_") and isinstance(obj.metadata_, dict):
            instance.sms_notifications_enabled = obj.metadata_.get(
                "sms_notifications_enabled", True
            )
        return instance

    @classmethod
    def from_orm_with_pin(cls, user) -> "UserOut":
        data = cls.model_validate(user)
        data.has_pin = user.pin_hash is not None
        return data


class UserUpdateIn(AGRIOSSchema):
    """Request body for PATCH /auth/me"""

    full_name: str | None = None
    language: str | None = None
    sms_notifications_enabled: bool | None = None  # stored in user.metadata_

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v and v not in ("en", "sw"):
            raise ValueError("Language must be 'en' or 'sw'")
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) == 0:
            raise ValueError("full_name cannot be blank")
        return v.strip() if v else v
