"""
Greena — Inventory & Asset Management Service (Module 6).

A general store/inventory system with a stock-movement ledger, plus fixed-asset
tracking (straight-line depreciation) and maintenance. Integrates with Finance:
stock-in and completed maintenance book expenses automatically.

Stock invariants:
  * item.quantity is never allowed below zero.
  * avg_cost is a weighted average maintained on inbound movements.
  * outbound movements value stock at the current average cost.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, case as sa_case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.inventory import (
    Asset,
    AssetMaintenance,
    InventoryItem,
    InventoryMovement,
    InventorySupplier,
)
from app.schemas.inventory import (
    AssetCreate,
    AssetResponse,
    AssetUpdate,
    CategoryValuation,
    InventoryAIContext,
    InventoryAlert,
    InventoryAnalytics,
    InventoryDashboard,
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    ItemVelocity,
    MaintenanceCreate,
    MaintenanceResponse,
    MaintenanceUpdate,
    MovementCreate,
    MovementResponse,
    MovementTrendPoint,
    ReorderRecommendation,
    SupplierCreate,
    SupplierPerformance,
    SupplierResponse,
    SupplierUpdate,
)

_Q3 = Decimal("0.001")
_Q4 = Decimal("0.0001")
_Q = Decimal("0.01")

_IN_TYPES = {"stock_in", "transfer_in", "return", "adjustment"}
_OUT_TYPES = {"stock_out", "transfer_out", "loss", "damage", "consumption"}

# Inventory category → finance expense category slug (for stock-in expenses).
_CATEGORY_EXPENSE_SLUG = {
    "feed": "feed_purchase",
    "medication": "medication",
    "vaccines": "vaccination",
    "equipment": "equipment",
    "spare_parts": "repairs",
    "cleaning_supplies": "biosecurity",
}


def _direction(movement_type: str) -> int:
    return 1 if movement_type in _IN_TYPES else -1


async def _get_item(db, farm_id, item_id) -> InventoryItem:
    res = await db.execute(select(InventoryItem).where(
        InventoryItem.id == item_id, InventoryItem.farm_id == farm_id, InventoryItem.deleted_at.is_(None)))
    item = res.scalar_one_or_none()
    if item is None:
        raise NotFoundException("Inventory item not found.")
    return item


async def _get_supplier(db, farm_id, supplier_id) -> InventorySupplier:
    res = await db.execute(select(InventorySupplier).where(
        InventorySupplier.id == supplier_id, InventorySupplier.farm_id == farm_id, InventorySupplier.deleted_at.is_(None)))
    s = res.scalar_one_or_none()
    if s is None:
        raise NotFoundException("Supplier not found.")
    return s


async def _get_asset(db, farm_id, asset_id) -> Asset:
    res = await db.execute(select(Asset).where(
        Asset.id == asset_id, Asset.farm_id == farm_id, Asset.deleted_at.is_(None)))
    a = res.scalar_one_or_none()
    if a is None:
        raise NotFoundException("Asset not found.")
    return a


async def _supplier_name(db, supplier_id) -> Optional[str]:
    if supplier_id is None:
        return None
    res = await db.execute(select(InventorySupplier.name).where(InventorySupplier.id == supplier_id))
    return res.scalar_one_or_none()


async def _audit(db, action, rtype, rid, farm_id, user_id, new_value=None):
    from app.services import audit_service
    await audit_service.log_action(db, action=action, resource_type=rtype, resource_id=rid,
                                   farm_id=farm_id, user_id=user_id, new_value=new_value)


def _item_response(item: InventoryItem, supplier_name: Optional[str] = None) -> ItemResponse:
    return ItemResponse(
        id=item.id, created_at=item.created_at, updated_at=item.updated_at,
        farm_id=item.farm_id, sku=item.sku, barcode=item.barcode, qr_code=item.qr_code,
        name=item.name, description=item.description, category=item.category, unit=item.unit,
        quantity=item.quantity, min_stock=item.min_stock, reorder_level=item.reorder_level,
        location=item.location, supplier_id=item.supplier_id, supplier_name=supplier_name,
        purchase_price=item.purchase_price, avg_cost=item.avg_cost, current_value=item.current_value,
        batch_number=item.batch_number, serial_number=item.serial_number,
        manufacture_date=item.manufacture_date, expiry_date=item.expiry_date,
        warranty_expiry=item.warranty_expiry, is_active=item.is_active, notes=item.notes,
        is_low_stock=item.is_low_stock, is_out_of_stock=item.is_out_of_stock,
        is_expired=item.is_expired, is_expiring_soon=item.is_expiring_soon,
        days_to_expiry=item.days_to_expiry, created_by=item.created_by,
    )


def _asset_response(asset: Asset) -> AssetResponse:
    return AssetResponse(
        id=asset.id, created_at=asset.created_at, updated_at=asset.updated_at,
        farm_id=asset.farm_id, asset_type=asset.asset_type, name=asset.name,
        description=asset.description, serial_number=asset.serial_number,
        purchase_date=asset.purchase_date, purchase_price=asset.purchase_price,
        depreciation_method=asset.depreciation_method, useful_life_years=asset.useful_life_years,
        salvage_value=asset.salvage_value, warranty_expiry=asset.warranty_expiry,
        location=asset.location, assigned_user_id=asset.assigned_user_id, condition=asset.condition,
        service_interval_days=asset.service_interval_days, last_service_date=asset.last_service_date,
        next_service_date=asset.next_service_date, is_active=asset.is_active, notes=asset.notes,
        age_days=asset.age_days, current_value=asset.current_value,
        accumulated_depreciation=asset.accumulated_depreciation,
        is_maintenance_due=asset.is_maintenance_due, is_warranty_expiring=asset.is_warranty_expiring,
        created_by=asset.created_by,
    )


# ── Suppliers ─────────────────────────────────────────────────────────────────

async def create_supplier(db, farm: Farm, data: SupplierCreate, user: User) -> InventorySupplier:
    s = InventorySupplier(
        farm_id=farm.id, name=data.name, contact_name=data.contact_name, phone=data.phone,
        email=data.email, address=data.address, products_supplied=data.products_supplied,
        rating=data.rating, outstanding_balance=data.outstanding_balance, notes=data.notes,
        created_by=user.id,
    )
    db.add(s)
    await db.flush()
    await _audit(db, "inventory.supplier.create", "inventory_supplier", s.id, farm.id, user.id, {"name": s.name})
    await db.commit()
    await db.refresh(s)
    return s


async def list_suppliers(db, farm_id, include_inactive=False) -> list[SupplierResponse]:
    filters = [InventorySupplier.farm_id == farm_id, InventorySupplier.deleted_at.is_(None)]
    if not include_inactive:
        filters.append(InventorySupplier.is_active.is_(True))
    res = await db.execute(select(InventorySupplier).where(*filters).order_by(InventorySupplier.name.asc()))
    suppliers = list(res.scalars().all())

    spend_res = await db.execute(
        select(InventoryMovement.supplier_id, func.coalesce(func.sum(InventoryMovement.total_cost), 0), func.count(InventoryMovement.id))
        .where(InventoryMovement.farm_id == farm_id, InventoryMovement.deleted_at.is_(None),
               InventoryMovement.movement_type == "stock_in", InventoryMovement.supplier_id.is_not(None))
        .group_by(InventoryMovement.supplier_id)
    )
    spend = {sid: (Decimal(c), int(n)) for sid, c, n in spend_res.all()}
    out = []
    for s in suppliers:
        cost, cnt = spend.get(s.id, (Decimal("0"), 0))
        resp = SupplierResponse.model_validate(s)
        resp.total_spend = cost
        resp.order_count = cnt
        out.append(resp)
    return out


async def get_supplier(db, farm_id, supplier_id) -> InventorySupplier:
    return await _get_supplier(db, farm_id, supplier_id)


async def update_supplier(db, farm_id, supplier_id, data: SupplierUpdate) -> InventorySupplier:
    s = await _get_supplier(db, farm_id, supplier_id)
    for f in ("name", "contact_name", "phone", "email", "address", "products_supplied",
              "rating", "outstanding_balance", "is_active", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(s, f, v)
    s.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(s)
    return s


async def delete_supplier(db, farm_id, supplier_id) -> None:
    s = await _get_supplier(db, farm_id, supplier_id)
    s.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Items ─────────────────────────────────────────────────────────────────────

def _gen_sku(category: str) -> str:
    return f"INV-{category[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"


async def create_item(db, farm: Farm, data: ItemCreate, user: User) -> InventoryItem:
    if data.supplier_id is not None:
        await _get_supplier(db, farm.id, data.supplier_id)
    item = InventoryItem(
        farm_id=farm.id, sku=data.sku or _gen_sku(data.category), barcode=data.barcode, qr_code=data.qr_code,
        name=data.name, description=data.description, category=data.category, unit=data.unit,
        quantity=data.opening_quantity, min_stock=data.min_stock, reorder_level=data.reorder_level,
        location=data.location, supplier_id=data.supplier_id, purchase_price=data.purchase_price,
        avg_cost=data.opening_cost, batch_number=data.batch_number, serial_number=data.serial_number,
        manufacture_date=data.manufacture_date, expiry_date=data.expiry_date,
        warranty_expiry=data.warranty_expiry, notes=data.notes, created_by=user.id,
    )
    db.add(item)
    await db.flush()
    if data.opening_quantity and data.opening_quantity > 0:
        db.add(InventoryMovement(
            farm_id=farm.id, item_id=item.id, movement_type="adjustment", direction=1,
            quantity=data.opening_quantity, qty_before=Decimal("0"), qty_after=data.opening_quantity,
            unit_cost=data.opening_cost, total_cost=(data.opening_quantity * data.opening_cost).quantize(_Q),
            reason="opening_balance", created_by=user.id,
        ))
    await _audit(db, "inventory.item.create", "inventory_item", item.id, farm.id, user.id,
                 {"name": item.name, "category": item.category})
    await db.commit()
    await db.refresh(item)
    return item


async def list_items(db, farm_id, include_inactive=False, category=None) -> list[ItemResponse]:
    filters = [InventoryItem.farm_id == farm_id, InventoryItem.deleted_at.is_(None)]
    if not include_inactive:
        filters.append(InventoryItem.is_active.is_(True))
    if category:
        filters.append(InventoryItem.category == category)
    res = await db.execute(
        select(InventoryItem, InventorySupplier.name)
        .outerjoin(InventorySupplier, InventoryItem.supplier_id == InventorySupplier.id)
        .where(*filters).order_by(InventoryItem.category.asc(), InventoryItem.name.asc())
    )
    return [_item_response(i, n) for i, n in res.all()]


async def get_item(db, farm_id, item_id) -> ItemResponse:
    item = await _get_item(db, farm_id, item_id)
    return _item_response(item, await _supplier_name(db, item.supplier_id))


async def update_item(db, farm_id, item_id, data: ItemUpdate) -> ItemResponse:
    item = await _get_item(db, farm_id, item_id)
    if data.supplier_id is not None:
        await _get_supplier(db, farm_id, data.supplier_id)
    for f in ("name", "description", "category", "sku", "barcode", "qr_code", "unit", "location",
              "min_stock", "reorder_level", "supplier_id", "purchase_price", "batch_number",
              "serial_number", "manufacture_date", "expiry_date", "warranty_expiry", "is_active", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(item, f, v)
    item.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _item_response(item, await _supplier_name(db, item.supplier_id))


async def delete_item(db, farm_id, item_id) -> None:
    item = await _get_item(db, farm_id, item_id)
    if item.quantity and item.quantity > 0:
        raise ValidationException("Cannot delete an item that still holds stock. Write it off first.")
    item.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Movements ─────────────────────────────────────────────────────────────────

async def record_movement(db, farm: Farm, data: MovementCreate, user: User) -> tuple[InventoryItem, InventoryMovement]:
    item = await _get_item(db, farm.id, data.item_id)
    if data.supplier_id is not None:
        await _get_supplier(db, farm.id, data.supplier_id)

    direction = _direction(data.movement_type)
    qty_before = item.quantity or Decimal("0")

    if direction < 0 and data.quantity > qty_before:
        raise ValidationException(
            f"Not enough stock: {qty_before} {item.unit} of {item.name} on hand, "
            f"tried to remove {data.quantity}."
        )

    # Cost.
    if data.movement_type == "stock_in":
        unit_cost = data.unit_cost if data.unit_cost is not None else (item.purchase_price or item.avg_cost or Decimal("0"))
    else:
        unit_cost = item.avg_cost or Decimal("0")
    total_cost = (data.quantity * unit_cost).quantize(_Q)

    if direction > 0:
        # Weighted-average cost update on genuine inbound cost (stock_in / return).
        new_qty = qty_before + data.quantity
        if data.movement_type in ("stock_in", "return") and unit_cost > 0:
            prev_val = qty_before * (item.avg_cost or Decimal("0"))
            item.avg_cost = ((prev_val + data.quantity * unit_cost) / new_qty).quantize(_Q4) if new_qty > 0 else Decimal("0")
        item.quantity = new_qty.quantize(_Q3)
    else:
        item.quantity = (qty_before - data.quantity).quantize(_Q3)
    item.updated_at = datetime.now(tz=timezone.utc)

    move = InventoryMovement(
        farm_id=farm.id, item_id=item.id, movement_type=data.movement_type, direction=direction,
        quantity=data.quantity, qty_before=qty_before, qty_after=item.quantity,
        unit_cost=unit_cost, total_cost=total_cost, reason=data.reason, reference=data.reference,
        location_from=item.location if direction < 0 else None,
        location_to=data.location_to or (item.location if direction > 0 else None),
        supplier_id=data.supplier_id or item.supplier_id,
        ai_context={"item": item.name, "category": item.category, "type": data.movement_type},
        notes=data.notes, created_by=user.id,
    )
    db.add(move)
    await db.flush()

    # ── Finance integration — stock-in books an expense ───────────────────────
    if data.movement_type == "stock_in" and total_cost > 0:
        from app.services import finance_service
        slug = _CATEGORY_EXPENSE_SLUG.get(item.category, "other")
        expense = await finance_service.record_category_expense(
            db, farm.id, None, slug, total_cost,
            f"Inventory purchase: {item.name} ({data.quantity} {item.unit})", user,
            data.movement_date or date.today(),
        )
        if expense is not None:
            move.expense_id = expense.id

    await _audit(db, f"inventory.movement.{data.movement_type}", "inventory_movement", move.id, farm.id, user.id,
                 {"item": item.name, "quantity": str(data.quantity)})
    await db.commit()
    await db.refresh(item)
    await db.refresh(move)
    return item, move


async def list_movements(db, farm_id, item_id=None, movement_type=None, date_from=None, date_to=None,
                         limit=50, offset=0) -> list[MovementResponse]:
    filters = [InventoryMovement.farm_id == farm_id, InventoryMovement.deleted_at.is_(None)]
    if item_id:
        filters.append(InventoryMovement.item_id == item_id)
    if movement_type:
        filters.append(InventoryMovement.movement_type == movement_type)
    if date_from:
        filters.append(func.date(InventoryMovement.created_at) >= date_from)
    if date_to:
        filters.append(func.date(InventoryMovement.created_at) <= date_to)
    res = await db.execute(
        select(InventoryMovement, InventoryItem.name, InventoryItem.category)
        .join(InventoryItem, InventoryMovement.item_id == InventoryItem.id)
        .where(*filters).order_by(InventoryMovement.created_at.desc()).limit(limit).offset(offset)
    )
    out = []
    for move, name, cat in res.all():
        resp = MovementResponse.model_validate(move)
        resp.item_name = name
        resp.category = cat
        out.append(resp)
    return out


# ── Assets ────────────────────────────────────────────────────────────────────

async def create_asset(db, farm: Farm, data: AssetCreate, user: User) -> Asset:
    next_service = None
    if data.service_interval_days:
        base = data.last_service_date or data.purchase_date
        next_service = base + timedelta(days=data.service_interval_days)
    asset = Asset(
        farm_id=farm.id, asset_type=data.asset_type, name=data.name, description=data.description,
        serial_number=data.serial_number, purchase_date=data.purchase_date, purchase_price=data.purchase_price,
        depreciation_method=data.depreciation_method, useful_life_years=data.useful_life_years,
        salvage_value=data.salvage_value, warranty_expiry=data.warranty_expiry, location=data.location,
        assigned_user_id=data.assigned_user_id, condition=data.condition,
        service_interval_days=data.service_interval_days, last_service_date=data.last_service_date,
        next_service_date=next_service, notes=data.notes, created_by=user.id,
    )
    db.add(asset)
    await db.flush()
    await _audit(db, "inventory.asset.create", "asset", asset.id, farm.id, user.id,
                 {"name": asset.name, "type": asset.asset_type})
    await db.commit()
    await db.refresh(asset)
    return asset


async def list_assets(db, farm_id, include_inactive=False, asset_type=None) -> list[AssetResponse]:
    filters = [Asset.farm_id == farm_id, Asset.deleted_at.is_(None)]
    if not include_inactive:
        filters.append(Asset.is_active.is_(True))
    if asset_type:
        filters.append(Asset.asset_type == asset_type)
    res = await db.execute(select(Asset).where(*filters).order_by(Asset.asset_type.asc(), Asset.name.asc()))
    return [_asset_response(a) for a in res.scalars().all()]


async def get_asset(db, farm_id, asset_id) -> AssetResponse:
    return _asset_response(await _get_asset(db, farm_id, asset_id))


async def update_asset(db, farm_id, asset_id, data: AssetUpdate) -> AssetResponse:
    asset = await _get_asset(db, farm_id, asset_id)
    for f in ("name", "description", "serial_number", "depreciation_method", "useful_life_years",
              "salvage_value", "warranty_expiry", "location", "assigned_user_id", "condition",
              "service_interval_days", "last_service_date", "next_service_date", "is_active", "notes"):
        v = getattr(data, f)
        if v is not None:
            setattr(asset, f, v)
    # Recompute next service if interval/last changed and not explicitly set.
    if (data.service_interval_days is not None or data.last_service_date is not None) and data.next_service_date is None:
        if asset.service_interval_days and asset.last_service_date:
            asset.next_service_date = asset.last_service_date + timedelta(days=asset.service_interval_days)
    asset.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(asset)
    return _asset_response(asset)


async def delete_asset(db, farm_id, asset_id) -> None:
    asset = await _get_asset(db, farm_id, asset_id)
    asset.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Maintenance ───────────────────────────────────────────────────────────────

def _maint_response(m: AssetMaintenance, asset_name: Optional[str] = None) -> MaintenanceResponse:
    resp = MaintenanceResponse.model_validate(m)
    resp.asset_name = asset_name
    return resp


async def create_maintenance(db, farm: Farm, data: MaintenanceCreate, user: User) -> AssetMaintenance:
    asset = await _get_asset(db, farm.id, data.asset_id)
    m = AssetMaintenance(
        farm_id=farm.id, asset_id=asset.id, title=data.title, status=data.status,
        scheduled_date=data.scheduled_date, completed_date=data.completed_date, cost=data.cost,
        parts_used=data.parts_used, technician=data.technician, notes=data.notes,
        attachments=data.attachments, created_by=user.id,
    )
    db.add(m)
    await db.flush()
    await _finalise_maintenance(db, farm.id, asset, m, user)
    await _audit(db, "inventory.maintenance.create", "asset_maintenance", m.id, farm.id, user.id,
                 {"asset": asset.name, "title": m.title})
    await db.commit()
    await db.refresh(m)
    return m


async def _finalise_maintenance(db, farm_id, asset, m: AssetMaintenance, user):
    """When a maintenance is completed: book expense + advance the service schedule."""
    if m.status == "completed":
        completed = m.completed_date or date.today()
        m.completed_date = completed
        asset.last_service_date = completed
        if asset.service_interval_days:
            asset.next_service_date = completed + timedelta(days=asset.service_interval_days)
        if m.cost and m.cost > 0 and m.expense_id is None:
            from app.services import finance_service
            expense = await finance_service.record_category_expense(
                db, farm_id, None, "repairs", m.cost,
                f"Maintenance: {asset.name} — {m.title}", user, completed,
            )
            if expense is not None:
                m.expense_id = expense.id


async def list_maintenance(db, farm_id, asset_id=None, status=None, limit=100, offset=0) -> list[MaintenanceResponse]:
    filters = [AssetMaintenance.farm_id == farm_id, AssetMaintenance.deleted_at.is_(None)]
    if asset_id:
        filters.append(AssetMaintenance.asset_id == asset_id)
    if status:
        filters.append(AssetMaintenance.status == status)
    res = await db.execute(
        select(AssetMaintenance, Asset.name)
        .join(Asset, AssetMaintenance.asset_id == Asset.id)
        .where(*filters)
        .order_by(AssetMaintenance.scheduled_date.desc().nullslast(), AssetMaintenance.created_at.desc())
        .limit(limit).offset(offset)
    )
    return [_maint_response(m, name) for m, name in res.all()]


async def update_maintenance(db, farm_id, maint_id, data: MaintenanceUpdate, user: User) -> MaintenanceResponse:
    res = await db.execute(select(AssetMaintenance).where(
        AssetMaintenance.id == maint_id, AssetMaintenance.farm_id == farm_id, AssetMaintenance.deleted_at.is_(None)))
    m = res.scalar_one_or_none()
    if m is None:
        raise NotFoundException("Maintenance record not found.")
    for f in ("title", "status", "scheduled_date", "completed_date", "cost", "parts_used",
              "technician", "notes", "attachments"):
        v = getattr(data, f)
        if v is not None:
            setattr(m, f, v)
    asset = await _get_asset(db, farm_id, m.asset_id)
    await _finalise_maintenance(db, farm_id, asset, m, user)
    m.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(m)
    return _maint_response(m, asset.name)


async def delete_maintenance(db, farm_id, maint_id) -> None:
    res = await db.execute(select(AssetMaintenance).where(
        AssetMaintenance.id == maint_id, AssetMaintenance.farm_id == farm_id, AssetMaintenance.deleted_at.is_(None)))
    m = res.scalar_one_or_none()
    if m is None:
        raise NotFoundException("Maintenance record not found.")
    m.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Alerts ────────────────────────────────────────────────────────────────────

async def get_alerts(db, farm_id) -> list[InventoryAlert]:
    alerts: list[InventoryAlert] = []
    items = await list_items(db, farm_id)
    for i in items:
        if i.is_out_of_stock:
            alerts.append(InventoryAlert(kind="out_of_stock", severity="critical", ref_id=i.id, ref_type="item",
                                         title=i.name, detail=f"Out of stock ({i.category})"))
        elif i.is_low_stock:
            alerts.append(InventoryAlert(kind="low_stock", severity="warning", ref_id=i.id, ref_type="item",
                                         title=i.name, detail=f"{i.quantity} {i.unit} left"))
        if i.is_expired:
            alerts.append(InventoryAlert(kind="expired", severity="critical", ref_id=i.id, ref_type="item",
                                         title=i.name, detail=f"Expired {i.expiry_date}"))
        elif i.is_expiring_soon:
            alerts.append(InventoryAlert(kind="expiring_soon", severity="warning", ref_id=i.id, ref_type="item",
                                         title=i.name, detail=f"Expires {i.expiry_date} ({i.days_to_expiry}d)"))
    assets = await list_assets(db, farm_id)
    for a in assets:
        if a.is_warranty_expiring:
            alerts.append(InventoryAlert(kind="warranty_expiry", severity="info", ref_id=a.id, ref_type="asset",
                                         title=a.name, detail=f"Warranty ends {a.warranty_expiry}"))
        if a.is_maintenance_due:
            alerts.append(InventoryAlert(kind="maintenance_due", severity="warning", ref_id=a.id, ref_type="asset",
                                         title=a.name, detail=f"Service due {a.next_service_date}"))
    return alerts


# ── Analytics helpers ─────────────────────────────────────────────────────────

async def _category_valuation(db, farm_id) -> list[CategoryValuation]:
    res = await db.execute(
        select(InventoryItem.category, func.count(InventoryItem.id),
               func.coalesce(func.sum(InventoryItem.quantity), 0),
               func.coalesce(func.sum(InventoryItem.quantity * InventoryItem.avg_cost), 0))
        .where(InventoryItem.farm_id == farm_id, InventoryItem.deleted_at.is_(None), InventoryItem.is_active.is_(True))
        .group_by(InventoryItem.category).order_by(func.sum(InventoryItem.quantity * InventoryItem.avg_cost).desc())
    )
    return [CategoryValuation(category=c, item_count=int(n), total_quantity=Decimal(q).quantize(_Q3),
                              total_value=Decimal(v).quantize(_Q)) for c, n, q, v in res.all()]


async def _consumption_velocity(db, farm_id, since: date) -> list[ItemVelocity]:
    res = await db.execute(
        select(InventoryItem.id, InventoryItem.name, InventoryItem.category,
               func.coalesce(func.sum(InventoryMovement.quantity), 0),
               func.coalesce(func.sum(InventoryMovement.total_cost), 0))
        .join(InventoryItem, InventoryMovement.item_id == InventoryItem.id)
        .where(InventoryMovement.farm_id == farm_id, InventoryMovement.deleted_at.is_(None),
               InventoryMovement.movement_type.in_(["consumption", "stock_out"]),
               func.date(InventoryMovement.created_at) >= since)
        .group_by(InventoryItem.id, InventoryItem.name, InventoryItem.category)
        .order_by(func.sum(InventoryMovement.quantity).desc())
    )
    return [ItemVelocity(item_id=i, name=n, category=c, consumed_qty=Decimal(q).quantize(_Q3),
                         consumed_value=Decimal(v).quantize(_Q)) for i, n, c, q, v in res.all()]


async def get_dashboard(db, farm_id, window_days=30) -> InventoryDashboard:
    items = await list_items(db, farm_id)
    assets = await list_assets(db, farm_id)
    alerts = await get_alerts(db, farm_id)
    cat_val = await _category_valuation(db, farm_id)
    recent = await list_movements(db, farm_id, limit=10)

    since = date.today() - timedelta(days=window_days)
    flow_res = await db.execute(
        select(
            func.coalesce(func.sum(sa_case((InventoryMovement.movement_type == "stock_in", InventoryMovement.total_cost), else_=0)), 0),
            func.coalesce(func.sum(sa_case((InventoryMovement.direction == -1, InventoryMovement.total_cost), else_=0)), 0),
        ).where(InventoryMovement.farm_id == farm_id, InventoryMovement.deleted_at.is_(None),
                func.date(InventoryMovement.created_at) >= since)
    )
    stock_in_val, stock_out_val = flow_res.one()

    return InventoryDashboard(
        item_count=len(items),
        total_inventory_value=sum((i.current_value for i in items), Decimal("0")).quantize(_Q),
        low_stock_count=sum(1 for i in items if i.is_low_stock and not i.is_out_of_stock),
        out_of_stock_count=sum(1 for i in items if i.is_out_of_stock),
        expiring_count=sum(1 for i in items if i.is_expiring_soon),
        expired_count=sum(1 for i in items if i.is_expired),
        asset_count=len(assets),
        total_asset_value=sum((a.current_value for a in assets), Decimal("0")).quantize(_Q),
        maintenance_due_count=sum(1 for a in assets if a.is_maintenance_due),
        window_days=window_days,
        stock_in_value=Decimal(stock_in_val).quantize(_Q),
        stock_out_value=Decimal(stock_out_val).quantize(_Q),
        category_valuation=cat_val,
        alerts=alerts,
        recent_movements=recent,
    )


async def get_analytics(db, farm_id, window_days=90) -> InventoryAnalytics:
    items = await list_items(db, farm_id)
    assets = await list_assets(db, farm_id)
    cat_val = await _category_valuation(db, farm_id)
    since = date.today() - timedelta(days=window_days)

    velocity = await _consumption_velocity(db, farm_id, since)
    most_consumed = velocity[:10]
    fast_moving = velocity[:5]
    slow_moving = list(reversed(velocity))[:5] if velocity else []

    # Dead stock — items with quantity but no outbound movement in the window.
    moved_ids = {v.item_id for v in velocity}
    dead_stock = [i for i in items if i.quantity > 0 and i.id not in moved_ids][:20]

    # Reorder recommendations.
    days = Decimal(str(window_days))
    recs: list[ReorderRecommendation] = []
    for i in items:
        if not i.is_low_stock:
            continue
        vel = next((v for v in velocity if v.item_id == i.id), None)
        avg_daily = (vel.consumed_qty / days).quantize(_Q3) if vel else Decimal("0")
        target = i.reorder_level or i.min_stock or Decimal("0")
        suggested = (target * 2 - i.quantity)
        if avg_daily > 0:
            suggested = max(suggested, (avg_daily * Decimal("30")).quantize(_Q3))
        if suggested < 0:
            suggested = Decimal("0")
        recs.append(ReorderRecommendation(
            item_id=i.id, name=i.name, category=i.category, quantity=i.quantity,
            reorder_level=i.reorder_level, avg_daily_consumption=avg_daily,
            suggested_order_qty=suggested.quantize(_Q3), supplier_name=i.supplier_name,
        ))

    # Movement trend (monthly, last 12).
    trend = await _movement_trend(db, farm_id, 12)

    # Supplier performance.
    suppliers = await list_suppliers(db, farm_id, include_inactive=True)
    perf = [SupplierPerformance(supplier_id=s.id, name=s.name, total_spend=s.total_spend or Decimal("0"),
                                order_count=s.order_count or 0, rating=s.rating,
                                outstanding_balance=s.outstanding_balance) for s in suppliers]

    maint_res = await db.execute(
        select(func.coalesce(func.sum(AssetMaintenance.cost), 0)).where(
            AssetMaintenance.farm_id == farm_id, AssetMaintenance.deleted_at.is_(None),
            AssetMaintenance.status == "completed")
    )
    maint_cost = Decimal(maint_res.scalar_one())

    return InventoryAnalytics(
        window_days=window_days,
        inventory_valuation=sum((i.current_value for i in items), Decimal("0")).quantize(_Q),
        asset_valuation=sum((a.current_value for a in assets), Decimal("0")).quantize(_Q),
        total_depreciation=sum((a.accumulated_depreciation for a in assets), Decimal("0")).quantize(_Q),
        maintenance_cost=maint_cost.quantize(_Q),
        category_valuation=cat_val,
        movement_trend=trend,
        most_consumed=most_consumed,
        fast_moving=fast_moving,
        slow_moving=slow_moving,
        dead_stock=dead_stock,
        reorder_recommendations=recs,
        supplier_performance=perf,
    )


async def _movement_trend(db, farm_id, months: int) -> list[MovementTrendPoint]:
    today = date.today()
    y, m = today.year, today.month
    sm = m - (months - 1)
    sy = y
    while sm <= 0:
        sm += 12
        sy -= 1
    start = date(sy, sm, 1)
    period = func.to_char(InventoryMovement.created_at, "YYYY-MM").label("period")
    res = await db.execute(
        select(period,
               func.coalesce(func.sum(sa_case((InventoryMovement.movement_type == "stock_in", InventoryMovement.quantity), else_=0)), 0),
               func.coalesce(func.sum(sa_case((InventoryMovement.direction == -1, InventoryMovement.quantity), else_=0)), 0))
        .where(InventoryMovement.farm_id == farm_id, InventoryMovement.deleted_at.is_(None),
               func.date(InventoryMovement.created_at) >= start)
        .group_by(period)
    )
    data = {k: (Decimal(i), Decimal(o)) for k, i, o in res.all()}
    points = []
    cy, cm = sy, sm
    for _ in range(months):
        key = f"{cy:04d}-{cm:02d}"
        i, o = data.get(key, (Decimal("0"), Decimal("0")))
        points.append(MovementTrendPoint(period=key, stock_in=i.quantize(_Q3), stock_out=o.quantize(_Q3)))
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1
    return points


async def get_ai_context(db, farm_id) -> InventoryAIContext:
    items = await list_items(db, farm_id)
    assets = await list_assets(db, farm_id)
    alerts = await get_alerts(db, farm_id)
    analytics = await get_analytics(db, farm_id)
    movements = await list_movements(db, farm_id, limit=100)

    return InventoryAIContext(
        farm_id=farm_id, generated_at=datetime.now(tz=timezone.utc),
        inventory_value=analytics.inventory_valuation, asset_value=analytics.asset_valuation,
        items=[{"name": i.name, "category": i.category, "quantity": str(i.quantity),
                "value": str(i.current_value), "low_stock": i.is_low_stock, "expiring": i.is_expiring_soon}
               for i in items],
        recent_movements=[{"item": m.item_name, "type": m.movement_type, "quantity": str(m.quantity),
                           "value": str(m.total_cost), "reason": m.reason,
                           "financial_impact": str(m.total_cost if m.movement_type == "stock_in" else -m.total_cost)}
                          for m in movements],
        alerts=[{"kind": a.kind, "title": a.title, "detail": a.detail, "severity": a.severity} for a in alerts],
        supplier_performance=[{"name": s.name, "total_spend": str(s.total_spend), "orders": s.order_count}
                              for s in analytics.supplier_performance],
        reorder_recommendations=[{"item": r.name, "suggested_qty": str(r.suggested_order_qty),
                                  "supplier": r.supplier_name} for r in analytics.reorder_recommendations],
    )
