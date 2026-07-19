"""
Greena — Production Readiness Models (Module 11).
Migration 050.

  backups         — a point-in-time snapshot of a farm's operational data.
  restore_runs    — an attempt to restore a backup (dry run or applied).
  import_jobs     — a bulk data import (CSV / Excel / JSON), dry run or applied.
  export_jobs     — a generated data export, kept for download history.
  release_records — deployed releases, for deployment and rollback verification.

Backup payloads are stored inline as JSONB. V1 has no object storage
configured, and keeping the snapshot in the same transactional store as the
data it describes means a backup can never be silently orphaned from its
metadata. RETENTION_MAX_PAYLOAD_BYTES caps a single snapshot; larger farms
should move to object storage before that becomes a limit.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AGRIOSBase

# Status values shared by every long-running job in this module.
JOB_STATUSES = ("pending", "running", "success", "failed")

BACKUP_SCOPES = ("farm", "organization")
BACKUP_TRIGGERS = ("manual", "scheduled", "pre_restore")

IMPORT_ENTITIES = (
    "daily_logs", "expenses", "revenue", "inventory_items", "feed_purchases", "flocks",
)
DATA_FORMATS = ("csv", "excel", "json")
EXPORT_FORMATS = ("csv", "excel", "json", "pdf")


class Backup(AGRIOSBase):
    """A point-in-time snapshot of a farm's (or organization's) data."""

    __tablename__ = "backups"

    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="farm", index=True)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)

    # Snapshot itself, plus the integrity data used to verify a restore.
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    record_counts: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)

    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1")
    app_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retention sweep deletes backups past this instant.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RestoreRun(AGRIOSBase):
    """An attempt to restore a backup. Dry runs report without writing."""

    __tablename__ = "restore_runs"

    backup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True
    )

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)

    # What the restore would do / did, per entity.
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    checksum_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # A safety snapshot taken before an applied restore, so it can be undone.
    safety_backup_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backups.id", ondelete="SET NULL"), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ImportJob(AGRIOSBase):
    """A bulk import of farm data from an uploaded file."""

    __tablename__ = "import_jobs"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    entity: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_format: Mapped[str] = mapped_column(String(10), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Per-row validation failures: [{row, field, message}]. Capped when stored.
    errors: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ExportJob(AGRIOSBase):
    """A generated export, recorded so the workspace can show download history."""

    __tablename__ = "export_jobs"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dataset: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    export_format: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", index=True)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ReleaseRecord(AGRIOSBase):
    """
    A deployed release. Written on startup when the running version differs from
    the newest recorded one, which is what makes deployment and rollback
    verifiable: a rollback is a release whose version is older than its
    predecessor, and it is flagged as such.
    """

    __tablename__ = "release_records"

    version: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)

    migration_revision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_rollback: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", index=True
    )
    # Result of the post-deploy verification sweep.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    verification: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
