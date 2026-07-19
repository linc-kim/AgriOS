"""
Greena — Diagnostics Service (Module 11).

A set of independent checks that answer "is this instance healthy, and if not,
what exactly is wrong?". Each returns (passed, detail) where the detail names
the remedy, not just the symptom.

Two entry points:

  run_startup_validation()  — called from the FastAPI lifespan. Refuses to start
                              a production instance whose configuration is
                              unsafe; warns but continues in development.
  run_diagnostics(db)       — the full sweep behind GET /production/diagnostics.
"""

import asyncio
import logging
import os
import shutil
import time
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)


class StartupValidationError(RuntimeError):
    """Raised when configuration is unsafe to serve production traffic."""


# ── Individual checks ─────────────────────────────────────────────────────────

async def check_database(db: AsyncSession) -> tuple[bool, str]:
    """Round-trip a trivial query, and report how long it took."""
    try:
        start = time.perf_counter()
        await db.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - start) * 1000
        return True, f"Reachable ({elapsed_ms:.1f} ms round trip)."
    except Exception as exc:
        return False, f"Unreachable: {exc}"


async def check_schema(db: AsyncSession) -> tuple[bool, str]:
    """
    Confirm the core tables exist and are queryable.

    Catches the case where migrations claim to be at head but the schema does
    not actually match the code — which is precisely how the ai_messages
    metadata bug reached production.
    """
    required = [
        "users", "organizations", "farms", "flocks", "daily_logs",
        "expenses", "revenue_records", "backups", "release_records",
    ]
    try:
        result = await db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        ))
        present = {row[0] for row in result}
        missing = [t for t in required if t not in present]
        if missing:
            return False, f"Missing tables: {', '.join(missing)}. Run 'alembic upgrade head'."
        return True, f"All {len(required)} core tables present ({len(present)} total)."
    except Exception as exc:
        return False, f"Could not inspect schema: {exc}"


def check_environment() -> tuple[bool, str]:
    """
    Validate configuration for the target environment.

    Development is permissive by design — the app ships with external
    verification gated off so it runs with no SMTP/SMS credentials. Production
    is not: a weak secret or a wildcard CORS origin is a genuine vulnerability,
    so those are failures rather than warnings.
    """
    problems: list[str] = []

    if settings.is_production:
        if len(settings.SECRET_KEY) < 32:
            problems.append("SECRET_KEY is shorter than 32 characters")
        if len(settings.JWT_SECRET) < 32:
            problems.append("JWT_SECRET is shorter than 32 characters")
        if settings.SECRET_KEY == settings.JWT_SECRET:
            problems.append("SECRET_KEY and JWT_SECRET are identical")
        for weak in ("changeme", "secret", "dev", "test", "password"):
            if settings.SECRET_KEY.lower().startswith(weak):
                problems.append("SECRET_KEY looks like a placeholder value")
                break
        if "*" in settings.allowed_origins:
            problems.append("ALLOWED_ORIGINS contains a wildcard")
        if not settings.allowed_origins:
            problems.append("ALLOWED_ORIGINS is empty — the frontend cannot call the API")
        for origin in settings.allowed_origins:
            if origin.startswith("http://") and "localhost" not in origin and "127.0.0.1" not in origin:
                problems.append(f"ALLOWED_ORIGINS contains a plaintext origin: {origin}")
        if not settings.SENTRY_DSN:
            problems.append("SENTRY_DSN is unset — errors will not be tracked")

    if problems:
        return False, "; ".join(problems)

    scope = "production" if settings.is_production else settings.ENVIRONMENT
    return True, f"Configuration valid for {scope}."


def check_disk() -> tuple[bool, str]:
    """Warn before the disk fills. Below 10% free is a failure."""
    try:
        usage = shutil.disk_usage(os.getcwd())
        free_pct = usage.free / usage.total * 100
        detail = (
            f"{free_pct:.1f}% free "
            f"({usage.free / 1_073_741_824:.1f} GB of {usage.total / 1_073_741_824:.1f} GB)."
        )
        return free_pct >= 10.0, detail
    except Exception as exc:
        return True, f"Could not determine disk usage: {exc}"


def check_ai_providers() -> tuple[bool, str]:
    """
    Report which AI providers are configured.

    Never a failure: ARIA falls back to the offline model, so an instance with
    no AI keys is degraded rather than broken.
    """
    configured = []
    if settings.GEMINI_API_KEY:
        configured.append("gemini")
    if settings.CLAUDE_API_KEY:
        configured.append("claude")
    if configured:
        return True, f"Configured: {', '.join(configured)} (offline fallback always available)."
    return True, "No API keys set — ARIA will use the offline model only."


def check_integrations() -> tuple[bool, str]:
    """Report the state of the optional external channels."""
    states = [
        f"email={settings.EMAIL_PROVIDER}",
        f"sms={'on' if settings.ENABLE_SMS_OTP else 'off'}",
        f"google_oauth={'on' if settings.ENABLE_GOOGLE_OAUTH else 'off'}",
        f"email_verification={'on' if settings.REQUIRE_EMAIL_VERIFICATION else 'off'}",
    ]
    return True, ", ".join(states)


