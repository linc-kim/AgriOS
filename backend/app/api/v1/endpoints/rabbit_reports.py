"""
Greena — Rabbit Analytics & Reporting API (Module 17, Milestone 7).

Executive dashboard, forecast, bottlenecks, executive summary and CSV export.
Thin routes only — all logic lives in the reporting service and pure engines.
Reads → RABBIT_REPORT_VIEW; CSV export → RABBIT_REPORT_EXPORT.

Route map (prefix /farms/{farm_id}/rabbit/reports):
  GET /dashboard            executive dashboard (facts + analytics + forecast)
  GET /forecast             herd/kits/feed/revenue/capacity forecast
  GET /bottlenecks          ranked operational constraints
  GET /executive-summary    concise executive summary
  GET /herd.csv             herd inventory export (CSV)
"""

from fastapi import APIRouter, Depends, Query, Response

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.services import rabbit_reporting_service as svc

router = APIRouter(prefix="/farms/{farm_id}/rabbit/reports", tags=["Rabbit Reports"])

_VIEW = Permission.RABBIT_REPORT_VIEW
_EXPORT = Permission.RABBIT_REPORT_EXPORT


@router.get("/dashboard", response_model=SuccessResponse[dict])
async def dashboard(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.executive_dashboard(db, farm.id))


@router.get("/forecast", response_model=SuccessResponse[dict])
async def forecast(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
    horizon_days: int = Query(90, ge=1, le=365),
    window_days: int = Query(90, ge=1, le=365),
):
    farm, _ = access
    return SuccessResponse(data=await svc.forecast(db, farm.id, horizon_days=horizon_days, window_days=window_days))


@router.get("/bottlenecks", response_model=SuccessResponse[list[dict]])
async def bottlenecks(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.bottlenecks(db, farm.id))


@router.get("/executive-summary", response_model=SuccessResponse[dict])
async def executive_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.executive_summary(db, farm.id))


@router.get("/herd.csv")
async def herd_csv(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=Depends(require_permission(_EXPORT)),
):
    farm, _ = access
    return Response(
        content=await svc.export_herd_csv(db, farm.id),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rabbit_herd.csv"'},
    )
