"""
AGRIOS — Authentication & Identity Models
Covers Migrations 001-005:
  001: roles
  002: users
  003: user_roles
  004: otp_requests
  005: sessions
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase


# ── Migration 001: Roles ──────────────────────────────────────────────────────

class Role(AGRIOSBase):
    """
    8 platform roles. Seeded at migration time. Not user-created.
    Role keys match the Engineering Constitution RBAC matrix.
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Role key: super_admin, platform_admin, enterprise_owner, farm_owner, farm_manager, vet_consultant, farm_worker, viewer",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_platform_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True for super_admin and platform_admin — not assignable to a farm",
    )

    # Relationships
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


# ── Migration 002: Users ──────────────────────────────────────────────────────

class User(AGRIOSBase):
    """
    AGRIOS user account.
    Phone is primary identifier (Kenya-first, no email required).
    PIN is used for subsequent login after initial OTP verification.
    """

    __tablename__ = "users"

    phone: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="E.164 (+254...). Optional secondary identifier since Phase 2 — email is primary.",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        comment="Primary account identifier since Phase 2 (nullable only for legacy phone-only rows).",
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="bcrypt hash of the account password. NULL for OAuth-only accounts (e.g. Google).",
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True once the user confirms their email via a verification token.",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set on password set/reset. Used to invalidate sessions issued earlier.",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    pin_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="bcrypt hash of 4-6 digit PIN. NULL until user completes PIN setup.",
    )
    language: Mapped[str] = mapped_column(
        String(5),
        default="en",
        nullable=False,
        comment="Preferred UI language: en | sw",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ai_queries_used_this_month: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Resets on 1st of each month via background job",
    )

    # Relationships
    # UserRole has two FKs to users (user_id, assigned_by); pin the join to
    # user_id so this collection is unambiguous (assigned_by is audit-only).
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )
    otp_requests: Mapped[list["OTPRequest"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    identity_providers: Mapped[list["IdentityProvider"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_tokens: Mapped[list["EmailToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    def __repr__(self) -> str:
        return f"<User {self.email or self.phone}>"


# ── Migration 003: User Roles ─────────────────────────────────────────────────

class UserRole(AGRIOSBase):
    """
    Junction table: connects users to roles, optionally scoped to a farm.
    Platform-level roles (super_admin, platform_admin) have farm_id = NULL.
    Farm-level roles must have farm_id set (FK added in Sprint 2 migration).

    Constraint: one role per user per farm (or per platform for NULL farm_id).
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "farm_id",
            name="uq_user_roles_user_farm",
            comment="One role per user per farm. NULL farm_id = platform-level role.",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # farm_id is UUID without FK constraint here.
    # FK to farms.id is added in Sprint 2 Migration 008.
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="NULL for platform roles. Set in Sprint 2 when farms table exists.",
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who granted this role. NULL if self-assigned at registration.",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="user_roles",
        foreign_keys=[user_id],
    )
    role: Mapped["Role"] = relationship(
        back_populates="user_roles",
    )

    def __repr__(self) -> str:
        return f"<UserRole user={self.user_id} role={self.role_id} farm={self.farm_id}>"


# ── Migration 004: OTP Requests ───────────────────────────────────────────────

class OTPRequest(AGRIOSBase):
    """
    Tracks OTP generation and verification attempts.
    Rate limiting rules (Engineering Constitution):
      - Max 3 wrong attempts per OTP before lock
      - Max 3 OTP requests per phone per 10 minutes
      - OTP expires after 10 minutes
    """

    __tablename__ = "otp_requests"

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL if user does not yet exist (first registration)",
    )
    code_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash of the 6-digit OTP code",
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of verification attempts. Locked at 3.",
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        back_populates="otp_requests",
    )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_locked(self) -> bool:
        from app.config import settings
        return self.attempts >= settings.OTP_MAX_ATTEMPTS

    def __repr__(self) -> str:
        return f"<OTPRequest phone={self.phone} attempts={self.attempts}>"


# ── Migration 005: Sessions ───────────────────────────────────────────────────

class Session(AGRIOSBase):
    """
    JWT refresh token sessions.
    Each successful OTP or PIN login creates a session.
    Refresh tokens rotate on every use (old token invalidated, new one issued).
    """

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="bcrypt hash of the refresh token. Raw token is never stored.",
    )
    token_lookup: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
        comment=(
            "SHA-256 hex of the raw refresh token for O(1) indexed lookup on refresh "
            "(Phase 2 email sessions). NULL for legacy OTP/PIN sessions, which fall back "
            "to the bcrypt scan."
        ),
    )
    device_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User-Agent string for device identification",
    )
    device_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        comment="Human-readable device label parsed from the User-Agent (e.g. 'Chrome on Windows').",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6 address",
    )
    remember_me: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True gives a long-lived refresh token; False a short session.",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Updated on each refresh; powers the device/session management screen.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when token is used for rotation or explicit logout",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="sessions",
    )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_revoked

    def revoke(self) -> None:
        self.revoked_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<Session user={self.user_id} valid={self.is_valid}>"


# ── Migration 033: Identity Providers (generic OAuth/SSO) ─────────────────────

class IdentityProvider(AGRIOSBase):
    """
    A federated identity linked to an AGRIOS account.

    Identity-first architecture: one AGRIOS user may authenticate through many
    providers (Google now; Apple / Microsoft / GitHub / SSO later) — each adds a
    row here, never a schema change. Account linking matches by verified email so
    signing in with a new provider never creates a duplicate user.
    """

    __tablename__ = "identity_providers"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_identity_provider_subject",
            comment="One federated identity (provider + subject) maps to exactly one user.",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Provider key: 'google' (Phase 2). Extensible: apple | microsoft | github | sso.",
    )
    provider_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Stable subject id from the provider (e.g. Google 'sub'). Never reused.",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Email asserted by the provider at link time (may differ from account email).",
    )
    raw_profile: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw provider profile payload captured at link time (audit / future use).",
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="identity_providers")

    def __repr__(self) -> str:
        return f"<IdentityProvider {self.provider}:{self.provider_user_id}>"


# ── Migration 034: Email Tokens (verify / reset / change-email) ───────────────

EMAIL_TOKEN_TYPES = ("verify_email", "password_reset", "change_email")


class EmailToken(AGRIOSBase):
    """
    Single-use, expiring token delivered by email.

    The raw token is emailed to the user; only its SHA-256 (`token_lookup`) is
    stored, so consuming a token is a single indexed query and the raw value is
    never persisted. Covers email verification, password reset, and change-email
    confirmation.
    """

    __tablename__ = "email_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="verify_email | password_reset | change_email",
    )
    token_lookup: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex of the raw token. The raw token is never stored.",
    )
    new_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Target address for a change_email token; NULL otherwise.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set the moment the token is redeemed. A consumed token is dead.",
    )
    requested_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="email_tokens")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_consumed

    def __repr__(self) -> str:
        return f"<EmailToken {self.token_type} user={self.user_id} valid={self.is_valid}>"
