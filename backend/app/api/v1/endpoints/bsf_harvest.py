"""
Greena — BSF Harvest & Frass API (Module 16, Part 4)

Harvest events, frass collection and harvest readiness. Farm-scoped and
permission-guarded. Harvested/frass output optionally flows into the platform
Inventory module via the service (inbound ``adjustment`` movement); revenue is a
recorded fact on the harvest. See docs/MODULE_16_BSF_LEDGER.md for the contract.

Route map (prefix /farms/{farm_id}/bsf):
  POST /batches/{batch_id}/harvests            record a harvest
  GET  /batches/{batch_id}/harvests            harvest history
  GET  /batches/{batch_id}/harvest-readiness   deterministic readiness signal
  POST /batches/{batch_id}/frass               record frass collection
  GET  /batches/{batch_id}/frass               frass history
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.bsf import (
    FrassProductionCreate,
    FrassProductionResponse,
    HarvestEventCreate,
    HarvestEventResponse,
)
from app.services import bsf_harvest_service as svc

router = APIRouter(prefix="/farms/{farm_id}/bsf", tags=["Black Soldier Fly"])


@router.post("/batches/{batch_id}/harvests", response_model=SuccessResponse[HarvestEventResponse],
             status_code=status.HTTP_201_CREATED)
async def record_harvest(
    farm_id: UUID, batch_id: UUID, body: HarvestEventCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_HARVEST_RECORD)),
):
    farm, _ = access
    row = await svc.record_harvest(db, farm, batch_id, body, current_user)
    return SuccessResponse(data=HarvestEventResponse.model_validate(row))


@router.get("/batches/{batch_id}/harvests", response_model=SuccessResponse[list[HarvestEventResponse]])
async def list_harvests(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_HARVEST_VIEW)),
):
    rows = await svc.list_harvests(db, farm_id, batch_id)
    return SuccessResponse(data=[HarvestEventResponse.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/harvest-readiness", response_model=SuccessResponse[dict])
async def harvest_readiness(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_HARVEST_VIEW)),
):
    data = await svc.harvest_readiness(db, farm_id, batch_id)
    return SuccessResponse(data=data)


@router.post("/batches/{batch_id}/frass", response_model=SuccessResponse[FrassProductionResponse],
             status_code=status.HTTP_201_CREATED)
async def record_frass(
    farm_id: UUID, batch_id: UUID, body: FrassProductionCreate, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_HARVEST_RECORD)),
):
    farm, _ = access
    row = await svc.record_frass(db, farm, batch_id, body, current_user)
    return SuccessResponse(data=FrassProductionResponse.model_validate(row))


@router.get("/batches/{batch_id}/frass", response_model=SuccessResponse[list[FrassProductionResponse]])
async def list_frass(
    farm_id: UUID, batch_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.BSF_HARVEST_VIEW)),
):
    rows = await svc.list_frass(db, farm_id, batch_id)
    return SuccessResponse(data=[FrassProductionResponse.model_validate(r) for r in rows])