async def check_migrations(db: AsyncSession) -> tuple[bool, str]:
    from app.services import release_service

    return await release_service.check_migrations(db)


async def check_background_jobs(db: AsyncSession) -> tuple[bool, str]:
    """Report recent background job failures, which are otherwise invisible."""
    from app.models.admin_platform import BackgroundJob

    try:
        result = await db.execute(
            select(BackgroundJob.status, func.count(BackgroundJob.id))
            .where(BackgroundJob.deleted_at.is_(None))
            .group_by(BackgroundJob.status)
        )
        counts = {status: count for status, count in result}
        failed = counts.get("failed", 0)
        total = sum(counts.values())
        if not total:
            return True, "No background jobs have run yet."
        if failed:
            return False, f"{failed} of {total} recorded jobs failed."
        return True, f"{total} recorded jobs, none failed."
    except Exception as exc:
        return True, f"Could not read job history: {exc}"


# ── Aggregate sweeps ──────────────────────────────────────────────────────────

async def run_diagnostics(db: AsyncSession) -> dict:
    """
    The full sweep behind GET /production/diagnostics.

    Checks are grouped so the UI can render them by area, and each carries a
    severity: a failing "critical" check means the instance should not serve
    traffic; a failing "warning" check means attention, not evacuation.
    """
    started = time.perf_counter()

    db_ok, db_detail = await check_database(db)
    schema_ok, schema_detail = await check_schema(db)
    mig_ok, mig_detail = await check_migrations(db)
    env_ok, env_detail = check_environment()
    disk_ok, disk_detail = check_disk()
    ai_ok, ai_detail = check_ai_providers()
    integ_ok, integ_detail = check_integrations()
    jobs_ok, jobs_detail = await check_background_jobs(db)

    checks = [
        {"name": "database", "group": "infrastructure", "severity": "critical", "passed": db_ok, "detail": db_detail},
        {"name": "schema", "group": "infrastructure", "severity": "critical", "passed": schema_ok, "detail": schema_detail},
        {"name": "migrations", "group": "infrastructure", "severity": "critical", "passed": mig_ok, "detail": mig_detail},
        {"name": "environment", "group": "configuration", "severity": "critical", "passed": env_ok, "detail": env_detail},
        {"name": "disk", "group": "infrastructure", "severity": "warning", "passed": disk_ok, "detail": disk_detail},
        {"name": "ai_providers", "group": "integrations", "severity": "info", "passed": ai_ok, "detail": ai_detail},
        {"name": "integrations", "group": "integrations", "severity": "info", "passed": integ_ok, "detail": integ_detail},
        {"name": "background_jobs", "group": "runtime", "severity": "warning", "passed": jobs_ok, "detail": jobs_detail},
    ]

    critical_failed = [c for c in checks if not c["passed"] and c["severity"] == "critical"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]

    if critical_failed:
        status = "unhealthy"
    elif warnings:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "passed_count": sum(1 for c in checks if c["passed"]),
        "failed_count": sum(1 for c in checks if not c["passed"]),
        "critical_failures": [c["name"] for c in critical_failed],
        "checks": checks,
    }


async def run_startup_validation() -> None:
    """
    Validate the instance at boot, before it accepts traffic.

    In production an invalid configuration raises, so the process dies and the
    orchestrator does not route to it — failing loudly at boot beats serving
    requests with a placeholder signing key. In development the same problems
    are logged and startup continues, so local work is never blocked.
    """
    env_ok, env_detail = check_environment()
    disk_ok, disk_detail = check_disk()

    if not env_ok:
        message = f"Environment validation failed: {env_detail}"
        if settings.is_production:
            raise StartupValidationError(message)
        logger.warning("%s (continuing — not production)", message)
    else:
        logger.info("Environment validation passed: %s", env_detail)

    if not disk_ok:
        logger.warning("Disk check: %s", disk_detail)

    # The database may briefly be unavailable while a dependent service starts,
    # so it is retried rather than treated as fatal on the first attempt.
    from app.database import AsyncSessionLocal

    for attempt in range(1, 4):
        try:
            async with AsyncSessionLocal() as session:
                ok, detail = await check_database(session)
                if ok:
                    logger.info("Database validation passed: %s", detail)
                    mig_ok, mig_detail = await check_migrations(session)
                    log = logger.info if mig_ok else logger.error
                    log("Migration check: %s", mig_detail)
                    return
                logger.warning("Database check attempt %d/3: %s", attempt, detail)
        except Exception as exc:
            logger.warning("Database check attempt %d/3 raised: %s", attempt, exc)
        if attempt < 3:
            await asyncio.sleep(2)

    message = "Database unreachable after 3 attempts."
    if settings.is_production:
        raise StartupValidationError(message)
    logger.warning("%s (continuing — not production)", message)
