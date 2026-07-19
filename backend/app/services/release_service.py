"""
Greena — Release & Deployment Service (Module 11).

Answers three questions an operator asks during a deploy:

  What is running?      version, git SHA, build time, environment, migration head
  Did the deploy work?  a verification sweep recorded against the release
  Did we roll back?     a release older than its predecessor, flagged as such

Release metadata comes from the environment (GIT_SHA / BUILD_TIME, set by the
build) and falls back to reading the local git checkout in development, so the
endpoint is useful before a real build pipeline exists.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.production import ReleaseRecord

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]


# ── Build metadata ────────────────────────────────────────────────────────────

def _git(*args: str) -> str | None:
    """Run a git command in the checkout; None if git or the checkout is absent."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        value = out.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def git_sha() -> str | None:
    """The deployed commit. GIT_SHA is set by the build; git is the dev fallback."""
    return os.getenv("GIT_SHA") or _git("rev-parse", "HEAD")


def build_time() -> str | None:
    """ISO timestamp of the build, or the commit time in development."""
    return os.getenv("BUILD_TIME") or _git("log", "-1", "--format=%cI")


def version_info() -> dict:
    """The full release descriptor served by GET /production/version."""
    sha = git_sha()
    return {
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "git_sha": sha,
        "git_sha_short": sha[:8] if sha else None,
        "build_time": build_time(),
        "python_version": os.getenv("PYTHON_VERSION") or _python_version(),
        "started_at": _STARTED_AT.isoformat(),
        "uptime_seconds": int((datetime.now(timezone.utc) - _STARTED_AT).total_seconds()),
    }


def _python_version() -> str:
    import sys

    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


# Process start, used for uptime. Set once at import.
_STARTED_AT = datetime.now(timezone.utc)


# ── Migration head ────────────────────────────────────────────────────────────

async def current_migration_revision(db: AsyncSession) -> str | None:
    """The Alembic revision the database is actually at."""
    from sqlalchemy import text

    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None
    except Exception as exc:  # table absent on a bare database
        logger.warning("Could not read alembic_version: %s", exc)
        return None


def expected_migration_revision() -> str | None:
    """
    The newest revision present in the codebase.

    Derived from the migration filenames, which are strictly numeric and
    zero-padded in this project ("050_production_readiness.py"), so the highest
    prefix is the head. Avoids importing Alembic's script machinery at runtime.
    """
    versions = BACKEND_DIR / "alembic" / "versions"
    if not versions.is_dir():
        return None
    revs = []
    for path in versions.glob("*.py"):
        prefix = path.name.split("_", 1)[0]
        if prefix.isdigit():
            revs.append(prefix)
    return max(revs) if revs else None


# ── Release history ───────────────────────────────────────────────────────────

def _version_tuple(v: str | None) -> tuple:
    """Parse "1.2.3" for ordering. Unparseable versions sort lowest."""
    if not v:
        return (0,)
    parts = []
    for chunk in v.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


