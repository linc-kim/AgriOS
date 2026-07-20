"""
Greena — Auth Endpoints (API v1)
Endpoints are thin. All logic is in AuthService.
Refresh token is always set as an httpOnly cookie — never in the response body.
Sprint 9: PATCH /auth/me extended with sms_notifications_enabled.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.config import settings
from app.dependencies import CurrentUser, DBSession
from app.schemas.auth import (
    EmailLoginIn,
    EmailSignupIn,
    EmailVerifyIn,
    ForgotPasswordIn,
    OTPRequestIn,
    OTPRequestOut,
    OTPVerifyIn,
    PINSetIn,
    PINVerifyIn,
    RefreshOut,
    ResendVerificationIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
    UserUpdateIn,
)
from app.schemas.base import SuccessResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Renamed from "agrios_refresh_token" during the Greena branding pass. The
# cookie name is user-visible, and changing it makes every previously issued
# cookie unreadable — every session dies. Done before launch, while the user
# table is empty, because it is free now and costs a forced logout of the entire
# user base at any later date.
REFRESH_COOKIE_NAME = "greena_refresh_token"


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


def _client_ip(request: Request) -> str | None:
    """Client IP, honouring a single proxy hop via X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ── POST /auth/signup ─────────────────────────────────────────────────────────

@router.post(
    "/signup",
    response_model=SuccessResponse[TokenOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account with email and password",
    description=(
        "Creates the identity and signs the user in. Organization and farm are "
        "created during onboarding. In development-auth mode the email is treated "
        "as verified immediately (no verification email required)."
    ),
)
async def signup(
    body: EmailSignupIn,
    db: DBSession,
    response: Response,
    request: Request,
) -> SuccessResponse[TokenOut]:
    user, access_token, raw_refresh, refresh_expiry = await auth_service.signup_email(
        db,
        body.email,
        body.password,
        full_name=body.full_name,
        remember_me=body.remember_me,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, raw_refresh, refresh_expiry)
    return SuccessResponse(
        data=TokenOut(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            is_new_user=True,
            has_pin=user.pin_hash is not None,
        )
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=SuccessResponse[TokenOut],
    status_code=status.HTTP_200_OK,
    summary="Log in with email and password",
)
async def login(
    body: EmailLoginIn,
    db: DBSession,
    response: Response,
    request: Request,
) -> SuccessResponse[TokenOut]:
    user, access_token, raw_refresh, refresh_expiry = await auth_service.login_email(
        db,
        body.email,
        body.password,
        remember_me=body.remember_me,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, raw_refresh, refresh_expiry)
    return SuccessResponse(
        data=TokenOut(
            access_token=access_token,
            expires_in=settings.JWT_EXPIRE_MINUTES * 60,
            is_new_user=False,
            has_pin=user.pin_hash is not None,
        )
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
    greena_refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> SuccessResponse[RefreshOut]:
    if not greena_refresh_token:
        from app.exceptions import UnauthenticatedException
        raise UnauthenticatedException("No refresh token found.")

    new_access, new_raw_refresh, new_expiry = await auth_service.refresh_token(
        db, greena_refresh_token
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
    greena_refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> SuccessResponse[dict]:
    await auth_service.logout(db, greena_refresh_token)
    _clear_refresh_cookie(response)
    return SuccessResponse(data={"message": "Logged out successfully"})


# ── POST /auth/logout-all ─────────────────────────────────────────────────────

@router.post(
    "/logout-all",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Revoke every active session (log out everywhere)",
)
async def logout_all(
    db: DBSession,
    current_user: CurrentUser,
    response: Response,
) -> SuccessResponse[dict]:
    count = await auth_service.logout_all(db, current_user.id)
    _clear_refresh_cookie(response)
    return SuccessResponse(data={"message": f"Logged out of {count} session(s)."})


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


# ── Email verification ────────────────────────────────────────────────────────

@router.post(
    "/verify-email",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Confirm an email address from an emailed link",
)
async def verify_email(
    body: EmailVerifyIn,
    request: Request,
    db: DBSession,
) -> SuccessResponse[dict]:
    """Redeem a verification token. Single-use; expires per EMAIL_VERIFY_TOKEN_HOURS."""
    user = await auth_service.verify_email(db, body.token, ip=_client_ip(request))
    return SuccessResponse(data={"email_verified": True, "email": user.email})


@router.post(
    "/resend-verification",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Send a fresh verification link",
)
async def resend_verification(
    body: ResendVerificationIn,
    request: Request,
    db: DBSession,
) -> SuccessResponse[dict]:
    """
    Always reports success.

    Confirming whether an address is registered would make this endpoint an
    account-enumeration oracle, so the response is identical either way.
    """
    from sqlalchemy import func, select

    from app.models.auth import User

    result = await db.execute(
        select(User).where(
            func.lower(User.email) == body.email, User.deleted_at.is_(None)
        )
    )
    user = result.scalar_one_or_none()
    if user is not None and not user.email_verified:
        await auth_service.send_verification_email(db, user, ip=_client_ip(request))
        await db.commit()

    return SuccessResponse(
        data={"sent": True, "detail": "If that address has an unverified account, a link is on its way."}
    )


# ── Password reset ────────────────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Request a password reset link",
)
async def forgot_password(
    body: ForgotPasswordIn,
    request: Request,
    db: DBSession,
) -> SuccessResponse[dict]:
    """Always reports success — see resend_verification for why."""
    await auth_service.request_password_reset(db, body.email, ip=_client_ip(request))
    return SuccessResponse(
        data={"sent": True, "detail": "If that address has an account, a reset link is on its way."}
    )


@router.post(
    "/reset-password",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Set a new password from a reset link",
)
async def reset_password(
    body: ResetPasswordIn,
    request: Request,
    response: Response,
    db: DBSession,
) -> SuccessResponse[dict]:
    """
    Consume the token and set the password.

    Every existing session is revoked — a reset is what someone does when they
    think the account is compromised, so an attacker's session must not survive
    it. The caller's refresh cookie is cleared for the same reason.
    """
    user = await auth_service.reset_password(
        db, body.token, body.new_password, ip=_client_ip(request)
    )
    _clear_refresh_cookie(response)
    return SuccessResponse(
        data={"password_reset": True, "email": user.email, "sessions_revoked": True}
    )
