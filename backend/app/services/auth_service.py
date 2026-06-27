"""
AGRIOS — Authentication Service
All auth business logic lives here. Endpoints are thin; services are fat.
Enforces all rate limits and security rules from the Engineering Constitution.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_otp_code,
    get_otp_expiry,
    hash_secret,
    verify_secret,
)
from app.exceptions import (
    OTPExpiredException,
    OTPInvalidException,
    OTPMaxAttemptsException,
    RateLimitedException,
    UnauthenticatedException,
)
from app.models.auth import OTPRequest, Role, Session, User, UserRole
from app.services.sms_service import sms_service

logger = logging.getLogger(__name__)


class AuthService:
    """
    Implements all authentication flows:
      1. OTP request (rate-limited, SMS delivery)
      2. OTP verification (attempt-limited, issues JWT)
      3. PIN setup
      4. PIN login (issues JWT)
      5. Token refresh (rotation)
      6. Logout (session revocation)
    """

    # ── OTP Request ───────────────────────────────────────────────────────────

    async def request_otp(self, db: AsyncSession, phone: str) -> OTPRequest:
        """
        Rate limit: max 3 OTP requests per phone per 10 minutes.
        Generates a 6-digit code, stores its hash, sends SMS.
        """
        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=settings.OTP_REQUEST_WINDOW_MINUTES
        )

        # Count recent requests for this phone
        recent_count_result = await db.execute(
            select(func.count(OTPRequest.id)).where(
                and_(
                    OTPRequest.phone == phone,
                    OTPRequest.created_at >= window_start,
                    OTPRequest.deleted_at.is_(None),
                )
            )
        )
        recent_count = recent_count_result.scalar_one()

        if recent_count >= settings.OTP_MAX_REQUESTS_PER_PHONE:
            raise RateLimitedException(
                f"Too many OTP requests. Please wait {settings.OTP_REQUEST_WINDOW_MINUTES} minutes."
            )

        # Look up or create user
        user_result = await db.execute(
            select(User).where(
                User.phone == phone,
                User.deleted_at.is_(None),
            )
        )
        user = user_result.scalar_one_or_none()

        # Generate and hash OTP
        raw_code = generate_otp_code()
        code_hash = hash_secret(raw_code)

        otp_request = OTPRequest(
            phone=phone,
            user_id=user.id if user else None,
            code_hash=code_hash,
            expires_at=get_otp_expiry(),
        )
        db.add(otp_request)
        await db.flush()

        # Send SMS (non-blocking — failure is logged, not raised)
        sms_sent = await sms_service.send_otp(phone, raw_code)
        if not sms_sent:
            logger.warning(f"OTP SMS delivery failed for {phone}. OTP still created.")

        return otp_request

    # ── OTP Verification ──────────────────────────────────────────────────────

    async def verify_otp(
        self, db: AsyncSession, phone: str, code: str
    ) -> tuple[User, str, str, datetime, bool]:
        """
        Verify an OTP code.
        Returns: (user, access_token, refresh_token, refresh_expiry, is_new_user)
        Raises: OTPExpiredException, OTPInvalidException, OTPMaxAttemptsException
        """
        # Find the most recent unverified OTP for this phone
        otp_result = await db.execute(
            select(OTPRequest)
            .where(
                and_(
                    OTPRequest.phone == phone,
                    OTPRequest.is_verified == False,
                    OTPRequest.deleted_at.is_(None),
                )
            )
            .order_by(OTPRequest.created_at.desc())
            .limit(1)
        )
        otp = otp_result.scalar_one_or_none()

        if not otp:
            raise OTPExpiredException()

        if otp.is_expired:
            raise OTPExpiredException()

        if otp.is_locked:
            raise OTPMaxAttemptsException()

        # Verify the code
        if not verify_secret(code, otp.code_hash):
            otp.attempts += 1
            await db.flush()
            remaining = settings.OTP_MAX_ATTEMPTS - otp.attempts
            if otp.is_locked:
                raise OTPMaxAttemptsException()
            raise OTPInvalidException(remaining)

        # Mark OTP as verified
        otp.is_verified = True

        # Get or create user
        is_new_user = False
        user_result = await db.execute(
            select(User)
            .where(User.phone == phone, User.deleted_at.is_(None))
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
        )
        user = user_result.scalar_one_or_none()

        if not user:
            is_new_user = True
            user = User(phone=phone, is_phone_verified=True)
            db.add(user)
            await db.flush()

            # Assign default farm_owner role (no farm yet — farm_id=NULL)
            farm_owner_result = await db.execute(
                select(Role).where(Role.name == "farm_owner")
            )
            farm_owner_role = farm_owner_result.scalar_one_or_none()
            if farm_owner_role:
                user_role = UserRole(
                    user_id=user.id,
                    role_id=farm_owner_role.id,
                    farm_id=None,
                )
                db.add(user_role)
        else:
            user.is_phone_verified = True
            user.last_login_at = datetime.now(timezone.utc)

        # Issue tokens
        access_token = create_access_token(subject=str(user.id))
        raw_refresh, hashed_refresh, refresh_expiry = create_refresh_token()

        session = Session(
            user_id=user.id,
            refresh_token_hash=hashed_refresh,
            expires_at=refresh_expiry,
        )
        db.add(session)
        await db.flush()

        return user, access_token, raw_refresh, refresh_expiry, is_new_user

    # ── PIN Management ────────────────────────────────────────────────────────

    async def set_pin(self, db: AsyncSession, user: User, pin: str) -> User:
        """Set or update a user's PIN."""
        user.pin_hash = hash_secret(pin)
        await db.flush()
        return user

    async def verify_pin(
        self, db: AsyncSession, phone: str, pin: str
    ) -> tuple[User, str, str, datetime]:
        """
        PIN login for returning users.
        Returns: (user, access_token, refresh_token, refresh_expiry)
        """
        user_result = await db.execute(
            select(User)
            .where(User.phone == phone, User.deleted_at.is_(None))
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            raise UnauthenticatedException("Invalid phone or PIN.")

        if not user.pin_hash:
            raise UnauthenticatedException("PIN not set. Please log in with OTP first.")

        if not verify_secret(pin, user.pin_hash):
            raise UnauthenticatedException("Invalid phone or PIN.")

        user.last_login_at = datetime.now(timezone.utc)

        # Issue tokens
        access_token = create_access_token(subject=str(user.id))
        raw_refresh, hashed_refresh, refresh_expiry = create_refresh_token()

        session = Session(
            user_id=user.id,
            refresh_token_hash=hashed_refresh,
            expires_at=refresh_expiry,
        )
        db.add(session)
        await db.flush()

        return user, access_token, raw_refresh, refresh_expiry

    # ── Token Refresh ─────────────────────────────────────────────────────────

    async def refresh_token(
        self, db: AsyncSession, raw_refresh_token: str
    ) -> tuple[str, str, datetime]:
        """
        Rotate refresh token. Old token is revoked, new tokens are issued.
        Returns: (new_access_token, new_raw_refresh_token, new_expiry)
        """
        # Find all valid sessions and check against the provided token
        sessions_result = await db.execute(
            select(Session).where(
                Session.revoked_at.is_(None),
                Session.expires_at > datetime.now(timezone.utc),
            )
        )
        sessions = sessions_result.scalars().all()

        matched_session = None
        for session in sessions:
            if verify_secret(raw_refresh_token, session.refresh_token_hash):
                matched_session = session
                break

        if not matched_session:
            raise UnauthenticatedException("Invalid or expired refresh token.")

        # Revoke old session
        matched_session.revoke()

        # Issue new tokens
        access_token = create_access_token(subject=str(matched_session.user_id))
        raw_refresh, hashed_refresh, refresh_expiry = create_refresh_token()

        new_session = Session(
            user_id=matched_session.user_id,
            refresh_token_hash=hashed_refresh,
            expires_at=refresh_expiry,
        )
        db.add(new_session)
        await db.flush()

        return access_token, raw_refresh, refresh_expiry

    # ── Logout ────────────────────────────────────────────────────────────────

    async def logout(self, db: AsyncSession, raw_refresh_token: str | None) -> None:
        """Revoke the current session's refresh token."""
        if not raw_refresh_token:
            return

        sessions_result = await db.execute(
            select(Session).where(Session.revoked_at.is_(None))
        )
        for session in sessions_result.scalars():
            if verify_secret(raw_refresh_token, session.refresh_token_hash):
                session.revoke()
                break


auth_service = AuthService()