async def latest_release(db: AsyncSession) -> ReleaseRecord | None:
    result = await db.execute(
        select(ReleaseRecord)
        .where(ReleaseRecord.environment == settings.ENVIRONMENT,
               ReleaseRecord.deleted_at.is_(None))
        .order_by(desc(ReleaseRecord.deployed_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_releases(db: AsyncSession, limit: int = 20) -> list[ReleaseRecord]:
    result = await db.execute(
        select(ReleaseRecord)
        .where(ReleaseRecord.deleted_at.is_(None))
        .order_by(desc(ReleaseRecord.deployed_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def record_release(db: AsyncSession, notes: str | None = None) -> ReleaseRecord:
    """
    Record the running version as a release, if it is not already the newest one
    for this environment.

    Idempotent per (version, git_sha): restarting a pod must not create a new
    release row, or the history stops meaning anything. A release whose version
    sorts below its predecessor is flagged is_rollback, which is what makes a
    rollback verifiable after the fact.
    """
    sha = git_sha()
    previous = await latest_release(db)

    if previous and previous.version == settings.VERSION and previous.git_sha == sha:
        return previous

    is_rollback = bool(
        previous and _version_tuple(settings.VERSION) < _version_tuple(previous.version)
    )

    release = ReleaseRecord(
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        git_sha=sha,
        migration_revision=await current_migration_revision(db),
        previous_version=previous.version if previous else None,
        is_rollback=is_rollback,
        deployed_at=datetime.now(timezone.utc),
        notes=notes,
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)

    if is_rollback:
        logger.warning(
            "Rollback detected: %s -> %s", previous.version if previous else "?", settings.VERSION
        )
    return release


# ── Deployment verification ───────────────────────────────────────────────────

async def verify_deployment(db: AsyncSession, release: ReleaseRecord | None = None) -> dict:
    """
    Post-deploy sweep: is this instance actually fit to serve traffic?

    Each check is independent and reports pass/fail with a human-readable
    detail, so a failure names the thing to fix. The overall result is the
    conjunction — anything failing means do not cut traffic over.
    """
    from app.services import diagnostics_service

    checks: list[dict] = []

    # 1. Database reachable.
    db_ok, db_detail = await diagnostics_service.check_database(db)
    checks.append({"name": "database", "passed": db_ok, "detail": db_detail})

    # 2. Migrations at head — the most common broken-deploy cause.
    at_head, mig_detail = await check_migrations(db)
    checks.append({"name": "migrations", "passed": at_head, "detail": mig_detail})

    # 3. Required configuration present for the target environment.
    env_ok, env_detail = diagnostics_service.check_environment()
    checks.append({"name": "environment", "passed": env_ok, "detail": env_detail})

    # 4. Core tables queryable (schema really matches the code).
    schema_ok, schema_detail = await diagnostics_service.check_schema(db)
    checks.append({"name": "schema", "passed": schema_ok, "detail": schema_detail})

    passed = all(c["passed"] for c in checks)
    result = {
        "passed": passed,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
    }

    target = release or await latest_release(db)
    if target:
        target.verified = passed
        target.verification = result
        await db.commit()

    return result


async def check_migrations(db: AsyncSession) -> tuple[bool, str]:
    """Compare the database's Alembic revision against the code's newest one."""
    current = await current_migration_revision(db)
    expected = expected_migration_revision()

    if current is None:
        return False, "No alembic_version row — database has never been migrated."
    if expected is None:
        return True, f"At revision {current} (no migration files found to compare)."
    if current == expected:
        return True, f"At head ({current})."
    return False, f"Database at {current}, code expects {expected} — run 'alembic upgrade head'."


async def verify_rollback(db: AsyncSession) -> dict:
    """
    Confirm the system is coherent after a rollback.

    The failure mode a rollback introduces is a database migrated *past* the
    code that is now running: older code against a newer schema. That is
    reported explicitly rather than being folded into a generic migration
    mismatch, because the remedy is the opposite one (downgrade, or roll
    forward again).
    """
    latest = await latest_release(db)
    current = await current_migration_revision(db)
    expected = expected_migration_revision()

    schema_ahead = bool(current and expected and current > expected)

    checks = [
        {
            "name": "rollback_detected",
            "passed": True,
            "detail": (
                f"Running {settings.VERSION}, rolled back from {latest.previous_version}."
                if latest and latest.is_rollback
                else "No rollback recorded for the running version."
            ),
        },
        {
            "name": "schema_compatible",
            "passed": not schema_ahead,
            "detail": (
                f"Database is at {current} but this build only knows {expected}: "
                "the schema is ahead of the code. Downgrade the database or roll forward."
                if schema_ahead
                else f"Database revision {current} is within what this build knows."
            ),
        },
    ]

    db_ok, db_detail = await _safe_db_check(db)
    checks.append({"name": "database", "passed": db_ok, "detail": db_detail})

    return {
        "passed": all(c["passed"] for c in checks),
        "is_rollback": bool(latest and latest.is_rollback),
        "version": settings.VERSION,
        "previous_version": latest.previous_version if latest else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


async def _safe_db_check(db: AsyncSession) -> tuple[bool, str]:
    from app.services import diagnostics_service

    return await diagnostics_service.check_database(db)
