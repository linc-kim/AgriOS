"""
Greena — APScheduler Background Job Registry (Sprint 7)
AD-13 (Frozen): APScheduler embedded in FastAPI handles background jobs in V1.

Jobs registered here:
  1. daily_log_reminder        — 20:00 EAT daily — SMS if farm unlogged today
  2. vaccination_reminders     — 08:00 EAT daily — SMS 3 days before due_date
  3. vaccination_overdue       — 08:00 EAT daily — SMS 1 day after due_date
  4. weekly_summary            — 18:00 EAT every Friday
  5. aria_daily_insights       — 06:00 EAT daily — generate ARIA proactive insights (Sprint 6 carryover)

Job failure handling:
  - All jobs are wrapped in try/except
  - Failures are logged to Sentry (if configured) and stderr
  - Job failures never raise — they are fire-and-forget

Usage (in main.py lifespan):
    from app.services.scheduler import start_scheduler, stop_scheduler
    scheduler = start_scheduler()
    ...
    stop_scheduler(scheduler)
"""

import asyncio
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


# ── Job Functions ─────────────────────────────────────────────────────────────

async def job_daily_log_reminder() -> None:
    """
    20:00 EAT: Send SMS reminders for farms that have not logged today.
    Queries farms with active flocks where no daily_log exists for today.
    """
    logger.info("SCHEDULER: Running daily_log_reminder job")
    try:
        from app.database import AsyncSessionLocal
        from app.services import sms_service
        from sqlalchemy import and_, func, select
        from app.models.flock import Flock, DailyLog
        from app.models.farm import Farm, FarmMember
        from app.models.auth import User

        today = date.today()

        async with AsyncSessionLocal() as db:
            # Get all active flocks that have no log for today
            logged_flock_ids = select(DailyLog.flock_id).where(
                DailyLog.log_date == today,
                DailyLog.deleted_at.is_(None),
            )
            result = await db.execute(
                select(Flock, Farm)
                .join(Farm, Flock.farm_id == Farm.id)
                .where(
                    Flock.status == "active",
                    Flock.deleted_at.is_(None),
                    Farm.deleted_at.is_(None),
                    ~Flock.id.in_(logged_flock_ids),
                )
            )
            rows = result.all()

            for flock, farm in rows:
                # Get farm owner phone
                owner_result = await db.execute(
                    select(User)
                    .join(FarmMember, FarmMember.user_id == User.id)
                    .where(
                        FarmMember.farm_id == farm.id,
                        FarmMember.role.has(name="farm_owner"),
                        FarmMember.deleted_at.is_(None),
                    )
                )
                owner = owner_result.scalar_one_or_none()
                if owner and owner.phone:
                    await sms_service.sms_daily_log_reminder(owner.phone, flock.name)

        logger.info(f"SCHEDULER: daily_log_reminder complete for {today}")
    except Exception as e:
        logger.error(f"SCHEDULER: daily_log_reminder failed: {e}")


async def job_vaccination_reminders() -> None:
    """
    08:00 EAT: Send SMS reminders for vaccinations due in 3 days.
    """
    logger.info("SCHEDULER: Running vaccination_reminders job")
    try:
        from app.database import AsyncSessionLocal
        from app.services import sms_service
        from sqlalchemy import select
        from app.models.health import VaccinationRecord
        from app.models.flock import Flock
        from app.models.farm import Farm, FarmMember
        from app.models.auth import User

        target_date = date.today() + timedelta(days=3)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VaccinationRecord, Flock, Farm)
                .join(Flock, VaccinationRecord.flock_id == Flock.id)
                .join(Farm, Flock.farm_id == Farm.id)
                .where(
                    VaccinationRecord.next_due_date == target_date,
                    VaccinationRecord.deleted_at.is_(None),
                    Flock.status == "active",
                    Flock.deleted_at.is_(None),
                )
            )
            rows = result.all()

            for vax, flock, farm in rows:
                owner_result = await db.execute(
                    select(User)
                    .join(FarmMember, FarmMember.user_id == User.id)
                    .where(
                        FarmMember.farm_id == farm.id,
                        FarmMember.role.has(name="farm_owner"),
                        FarmMember.deleted_at.is_(None),
                    )
                )
                owner = owner_result.scalar_one_or_none()
                if owner and owner.phone:
                    await sms_service.sms_vaccination_reminder(
                        owner.phone,
                        vax.vaccine_name,
                        flock.name,
                        str(target_date),
                    )

        logger.info("SCHEDULER: vaccination_reminders complete")
    except Exception as e:
        logger.error(f"SCHEDULER: vaccination_reminders failed: {e}")


