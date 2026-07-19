"""
Greena — Backup & Restore Service (Module 11).

A backup is a JSON snapshot of one farm's operational data, stored inline with
a SHA-256 checksum. A restore replays it.

Two properties matter more than raw capability here:

  Verifiable — the checksum is recomputed before any restore, so a corrupted or
               tampered snapshot is refused rather than half-applied.
  Reversible — an applied restore first takes a safety backup of current state,
               so the operation can itself be undone.

Restores are additive-by-default: rows absent from the live farm are recreated,
rows already present are left alone unless the caller opts into overwrite. The
destructive path is opt-in, never the default.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense, RevenueRecord
from app.models.flock import DailyLog, Flock
from app.models.health import VaccinationRecord
from app.models.inventory import InventoryItem
from app.models.production import Backup, RestoreRun

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

# A single inline snapshot is capped so one oversized farm cannot exhaust the
# row limit or the request memory. Beyond this, move to object storage.
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024  # 32 MB

DEFAULT_RETENTION_DAYS = 30
MAX_BACKUPS_PER_FARM = 20

# Entities captured, in dependency order — flocks before the logs that reference
# them, so a restore can insert without violating foreign keys.
BACKUP_ENTITIES: tuple[tuple[str, Any], ...] = (
    ("flocks", Flock),
    ("daily_logs", DailyLog),
    ("expenses", Expense),
    ("revenue_records", RevenueRecord),
    ("vaccination_records", VaccinationRecord),
    ("inventory_items", InventoryItem),
)


# ── Serialisation ─────────────────────────────────────────────────────────────

def _encode(value: Any) -> Any:
    """JSON-encode a column value without losing precision."""
    if isinstance(value, Decimal):
        # str, not float: these are money and weight columns, and float would
        # silently round them on the way back in.
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _row_to_dict(row: Any) -> dict:
    """
    Serialise an ORM row, keyed by database column name.

    Reads through the mapper rather than doing getattr(row, col.name): the
    column named "metadata" is mapped to the attribute `metadata_`, because
    `metadata` is already taken by SQLAlchemy's declarative machinery. Going by
    column name would return the MetaData object instead of the row's value,
    which is not JSON-serialisable and fails the whole backup.
    """
    mapper = sa_inspect(type(row))
    return {
        prop.columns[0].name: _encode(getattr(row, prop.key))
        for prop in mapper.column_attrs
    }


def _column_to_attr(model: Any) -> dict[str, str]:
    """Map database column name -> ORM attribute name for a model."""
    return {
        prop.columns[0].name: prop.key
        for prop in sa_inspect(model).column_attrs
    }


def _checksum(payload: dict) -> str:
    """
    SHA-256 over the canonical JSON form.

    sort_keys is what makes this reproducible — without it, dict ordering would
    change the digest between runs and every verification would fail.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Create ────────────────────────────────────────────────────────────────────

