"""
Greena — Authentication Service
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
    hash_password,
    hash_secret,
    sha256_hex,
    validate_password_strength,
    verify_password,
    verify_secret,
)
from app.exceptions import (
    ConflictException,
    EmailNotVerifiedException,
    OTPExpiredException,
    OTPInvalidException,
    OTPMaxAttemptsException,
    RateLimitedException,
    UnauthenticatedException,
)
from app.models.auth import OTPRequest, Role, Session, User, UserRole
from app.services.audit_service import log_action
from app.services.sms_service import send_sms

logger = logging.getLogger(__name__)

# Precomputed Argon2 hash used to equalise timing when an email is not found,
# so login response time doesn't reveal whether an account exists.
_DUMMY_PASSWORD_HASH = hash_password("greena-timing-equalizer")


def _device_label(user_agent: str | None) -> str | None:
    """Best-effort friendly device label from a User-Agent (for session mgmt)."""
    if not user_agent:
        return None
    browser = next(
        (b for b in ("Edg", "Chrome", "Firefox", "Safari") if b in user_agent), None
    )
    browser = {"Edg": "Edge"}.get(browser, browser)
    os_name = next(
        (
            name
            for token, name in (
                ("Windows", "Windows"),
                ("Mac OS", "macOS"),
                ("iPhone", "iPhone"),
                ("iPad", "iPad"),
                ("Android", "Android"),
                ("Linux", "Linux"),
            )
            if token in user_agent
        ),
        None,
    )
    label = " on ".join([p for p in (browser, os_name) if p])
    return label or None


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
        message = (
            f"Your Greena verification code is {raw_code}. "
            f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes."
        )
        sms_sent = await send_sms(phone, message)
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

        # Fast path: O(1) indexed lookup for Phase 2 sessions.
        matched = await db.execute(
            select(Session).where(
                Session.token_lookup == sha256_hex(raw_refresh_token),
                Session.revoked_at.is_(None),
            )
        )
        session = matched.scalar_one_or_none()
        if session:
            session.revoke()
            return

        # Fallback: legacy OTP/PIN sessions (bcrypt only, no token_lookup).
        sessions_result = await db.execute(
            select(Session).where(
                Session.revoked_at.is_(None), Session.token_lookup.is_(None)
            )
        )
        for legacy in sessions_result.scalars():
            if verify_secret(raw_refresh_token, legacy.refresh_token_hash):
                legacy.revoke()
                break

    async def logout_all(self, db: AsyncSession, user_id: UUID) -> int:
        """Revoke every active session for a user ('log out everywhere'). Returns count."""
        result = await db.execute(
            select(Session).where(
                Session.user_id == user_id, Session.revoked_at.is_(None)
            )
        )
        count = 0
        for session in result.scalars():
            session.revoke()
            count += 1
        await db.flush()
        return count

    # ── Email / Password Auth (Phase 2) ───────────────────────────────────────

    async def _create_session(
        self,
        db: AsyncSession,
        user: User,
        *,
        remember_me: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, datetime]:
        """
        Issue an access token and a rotating refresh session.
        Returns (access_token, raw_refresh_token, refresh_expiry).
        Stores both the bcrypt hash (legacy compat) and a SHA-256 token_lookup
        so refresh/logout resolve with a single indexed query.
        """
        access_token = create_access_token(subject=str(user.id))
        raw_refresh, hashed_refresh, _ = create_refresh_token()
        ttl_days = settings.REFRESH_TOKEN_EXPIRE_DAYS if remember_me else 1
        expiry = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        session = Session(
            user_id=user.id,
            refresh_token_hash=hashed_refresh,
            token_lookup=sha256_hex(raw_refresh),
            remember_me=remember_me,
            device_info=user_agent,
            device_name=_device_label(user_agent),
            ip_address=ip,
            last_used_at=datetime.now(timezone.utc),
            expires_at=expiry,
        )
        db.add(session)
        await db.flush()
        return access_token, raw_refresh, expiry

    async def signup_email(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        *,
        full_name: str | None = None,
        remember_me: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str, datetime]:
        """
        Create an account from email + password and issue a session.

        Identity only — no organization/role/farm is created here (that happens in
        onboarding). In development-auth mode (REQUIRE_EMAIL_VERIFICATION=False) the
        email is marked verified immediately so the user can enter the app at once.
        """
        email = email.strip().lower()
        existing = await db.execute(
            select(User).where(
                func.lower(User.email) == email, User.deleted_at.is_(None)
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictException("An account with this email already exists.")

        validate_password_strength(password)

        now = datetime.now(timezone.utc)
        verified = not settings.REQUIRE_EMAIL_VERIFICATION
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            email_verified=verified,
            email_verified_at=now if verified else None,
            password_changed_at=now,
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
        await db.flush()

        access, raw_refresh, expiry = await self._create_session(
            db, user, remember_me=remember_me, ip=ip, user_agent=user_agent
        )
        await log_action(
            db,
            action="auth.signup",
            resource_type="user",
            user_id=user.id,
            ip_address=ip,
            user_agent=user_agent,
        )
        return user, access, raw_refresh, expiry

    async def login_email(
        self,
        db: AsyncSession,
        email: str,
        password: str,
        *,
        remember_me: bool = False,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str, datetime]:
        """Authenticate email + password and issue a session (enumeration-safe)."""
        email = email.strip().lower()
        result = await db.execute(
            select(User)
            .where(func.lower(User.email) == email, User.deleted_at.is_(None))
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
        )
        user = result.scalar_one_or_none()

        if user is None or not user.password_hash:
            # Equalise timing and return an identical error either way.
            verify_password(password, _DUMMY_PASSWORD_HASH)
            await log_action(
                db,
                action="auth.login_failed",
                resource_type="user",
                ip_address=ip,
                user_agent=user_agent,
            )
            raise UnauthenticatedException("Invalid email or password.")

        if not verify_password(password, user.password_hash):
            await log_action(
                db,
                action="auth.login_failed",
                resource_type="user",
                user_id=user.id,
                ip_address=ip,
                user_agent=user_agent,
            )
            raise UnauthenticatedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthenticatedException("This account has been deactivated.")

        if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
            raise EmailNotVerifiedException()

        user.last_login_at = datetime.now(timezone.utc)
        access, raw_refresh, expiry = await self._create_session(
            db, user, remember_me=remember_me, ip=ip, user_agent=user_agent
        )
        await log_action(
            db,
            action="auth.login",
            resource_type="user",
            user_id=user.id,
            ip_address=ip,
            user_agent=user_agent,
        )
        return user, access, raw_refresh, expiry


auth_service = AuthService()
