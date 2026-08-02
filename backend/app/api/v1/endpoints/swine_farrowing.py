"""
Greena — Swine Farrowing, Litters & Fostering API (Module 20, Milestone 4).

Farrowing → litter → (optional individual pigs) → fostering → weaning. Litter-level
and individualised management are both supported. Writes require
SWINE_BREEDING_MANAGE; reads SWINE_BREEDING_VIEW.

Route map (prefix /farms/{farm_id}/swine/farrowing):
    POST  /                         record a farrowing (+ litter, optional piglets)
    GET   /                         list farrowings
    GET   /summary                  herd litter/farrowing analytics
    GET   /{farrowing_id}           farrowing + litter + performance
    GET   /litters                  list litters
    GET   /litters/{litter_id}      litter + performance + individual count
    POST  /litters/{litter_id}/piglets    add an individual piglet
    POST  /litters/{litter_id}/mortality  record pre-wean mortality
    POST  /litters/{litter_id}/wean       wean the litter
    POST  /foster                   cross-foster piglets between litters
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.swine import (
    FarrowingRecordInput,
    FarrowingResponse,
    FosterTransferInput,
    FosterTransferResponse,
    LitterMortalityInput,
    LitterResponse,
    PigletAddInput,
    PigResponse,
    WeaningInput,
)
from app.services import swine_farrowing_service as fsvc

router = APIRouter(prefix="/farms/{farm_id}/swine/farrowing", tags=["Swine Farrowing"])


@router.post("", response_model=SuccessResponse[dict], status_code=status.HTTP_201_CREATED)
async def record_farrowing(
    farm_id: str, body: FarrowingRecordInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    farrowing, litter, created = await fsvc.record_farrowing(db, farm, body, current_user)
    return SuccessResponse(data={
        "farrowing": FarrowingResponse.model_validate(farrowing).model_dump(mode="json"),
        "litter": LitterResponse.model_validate(litter).model_dump(mode="json"),
        "individuals_created": created,
    })


@router.get("", response_model=SuccessResponse[list[FarrowingResponse]])
async def list_farrowings(
    farm_id: str, db: DBSession, current_user: CurrentUser, dam_id: UUID | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await fsvc.list_farrowings(db, farm.id, dam_id=dam_id)
    return SuccessResponse(data=[FarrowingResponse.model_validate(r) for r in rows])


@router.get("/summary", response_model=SuccessResponse[dict])
async def farrowing_summary(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    return SuccessResponse(data=await fsvc.farrowing_summary(db, farm.id))


@router.get("/litters", response_model=SuccessResponse[list[LitterResponse]])
async def list_litters(
    farm_id: str, db: DBSession, current_user: CurrentUser,
    dam_id: UUID | None = None, status_: str | None = None,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    rows = await fsvc.list_litters(db, farm.id, dam_id=dam_id, status=status_)
    return SuccessResponse(data=[LitterResponse.model_validate(r) for r in rows])


@router.get("/litters/{litter_id}", response_model=SuccessResponse[dict])
async def get_litter(
    farm_id: str, litter_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    litter, performance, individuals = await fsvc.get_litter_detail(db, farm.id, litter_id)
    return SuccessResponse(data={
        "litter": LitterResponse.model_validate(litter).model_dump(mode="json"),
        "performance": performance,
        "individual_pig_count": individuals,
    })


@router.post("/litters/{litter_id}/piglets", response_model=SuccessResponse[PigResponse],
             status_code=status.HTTP_201_CREATED)
async def add_piglet(
    farm_id: str, litter_id: UUID, body: PigletAddInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    pig = await fsvc.add_piglet(db, farm, litter_id, body, current_user)
    return SuccessResponse(data=PigResponse.model_validate(pig))


@router.post("/litters/{litter_id}/mortality", response_model=SuccessResponse[LitterResponse])
async def record_mortality(
    farm_id: str, litter_id: UUID, body: LitterMortalityInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    litter = await fsvc.record_mortality(db, farm.id, litter_id, body, current_user)
    return SuccessResponse(data=LitterResponse.model_validate(litter))


@router.post("/litters/{litter_id}/wean", response_model=SuccessResponse[LitterResponse])
async def record_weaning(
    farm_id: str, litter_id: UUID, body: WeaningInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    litter = await fsvc.record_weaning(db, farm, litter_id, body, current_user)
    return SuccessResponse(data=LitterResponse.model_validate(litter))


@router.post("/foster", response_model=SuccessResponse[FosterTransferResponse],
             status_code=status.HTTP_201_CREATED)
async def foster_transfer(
    farm_id: str, body: FosterTransferInput, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_MANAGE)),
):
    farm, _ = access
    transfer = await fsvc.foster_transfer(db, farm, body, current_user)
    return SuccessResponse(data=FosterTransferResponse.model_validate(transfer))


# Declared last so the static /summary, /litters and /foster paths above are not
# shadowed by the {farrowing_id} path parameter.
@router.get("/{farrowing_id}", response_model=SuccessResponse[dict])
async def get_farrowing(
    farm_id: str, farrowing_id: UUID, db: DBSession, current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.SWINE_BREEDING_VIEW)),
):
    farm, _ = access
    farrowing, litter, performance = await fsvc.get_farrowing_detail(db, farm.id, farrowing_id)
    return SuccessResponse(data={
        "farrowing": FarrowingResponse.model_validate(farrowing).model_dump(mode="json"),
        "litter": (LitterResponse.model_validate(litter).model_dump(mode="json") if litter else None),
        "performance": performance,
    })
