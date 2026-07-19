"""
Greena — Production Readiness Endpoints (Module 11).

Two groups:

  /production/*              platform-level: version, diagnostics, metrics,
                             system status, release info, deployment checks.
  /farms/{farm_id}/data/*    farm-scoped: backups, restores, imports, exports.

Farm-scoped routes go through require_farm_access, so tenant isolation is
enforced the same way as every other farm route — a token for one farm cannot
reach another farm's backups.

/production/version and /production/metrics are intentionally unauthenticated:
uptime checks and Prometheus scrapers cannot hold a user token. Neither exposes
tenant data — version returns build metadata, metrics returns aggregate counters.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.production import (
    BackupCreateInput, BackupRow, BackupVerification, DiagnosticsReport,
    ExportDatasetInfo, ExportJobRow, ImportEntityInfo, ImportJobRow, ReleaseInfo,
    ReleaseRow, RestoreInput, RestoreRunRow, RetentionResult, RollbackVerification,
    SystemStatus, VerificationResult, VersionInfo,
)
from app.services import (
    backup_service,
    data_export_service,
    diagnostics_service,
    import_service,
    metrics_service,
    release_service,
)

router = APIRouter(tags=["Production"])


# ── Platform: version & release ───────────────────────────────────────────────

@router.get("/production/version", response_model=SuccessResponse[VersionInfo],
            summary="Running version and build metadata")
async def version() -> SuccessResponse[VersionInfo]:
    """Unauthenticated: deployment tooling and uptime checks need this."""
    return SuccessResponse(data=VersionInfo(**release_service.version_info()))


@router.get("/production/release", response_model=SuccessResponse[ReleaseInfo],
            summary="Release information and deployment history")
async def release_info(db: DBSession, current_user: CurrentUser,
                       _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    current = await release_service.current_migration_revision(db)
    expected = release_service.expected_migration_revision()
    latest = await release_service.latest_release(db)
    history = await release_service.list_releases(db, limit=20)

    return SuccessResponse(data=ReleaseInfo(
        current=VersionInfo(**release_service.version_info()),
        migration_current=current,
        migration_expected=expected,
        migrations_at_head=bool(current and expected and current == expected),
        latest_release=ReleaseRow.model_validate(latest) if latest else None,
        history=[ReleaseRow.model_validate(r) for r in history],
    ))


@router.post("/production/release/record", response_model=SuccessResponse[ReleaseRow],
             summary="Record the running version as a release")
async def record_release(db: DBSession, current_user: CurrentUser,
                         notes: str | None = Query(default=None),
                         _p=Depends(require_permission(Permission.DIAGNOSTICS_RUN))):
    release = await release_service.record_release(db, notes=notes)
    return SuccessResponse(data=ReleaseRow.model_validate(release))


@router.post("/production/deployment/verify", response_model=SuccessResponse[VerificationResult],
             summary="Verify this deployment is fit to serve traffic")
async def verify_deployment(db: DBSession, current_user: CurrentUser,
                            _p=Depends(require_permission(Permission.DIAGNOSTICS_RUN))):
    return SuccessResponse(data=VerificationResult(**await release_service.verify_deployment(db)))


@router.post("/production/rollback/verify", response_model=SuccessResponse[RollbackVerification],
             summary="Verify system coherence after a rollback")
async def verify_rollback(db: DBSession, current_user: CurrentUser,
                          _p=Depends(require_permission(Permission.DIAGNOSTICS_RUN))):
    return SuccessResponse(data=RollbackVerification(**await release_service.verify_rollback(db)))


# ── Platform: diagnostics, metrics, status ────────────────────────────────────

@router.get("/production/diagnostics", response_model=SuccessResponse[DiagnosticsReport],
            summary="Full diagnostic sweep")
async def diagnostics(db: DBSession, current_user: CurrentUser,
                      _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    return SuccessResponse(data=DiagnosticsReport(**await diagnostics_service.run_diagnostics(db)))


@router.get("/production/metrics", response_class=PlainTextResponse,
            summary="Prometheus metrics exposition")
async def prometheus_metrics(db: DBSession) -> Response:
    """
    Prometheus text format. Unauthenticated so a scraper can reach it — it
    exposes aggregate counters and row counts, never tenant records.
    Restrict at the network layer if the endpoint is internet-facing.
    """
    business = await metrics_service.collect_business_metrics(db)
    return PlainTextResponse(
        content=metrics_service.render_prometheus(business),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/production/status", response_model=SuccessResponse[SystemStatus],
            summary="System status: health, metrics and entity counts")
async def system_status(db: DBSession, current_user: CurrentUser,
                        _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    report = await diagnostics_service.run_diagnostics(db)
    business = await metrics_service.collect_business_metrics(db)

    return SuccessResponse(data=SystemStatus(
        status=report["status"],
        version=report["version"],
        environment=report["environment"],
        checked_at=report["checked_at"],
        metrics=metrics_service.registry.summary(),
        entities=business["entities"],
        active_users_24h=business["active_users_24h"],
        diagnostics=report,
    ))


# ── Farm-scoped: backups ──────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/data/backups", response_model=SuccessResponse[list[BackupRow]],
            summary="List backups")
async def list_backups(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    backups = await backup_service.list_backups(db, farm_id)
    return SuccessResponse(data=[BackupRow.model_validate(b) for b in backups])


@router.post("/farms/{farm_id}/data/backups", response_model=SuccessResponse[BackupRow],
             status_code=201, summary="Create a backup")
async def create_backup(farm_id: uuid.UUID, body: BackupCreateInput, db: DBSession,
                        current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.BACKUP_MANAGE))):
    farm, _ = access
    backup = await backup_service.create_backup(
        db, farm, current_user, label=body.label, retention_days=body.retention_days
    )
    return SuccessResponse(data=BackupRow.model_validate(backup))


@router.get("/farms/{farm_id}/data/backups/{backup_id}/verify",
            response_model=SuccessResponse[BackupVerification], summary="Verify backup integrity")
async def verify_backup(farm_id: uuid.UUID, backup_id: uuid.UUID, db: DBSession,
                        current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    return SuccessResponse(data=BackupVerification(
        **await backup_service.verify_backup(db, farm_id, backup_id)
    ))


@router.get("/farms/{farm_id}/data/backups/{backup_id}/download", summary="Download a backup")
async def download_backup(farm_id: uuid.UUID, backup_id: uuid.UUID, db: DBSession,
                          current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.BACKUP_MANAGE))):
    import json

    backup = await backup_service.get_backup(db, farm_id, backup_id)
    content = json.dumps(backup.payload, indent=2, default=str).encode("utf-8")
    filename = f"backup_{backup.id}.json"
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/farms/{farm_id}/data/backups/{backup_id}", response_model=SuccessResponse[dict],
               summary="Delete a backup")
async def delete_backup(farm_id: uuid.UUID, backup_id: uuid.UUID, db: DBSession,
                        current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.BACKUP_MANAGE))):
    await backup_service.delete_backup(db, farm_id, backup_id)
    return SuccessResponse(data={"deleted": True})


@router.post("/farms/{farm_id}/data/restore", response_model=SuccessResponse[RestoreRunRow],
             summary="Restore a backup (dry run by default)")
async def restore(farm_id: uuid.UUID, body: RestoreInput, db: DBSession,
                  current_user: CurrentUser,
                  access: tuple = Depends(require_farm_access()),
                  _p=Depends(require_permission(Permission.BACKUP_MANAGE))):
    farm, _ = access
    run = await backup_service.restore_backup(
        db, farm, body.backup_id, current_user,
        dry_run=body.dry_run, overwrite=body.overwrite,
    )
    return SuccessResponse(data=RestoreRunRow.model_validate(run))


@router.get("/farms/{farm_id}/data/restores", response_model=SuccessResponse[list[RestoreRunRow]],
            summary="List restore runs")
async def list_restores(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    runs = await backup_service.list_restore_runs(db, farm_id)
    return SuccessResponse(data=[RestoreRunRow.model_validate(r) for r in runs])


@router.post("/farms/{farm_id}/data/backups/retention", response_model=SuccessResponse[RetentionResult],
             summary="Apply the backup retention policy")
async def apply_retention(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.BACKUP_MANAGE))):
    return SuccessResponse(data=RetentionResult(
        **await backup_service.apply_retention(db, farm_id)
    ))


# ── Farm-scoped: imports ──────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/data/imports/entities",
            response_model=SuccessResponse[list[ImportEntityInfo]],
            summary="Importable entities and their columns")
async def import_entities(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    return SuccessResponse(data=[
        ImportEntityInfo(entity=name, columns=spec.columns, required=spec.required)
        for name, spec in sorted(import_service.ENTITY_SPECS.items())
    ])


@router.get("/farms/{farm_id}/data/imports/template", summary="Download a CSV import template")
async def import_template(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                          entity: str = Query(...),
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    content = import_service.entity_template(entity)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}_template.csv"'},
    )


@router.post("/farms/{farm_id}/data/imports", response_model=SuccessResponse[ImportJobRow],
             summary="Import a file (dry run by default)")
async def create_import(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                        file: UploadFile = File(...),
                        entity: str = Query(...),
                        source_format: str = Query(default="csv"),
                        dry_run: bool = Query(default=True),
                        skip_invalid: bool = Query(default=False),
                        access: tuple = Depends(require_farm_access()),
                        _p=Depends(require_permission(Permission.DATA_IMPORT))):
    farm, _ = access
    content = await file.read()
    job = await import_service.run_import(
        db, farm, entity, content, source_format, current_user,
        filename=file.filename, dry_run=dry_run, skip_invalid=skip_invalid,
    )
    return SuccessResponse(data=ImportJobRow.model_validate(job))


@router.get("/farms/{farm_id}/data/imports", response_model=SuccessResponse[list[ImportJobRow]],
            summary="Import history")
async def list_imports(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    jobs = await import_service.list_import_jobs(db, farm_id)
    return SuccessResponse(data=[ImportJobRow.model_validate(j) for j in jobs])


# ── Farm-scoped: exports ──────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/data/exports/datasets",
            response_model=SuccessResponse[list[ExportDatasetInfo]],
            summary="Exportable datasets")
async def export_datasets(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    return SuccessResponse(data=[
        ExportDatasetInfo(dataset=name, formats=list(data_export_service.SUPPORTED_FORMATS))
        for name in sorted(data_export_service.DATASETS)
    ])


@router.get("/farms/{farm_id}/data/exports/download", summary="Export a dataset")
async def download_export(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                          dataset: str = Query(...),
                          export_format: str = Query(default="csv"),
                          access: tuple = Depends(require_farm_access()),
                          _p=Depends(require_permission(Permission.DATA_EXPORT))):
    farm, _ = access
    content, filename, media_type = await data_export_service.export_dataset(
        db, farm, dataset, export_format, current_user
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/farms/{farm_id}/data/exports", response_model=SuccessResponse[list[ExportJobRow]],
            summary="Export history")
async def list_exports(farm_id: uuid.UUID, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.PRODUCTION_VIEW))):
    jobs = await data_export_service.list_export_jobs(db, farm_id)
    return SuccessResponse(data=[ExportJobRow.model_validate(j) for j in jobs])
