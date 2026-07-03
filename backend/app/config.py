"""
AGRIOS — Application Configuration
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
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AGRIOS"
    VERSION: str = "1.0.0"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str

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

    # ── Africa's Talking ─────────────────────────────────────────────────
    AT_API_KEY: str = ""
    AT_USERNAME: str = ""
    AT_SENDER_ID: str = "AGRIOS"
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

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

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
