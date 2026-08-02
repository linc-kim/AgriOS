"""
Greena — Swine Reports & Analytics API (Module 20, Milestone 9).

Composed, explainable, read-only analytics at every level — individual pig, litter,
pen, farm and organization — plus CSV exports. Nothing is stored: reports are
generated on demand from the domain engines. Reads require SWINE_REPORT_VIEW; CSV
exports require SWINE_REPORT_EXPORT (workers excluded — strategic views).

Route map (prefix /farms/{farm_id}/swine/reports):
    GET /pig/{pig_id}         individual pig report (growth/health/breeding/movement/finance)
    GET /litter/{litter_id}   litter report (birth/survival/growth/weaning)
    GET /pen/{pen_id}         pen report (occupancy/production/growth/health)
    GET /farm                 farm dashboard (production/finance/health/growth/reproduction)
    GET /organization         cross-farm comparison + executive KPIs + benchmarking
    GET /registry.csv         registry export
    GET /sales.csv            sales export
    GET /mortality.csv        mortality export
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.services import swine_reporting_service as rsvc

router = APIRouter(prefix="/farms/{farm_id}/swine/reports", tags=["Swine Reports"])

_VIEW = Depends(require_permission(Permission.SWINE_REPORT_VIEW))
_EXPORT = Depends(require_permission(Permission.SWINE_REPORT_EXPORT))


@router.get("/pig/{pig_id}", response_model=SuccessResponse[dict])
async def pig_report(
    farm_id: str, pig_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.pig_report(db, farm.id, pig_id))


@router.get("/litter/{litter_id}", response_model=SuccessResponse[dict])
async def litter_report(
    farm_id: str, litter_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.litter_report(db, farm.id, litter_id))


@router.get("/pen/{pen_id}", response_model=SuccessResponse[dict])
async def pen_report(
    farm_id: str, pen_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.pen_report(db, farm.id, pen_id))


@router.get("/farm", response_model=SuccessResponse[dict])
async def farm_dashboard(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.farm_dashboard(db, farm.id))


@router.get("/organization", response_model=SuccessResponse[dict])
async def organization_report(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_VIEW,
):
    farm, _ = access
    return SuccessResponse(data=await rsvc.organization_report(db, farm))


def _csv(text: str, name: str) -> Response:
    return Response(content=text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/registry.csv")
async def registry_csv(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_EXPORT,
):
    farm, _ = access
    return _csv(await rsvc.export_registry_csv(db, farm.id), "swine_registry.csv")


@router.get("/sales.csv")
async def sales_csv(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_EXPORT,
):
    farm, _ = access
    return _csv(await rsvc.export_sales_csv(db, farm.id), "swine_sales.csv")


@router.get("/mortality.csv")
async def mortality_csv(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()), _perm=_EXPORT,
):
    farm, _ = access
    return _csv(await rsvc.export_mortality_csv(db, farm.id), "swine_mortality.csv")
