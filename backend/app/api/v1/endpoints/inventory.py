"""
Greena — Inventory & Asset Management Endpoints (Module 6).

All farm-scoped under /farms/{farm_id}/inventory.

  Suppliers    POST/GET/GET{id}/PATCH/DELETE  /inventory/suppliers
  Items        POST/GET/GET{id}/PATCH/DELETE  /inventory/items
  Movements    POST /inventory/movements ; GET /inventory/movements
  Assets       POST/GET/GET{id}/PATCH/DELETE  /inventory/assets
  Maintenance  POST/GET/PATCH{id}/DELETE{id}  /inventory/maintenance
  Reporting    GET /inventory/dashboard | /alerts | /analytics | /ai-context

RBAC: INVENTORY_MANAGE (write) / INVENTORY_VIEW (read).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.schemas.base import SuccessResponse
from app.schemas.inventory import (
    AssetCreate,
    AssetResponse,
    AssetUpdate,
    InventoryAIContext,
    InventoryAlert,
    InventoryAnalytics,
    InventoryDashboard,
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    MaintenanceCreate,
    MaintenanceResponse,
    MaintenanceUpdate,
    MovementCreate,
    MovementResponse,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services import inventory_service

router = APIRouter()

_WRITE = {"enterprise_owner", "farm_owner", "farm_manager", "farm_worker"}


# ── Suppliers ─────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/inventory/suppliers", response_model=SuccessResponse[SupplierResponse],
             status_code=status.HTTP_201_CREATED, summary="Create supplier", tags=["Inventory"])
async def create_supplier(farm_id: str, body: SupplierCreate, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access(_WRITE)),
                          _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    s = await inventory_service.create_supplier(db, farm, body, current_user)
    return SuccessResponse(data=SupplierResponse.model_validate(s))


@router.get("/farms/{farm_id}/inventory/suppliers", response_model=SuccessResponse[list[SupplierResponse]],
            summary="List suppliers", tags=["Inventory"])
async def list_suppliers(farm_id: str, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access()),
                         _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                         include_inactive: bool = Query(default=False)):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.list_suppliers(db, farm.id, include_inactive))


@router.get("/farms/{farm_id}/inventory/suppliers/{supplier_id}", response_model=SuccessResponse[SupplierResponse],
            summary="Get supplier", tags=["Inventory"])
async def get_supplier(farm_id: str, supplier_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access()),
                       _p=Depends(require_permission(Permission.INVENTORY_VIEW))):
    farm, _ = access
    return SuccessResponse(data=SupplierResponse.model_validate(await inventory_service.get_supplier(db, farm.id, UUID(supplier_id))))


@router.patch("/farms/{farm_id}/inventory/suppliers/{supplier_id}", response_model=SuccessResponse[SupplierResponse],
              summary="Update supplier", tags=["Inventory"])
async def update_supplier(farm_id: str, supplier_id: str, body: SupplierUpdate, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access(_WRITE)),
                          _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=SupplierResponse.model_validate(await inventory_service.update_supplier(db, farm.id, UUID(supplier_id), body)))


@router.delete("/farms/{farm_id}/inventory/suppliers/{supplier_id}", response_model=SuccessResponse[dict],
               summary="Delete supplier", tags=["Inventory"])
async def delete_supplier(farm_id: str, supplier_id: str, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access(_WRITE)),
                          _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    await inventory_service.delete_supplier(db, farm.id, UUID(supplier_id))
    return SuccessResponse(data={"deleted": True})


# ── Items ─────────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/inventory/items", response_model=SuccessResponse[ItemResponse],
             status_code=status.HTTP_201_CREATED, summary="Create inventory item", tags=["Inventory"])
async def create_item(farm_id: str, body: ItemCreate, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    item = await inventory_service.create_item(db, farm, body, current_user)
    return SuccessResponse(data=await inventory_service.get_item(db, farm.id, item.id))


@router.get("/farms/{farm_id}/inventory/items", response_model=SuccessResponse[list[ItemResponse]],
            summary="List inventory items", tags=["Inventory"])
async def list_items(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                     include_inactive: bool = Query(default=False), category: str | None = Query(default=None)):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.list_items(db, farm.id, include_inactive, category))


@router.get("/farms/{farm_id}/inventory/items/{item_id}", response_model=SuccessResponse[ItemResponse],
            summary="Get inventory item", tags=["Inventory"])
async def get_item(farm_id: str, item_id: str, db: DBSession, current_user: CurrentUser,
                   access: tuple = Depends(require_farm_access()),
                   _p=Depends(require_permission(Permission.INVENTORY_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_item(db, farm.id, UUID(item_id)))


@router.patch("/farms/{farm_id}/inventory/items/{item_id}", response_model=SuccessResponse[ItemResponse],
              summary="Update inventory item", tags=["Inventory"])
async def update_item(farm_id: str, item_id: str, body: ItemUpdate, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.update_item(db, farm.id, UUID(item_id), body))


@router.delete("/farms/{farm_id}/inventory/items/{item_id}", response_model=SuccessResponse[dict],
               summary="Delete inventory item", tags=["Inventory"])
async def delete_item(farm_id: str, item_id: str, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access(_WRITE)),
                      _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    await inventory_service.delete_item(db, farm.id, UUID(item_id))
    return SuccessResponse(data={"deleted": True})


# ── Movements ─────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/inventory/movements", response_model=SuccessResponse[dict],
             status_code=status.HTTP_201_CREATED, summary="Record a stock movement", tags=["Inventory"])
async def record_movement(farm_id: str, body: MovementCreate, db: DBSession, current_user: CurrentUser,
                          access: tuple = Depends(require_farm_access(_WRITE)),
                          _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    item, move = await inventory_service.record_movement(db, farm, body, current_user)
    return SuccessResponse(data={
        "item": (await inventory_service.get_item(db, farm.id, item.id)).model_dump(mode="json"),
        "movement": MovementResponse.model_validate(move).model_dump(mode="json"),
    })


@router.get("/farms/{farm_id}/inventory/movements", response_model=SuccessResponse[list[MovementResponse]],
            summary="List stock movements", tags=["Inventory"])
async def list_movements(farm_id: str, db: DBSession, current_user: CurrentUser,
                         access: tuple = Depends(require_farm_access()),
                         _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                         item_id: str | None = Query(default=None), movement_type: str | None = Query(default=None),
                         date_from: date | None = Query(default=None), date_to: date | None = Query(default=None),
                         limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    farm, _ = access
    data = await inventory_service.list_movements(
        db, farm.id, item_id=UUID(item_id) if item_id else None, movement_type=movement_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return SuccessResponse(data=data)


# ── Assets ────────────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/inventory/assets", response_model=SuccessResponse[AssetResponse],
             status_code=status.HTTP_201_CREATED, summary="Create asset", tags=["Inventory"])
async def create_asset(farm_id: str, body: AssetCreate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_WRITE)),
                       _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    asset = await inventory_service.create_asset(db, farm, body, current_user)
    return SuccessResponse(data=await inventory_service.get_asset(db, farm.id, asset.id))


@router.get("/farms/{farm_id}/inventory/assets", response_model=SuccessResponse[list[AssetResponse]],
            summary="List assets", tags=["Inventory"])
async def list_assets(farm_id: str, db: DBSession, current_user: CurrentUser,
                      access: tuple = Depends(require_farm_access()),
                      _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                      include_inactive: bool = Query(default=False), asset_type: str | None = Query(default=None)):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.list_assets(db, farm.id, include_inactive, asset_type))


@router.get("/farms/{farm_id}/inventory/assets/{asset_id}", response_model=SuccessResponse[AssetResponse],
            summary="Get asset", tags=["Inventory"])
async def get_asset(farm_id: str, asset_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.INVENTORY_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_asset(db, farm.id, UUID(asset_id)))


@router.patch("/farms/{farm_id}/inventory/assets/{asset_id}", response_model=SuccessResponse[AssetResponse],
              summary="Update asset", tags=["Inventory"])
async def update_asset(farm_id: str, asset_id: str, body: AssetUpdate, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_WRITE)),
                       _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.update_asset(db, farm.id, UUID(asset_id), body))


@router.delete("/farms/{farm_id}/inventory/assets/{asset_id}", response_model=SuccessResponse[dict],
               summary="Delete asset", tags=["Inventory"])
async def delete_asset(farm_id: str, asset_id: str, db: DBSession, current_user: CurrentUser,
                       access: tuple = Depends(require_farm_access(_WRITE)),
                       _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    await inventory_service.delete_asset(db, farm.id, UUID(asset_id))
    return SuccessResponse(data={"deleted": True})


# ── Maintenance ───────────────────────────────────────────────────────────────

@router.post("/farms/{farm_id}/inventory/maintenance", response_model=SuccessResponse[MaintenanceResponse],
             status_code=status.HTTP_201_CREATED, summary="Log maintenance", tags=["Inventory"])
async def create_maintenance(farm_id: str, body: MaintenanceCreate, db: DBSession, current_user: CurrentUser,
                             access: tuple = Depends(require_farm_access(_WRITE)),
                             _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    m = await inventory_service.create_maintenance(db, farm, body, current_user)
    return SuccessResponse(data=MaintenanceResponse.model_validate(m))


@router.get("/farms/{farm_id}/inventory/maintenance", response_model=SuccessResponse[list[MaintenanceResponse]],
            summary="List maintenance", tags=["Inventory"])
async def list_maintenance(farm_id: str, db: DBSession, current_user: CurrentUser,
                           access: tuple = Depends(require_farm_access()),
                           _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                           asset_id: str | None = Query(default=None), status_filter: str | None = Query(default=None, alias="status")):
    farm, _ = access
    data = await inventory_service.list_maintenance(db, farm.id, asset_id=UUID(asset_id) if asset_id else None, status=status_filter)
    return SuccessResponse(data=data)


@router.patch("/farms/{farm_id}/inventory/maintenance/{maint_id}", response_model=SuccessResponse[MaintenanceResponse],
              summary="Update / complete maintenance", tags=["Inventory"])
async def update_maintenance(farm_id: str, maint_id: str, body: MaintenanceUpdate, db: DBSession, current_user: CurrentUser,
                             access: tuple = Depends(require_farm_access(_WRITE)),
                             _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.update_maintenance(db, farm.id, UUID(maint_id), body, current_user))


@router.delete("/farms/{farm_id}/inventory/maintenance/{maint_id}", response_model=SuccessResponse[dict],
               summary="Delete maintenance", tags=["Inventory"])
async def delete_maintenance(farm_id: str, maint_id: str, db: DBSession, current_user: CurrentUser,
                             access: tuple = Depends(require_farm_access(_WRITE)),
                             _p=Depends(require_permission(Permission.INVENTORY_MANAGE))):
    farm, _ = access
    await inventory_service.delete_maintenance(db, farm.id, UUID(maint_id))
    return SuccessResponse(data={"deleted": True})


# ── Reporting ─────────────────────────────────────────────────────────────────

@router.get("/farms/{farm_id}/inventory/dashboard", response_model=SuccessResponse[InventoryDashboard],
            summary="Inventory & asset dashboard", tags=["Inventory"])
async def dashboard(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                    window_days: int = Query(default=30, ge=1, le=365)):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_dashboard(db, farm.id, window_days))


@router.get("/farms/{farm_id}/inventory/alerts", response_model=SuccessResponse[list[InventoryAlert]],
            summary="Inventory & asset alerts", tags=["Inventory"])
async def alerts(farm_id: str, db: DBSession, current_user: CurrentUser,
                 access: tuple = Depends(require_farm_access()),
                 _p=Depends(require_permission(Permission.INVENTORY_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_alerts(db, farm.id))


@router.get("/farms/{farm_id}/inventory/analytics", response_model=SuccessResponse[InventoryAnalytics],
            summary="Inventory analytics (valuation, velocity, reorder, suppliers)", tags=["Inventory"])
async def analytics(farm_id: str, db: DBSession, current_user: CurrentUser,
                    access: tuple = Depends(require_farm_access()),
                    _p=Depends(require_permission(Permission.INVENTORY_VIEW)),
                    window_days: int = Query(default=90, ge=1, le=365)):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_analytics(db, farm.id, window_days))


@router.get("/farms/{farm_id}/inventory/ai-context", response_model=SuccessResponse[InventoryAIContext],
            summary="Structured inventory intelligence for ARIA / Gemini", tags=["Inventory"])
async def ai_context(farm_id: str, db: DBSession, current_user: CurrentUser,
                     access: tuple = Depends(require_farm_access()),
                     _p=Depends(require_permission(Permission.INVENTORY_VIEW))):
    farm, _ = access
    return SuccessResponse(data=await inventory_service.get_ai_context(db, farm.id))
