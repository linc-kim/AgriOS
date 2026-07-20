"""
Greena — Async Database Engine
Uses SQLAlchemy 2.x async with asyncpg driver.
Connection pooling is handled by SQLAlchemy; PgBouncer handles it at the Supabase level.
"""

import logging
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


def _connect_args() -> dict:
    """
    Force TLS on connections to a remote database.

    Managed Postgres is reached across the public internet and providers
    commonly accept plaintext instead of requiring TLS, so leaving this to the
    default means the credential and every row can travel unencrypted. Local
    development is exempt — there is no network to protect and no certificate
    to present.
    """
    if not settings.DATABASE_SSL:
        return {}

    host = (make_url(settings.DATABASE_URL).host or "").lower()
    if host in _LOCAL_HOSTS:
        return {}

    if settings.DATABASE_SSL_CA:
        # Encrypted *and* authenticated: the provider's CA is pinned, so an
        # active man-in-the-middle cannot present its own certificate.
        context = ssl.create_default_context(cafile=settings.DATABASE_SSL_CA)
        logger.info("Database TLS: verifying against %s", settings.DATABASE_SSL_CA)
    else:
        # Encrypted only. Supabase and friends present a self-signed chain that
        # public roots cannot verify; without their CA bundle the choice is
        # between unverified TLS and no TLS, and unverified TLS is strictly
        # better — it defeats passive interception on the path.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.warning(
            "Database TLS enabled without certificate verification. "
            "Set DATABASE_SSL_CA to the provider's CA bundle to authenticate the server."
        )

    return {"ssl": context}


# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args(),
    echo=settings.is_development,       # Log SQL in development only
    # Sized from settings so the pool can be tuned to the provider's connection
    # cap without a code change. See DB_POOL_SIZE in config.py for the maths.
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,                 # Verify connection health before use
    # Shorter than the default hour: managed Postgres (Supabase/PgBouncer) drops
    # idle connections server-side, and recycling first avoids handing a dead
    # connection to a request.
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,             # Don't expire objects after commit
    autocommit=False,
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.
    Always yields a session and closes it after the request completes.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