async def job_vaccination_overdue() -> None:
    """
    08:00 EAT: Send SMS for vaccinations that became overdue yesterday.
    """
    logger.info("SCHEDULER: Running vaccination_overdue job")
    try:
        from app.database import AsyncSessionLocal
        from app.services import sms_service
        from sqlalchemy import select
        from app.models.health import VaccinationRecord
        from app.models.flock import Flock
        from app.models.farm import Farm, FarmMember
        from app.models.auth import User

        overdue_date = date.today() - timedelta(days=1)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VaccinationRecord, Flock, Farm)
                .join(Flock, VaccinationRecord.flock_id == Flock.id)
                .join(Farm, Flock.farm_id == Farm.id)
                .where(
                    VaccinationRecord.next_due_date == overdue_date,
                    VaccinationRecord.deleted_at.is_(None),
                    Flock.status == "active",
                    Flock.deleted_at.is_(None),
                )
            )
            rows = result.all()

            for vax, flock, farm in rows:
                owner_result = await db.execute(
                    select(User)
                    .join(FarmMember, FarmMember.user_id == User.id)
                    .where(
                        FarmMember.farm_id == farm.id,
                        FarmMember.role.has(name="farm_owner"),
                        FarmMember.deleted_at.is_(None),
                    )
                )
                owner = owner_result.scalar_one_or_none()
                if owner and owner.phone:
                    await sms_service.sms_vaccination_overdue(
                        owner.phone,
                        vax.vaccine_name,
                        flock.name,
                        str(overdue_date),
                    )

        logger.info("SCHEDULER: vaccination_overdue complete")
    except Exception as e:
        logger.error(f"SCHEDULER: vaccination_overdue failed: {e}")


async def job_weekly_summary() -> None:
    """
    18:00 EAT every Friday: Send weekly farm summary SMS to farm owners.
    """
    logger.info("SCHEDULER: Running weekly_summary job")
    try:
        from app.database import AsyncSessionLocal
        from app.services import sms_service
        from sqlalchemy import and_, func, select
        from app.models.farm import Farm, FarmMember
        from app.models.flock import Flock
        from app.models.auth import User

        async with AsyncSessionLocal() as db:
            # All active farms
            farms_result = await db.execute(
                select(Farm).where(Farm.deleted_at.is_(None))
            )
            farms = farms_result.scalars().all()

            for farm in farms:
                # Count active flocks
                flock_count_result = await db.execute(
                    select(func.count()).where(
                        and_(
                            Flock.farm_id == farm.id,
                            Flock.status == "active",
                            Flock.deleted_at.is_(None),
                        )
                    )
                )
                flock_count = flock_count_result.scalar_one()

                # Get owner
                owner_result = await db.execute(
                    select(User)
                    .join(FarmMember, FarmMember.user_id == User.id)
                    .where(
                        FarmMember.farm_id == farm.id,
                        FarmMember.role.has(name="farm_owner"),
                        FarmMember.deleted_at.is_(None),
                    )
                )
                owner = owner_result.scalar_one_or_none()
                if owner and owner.phone:
                    # Simplified survival rate calculation
                    # Real implementation would query daily_logs for the week
                    survival_rate = 98.5  # Placeholder — real query in production
                    await sms_service.sms_weekly_summary(
                        owner.phone,
                        farm.name,
                        survival_rate,
                        flock_count,
                    )

        logger.info("SCHEDULER: weekly_summary complete")
    except Exception as e:
        logger.error(f"SCHEDULER: weekly_summary failed: {e}")


async def job_aria_daily_insights() -> None:
    """
    06:00 EAT: Generate proactive ARIA insights for all farms.
    Sprint 6 carryover — APScheduler wiring required in Sprint 7.
    """
    logger.info("SCHEDULER: Running aria_daily_insights job")
    try:
        from app.database import AsyncSessionLocal
        from app.services.aria_service import generate_daily_insights
        from sqlalchemy import select
        from app.models.farm import Farm

        async with AsyncSessionLocal() as db:
            farms_result = await db.execute(
                select(Farm.id).where(Farm.deleted_at.is_(None))
            )
            farm_ids = [row[0] for row in farms_result.all()]

            generated = 0
            for farm_id in farm_ids:
                try:
                    insights = await generate_daily_insights(db, farm_id)
                    generated += len(insights)
                except Exception as farm_err:
                    logger.error(f"ARIA insights failed for farm {farm_id}: {farm_err}")

        logger.info(f"SCHEDULER: aria_daily_insights complete — {generated} insights generated")
    except Exception as e:
        logger.error(f"SCHEDULER: aria_daily_insights failed: {e}")


# ── Scheduler Lifecycle ───────────────────────────────────────────────────────

async def job_backup_retention() -> None:
    """
    02:30 EAT: enforce the backup retention policy across every farm.

    Expired backups are soft-deleted and each farm is pruned to its cap, so
    snapshot storage cannot grow without bound.
    """
    logger.info("SCHEDULER: Running backup_retention job")
    try:
        from app.database import AsyncSessionLocal
        from app.services import backup_service

        async with AsyncSessionLocal() as session:
            result = await backup_service.apply_retention(session)
            logger.info("SCHEDULER: backup_retention complete — %s", result)
    except Exception as exc:
        logger.error("SCHEDULER: backup_retention failed: %s", exc)


# A fixed, arbitrary key identifying "the Greena scheduler" to Postgres.
# Any process holding this advisory lock owns the cron jobs.
SCHEDULER_LOCK_KEY = 4207731  # "greena-scheduler"