async def create_backup(
    db: AsyncSession,
    farm: Farm,
    user: User | None = None,
    label: str | None = None,
    trigger: str = "manual",
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> Backup:
    """Snapshot every backed-up entity for this farm."""
    started = time.perf_counter()
    now = datetime.now(timezone.utc)

    # Captured before any rollback can expire the `farm` instance — see the note
    # in restore_backup.
    farm_id = farm.id
    org_id = farm.organization_id
    farm_name = farm.name
    user_id = user.id if user else None

    backup = Backup(
        scope="farm",
        farm_id=farm_id,
        organization_id=org_id,
        label=label or f"{farm_name} — {now:%Y-%m-%d %H:%M}",
        trigger=trigger,
        status="running",
        started_at=now,
        schema_version=SCHEMA_VERSION,
        app_version=settings.VERSION,
        expires_at=now + timedelta(days=retention_days) if retention_days else None,
        created_by=user.id if user else None,
    )
    db.add(backup)
    await db.flush()

    try:
        data: dict[str, list[dict]] = {}
        counts: dict[str, int] = {}

        for name, model in BACKUP_ENTITIES:
            result = await db.execute(
                select(model).where(
                    model.farm_id == farm.id,
                    model.deleted_at.is_(None),
                )
            )
            rows = [_row_to_dict(r) for r in result.scalars().all()]
            data[name] = rows
            counts[name] = len(rows)

        payload = {
            "schema_version": SCHEMA_VERSION,
            "app_version": settings.VERSION,
            "farm": {
                "id": str(farm.id),
                "name": farm.name,
                "county": farm.county,
                "organization_id": str(farm.organization_id) if farm.organization_id else None,
            },
            "created_at": now.isoformat(),
            "data": data,
        }

        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        size = len(encoded.encode("utf-8"))
        if size > MAX_PAYLOAD_BYTES:
            raise ValidationException(
                f"Backup is {size / 1_048_576:.1f} MB, over the {MAX_PAYLOAD_BYTES / 1_048_576:.0f} MB limit."
            )

        backup.payload = payload
        backup.checksum = _checksum(payload)
        backup.size_bytes = size
        backup.record_counts = counts
        backup.status = "success"
        backup.completed_at = datetime.now(timezone.utc)
        backup.duration_ms = int((time.perf_counter() - started) * 1000)

        await db.commit()
        await db.refresh(backup)

        from app.services.metrics_service import registry

        registry.record_event("backup_created")
        logger.info("Backup %s created for farm %s (%d bytes)", backup.id, farm.id, size)

    except Exception as exc:
        # Rebuilt on a clean transaction rather than mutating `backup`: if the
        # failure came from the database the session is already poisoned, and
        # after a rollback the original instance is expired.
        await db.rollback()

        failed = Backup(
            scope="farm",
            farm_id=farm_id,
            organization_id=org_id,
            label=label or f"{farm_name} — failed {now:%Y-%m-%d %H:%M}",
            trigger=trigger,
            status="failed",
            started_at=now,
            completed_at=datetime.now(timezone.utc),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc)[:2000],
            schema_version=SCHEMA_VERSION,
            app_version=settings.VERSION,
            created_by=user_id,
        )
        db.add(failed)
        await db.commit()

        from app.services.metrics_service import registry

        registry.record_event("backup_failed")
        logger.error("Backup failed for farm %s: %s", farm_id, exc)
        raise

    return backup


# ── Read ──────────────────────────────────────────────────────────────────────

