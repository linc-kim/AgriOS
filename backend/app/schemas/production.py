"""
Greena — Production Readiness Schemas (Module 11).
"""

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import Field

from app.schemas.base import AGRIOSSchema


# ── Version / release ─────────────────────────────────────────────────────────

class VersionInfo(AGRIOSSchema):
    version: str
    environment: str
    git_sha: Optional[str] = None
    git_sha_short: Optional[str] = None
    build_time: Optional[str] = None
    python_version: Optional[str] = None
    started_at: str
    uptime_seconds: int


class ReleaseRow(AGRIOSSchema):
    id: uuid.UUID
    version: str
    environment: str
    git_sha: Optional[str] = None
    migration_revision: Optional[str] = None
    previous_version: Optional[str] = None
    is_rollback: bool
    deployed_at: datetime
    verified: bool
    verification: dict = Field(default_factory=dict)
    notes: Optional[str] = None


class ReleaseInfo(AGRIOSSchema):
    """Everything the Release Information page renders."""

    current: VersionInfo
    migration_current: Optional[str] = None
    migration_expected: Optional[str] = None
    migrations_at_head: bool
    latest_release: Optional[ReleaseRow] = None
    history: list[ReleaseRow] = Field(default_factory=list)


# ── Diagnostics ───────────────────────────────────────────────────────────────

class DiagnosticCheck(AGRIOSSchema):
    name: str
    group: str
    severity: Literal["critical", "warning", "info"]
    passed: bool
    detail: str


class DiagnosticsReport(AGRIOSSchema):
    status: Literal["healthy", "degraded", "unhealthy"]
    checked_at: str
    duration_ms: int
    version: str
    environment: str
    passed_count: int
    failed_count: int
    critical_failures: list[str] = Field(default_factory=list)
    checks: list[DiagnosticCheck] = Field(default_factory=list)


class VerificationCheck(AGRIOSSchema):
    name: str
    passed: bool
    detail: str


class VerificationResult(AGRIOSSchema):
    passed: bool
    checked_at: str
    version: str
    environment: Optional[str] = None
    checks: list[VerificationCheck] = Field(default_factory=list)


class RollbackVerification(AGRIOSSchema):
    passed: bool
    is_rollback: bool
    version: str
    previous_version: Optional[str] = None
    checked_at: str
    checks: list[VerificationCheck] = Field(default_factory=list)


# ── System status / metrics ───────────────────────────────────────────────────

class RouteLatency(AGRIOSSchema):
    method: str
    path: str
    count: int
    avg_ms: float


class MetricsSummary(AGRIOSSchema):
    uptime_seconds: int
    total_requests: int
    server_errors: int
    client_errors: int
    error_rate: float
    avg_latency_ms: float
    exceptions: dict[str, int] = Field(default_factory=dict)
    events: dict[str, int] = Field(default_factory=dict)
    slowest_routes: list[RouteLatency] = Field(default_factory=list)


class SystemStatus(AGRIOSSchema):
    """The System Status page: health, metrics and entity counts in one call."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    checked_at: str
    metrics: MetricsSummary
    entities: dict[str, int] = Field(default_factory=dict)
    active_users_24h: int = 0
    diagnostics: DiagnosticsReport


# ── Backups ───────────────────────────────────────────────────────────────────

class BackupRow(AGRIOSSchema):
    id: uuid.UUID
    scope: str
    farm_id: Optional[uuid.UUID] = None
    label: str
    trigger: str
    status: str
    checksum: Optional[str] = None
    size_bytes: int
    record_counts: dict[str, int] = Field(default_factory=dict)
    schema_version: str
    app_version: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class BackupCreateInput(AGRIOSSchema):
    label: Optional[str] = Field(default=None, max_length=200)
    retention_days: int = Field(default=30, ge=1, le=3650)


class BackupVerification(AGRIOSSchema):
    backup_id: str
    valid: bool
    detail: str
    expected_checksum: Optional[str] = None
    actual_checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    record_counts: dict[str, int] = Field(default_factory=dict)


class RestoreInput(AGRIOSSchema):
    backup_id: uuid.UUID
    # Dry run by default: restoring is destructive, so it must be chosen twice.
    dry_run: bool = True
    overwrite: bool = False


class RestoreRunRow(AGRIOSSchema):
    id: uuid.UUID
    backup_id: uuid.UUID
    farm_id: Optional[uuid.UUID] = None
    dry_run: bool
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    checksum_verified: bool
    safety_backup_id: Optional[uuid.UUID] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime


class RetentionResult(AGRIOSSchema):
    expired_removed: int
    pruned_over_limit: int
    retention_days: int
    max_per_farm: int
    swept_at: str


# ── Imports ───────────────────────────────────────────────────────────────────

class ImportError_(AGRIOSSchema):
    row: int
    message: str


class ImportJobRow(AGRIOSSchema):
    id: uuid.UUID
    farm_id: uuid.UUID
    entity: str
    source_format: str
    filename: Optional[str] = None
    dry_run: bool
    status: str
    total_rows: int
    valid_rows: int
    imported_rows: int
    failed_rows: int
    errors: list[ImportError_] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime


class ImportEntityInfo(AGRIOSSchema):
    entity: str
    columns: list[str]
    required: list[str]


# ── Exports ───────────────────────────────────────────────────────────────────

class ExportJobRow(AGRIOSSchema):
    id: uuid.UUID
    farm_id: uuid.UUID
    dataset: str
    export_format: str
    status: str
    row_count: int
    size_bytes: int
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime


class ExportDatasetInfo(AGRIOSSchema):
    dataset: str
    formats: list[str]
