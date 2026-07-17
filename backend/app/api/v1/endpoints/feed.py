"""
Greena — Feed Management API Endpoints (Phase 3, Module 4).

Route map (all farm-scoped under /farms/{farm_id}/feed):

  Suppliers
    POST   /feed/suppliers                 create supplier
    GET    /feed/suppliers                  list suppliers (+ spend history)
    GET    /feed/suppliers/{supplier_id}    single supplier
    PATCH  /feed/suppliers/{supplier_id}    update supplier
    DELETE /feed/suppliers/{supplier_id}    soft-delete supplier

  Inventory
    POST   /feed/inventory                  create stock item
    GET    /feed/inventory                  list stock items (levels + valuation)
    GET    /feed/inventory/{item_id}        single item
    PATCH  /feed/inventory/{item_id}        update item (reorder level, supplier…)
    DELETE /feed/inventory/{item_id}        soft-delete an empty item

  Movements
    POST   /feed/purchases                  buy feed in (books a finance expense)
    POST   /feed/consumption                feed a flock (draws stock down)
    POST   /feed/transfers                  move stock between locations
    POST   /feed/wastage                    write off spoiled / lost stock

  Reporting
    GET    /feed/transactions               ledger (filterable)
    GET    /feed/dashboard                  stock, valuation, reorder, activity
    GET    /feed/alerts                     reorder alerts
    GET    /feed/analytics                  usage, cost per bird / egg, suppliers
    GET    /feed/ai-context                 structured AI (Gemini) payload

  Per-flock
    GET    /flocks/{flock_id}/feed-consumption   a flock's feed-in history

RBAC:
  FEED_MANAGE → enterprise_owner, farm_owner, farm_manager, farm_worker
  FEED_VIEW   → all roles
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.feed import (
    FeedAIContext,
    FeedAnalyticsResponse,
    FeedConsumptionInput,
    FeedDashboardResponse,
    FeedInventoryItemCreate,
    FeedInventoryItemResponse,
    FeedInventoryItemUpdate,
    FeedPurchaseInput,
    FeedReorderAlert,
    FeedSupplierCreate,
    FeedSupplierResponse,
    FeedSupplierUpdate,
    FeedTransactionResponse,
    FeedTransferInput,
    FeedWastageInput,
)
from app.services import feed_service

router = APIRouter()

_FEED_WRITE_ROLES = {"enterprise_owner", "farm_owner", "farm_manager", "farm_worker"}


# ── Suppliers ─────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/feed/suppliers",
    response_model=SuccessResponse[FeedSupplierResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a feed supplier",
    tags=["Feed"],
)
async def create_supplier(
    farm_id: str,
    body: FeedSupplierCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[FeedSupplierResponse]:
    farm, _ = access
    supplier = await feed_service.create_supplier(db, farm, body, current_user)
    return SuccessResponse(data=FeedSupplierResponse.model_validate(supplier))


@router.get(
    "/farms/{farm_id}/feed/suppliers",
    response_model=SuccessResponse[list[FeedSupplierResponse]],
    summary="List feed suppliers with spend history",
    tags=["Feed"],
)
async def list_suppliers(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    include_inactive: bool = Query(default=False),
) -> SuccessResponse[list[FeedSupplierResponse]]:
    farm, _ = access
    suppliers = await feed_service.list_suppliers(db, farm.id, include_inactive)
    return SuccessResponse(data=suppliers)


@router.get(
    "/farms/{farm_id}/feed/suppliers/{supplier_id}",
    response_model=SuccessResponse[FeedSupplierResponse],
    summary="Get a feed supplier",
    tags=["Feed"],
)
async def get_supplier(
    farm_id: str,
    supplier_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
) -> SuccessResponse[FeedSupplierResponse]:
    farm, _ = access
    supplier = await feed_service.get_supplier(db, farm.id, UUID(supplier_id))
    return SuccessResponse(data=FeedSupplierResponse.model_validate(supplier))


@router.patch(
    "/farms/{farm_id}/feed/suppliers/{supplier_id}",
    response_model=SuccessResponse[FeedSupplierResponse],
    summary="Update a feed supplier",
    tags=["Feed"],
)
async def update_supplier(
    farm_id: str,
    supplier_id: str,
    body: FeedSupplierUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[FeedSupplierResponse]:
    farm, _ = access
    supplier = await feed_service.update_supplier(db, farm.id, UUID(supplier_id), body)
    return SuccessResponse(data=FeedSupplierResponse.model_validate(supplier))


@router.delete(
    "/farms/{farm_id}/feed/suppliers/{supplier_id}",
    response_model=SuccessResponse[dict],
    summary="Soft-delete a feed supplier",
    tags=["Feed"],
)
async def delete_supplier(
    farm_id: str,
    supplier_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    await feed_service.delete_supplier(db, farm.id, UUID(supplier_id))
    return SuccessResponse(data={"deleted": True})


# ── Inventory ─────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/feed/inventory",
    response_model=SuccessResponse[FeedInventoryItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a feed inventory item",
    tags=["Feed"],
)
async def create_item(
    farm_id: str,
    body: FeedInventoryItemCreate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[FeedInventoryItemResponse]:
    farm, _ = access
    item = await feed_service.create_item(db, farm, body, current_user)
    return SuccessResponse(data=await feed_service.get_item(db, farm.id, item.id))


@router.get(
    "/farms/{farm_id}/feed/inventory",
    response_model=SuccessResponse[list[FeedInventoryItemResponse]],
    summary="List feed inventory items (stock levels + valuation)",
    tags=["Feed"],
)
async def list_items(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    include_inactive: bool = Query(default=False),
) -> SuccessResponse[list[FeedInventoryItemResponse]]:
    farm, _ = access
    items = await feed_service.list_items(db, farm.id, include_inactive)
    return SuccessResponse(data=items)


@router.get(
    "/farms/{farm_id}/feed/inventory/{item_id}",
    response_model=SuccessResponse[FeedInventoryItemResponse],
    summary="Get a feed inventory item",
    tags=["Feed"],
)
async def get_item(
    farm_id: str,
    item_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
) -> SuccessResponse[FeedInventoryItemResponse]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.get_item(db, farm.id, UUID(item_id)))


@router.patch(
    "/farms/{farm_id}/feed/inventory/{item_id}",
    response_model=SuccessResponse[FeedInventoryItemResponse],
    summary="Update a feed inventory item",
    tags=["Feed"],
)
async def update_item(
    farm_id: str,
    item_id: str,
    body: FeedInventoryItemUpdate,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[FeedInventoryItemResponse]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.update_item(db, farm.id, UUID(item_id), body))


@router.delete(
    "/farms/{farm_id}/feed/inventory/{item_id}",
    response_model=SuccessResponse[dict],
    summary="Soft-delete an empty feed inventory item",
    tags=["Feed"],
)
async def delete_item(
    farm_id: str,
    item_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    await feed_service.delete_item(db, farm.id, UUID(item_id))
    return SuccessResponse(data={"deleted": True})


# ── Movements ─────────────────────────────────────────────────────────────────

@router.post(
    "/farms/{farm_id}/feed/purchases",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Record a feed purchase (adds stock, books a finance expense)",
    tags=["Feed"],
)
async def record_purchase(
    farm_id: str,
    body: FeedPurchaseInput,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    item, txn = await feed_service.record_purchase(db, farm, body, current_user)
    return SuccessResponse(data={
        "item": (await feed_service.get_item(db, farm.id, item.id)).model_dump(mode="json"),
        "transaction": FeedTransactionResponse.model_validate(txn).model_dump(mode="json"),
    })


@router.post(
    "/farms/{farm_id}/feed/consumption",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Record feed consumption for a flock (draws stock down)",
    tags=["Feed"],
)
async def record_consumption(
    farm_id: str,
    body: FeedConsumptionInput,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    item, txn = await feed_service.record_consumption(db, farm, body, current_user)
    return SuccessResponse(data={
        "item": (await feed_service.get_item(db, farm.id, item.id)).model_dump(mode="json"),
        "transaction": FeedTransactionResponse.model_validate(txn).model_dump(mode="json"),
    })


@router.post(
    "/farms/{farm_id}/feed/transfers",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Transfer feed between storage locations",
    tags=["Feed"],
)
async def record_transfer(
    farm_id: str,
    body: FeedTransferInput,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    src, dst = await feed_service.record_transfer(db, farm, body, current_user)
    return SuccessResponse(data={
        "from_item": (await feed_service.get_item(db, farm.id, src.id)).model_dump(mode="json"),
        "to_item": (await feed_service.get_item(db, farm.id, dst.id)).model_dump(mode="json"),
    })


@router.post(
    "/farms/{farm_id}/feed/wastage",
    response_model=SuccessResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Write off spoiled / lost feed",
    tags=["Feed"],
)
async def record_wastage(
    farm_id: str,
    body: FeedWastageInput,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access(_FEED_WRITE_ROLES)),
    _perm=Depends(require_permission(Permission.FEED_MANAGE)),
) -> SuccessResponse[dict]:
    farm, _ = access
    item, txn = await feed_service.record_wastage(db, farm, body, current_user)
    return SuccessResponse(data={
        "item": (await feed_service.get_item(db, farm.id, item.id)).model_dump(mode="json"),
        "transaction": FeedTransactionResponse.model_validate(txn).model_dump(mode="json"),
    })


# ── Reporting ─────────────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/feed/transactions",
    response_model=SuccessResponse[list[FeedTransactionResponse]],
    summary="List feed transactions (ledger)",
    tags=["Feed"],
)
async def list_transactions(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    item_id: str | None = Query(default=None),
    flock_id: str | None = Query(default=None),
    txn_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[FeedTransactionResponse]]:
    farm, _ = access
    txns = await feed_service.list_transactions(
        db, farm.id,
        item_id=UUID(item_id) if item_id else None,
        flock_id=UUID(flock_id) if flock_id else None,
        txn_type=txn_type, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return SuccessResponse(data=txns)


@router.get(
    "/farms/{farm_id}/feed/dashboard",
    response_model=SuccessResponse[FeedDashboardResponse],
    summary="Feed dashboard: stock, valuation, reorder alerts, recent activity",
    tags=["Feed"],
)
async def feed_dashboard(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    window_days: int = Query(default=30, ge=1, le=365),
) -> SuccessResponse[FeedDashboardResponse]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.get_dashboard(db, farm.id, window_days))


@router.get(
    "/farms/{farm_id}/feed/alerts",
    response_model=SuccessResponse[list[FeedReorderAlert]],
    summary="Feed reorder alerts",
    tags=["Feed"],
)
async def feed_alerts(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
) -> SuccessResponse[list[FeedReorderAlert]]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.get_reorder_alerts(db, farm.id))


@router.get(
    "/farms/{farm_id}/feed/analytics",
    response_model=SuccessResponse[FeedAnalyticsResponse],
    summary="Feed analytics: usage, cost per bird / egg, supplier + type breakdowns",
    tags=["Feed"],
)
async def feed_analytics(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    window_days: int = Query(default=90, ge=1, le=365),
) -> SuccessResponse[FeedAnalyticsResponse]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.get_analytics(db, farm.id, window_days))


@router.get(
    "/farms/{farm_id}/feed/ai-context",
    response_model=SuccessResponse[FeedAIContext],
    summary="Structured feed intelligence for ARIA / Gemini",
    tags=["Feed"],
)
async def feed_ai_context(
    farm_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    window_days: int = Query(default=90, ge=1, le=365),
) -> SuccessResponse[FeedAIContext]:
    farm, _ = access
    return SuccessResponse(data=await feed_service.get_ai_context(db, farm.id, window_days))


# ── Per-flock consumption ─────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/flocks/{flock_id}/feed-consumption",
    response_model=SuccessResponse[list[FeedTransactionResponse]],
    summary="A flock's feed consumption history",
    tags=["Feed"],
)
async def flock_feed_consumption(
    farm_id: str,
    flock_id: str,
    db: DBSession,
    current_user: CurrentUser,
    access: tuple = Depends(require_farm_access()),
    _perm=Depends(require_permission(Permission.FEED_VIEW)),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[FeedTransactionResponse]]:
    farm, _ = access
    txns = await feed_service.list_flock_consumption(db, farm.id, UUID(flock_id), limit, offset)
    return SuccessResponse(data=[FeedTransactionResponse.model_validate(t) for t in txns])
