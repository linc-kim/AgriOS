"""
Greena — Application Configuration
All environment variables are validated here at startup.
The app will not start if required variables are missing.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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

    # ── Cookies ──────────────────────────────────────────────────────────
    # SameSite policy for the refresh cookie.
    #
    #   strict — the cookie is sent only on same-site requests. Correct and
    #            safest when the frontend and API share a registrable domain
    #            (app.greena.app + api.greena.app).
    #   none   — required when they do NOT. *.vercel.app and *.up.railway.app
    #            are each on the Public Suffix List, so a Vercel frontend
    #            calling a Railway API is cross-site and a strict cookie is
    #            never sent: refresh fails and every user is logged out when
    #            their access token expires.
    #
    # "none" forces Secure (browsers reject SameSite=None without it) and gives
    # up the browser's built-in CSRF protection for this cookie, so the refresh
    # endpoint additionally checks the Origin header against ALLOWED_ORIGINS.
    # Set back to "strict" once both sides sit on one domain.
    REFRESH_COOKIE_SAMESITE: Literal["strict", "lax", "none"] = "strict"

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

    # ── Email provider ────────────────────────────────────────────────────
    # "console" logs the message instead of sending — the development default,
    # so signup and password reset work with no credentials configured.
    # "smtp" sends over SMTP using the SMTP_* settings below (Gmail included).
    EMAIL_PROVIDER: Literal[
        "zoho", "resend", "ses", "sendgrid", "mailgun", "smtp", "console"
    ] = "console"
    EMAIL_FROM: str = "Greena <no-reply@greena.app>"

    # Generic SMTP. Defaults target Gmail, which requires an App Password —
    # a Google account password will not authenticate, and 2FA must be on to
    # create one. SMTP_USER is the full address the App Password belongs to.
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    # STARTTLS on 587 (Gmail's recommendation). Set False only for port 465,
    # which is implicit TLS instead.
    SMTP_STARTTLS: bool = True
    SMTP_TIMEOUT_SECONDS: int = 20

    # Legacy Zoho fields, retained so an existing configuration keeps working.
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
    # Gemini supports multiple keys for round-robin rotation + failover, managed
    # by the AI Provider Manager (Gate 4). GEMINI_API_KEY is the primary;
    # GEMINI_API_KEY_2 (and any GEMINI_API_KEY_3…) are registered alongside it.
    # GEMINI_API_KEYS (comma-separated) is an alternative that supplies several at
    # once. All are backend-only and must never reach the frontend (Doc 3 §17).
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEYS: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"

    # AI Provider Manager key-selection policy (Gate 4): how Gemini keys are
    # chosen across the pool. round_robin spreads load; primary sticks to the
    # lowest-index usable key; least_failures prefers the healthiest key.
    AI_KEY_ROUTING: Literal["round_robin", "primary", "least_failures"] = "round_robin"

    # AI context and quota (locked in Engineering Constitution)
    AI_CONTEXT_MAX_TOKENS: int = 8000
    AI_CALL_TIMEOUT_SECONDS: int = 15
    AI_RESPONSE_MAX_WORDS: int = 150

    # Deterministic AI response cache (Gate 4): identical prompts return the cached
    # completion for this many seconds. Keyed by the full prompt hash (which embeds
    # the farm-context snapshot, so it is tenant-safe); the offline fallback is
    # never cached. 0 disables it (default — opt in explicitly).
    AI_RESPONSE_CACHE_TTL_SECONDS: int = 0

    # ── PostHog (analytics / feature flags) — disabled by default ─────────────
    # Behind configuration: nothing is sent unless POSTHOG_ENABLED is true AND a
    # key is set. The project key is frontend-safe; never expose a personal API key.
    POSTHOG_ENABLED: bool = False
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://us.i.posthog.com"

    # ── Monitoring ───────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    # ── Timezone ─────────────────────────────────────────────────────────
    TZ: str = "Africa/Nairobi"

    @property
    def gemini_api_keys(self) -> list[str]:
        """
        All configured Gemini keys, de-duplicated, order-preserving.

        Sources, in order: GEMINI_API_KEY, GEMINI_API_KEY_2, then each entry of
        the comma-separated GEMINI_API_KEYS. Empty values are dropped, so an
        unconfigured slot simply reduces the pool rather than breaking rotation.
        """
        raw = [self.GEMINI_API_KEY, self.GEMINI_API_KEY_2, *self.GEMINI_API_KEYS.split(",")]
        seen: dict[str, None] = {}
        for key in raw:
            k = key.strip()
            if k:
                seen.setdefault(k, None)
        return list(seen)

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
