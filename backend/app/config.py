"""
Greena — Application Configuration
All environment variables are validated here at startup.
The app will not start if required variables are missing.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    SECRET_KEY: str
    # Comma-separated string, NOT list[str]: pydantic-settings JSON-decodes
    # complex-typed fields from env before validators run, which breaks a plain
    # comma-separated value. Parsed into a list via the allowed_origins property.
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Greena"
    VERSION: str = "1.0.0"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str

    # Connection pool, per worker process. The effective ceiling on the database
    # is (DB_POOL_SIZE + DB_MAX_OVERFLOW) × workers, plus one connection for the
    # scheduler advisory lock — size these against the provider's connection
    # cap, not the app's appetite. Supabase's free tier allows 60 in total, so
    # the defaults keep two workers well inside it (2 × 15 + 1 = 31).
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # TLS for the database connection.
    #
    # Managed Postgres is reached over the public internet, and providers
    # commonly *accept* plaintext rather than requiring TLS — Supabase's pooler
    # does. Without this the password and every row in transit are unencrypted,
    # so TLS is forced on for any non-local host.
    #
    # Supabase presents a self-signed chain, so certificate verification needs
    # their CA bundle: Project Settings → Database → SSL Configuration →
    # download, then point DATABASE_SSL_CA at the file to upgrade from
    # "encrypted" to "encrypted and authenticated". Without it the connection is
    # still encrypted against passive eavesdropping, but not authenticated
    # against an active man-in-the-middle.
    DATABASE_SSL: bool = True
    DATABASE_SSL_CA: str = ""

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        v = v.strip()
        """
        Railway and Supabase supply DATABASE_URL as:
          postgres://...          (Railway shorthand)
          postgresql://...        (standard psycopg2 scheme)

        SQLAlchemy 2.x async + asyncpg requires:
          postgresql+asyncpg://...

        This validator rewrites the scheme at startup so the caller
        never needs to remember — set DATABASE_URL to any valid
        postgres URL and it will be corrected automatically.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Already correct (postgresql+asyncpg://) or custom scheme — pass through
        return v

    # ── Authentication ───────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OTP configuration (locked in Engineering Constitution)
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 3
    OTP_MAX_REQUESTS_PER_PHONE: int = 3
    OTP_REQUEST_WINDOW_MINUTES: int = 10

    # ── Auth mode: development authentication ────────────────────────────
    # The permanent auth system ships with external verification gated OFF, so
    # signup/login/onboarding work with no SMTP/SMS/OTP/Google. Turn each flag
    # on to enable the corresponding production feature — no code changes.
    REQUIRE_EMAIL_VERIFICATION: bool = False
    ENABLE_GOOGLE_OAUTH: bool = False
    ENABLE_SMS_OTP: bool = False
    ENABLE_LOGIN_ALERTS: bool = False

    # ── Passwords ────────────────────────────────────────────────────────
    # Argon2id is the primary hasher (passphrase-friendly, no 72-byte cap).
    PASSWORD_MIN_LENGTH: int = 12

    # Email-token lifetimes (used once verification/reset are enabled).
    EMAIL_VERIFY_TOKEN_HOURS: int = 24
    PASSWORD_RESET_TOKEN_HOURS: int = 1

    # ── Google OAuth (only consulted when ENABLE_GOOGLE_OAUTH) ────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── Email provider (Zoho first; abstracted, dormant in dev mode) ──────
    EMAIL_PROVIDER: Literal["zoho", "resend", "ses", "sendgrid", "mailgun", "smtp", "console"] = "console"
    EMAIL_FROM: str = "Greena <no-reply@greena.app>"
    ZOHO_SMTP_HOST: str = "smtp.zoho.com"
    ZOHO_SMTP_PORT: int = 587
    ZOHO_SMTP_USER: str = ""
    ZOHO_SMTP_PASSWORD: str = ""

    # Public app URL for links in emails / OAuth redirects.
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Africa's Talking ─────────────────────────────────────────────────
    AT_API_KEY: str = ""
    AT_USERNAME: str = ""
    AT_SENDER_ID: str = "Greena"
    AT_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"

    # ── AI Providers ─────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"

    # AI context and quota (locked in Engineering Constitution)
    AI_CONTEXT_MAX_TOKENS: int = 8000
    AI_CALL_TIMEOUT_SECONDS: int = 15
    AI_RESPONSE_MAX_WORDS: int = 150

    # ── Monitoring ───────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Timezone ─────────────────────────────────────────────────────────
    TZ: str = "Africa/Nairobi"

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