async def list_backups(db: AsyncSession, farm_id: uuid.UUID) -> list[Backup]:
    """Backup history for a farm, newest first. Payloads are not loaded."""
    result = await db.execute(
        select(Backup)
        .where(Backup.farm_id == farm_id, Backup.deleted_at.is_(None))
        .order_by(Backup.created_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())


async def get_backup(db: AsyncSession, farm_id: uuid.UUID, backup_id: uuid.UUID) -> Backup:
    result = await db.execute(
        select(Backup).where(
            Backup.id == backup_id,
            Backup.farm_id == farm_id,
            Backup.deleted_at.is_(None),
        )
    )
    backup = result.scalar_one_or_none()
    if not backup:
        raise NotFoundException("Backup")
    return backup


async def verify_backup(db: AsyncSession, farm_id: uuid.UUID, backup_id: uuid.UUID) -> dict:
    """
    Recompute the checksum and compare it to the stored one.

    This is the integrity gate a restore depends on, exposed on its own so an
    operator can confirm a backup is sound without restoring it.
    """
    backup = await get_backup(db, farm_id, backup_id)

    if backup.status != "success":
        return {
            "backup_id": str(backup.id),
            "valid": False,
            "detail": f"Backup status is '{backup.status}', not 'success'.",
        }
    if not backup.checksum:
        return {
            "backup_id": str(backup.id),
            "valid": False,
            "detail": "Backup has no stored checksum.",
        }

    actual = _checksum(backup.payload)
    valid = actual == backup.checksum
    return {
        "backup_id": str(backup.id),
        "valid": valid,
        "expected_checksum": backup.checksum,
        "actual_checksum": actual,
        "size_bytes": backup.size_bytes,
        "record_counts": backup.record_counts,
        "detail": (
            "Checksum matches; the snapshot is intact."
            if valid
            else "Checksum mismatch — the snapshot has been altered or corrupted and must not be restored."
        ),
    }


async def delete_backup(db: AsyncSession, farm_id: uuid.UUID, backup_id: uuid.UUID) -> None:
    backup = await get_backup(db, farm_id, backup_id)
    backup.soft_delete()
    await db.commit()


# ── Restore ───────────────────────────────────────────────────────────────────

async def restore_backup(
    db: AsyncSession,
    farm: Farm,
    backup_id: uuid.UUID,
    user: User | None = None,
    dry_run: bool = True,
    overwrite: bool = False,
) -> RestoreRun:
    """
    Restore a backup into its farm.

    Always refuses on a checksum mismatch. A dry run reports what would change
    and writes nothing. An applied restore takes a safety backup first, so the
    operation is reversible.
    """
    started = time.perf_counter()

    # Snapshot the identifiers now. db.rollback() in the failure path expires
    # every instance in the session — `farm` included — so reading farm.id after
    # it would itself be a lazy load, and lazy loads raise on an async session.
    farm_id = farm.id
    user_id = user.id if user else None

    backup = await get_backup(db, farm_id, backup_id)

    run = RestoreRun(
        backup_id=backup.id,
        farm_id=farm_id,
        dry_run=dry_run,
        status="running",
        started_at=datetime.now(timezone.utc),
        created_by=user.id if user else None,
    )
    db.add(run)
    await db.flush()

    # Mirrored in plain locals so the failure path can rebuild the audit row
    # without touching `run` — a rollback expires that instance, and reading an
    # expired attribute triggers a lazy load, which raises MissingGreenlet on an
    # async session.
    started_at = run.started_at
    checksum_verified = False
    safety_backup_id: uuid.UUID | None = None

    try:
        verification = await verify_backup(db, farm.id, backup_id)
        checksum_verified = bool(verification["valid"])
        run.checksum_verified = checksum_verified
        if not verification["valid"]:
            raise ValidationException(f"Refusing to restore: {verification['detail']}")

        # Safety net before touching live data.
        if not dry_run:
            safety = await create_backup(
                db, farm, user,
                label=f"Pre-restore safety — {datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
                trigger="pre_restore",
            )
            safety_backup_id = safety.id
            run.safety_backup_id = safety_backup_id

        summary: dict[str, dict] = {}
        data = backup.payload.get("data", {})

        for name, model in BACKUP_ENTITIES:
            rows = data.get(name, [])

            # deleted_at comes back with the id because a soft-deleted row still
            # occupies its primary key. A backup only ever captures live rows, so
            # a row that is in the snapshot but soft-deleted now is exactly the
            # case a restore exists to undo — it must be revived, not skipped.
            # Treating it as "already present" would make restore a no-op for the
            # very scenario people restore from.
            existing_result = await db.execute(
                select(model.id, model.deleted_at).where(model.farm_id == farm.id)
            )
            existing = {str(row_id): deleted_at for row_id, deleted_at in existing_result}

            to_create = [r for r in rows if r.get("id") not in existing]
            to_revive = [r for r in rows if existing.get(r.get("id")) is not None]
            already_live = len(rows) - len(to_create) - len(to_revive)

            summary[name] = {
                "in_backup": len(rows),
                "would_create" if dry_run else "created": len(to_create),
                "would_revive" if dry_run else "revived": len(to_revive),
                "already_present": already_live,
                "overwritten": 0,
            }

            # A dry run reads and reports only — it never stages a write, so
            # there is nothing to undo afterwards.
            if dry_run:
                continue

            for row in to_create:
                db.add(model(**_decode_row(model, row)))

            for row in to_revive:
                live = await db.get(model, uuid.UUID(row["id"]))
                if live is None:
                    continue
                for key, value in _decode_row(model, row).items():
                    if key not in ("id", "farm_id", "created_at"):
                        setattr(live, key, value)
                live.deleted_at = None  # the revival itself

            if overwrite and already_live:
                live_ids = {k for k, v in existing.items() if v is None}
                overwritten = await _overwrite_existing(db, model, rows, live_ids)
                summary[name]["overwritten"] = overwritten

        run.summary = summary
        run.status = "success"
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        await db.commit()
        await db.refresh(run)

        from app.services.metrics_service import registry

        registry.record_event("restore_dry_run" if dry_run else "restore_applied")
        logger.info(
            "Restore %s (%s) for farm %s: %s",
            run.id, "dry run" if dry_run else "applied", farm.id, summary,
        )

    except Exception as exc:
        # The rollback unwinds the RestoreRun insert along with everything else,
        # so the audit row is written again on a clean transaction — a refused
        # or failed restore must still leave a trace. Built entirely from the
        # locals above; `run` is expired at this point and must not be read.
        await db.rollback()

        failed = RestoreRun(
            backup_id=backup_id,
            farm_id=farm_id,
            dry_run=dry_run,
            status="failed",
            checksum_verified=checksum_verified,
            safety_backup_id=safety_backup_id,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc)[:2000],
            created_by=user_id,
        )
        db.add(failed)
        await db.commit()
        await db.refresh(failed)

        from app.services.metrics_service import registry

        registry.record_event("restore_failed")
        logger.error("Restore failed for farm %s: %s", farm_id, exc)
        raise

    return run


