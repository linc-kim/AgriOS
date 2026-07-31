"""
Greena — BSF Reports & Executive Dashboard API (Module 16, Part 6)

Composed reporting over the deterministic engines (Spec Part 4 §11 §13 §16,
Part 7 §11-19). Farm-scoped and permission-guarded. The dashboard exposes both
recorded facts and derived analytics so every conclusion is traceable; forecasts
are always labelled and never presented as confirmed. CSV export reuses the
platform ``Response`` pattern.

Route map (prefix /farms/{farm_id}/bsf/reports):
  GET /dashboard            executive dashboard (facts + analytics + scores + forecast + bottlenecks)
  GET /forecast            production/feed/revenue projections (labelled forecast)
  GET /bottlenecks          ranked operational bottlenecks
  GET /production.csv       per-batch production export (CSV)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.services import bsf_reporting_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf/reports", tags=["Black Soldier Fly"])


@router.get("/dashboard", response_model=SuccessResponse[dict])
async def dashboard(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_REPORT_VIEW)),
):
    return SuccessResponse(data=await svc.executive_dashboard(db, farm_id))


@router.get("/forecast", response_model=SuccessResponse[dict])
async def forecast(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_REPORT_VIEW)),
    horizon_days: int = Query(90, ge=1, le=365),
    window_days: int = Query(90, ge=1, le=365),
):
    return SuccessResponse(data=await svc.forecast(db, farm_id, horizon_days=horizon_days, window_days=window_days))


@router.get("/bottlenecks", response_model=SuccessResponse[list[dict]])
async def bottlenecks(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_REPORT_VIEW)),
):
    dash = await svc.executive_dashboard(db, farm_id)
    return SuccessResponse(data=dash["bottlenecks"])


@router.get("/production.csv")
async def production_csv(
    farm_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_REPORT_EXPORT)),
):
    content = await svc.export_production_rows(db, farm_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bsf_production.csv"'},
    )
