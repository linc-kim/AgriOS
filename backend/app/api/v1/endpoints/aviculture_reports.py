"""
Greena — Aviculture Reports & Analytics API (Module 15, Part 8)

Evidence-backed, computed-not-stored reports: a farm-level aviculture dashboard,
a deterministic population forecast, and a collection export. Reports compose the
existing engines; every figure is honesty-labelled. Farm-scoped, permission-guarded.

Prefix: /farms/{farm_id}/aviculture/reports
"""

import csv
import io

from fastapi import APIRouter, Depends, Query, Response

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.services import aviculture_reporting_service as svc

router = APIRouter(prefix="/farms/{farm_id}/aviculture/reports", tags=["Aviculture — Reports"])


@router.get("/dashboard", response_model=SuccessResponse[dict])
async def dashboard(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await svc.dashboard(db, farm))


@router.get("/forecast", response_model=SuccessResponse[dict])
async def population_forecast(farm_id: str, db: DBSession, current_user: CurrentUser,
                             access: tuple = Depends(require_farm_access()),
                             _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW)),
                             horizon_days: int = Query(90, ge=1, le=730),
                             window_days: int = Query(90, ge=1, le=730)):
    farm, _ = access
    return SuccessResponse(data=await svc.population_forecast(
        db, farm, horizon_days=horizon_days, window_days=window_days))


@router.get("/collection.csv")
async def export_collection_csv(farm_id: str, db: DBSession, current_user: CurrentUser,
                                access: tuple = Depends(require_farm_access()),
                                _perm=Depends(require_permission(Permission.AVI_BIRD_VIEW))):
    farm, _ = access
    rows = await svc.export_collection_rows(db, farm)
    buf = io.StringIO()
    fields = ["reference", "name", "species", "sex", "lifecycle_stage", "status"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="aviculture_collection.csv"'},
    )