def _decode_row(model: Any, row: dict) -> dict:
    """
    Convert an encoded snapshot row into kwargs for the model constructor.

    Keyed by ORM attribute name, not column name — the "metadata" column must be
    passed as `metadata_`, since `metadata` on the constructor would collide with
    SQLAlchemy's declarative attribute.
    """
    import datetime as _dt
    from sqlalchemy import Date, DateTime, Numeric
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    attr_by_column = _column_to_attr(model)
    decoded: dict[str, Any] = {}

    for col in model.__table__.columns:
        if col.name not in row:
            continue
        attr = attr_by_column.get(col.name)
        if attr is None:
            continue

        value = row[col.name]
        if value is None:
            decoded[attr] = None
            continue

        col_type = col.type
        try:
            if isinstance(col_type, PGUUID):
                decoded[attr] = uuid.UUID(str(value))
            elif isinstance(col_type, Numeric):
                decoded[attr] = Decimal(str(value))
            elif isinstance(col_type, DateTime):
                decoded[attr] = _dt.datetime.fromisoformat(str(value))
            elif isinstance(col_type, Date):
                decoded[attr] = _dt.date.fromisoformat(str(value))
            else:
                decoded[attr] = value
        except (ValueError, TypeError):
            # A single unparseable cell must not abort the whole restore; the
            # column keeps its default and the row still lands.
            logger.warning("Could not decode %s.%s=%r", model.__tablename__, col.name, value)
    return decoded


async def _overwrite_existing(
    db: AsyncSession, model: Any, rows: list[dict], existing_ids: set[str]
) -> int:
    """Update rows that exist in both the snapshot and the live farm."""
    count = 0
    for row in rows:
        row_id = row.get("id")
        if row_id not in existing_ids:
            continue
        live = await db.get(model, uuid.UUID(row_id))
        if live is None:
            continue
        for key, value in _decode_row(model, row).items():
            if key not in ("id", "farm_id", "created_at"):
                setattr(live, key, value)
        count += 1
    return count


async def list_restore_runs(db: AsyncSession, farm_id: uuid.UUID) -> list[RestoreRun]:
    result = await db.execute(
        select(RestoreRun)
        .where(RestoreRun.farm_id == farm_id, RestoreRun.deleted_at.is_(None))
        .order_by(RestoreRun.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


# ── Retention ─────────────────────────────────────────────────────────────────

async def apply_retention(db: AsyncSession, farm_id: uuid.UUID | None = None) -> dict:
    """
    Enforce the retention policy: drop expired backups, and keep only the newest
    MAX_BACKUPS_PER_FARM per farm.

    Soft-deletes, per the no-hard-deletes rule, so a retention sweep is itself
    recoverable. Safety backups from restores are exempt from the count cap —
    losing the undo point for a restore because of routine pruning would defeat
    the purpose of taking it.
    """
    now = datetime.now(timezone.utc)
    expired_count = 0
    pruned_count = 0

    expired_q = select(Backup).where(
        Backup.deleted_at.is_(None),
        Backup.expires_at.is_not(None),
        Backup.expires_at < now,
    )
    if farm_id:
        expired_q = expired_q.where(Backup.farm_id == farm_id)

    for backup in (await db.execute(expired_q)).scalars().all():
        backup.soft_delete()
        expired_count += 1

    farm_ids: list[uuid.UUID]
    if farm_id:
        farm_ids = [farm_id]
    else:
        result = await db.execute(
            select(Backup.farm_id)
            .where(Backup.deleted_at.is_(None), Backup.farm_id.is_not(None))
            .group_by(Backup.farm_id)
            .having(func.count(Backup.id) > MAX_BACKUPS_PER_FARM)
        )
        farm_ids = [r for r in result.scalars().all()]

    for fid in farm_ids:
        result = await db.execute(
            select(Backup)
            .where(
                Backup.farm_id == fid,
                Backup.deleted_at.is_(None),
                Backup.trigger != "pre_restore",
            )
            .order_by(Backup.created_at.desc())
        )
        backups = list(result.scalars().all())
        for backup in backups[MAX_BACKUPS_PER_FARM:]:
            backup.soft_delete()
            pruned_count += 1

    await db.commit()

    result = {
        "expired_removed": expired_count,
        "pruned_over_limit": pruned_count,
        "retention_days": DEFAULT_RETENTION_DAYS,
        "max_per_farm": MAX_BACKUPS_PER_FARM,
        "swept_at": now.isoformat(),
    }
    if expired_count or pruned_count:
        logger.info("Backup retention sweep: %s", result)
    return result
