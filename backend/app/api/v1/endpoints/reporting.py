"""
Greena — Reporting & Business Intelligence Endpoints (Module 7).

All farm-scoped under /farms/{farm_id}/reporting. Reports are cross-module,
read-only compositions, so reads are gated on FLOCK_VIEW (all farm members).

  GET  /reporting/generate            report_type + period → section-based report
  GET  /reporting/generate/csv        same, as CSV download
  GET  /reporting/dashboards/{role}   role dashboard
  GET  /reporting/comparisons         flock/month/year comparison
  CRUD /reporting/saved               saved / pinned report configurations
"""

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from fastapi import status as http_status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.reporting import (
    Report,
    SavedReportCreate,
    SavedReportResponse,
    SavedReportUpdate,
)
from app.services import reporting_service

router = APIRouter()


@router.get("/farms/{farm_id}/reporting/generate", response_model=SuccessResponse[Report],
            summary="Generate a report", tags=["Reporting"])
async def generate(farm_id: str, db: DBSession, current_user: CurrentUser,
                   access: tuple = Depends(require_farm_access()),
                   _p=Depends(require_permission(Permission.FLOCK_VIEW)),
                   report_type: str = Query(...), period_type: str = Query(default="monthly"),
                   start: date | None = Query(default=None), end: date | None = Query(default=None)):
    farm, _ = access
    return SuccessResponse(data=await reporting_service.generate_report(db, farm, report_type, period_type, start, end))


@router.get("/farms/{farm_id}/reporting/generate/csv", summary="Generate a report as CSV", tags=["Reporting"])
async def generate_csv(farm_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.FLOCK_VIEW)),
                       report_type: str = Query(...), period_type: str = Query(default="monthly"),
                       start: date | None = Query(default=None), end: date | None = Query(default=None)) -> Response:
    farm, _ = access
    report = await reporting_service.generate_report(db, farm, report_type, period_type, start, end)
    csv_text = reporting_service.report_to_csv(report)
    return Response(content=csv_text, media_type="text/csv", status_code=http_status.HTTP_200_OK,
                    headers={"Content-Disposition": f'attachment; filename="{report_type}_report.csv"'})


@router.get("/farms/{farm_id}/reporting/dashboards/{role}", response_model=SuccessResponse[Report],
            summary="Role dashboard", tags=["Reporting"])
async def dashboard(farm_id: str, role: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.FLOCK_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await reporting_service.get_dashboard(db, farm, role))


@router.get("/farms/{farm_id}/reporting/comparisons", response_model=SuccessResponse[Report],
            summary="Comparison report", tags=["Reporting"])
async def comparison(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _p=Depends(require_permission(Permission.FLOCK_VIEW)),
                     comparison_type: str = Query(...),
                     flock_a: str | None = Query(default=None), flock_b: str | None = Query(default=None)):
    from uuid import UUID
    farm, _ = access
    return SuccessResponse(data=await reporting_service.get_comparison(
        db, farm, comparison_type,
        UUID(flock_a) if flock_a else None, UUID(flock_b) if flock_b else None))


# ── Saved reports ─────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/reporting/saved", response_model=SuccessResponse[SavedReportResponse],
             status_code=http_status.HTTP_201_CREATED, summary="Save a report", tags=["Reporting"])
async def create_saved(farm_id: str, body: SavedReportCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.FLOCK_VIEW))):
    farm, _ = access
    sr = await reporting_service.create_saved_report(db, farm.id, current_user, body)
    return SuccessResponse(data=SavedReportResponse.model_validate(sr))


@router.get("/farms/{farm_id}/reporting/saved", response_model=SuccessResponse[list[SavedReportResponse]],
            summary="List saved / pinned reports", tags=["Reporting"])
async def list_saved(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _p=Depends(require_permission(Permission.FLOCK_VIEW))):
    farm, _ = access
    rows = await reporting_service.list_saved_reports(db, farm.id)
    return SuccessResponse(data=[SavedReportResponse.model_validate(r) for r in rows])


@router.patch("/farms/{farm_id}/reporting/saved/{report_id}", response_model=SuccessResponse[SavedReportResponse],
              summary="Update / pin a saved report", tags=["Reporting"])
async def update_saved(farm_id: str, report_id: str, body: SavedReportUpdate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.FLOCK_VIEW))):
    from uuid import UUID
    farm, _ = access
    sr = await reporting_service.update_saved_report(db, farm.id, UUID(report_id), body)
    return SuccessResponse(data=SavedReportResponse.model_validate(sr))


@router.delete("/farms/{farm_id}/reporting/saved/{report_id}", response_model=SuccessResponse[dict],
               summary="Delete a saved report", tags=["Reporting"])
async def delete_saved(farm_id: str, report_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.FLOCK_VIEW))):
    from uuid import UUID
    farm, _ = access
    await reporting_service.delete_saved_report(db, farm.id, UUID(report_id))
    return SuccessResponse(data={"deleted": True})
