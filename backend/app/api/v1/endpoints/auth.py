"""
AGRIOS — Auth Endpoints (API v1)
Endpoints are thin. All logic is in AuthService.
Refresh token is always set as an httpOnly cookie — never in the response body.
Sprint 9: PATCH /auth/me extended with sms_notifications_enabled.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.config import settings
from app.dependencies import CurrentUser, DBSession
from app.schemas.auth import (
    OTPRequestIn,
    OTPRequestOut,
    OTPVerifyIn,
    PINSetIn,
    PINVerifyIn,
    RefreshOut,
    TokenOut,
    UserOut,
    UserUpdateIn,
)
from app.schemas.base import SuccessResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

REFRESH_COOKIE_NAME = "agrios_refresh_token"


def _set_refresh_cookie(response: Response, token: str, expiry: datetime) -> None:
    """
    Sets the refresh token as a secure httpOnly cookie.
    httpOnly: not accessible to JavaScript (XSS protection)
    secure: HTTPS only in production
    samesite: strict (CSRF protection)
    """
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        expires=expiry,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )


# ── POST /auth/request-otp ────────────────────────────────────────────────────

@router.post(
    "/request-otp",
    response_model=SuccessResponse[OTPRequestOut],
    status_code=status.HTTP_200_OK,
    summary="Request an OTP code via SMS",
    description=(
        "Rate limited: max 3 requests per phone number per 10 minutes. "
        "OTP expires after 10 minutes."
    ),
)
async def request_otp(
    body: OTPRequestIn,
    db: DBSession,
) -> SuccessResponse[OTPRequestOut]:
    otp = await auth_service.request_otp(db, body.phone)
    return SuccessResponse(
        data=OTPRequestOut(
            phone=body.phone,
            message="OTP sent to your phone",
            expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        )
    )


# ── POST /auth/verify-otp ─────────────────────────────────────────────────────

@router.post(
    "/verify-otp",
    response_model=SuccessResponse[TokenOut],
    status_code=status.HTTP_200_OK,
    summary="Verify OTP and receive access token",
    description=(
        "Max 3 incorrect attempts before OTP is locked. "
        "New users are created automatically. "
        "Refresh token is set as an httpOnly cookie."
    ),
)
async def verify_otp(
    body: OTPVerifyIn,
    db: DBSession,
    response: Response,
) -> SuccessResponse[TokenOut]:
    user, access_token, raw_refresh, refresh_expiry, is_new_user = (
        await auth_service.verify_otp(db, body.phone, body.code)
    )

    _set_refresh_cookie(response, raw_refresh, refresh_expiry)

    return SuccessResponse(
        data=TokenOut(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            is_new_user=is_new_user,
            has_pin=user.pin_hash is not None,
        )
    )


# ── POST /auth/set-pin ────────────────────────────────────────────────────────

@router.post(
    "/set-pin",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Set or update login PIN",
)
async def set_pin(
    body: PINSetIn,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[dict]:
    await auth_service.set_pin(db, current_user, body.pin)
    return SuccessResponse(data={"message": "PIN set successfully"})


# ── POST /auth/verify-pin ─────────────────────────────────────────────────────

@router.post(
    "/verify-pin",
    response_model=SuccessResponse[TokenOut],
    status_code=status.HTTP_200_OK,
    summary="Login with phone number and PIN",
    description="For returning users who have set a PIN. Issues new JWT tokens.",
)
async def verify_pin(
    body: PINVerifyIn,
    db: DBSession,
    response: Response,
) -> SuccessResponse[TokenOut]:
    user, access_token, raw_refresh, refresh_expiry = (
        await auth_service.verify_pin(db, body.phone, body.pin)
    )

    _set_refresh_cookie(response, raw_refresh, refresh_expiry)

    return SuccessResponse(
        data=TokenOut(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            is_new_user=False,
            has_pin=True,
        )
    )


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=SuccessResponse[RefreshOut],
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
    description=(
        "Reads refresh token from httpOnly cookie. "
        "Old refresh token is revoked. New refresh token is set in cookie."
    ),
)
async def refresh_token(
    db: DBSession,
    response: Response,
    agrios_refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> SuccessResponse[RefreshOut]:
    if not agrios_refresh_token:
        from app.exceptions import UnauthenticatedException
        raise UnauthenticatedException("No refresh token found.")

    new_access, new_raw_refresh, new_expiry = await auth_service.refresh_token(
        db, agrios_refresh_token
    )

    _set_refresh_cookie(response, new_raw_refresh, new_expiry)

    return SuccessResponse(
        data=RefreshOut(
            access_token=new_access,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        )
    )


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Revoke current session",
)
async def logout(
    db: DBSession,
    current_user: CurrentUser,
    response: Response,
    agrios_refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> SuccessResponse[dict]:
    await auth_service.logout(db, agrios_refresh_token)
    _clear_refresh_cookie(response)
    return SuccessResponse(data={"message": "Logged out successfully"})


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=SuccessResponse[UserOut],
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def get_me(current_user: CurrentUser) -> SuccessResponse[UserOut]:
    return SuccessResponse(data=UserOut.model_validate(current_user))


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

@router.patch(
    "/me",
    response_model=SuccessResponse[UserOut],
    status_code=status.HTTP_200_OK,
    summary="Update current user profile (name, language, notification prefs)",
)
async def update_me(
    body: UserUpdateIn,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[UserOut]:
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.language is not None:
        current_user.language = body.language
    if body.sms_notifications_enabled is not None:
        meta = dict(current_user.metadata_ or {})
        meta["sms_notifications_enabled"] = body.sms_notifications_enabled
        current_user.metadata_ = meta
    await db.flush()
    return SuccessResponse(data=UserOut.model_validate(current_user))
