"""
Greena — Swine Biosecurity API (Module 20, Milestone 6).

Operational biosecurity records — visitor/vehicle logs, equipment disinfection,
staff sanitation, pen cleaning, rodent control, dead-stock disposal, quarantine and
inspections. ``reminder_id`` softly links a record to a Greena Operations task.
Writes require SWINE_HEALTH_LOG; reads SWINE_HEALTH_VIEW.

Route map (prefix /farms/{farm_id}/swine/biosecurity):
    GET/POST /            list / create biosecurity records (filter ?record_type=)
    PATCH    /{record_id} update a record
    GET      /summary     tally by record type
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    BiosecurityRecordCreate,
    BiosecurityRecordResponse,
    BiosecurityRecordUpdate,
)
from app.services import swine_biosecurity_service as svc

router = APIRouter(prefix="/farms/{farm_id}/swine/biosecurity", tags=["Swine Biosecurity"])


@router.get("", response_model=SuccessResponse[list[BiosecurityRecordResponse]])
async def list_records(
    farm_id: str, db: DBSession, current_user: CurrentUser, record_type: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HEALTH_VIEW)),
):
    farm, _ = access
    rows = await svc.list_records(db, farm.id, record_type=record_type)
    return SuccessResponse(data=[BiosecurityRecordResponse.model_validate(r) for r in rows])


@router.post("", response_model=SuccessResponse[BiosecurityRecordResponse], status_code=status.HTTP_201_CREATED)
async def create_record(
    farm_id: str, body: BiosecurityRecordCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HEALTH_LOG)),
):
    farm, _ = access
    row = await svc.create_record(db, farm, body, current_user)
    return SuccessResponse(data=BiosecurityRecordResponse.model_validate(row))


@router.get("/summary", response_model=SuccessResponse[dict])
async def biosecurity_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HEALTH_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await svc.summary(db, farm.id))


@router.patch("/{record_id}", response_model=SuccessResponse[BiosecurityRecordResponse])
async def update_record(
    farm_id: str, record_id: UUID, body: BiosecurityRecordUpdate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_HEALTH_LOG)),
):
    farm, _ = access
    row = await svc.update_record(db, farm.id, record_id, body, current_user)
    return SuccessResponse(data=BiosecurityRecordResponse.model_validate(row))