# Connection holding the advisory lock, kept open for the process lifetime.
# Releasing it (or the process dying) frees the lock for another instance.
_lock_conn = None


async def acquire_scheduler_lock() -> bool:
    """
    Try to become the single process that runs scheduled jobs.

    The server runs multiple uvicorn workers, and each worker executes the
    FastAPI lifespan — so without this every cron job fires once per worker.
    That means duplicate SMS to farmers (billed per message by Africa's
    Talking), duplicate ARIA insights, and duplicate reminders.

    A Postgres advisory lock is used rather than a worker-index check because it
    is also correct across horizontally scaled instances: whichever process wins
    the lock owns the schedule, and if it dies the lock is released with its
    connection so another instance takes over on its next start.

    Returns True if this process should run the scheduler.
    """
    global _lock_conn

    from sqlalchemy import text

    from app.database import engine

    try:
        _lock_conn = await engine.connect()
        result = await _lock_conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEDULER_LOCK_KEY}
        )
        acquired = bool(result.scalar())
        if not acquired:
            await _lock_conn.close()
            _lock_conn = None
        return acquired
    except Exception as exc:
        # Never let lock acquisition stop the app from serving HTTP. Declining
        # the scheduler is the safe failure: missing a reminder beats sending
        # every farmer a duplicate, and another worker will hold the lock.
        logger.error("Could not acquire scheduler lock: %s", exc)
        if _lock_conn is not None:
            try:
                await _lock_conn.close()
            except Exception:
                pass
            _lock_conn = None
        return False


async def run_scheduler_when_leader(poll_seconds: int = 60):
    """
    Keep trying for the lock, and run the scheduler once this process wins it.

    Acquiring once at startup is not enough. During a rolling deploy the
    outgoing container still holds the lock while the incoming one boots, so
    every new worker loses the race — and once the old container exits the lock
    is free with nobody left to take it. The scheduler would then stay dead
    until the next restart, silently.

    Retrying turns that into a handover: the new leader picks the lock up on its
    next poll, usually within a minute of the old one exiting.

    Returns the running scheduler (for shutdown), or None if cancelled first.
    """
    while True:
        if await acquire_scheduler_lock():
            scheduler = start_scheduler()
            logger.info("Scheduler started — this worker holds the scheduler lock")
            return scheduler
        await asyncio.sleep(poll_seconds)


async def release_scheduler_lock() -> None:
    """Release the advisory lock at shutdown so another process can take over."""
    global _lock_conn

    if _lock_conn is None:
        return
    try:
        from sqlalchemy import text

        await _lock_conn.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": SCHEDULER_LOCK_KEY}
        )
        await _lock_conn.close()
        logger.info("Scheduler lock released")
    except Exception as exc:
        logger.warning("Could not cleanly release scheduler lock: %s", exc)
    finally:
        _lock_conn = None


def start_scheduler() -> AsyncIOScheduler:
    """
    Create, configure, and start the APScheduler instance.
    Call this from FastAPI lifespan startup, only after acquire_scheduler_lock()
    has returned True.
    All times in Africa/Nairobi (EAT = UTC+3).
    """
    scheduler = AsyncIOScheduler(timezone="Africa/Nairobi")

    # 06:00 EAT — ARIA proactive insights
    scheduler.add_job(
        job_aria_daily_insights,
        CronTrigger(hour=6, minute=0, timezone="Africa/Nairobi"),
        id="aria_daily_insights",
        name="ARIA Daily Insights",
        replace_existing=True,
        misfire_grace_time=300,  # 5 min grace window
    )

    # 08:00 EAT — Vaccination reminders (3 days ahead)
    scheduler.add_job(
        job_vaccination_reminders,
        CronTrigger(hour=8, minute=0, timezone="Africa/Nairobi"),
        id="vaccination_reminders",
        name="Vaccination Reminders",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 08:00 EAT — Vaccination overdue alerts
    scheduler.add_job(
        job_vaccination_overdue,
        CronTrigger(hour=8, minute=5, timezone="Africa/Nairobi"),
        id="vaccination_overdue",
        name="Vaccination Overdue",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 20:00 EAT — Daily log reminder
    scheduler.add_job(
        job_daily_log_reminder,
        CronTrigger(hour=20, minute=0, timezone="Africa/Nairobi"),
        id="daily_log_reminder",
        name="Daily Log Reminder",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 18:00 EAT every Friday — Weekly summary
    scheduler.add_job(
        job_weekly_summary,
        CronTrigger(day_of_week="fri", hour=18, minute=0, timezone="Africa/Nairobi"),
        id="weekly_summary",
        name="Weekly Summary",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 02:30 EAT — backup retention sweep (Module 11). Runs in the quiet window,
    # after the day's data has settled and well before morning traffic.
    scheduler.add_job(
        job_backup_retention,
        CronTrigger(hour=2, minute=30, timezone="Africa/Nairobi"),
        id="backup_retention",
        name="Backup Retention Sweep",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    logger.info("APScheduler started — 6 jobs registered")
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Gracefully shut down the scheduler. Call from FastAPI lifespan shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
