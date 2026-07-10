"""
Greena — FastAPI Application Entry Point
The app is configured here. Business logic lives in services, not here.

Sprint 7: APScheduler lifespan added for background jobs.
Sprint 10: SecurityHeadersMiddleware added for production hardening.
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.api.v1.router import api_router
from app.config import settings
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, TimingMiddleware
from app.exceptions import register_exception_handlers

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.is_development else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Sentry ────────────────────────────────────────────────────────────────────

if settings.SENTRY_DSN and not settings.is_development:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.2,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )
    logger.info("Sentry initialised")


# ── Lifespan (APScheduler) ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Starts APScheduler on startup, stops it on shutdown.
    AD-13 (Frozen): APScheduler embedded in FastAPI handles background jobs in V1.
    """
    from app.services.scheduler import start_scheduler, stop_scheduler

    scheduler = start_scheduler()
    logger.info("Greena background scheduler started")

    yield  # App runs here

    stop_scheduler(scheduler)
    logger.info("Greena background scheduler stopped")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Greena API",
    description="Agricultural Operating System — API v1",
    version=settings.VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Middleware (order matters — applied bottom-up) ────────────────────────────
# Starlette applies middleware in reverse registration order (last registered = outermost).
# Order here (innermost first): Timing → RequestID → Security → CORS
# Result (outermost first):     CORS → Security → RequestID → Timing

app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────

register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# ── Health Check (not versioned) ──────────────────────────────────────────────

@app.get("/health", tags=["Health"], include_in_schema=False)
async def health_check() -> JSONResponse:
    """
    Platform health endpoint.
    Railway uses this for deployment health checks.

    Returns HTTP 200 only when the database is reachable; returns HTTP 503
    when it is not, so Railway's health check correctly detects a degraded
    instance and does not route traffic to (or complete cutover to) a
    backend that cannot serve requests.
    """
    from sqlalchemy import text
    from app.database import AsyncSessionLocal

    db_status = "unknown"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error(f"Health check DB failure: {e}")

    healthy = db_status == "connected"
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if healthy else "degraded",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "db": db_status,
        },
    )


logger.info(f"Greena API started — {settings.ENVIRONMENT} — v{settings.VERSION}")
