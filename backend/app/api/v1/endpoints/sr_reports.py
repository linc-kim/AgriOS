"""
Greena — Small Ruminant Reports API (Modules 18/19, Milestone 9).

Composed deterministic analytics for a goat or sheep workspace: an executive
dashboard, a short-range forecast, ranked operational bottlenecks and a CSV export
of the registry. Reads require SR_REPORT_VIEW; the CSV export requires
SR_REPORT_EXPORT (workers excluded — strategic views).

Route map (prefix /farms/{farm_id}/sr/{species}/reports):
    GET  /dashboard        executive dashboard (composed summaries + forecast + bottlenecks)
    GET  /forecast         short-range herd/offspring projection
    GET  /bottlenecks      ranked operational constraints
    GET  /registry.csv     registry export (CSV)
"""

from fastapi import APIRouter, Depends, Query

from fastapi.responses import Response

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.services import small_ruminant_reporting_service as rsvc
from app.api.v1.endpoints.sr_animals import SpeciesParam

router = APIRouter(prefix="/farms/{farm_id}/sr/{species}/reports", tags=["Small Ruminant Reports"])


@router.get("/dashboard", response_model=SuccessResponse[dict])
async def dashboard(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    forecast_months: int = Query(6, ge=1, le=36),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_REPORT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.executive_dashboard(db, farm.id, species, forecast_months))


@router.get("/forecast", response_model=SuccessResponse[dict])
async def forecast(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    months: int = Query(6, ge=1, le=36),
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_REPORT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.forecast_report(db, farm.id, species, months))


@router.get("/bottlenecks", response_model=SuccessResponse[list[dict]])
async def bottlenecks(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_REPORT_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.bottlenecks(db, farm.id, species))


@router.get("/registry.csv")
async def registry_csv(
    farm_id: str, db: DBSession, current_user: CurrentUser, species: str = SpeciesParam,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SR_REPORT_EXPORT)),
):
    farm, _ = access
    csv_text = await rsvc.export_registry_csv(db, farm.id, species)
    return Response(content=csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{species}_registry.csv"'})
