"""
Greena — Feed Management Service (Phase 3, Module 4).

Business logic for a small event-sourced feed system:

  Suppliers      — CRUD + spend history
  Inventory      — stock lines per feed type + location, weighted-average cost
  Purchases      — add stock, recompute weighted-average cost, book a finance
                   expense (integration), reorder-alert check
  Consumption    — draw a flock's feed down at the item's average cost
                   (allocates feed cost per flock, feeding cost-per-bird/egg)
  Transfers      — move stock between locations (value moves, no new cost)
  Wastage        — write off spoiled/lost stock, recording the value loss
  Dashboard      — stock levels, valuation, reorder alerts, rolling activity
  Analytics      — usage trend, feed-type / supplier / flock breakdowns,
                   automatic feed cost per bird and per egg
  AI context     — structured payload for ARIA / Gemini

Permission enforcement happens at the endpoint layer (require_permission). The
service trusts that the caller is authorised, but always re-scopes every query
to the caller's farm (DB-04 Frozen).

Stock invariants:
  * quantity_kg on an item is never allowed to go negative.
  * avg_cost_per_kg is a weighted average maintained only on purchase / transfer_in.
  * Draw-downs (consumption / wastage / transfer_out) value stock at the current
    average cost and leave the average unchanged.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import and_, case as sa_case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.feed import FeedInventoryItem, FeedSupplier, FeedTransaction
from app.models.flock import DailyLog, Flock, ProductionRecord, WeighinRecord
from app.schemas.feed import (
    FeedAIContext,
    FeedAnalyticsResponse,
    FeedConsumptionInput,
    FeedDashboardResponse,
    FeedExpiryAlert,
    FeedFlockCost,
    FeedForecastItem,
    FeedForecastResponse,
    FeedInventoryItemCreate,
    FeedInventoryItemResponse,
    FeedInventoryItemUpdate,
    FeedPurchaseInput,
    FeedReorderAlert,
    FeedSupplierCreate,
    FeedSupplierResponse,
    FeedSupplierSpend,
    FeedSupplierUpdate,
    FeedTopFlock,
    FeedTransactionResponse,
    FeedTransferInput,
    FeedTypeBreakdown,
    FeedUsagePoint,
    FeedWastageInput,
)

_Q_KG = Decimal("0.001")
_Q_COST = Decimal("0.0001")
_Q_KES = Decimal("0.01")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_item_or_404(
    db: AsyncSession, farm_id: uuid.UUID, item_id: uuid.UUID
) -> FeedInventoryItem:
    res = await db.execute(
        select(FeedInventoryItem).where(
            FeedInventoryItem.id == item_id,
            FeedInventoryItem.farm_id == farm_id,
            FeedInventoryItem.deleted_at.is_(None),
        )
    )
    item = res.scalar_one_or_none()
    if item is None:
        raise NotFoundException("Feed inventory item not found.")
    return item


async def _get_supplier_or_404(
    db: AsyncSession, farm_id: uuid.UUID, supplier_id: uuid.UUID
) -> FeedSupplier:
    res = await db.execute(
        select(FeedSupplier).where(
            FeedSupplier.id == supplier_id,
            FeedSupplier.farm_id == farm_id,
            FeedSupplier.deleted_at.is_(None),
        )
    )
    supplier = res.scalar_one_or_none()
    if supplier is None:
        raise NotFoundException("Feed supplier not found.")
    return supplier


async def _get_flock_or_404(
    db: AsyncSession, farm_id: uuid.UUID, flock_id: uuid.UUID
) -> Flock:
    res = await db.execute(
        select(Flock).where(
            Flock.id == flock_id,
            Flock.farm_id == farm_id,
            Flock.deleted_at.is_(None),
        )
    )
    flock = res.scalar_one_or_none()
    if flock is None:
        raise NotFoundException("Flock not found.")
    return flock


async def _supplier_name(db: AsyncSession, supplier_id: Optional[uuid.UUID]) -> Optional[str]:
    if supplier_id is None:
        return None
    res = await db.execute(
        select(FeedSupplier.name).where(FeedSupplier.id == supplier_id)
    )
    return res.scalar_one_or_none()


def _item_response(
    item: FeedInventoryItem, supplier_name: Optional[str] = None
) -> FeedInventoryItemResponse:
    return FeedInventoryItemResponse(
        id=item.id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        farm_id=item.farm_id,
        feed_type=item.feed_type,
        name=item.name,
        brand=item.brand,
        batch_number=item.batch_number,
        expiry_date=item.expiry_date,
        location=item.location,
        unit=item.unit,
        quantity_kg=item.quantity_kg,
        avg_cost_per_kg=item.avg_cost_per_kg,
        reorder_level_kg=item.reorder_level_kg,
        supplier_id=item.supplier_id,
        supplier_name=supplier_name,
        is_active=item.is_active,
        notes=item.notes,
        stock_value_kes=item.stock_value_kes,
        is_low_stock=item.is_low_stock,
        days_to_expiry=item.days_to_expiry,
        is_expired=item.is_expired,
        is_expiring_soon=item.is_expiring_soon,
        created_by=item.created_by,
    )


async def _audit(db, action, resource_type, resource_id, farm_id, user_id, new_value=None):
    from app.services import audit_service

    await audit_service.log_action(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        farm_id=farm_id,
        user_id=user_id,
        new_value=new_value,
    )


async def _maybe_reorder_notification(
    db: AsyncSession, farm: Farm, item: FeedInventoryItem
) -> None:
    """Best-effort in-app reorder alert to the farm owner when stock is low."""
    if not item.is_low_stock:
        return
    try:
        from app.schemas.platform import NotificationCreate
        from app.services import notification_service

        await notification_service.create_notification(
            db,
            NotificationCreate(
                farm_id=farm.id,
                user_id=farm.owner_id,
                notification_type="feed_reorder",
                title="Feed running low",
                body=(
                    f"{item.feed_type} at {item.location} is down to "
                    f"{item.quantity_kg} kg (reorder at {item.reorder_level_kg} kg)."
                ),
                action_route="/inventory",
                source="feed",
            ),
        )
    except Exception:
        # Notifications must never break a stock mutation.
        pass


# ── Suppliers ─────────────────────────────────────────────────────────────────

async def create_supplier(
    db: AsyncSession, farm: Farm, data: FeedSupplierCreate, current_user: User
) -> FeedSupplier:
    supplier = FeedSupplier(
        farm_id=farm.id,
        name=data.name,
        contact_name=data.contact_name,
        phone=data.phone,
        email=data.email,
        location=data.location,
        feed_types=data.feed_types,
        rating=data.rating,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(supplier)
    await db.flush()
    await _audit(db, "feed.supplier.create", "feed_supplier", supplier.id, farm.id, current_user.id,
                 {"name": supplier.name})
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def list_suppliers(
    db: AsyncSession, farm_id: uuid.UUID, include_inactive: bool = False
) -> list[FeedSupplierResponse]:
    filters = [
        FeedSupplier.farm_id == farm_id,
        FeedSupplier.deleted_at.is_(None),
    ]
    if not include_inactive:
        filters.append(FeedSupplier.is_active.is_(True))
    res = await db.execute(
        select(FeedSupplier).where(*filters).order_by(FeedSupplier.name.asc())
    )
    suppliers = list(res.scalars().all())

    # Spend history per supplier (purchases only).
    spend_res = await db.execute(
        select(
            FeedTransaction.supplier_id,
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.count(FeedTransaction.id),
        )
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.txn_type == "purchase",
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.supplier_id.is_not(None),
        )
        .group_by(FeedTransaction.supplier_id)
    )
    spend = {
        sid: (Decimal(cost), Decimal(kg), int(cnt))
        for sid, cost, kg, cnt in spend_res.all()
    }

    out: list[FeedSupplierResponse] = []
    for s in suppliers:
        cost, kg, cnt = spend.get(s.id, (Decimal("0"), Decimal("0"), 0))
        resp = FeedSupplierResponse.model_validate(s)
        resp.total_spend_kes = cost
        resp.total_kg_purchased = kg
        resp.purchase_count = cnt
        out.append(resp)
    return out


async def get_supplier(db: AsyncSession, farm_id: uuid.UUID, supplier_id: uuid.UUID) -> FeedSupplier:
    return await _get_supplier_or_404(db, farm_id, supplier_id)


async def update_supplier(
    db: AsyncSession, farm_id: uuid.UUID, supplier_id: uuid.UUID, data: FeedSupplierUpdate
) -> FeedSupplier:
    supplier = await _get_supplier_or_404(db, farm_id, supplier_id)
    for field in ("name", "contact_name", "phone", "email", "location",
                  "feed_types", "rating", "is_active", "notes"):
        val = getattr(data, field)
        if val is not None:
            setattr(supplier, field, val)
    supplier.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def delete_supplier(db: AsyncSession, farm_id: uuid.UUID, supplier_id: uuid.UUID) -> None:
    supplier = await _get_supplier_or_404(db, farm_id, supplier_id)
    supplier.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Inventory items ───────────────────────────────────────────────────────────

async def create_item(
    db: AsyncSession, farm: Farm, data: FeedInventoryItemCreate, current_user: User
) -> FeedInventoryItem:
    if data.supplier_id is not None:
        await _get_supplier_or_404(db, farm.id, data.supplier_id)

    item = FeedInventoryItem(
        farm_id=farm.id,
        feed_type=data.feed_type,
        name=data.name,
        brand=data.brand,
        batch_number=data.batch_number,
        expiry_date=data.expiry_date,
        location=data.location,
        unit=data.unit,
        quantity_kg=data.opening_quantity_kg,
        avg_cost_per_kg=data.opening_cost_per_kg,
        reorder_level_kg=data.reorder_level_kg,
        supplier_id=data.supplier_id,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(item)
    await db.flush()

    # An opening balance is recorded as an adjustment so the ledger is complete.
    if data.opening_quantity_kg and data.opening_quantity_kg > 0:
        db.add(FeedTransaction(
            farm_id=farm.id,
            item_id=item.id,
            txn_type="adjustment",
            direction=1,
            txn_date=date.today(),
            quantity_kg=data.opening_quantity_kg,
            unit_cost_per_kg=data.opening_cost_per_kg,
            total_cost=(data.opening_quantity_kg * data.opening_cost_per_kg).quantize(_Q_KES),
            reason="opening_balance",
            created_by=current_user.id,
        ))
    await _audit(db, "feed.item.create", "feed_inventory_item", item.id, farm.id, current_user.id,
                 {"feed_type": item.feed_type, "location": item.location})
    await db.commit()
    await db.refresh(item)
    return item


async def list_items(
    db: AsyncSession, farm_id: uuid.UUID, include_inactive: bool = False
) -> list[FeedInventoryItemResponse]:
    filters = [
        FeedInventoryItem.farm_id == farm_id,
        FeedInventoryItem.deleted_at.is_(None),
    ]
    if not include_inactive:
        filters.append(FeedInventoryItem.is_active.is_(True))
    res = await db.execute(
        select(FeedInventoryItem, FeedSupplier.name)
        .outerjoin(FeedSupplier, FeedInventoryItem.supplier_id == FeedSupplier.id)
        .where(*filters)
        .order_by(FeedInventoryItem.feed_type.asc(), FeedInventoryItem.location.asc())
    )
    return [_item_response(item, name) for item, name in res.all()]


async def get_item(db: AsyncSession, farm_id: uuid.UUID, item_id: uuid.UUID) -> FeedInventoryItemResponse:
    item = await _get_item_or_404(db, farm_id, item_id)
    return _item_response(item, await _supplier_name(db, item.supplier_id))


async def update_item(
    db: AsyncSession, farm_id: uuid.UUID, item_id: uuid.UUID, data: FeedInventoryItemUpdate
) -> FeedInventoryItemResponse:
    item = await _get_item_or_404(db, farm_id, item_id)
    if data.supplier_id is not None:
        await _get_supplier_or_404(db, farm_id, data.supplier_id)
    for field in ("name", "brand", "batch_number", "expiry_date", "location",
                  "reorder_level_kg", "supplier_id", "is_active", "notes"):
        val = getattr(data, field)
        if val is not None:
            setattr(item, field, val)
    item.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(item)
    return _item_response(item, await _supplier_name(db, item.supplier_id))


async def delete_item(db: AsyncSession, farm_id: uuid.UUID, item_id: uuid.UUID) -> None:
    item = await _get_item_or_404(db, farm_id, item_id)
    if item.quantity_kg and item.quantity_kg > 0:
        raise ValidationException(
            "Cannot delete an item that still holds stock. Transfer or write off the stock first."
        )
    item.deleted_at = datetime.now(tz=timezone.utc)
    await db.commit()


# ── Purchases ─────────────────────────────────────────────────────────────────

async def _find_or_create_item_for_purchase(
    db: AsyncSession, farm: Farm, data: FeedPurchaseInput, current_user: User
) -> FeedInventoryItem:
    if data.item_id is not None:
        return await _get_item_or_404(db, farm.id, data.item_id)

    # Match an existing active line by feed_type + location, else create one.
    res = await db.execute(
        select(FeedInventoryItem).where(
            FeedInventoryItem.farm_id == farm.id,
            FeedInventoryItem.feed_type == data.feed_type,
            FeedInventoryItem.location == data.location,
            FeedInventoryItem.deleted_at.is_(None),
            FeedInventoryItem.is_active.is_(True),
        )
    )
    item = res.scalar_one_or_none()
    if item is not None:
        return item

    item = FeedInventoryItem(
        farm_id=farm.id,
        feed_type=data.feed_type,
        location=data.location,
        quantity_kg=Decimal("0"),
        avg_cost_per_kg=Decimal("0"),
        supplier_id=data.supplier_id,
        created_by=current_user.id,
    )
    db.add(item)
    await db.flush()
    return item


async def record_purchase(
    db: AsyncSession, farm: Farm, data: FeedPurchaseInput, current_user: User
) -> tuple[FeedInventoryItem, FeedTransaction]:
    """Buy feed into a store: add stock, recompute weighted-average cost, book expense."""
    # Resolve / create supplier by name if provided as free text.
    supplier_id = data.supplier_id
    if supplier_id is not None:
        await _get_supplier_or_404(db, farm.id, supplier_id)
    elif data.supplier_name:
        res = await db.execute(
            select(FeedSupplier).where(
                FeedSupplier.farm_id == farm.id,
                func.lower(FeedSupplier.name) == data.supplier_name.strip().lower(),
                FeedSupplier.deleted_at.is_(None),
            )
        )
        existing = res.scalar_one_or_none()
        if existing is None:
            existing = FeedSupplier(
                farm_id=farm.id, name=data.supplier_name.strip(), created_by=current_user.id
            )
            db.add(existing)
            await db.flush()
        supplier_id = existing.id

    if data.flock_id is not None:
        await _get_flock_or_404(db, farm.id, data.flock_id)

    item = await _find_or_create_item_for_purchase(db, farm, data, current_user)
    if supplier_id is not None and item.supplier_id is None:
        item.supplier_id = supplier_id
    # A purchase brings a new batch — record its brand / batch / expiry on the item.
    if data.brand is not None:
        item.brand = data.brand
    if data.batch_number is not None:
        item.batch_number = data.batch_number
    if data.expiry_date is not None:
        item.expiry_date = data.expiry_date

    qty = data.quantity_kg
    price = data.price_per_kg
    total = (qty * price).quantize(_Q_KES)

    # Weighted-average cost update.
    prev_qty = item.quantity_kg or Decimal("0")
    prev_val = prev_qty * (item.avg_cost_per_kg or Decimal("0"))
    new_qty = prev_qty + qty
    new_val = prev_val + (qty * price)
    item.quantity_kg = new_qty.quantize(_Q_KG)
    item.avg_cost_per_kg = (
        (new_val / new_qty).quantize(_Q_COST) if new_qty > 0 else Decimal("0")
    )
    item.updated_at = datetime.now(tz=timezone.utc)

    txn = FeedTransaction(
        farm_id=farm.id,
        item_id=item.id,
        flock_id=data.flock_id,
        txn_type="purchase",
        direction=1,
        txn_date=data.purchase_date,
        quantity_kg=qty,
        unit_cost_per_kg=price,
        total_cost=total,
        supplier_id=supplier_id,
        reference=data.reference,
        notes=data.notes,
        ai_context={
            "feed_type": item.feed_type,
            "location": item.location,
            "avg_cost_after": str(item.avg_cost_per_kg),
            "brand": data.brand,
            "batch_number": data.batch_number,
            "expiry_date": data.expiry_date.isoformat() if data.expiry_date else None,
            "delivery_date": data.delivery_date.isoformat() if data.delivery_date else None,
        },
        created_by=current_user.id,
    )
    db.add(txn)
    await db.flush()

    # ── Finance integration — a purchase becomes a farm expense ───────────────
    from app.services import finance_service

    expense = await finance_service.record_category_expense(
        db, farm.id, data.flock_id, "feed_purchase", total,
        f"Feed purchase: {item.feed_type} ({qty} kg)", current_user, data.purchase_date,
    )
    if expense is not None:
        txn.expense_id = expense.id

    await _audit(db, "feed.purchase", "feed_transaction", txn.id, farm.id, current_user.id,
                 {"feed_type": item.feed_type, "quantity_kg": str(qty), "total_cost": str(total)})

    await db.commit()

    # Snapshot recompute (flock-linked only) after the commit, mirroring health.
    if data.flock_id and txn.expense_id:
        await finance_service.recompute_snapshot(db, farm.id, data.flock_id)

    await db.refresh(item)
    await db.refresh(txn)
    return item, txn


# ── Consumption ───────────────────────────────────────────────────────────────

async def record_consumption(
    db: AsyncSession, farm: Farm, data: FeedConsumptionInput, current_user: User
) -> tuple[FeedInventoryItem, FeedTransaction]:
    """Feed a flock: draw stock down at the item's weighted-average cost."""
    item = await _get_item_or_404(db, farm.id, data.item_id)
    flock = await _get_flock_or_404(db, farm.id, data.flock_id)

    if data.quantity_kg > (item.quantity_kg or Decimal("0")):
        raise ValidationException(
            f"Not enough stock: {item.quantity_kg} kg of {item.feed_type} on hand, "
            f"tried to consume {data.quantity_kg} kg."
        )

    unit_cost = item.avg_cost_per_kg or Decimal("0")
    total = (data.quantity_kg * unit_cost).quantize(_Q_KES)

    item.quantity_kg = (item.quantity_kg - data.quantity_kg).quantize(_Q_KG)
    item.updated_at = datetime.now(tz=timezone.utc)

    txn = FeedTransaction(
        farm_id=farm.id,
        item_id=item.id,
        flock_id=flock.id,
        txn_type="consumption",
        direction=-1,
        txn_date=data.consumption_date,
        quantity_kg=data.quantity_kg,
        unit_cost_per_kg=unit_cost,
        total_cost=total,
        notes=data.notes,
        ai_context={"feed_type": item.feed_type, "flock": flock.name},
        created_by=current_user.id,
    )
    db.add(txn)
    await db.flush()
    await _audit(db, "feed.consumption", "feed_transaction", txn.id, farm.id, current_user.id,
                 {"feed_type": item.feed_type, "quantity_kg": str(data.quantity_kg),
                  "flock_id": str(flock.id)})
    await db.commit()

    await _maybe_reorder_notification(db, farm, item)

    await db.refresh(item)
    await db.refresh(txn)
    return item, txn


async def list_flock_consumption(
    db: AsyncSession, farm_id: uuid.UUID, flock_id: uuid.UUID, limit: int = 50, offset: int = 0
) -> list[FeedTransaction]:
    res = await db.execute(
        select(FeedTransaction)
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.flock_id == flock_id,
            FeedTransaction.txn_type == "consumption",
            FeedTransaction.deleted_at.is_(None),
        )
        .order_by(FeedTransaction.txn_date.desc(), FeedTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(res.scalars().all())


# ── Transfers ─────────────────────────────────────────────────────────────────

async def record_transfer(
    db: AsyncSession, farm: Farm, data: FeedTransferInput, current_user: User
) -> tuple[FeedInventoryItem, FeedInventoryItem]:
    """Move stock from one item/location to another. Value moves with the stock."""
    src = await _get_item_or_404(db, farm.id, data.from_item_id)

    if data.to_location.strip() == src.location:
        raise ValidationException("Transfer destination must differ from the source location.")
    if data.quantity_kg > (src.quantity_kg or Decimal("0")):
        raise ValidationException(
            f"Not enough stock: {src.quantity_kg} kg on hand, tried to transfer {data.quantity_kg} kg."
        )

    unit_cost = src.avg_cost_per_kg or Decimal("0")
    total = (data.quantity_kg * unit_cost).quantize(_Q_KES)

    # Destination item (same feed type at the target location), created if absent.
    res = await db.execute(
        select(FeedInventoryItem).where(
            FeedInventoryItem.farm_id == farm.id,
            FeedInventoryItem.feed_type == src.feed_type,
            FeedInventoryItem.location == data.to_location.strip(),
            FeedInventoryItem.deleted_at.is_(None),
        )
    )
    dst = res.scalar_one_or_none()
    if dst is None:
        dst = FeedInventoryItem(
            farm_id=farm.id,
            feed_type=src.feed_type,
            name=src.name,
            location=data.to_location.strip(),
            unit=src.unit,
            quantity_kg=Decimal("0"),
            avg_cost_per_kg=Decimal("0"),
            supplier_id=src.supplier_id,
            created_by=current_user.id,
        )
        db.add(dst)
        await db.flush()

    # Source draw-down.
    src.quantity_kg = (src.quantity_kg - data.quantity_kg).quantize(_Q_KG)
    src.updated_at = datetime.now(tz=timezone.utc)

    # Destination weighted-average update.
    prev_qty = dst.quantity_kg or Decimal("0")
    prev_val = prev_qty * (dst.avg_cost_per_kg or Decimal("0"))
    new_qty = prev_qty + data.quantity_kg
    new_val = prev_val + (data.quantity_kg * unit_cost)
    dst.quantity_kg = new_qty.quantize(_Q_KG)
    dst.avg_cost_per_kg = (new_val / new_qty).quantize(_Q_COST) if new_qty > 0 else Decimal("0")
    dst.updated_at = datetime.now(tz=timezone.utc)

    out_txn = FeedTransaction(
        farm_id=farm.id, item_id=src.id, txn_type="transfer_out", direction=-1,
        txn_date=data.transfer_date, quantity_kg=data.quantity_kg, unit_cost_per_kg=unit_cost,
        total_cost=total, counterparty_item_id=dst.id, reason=data.reason, notes=data.notes,
        ai_context={"from": src.location, "to": dst.location}, created_by=current_user.id,
    )
    in_txn = FeedTransaction(
        farm_id=farm.id, item_id=dst.id, txn_type="transfer_in", direction=1,
        txn_date=data.transfer_date, quantity_kg=data.quantity_kg, unit_cost_per_kg=unit_cost,
        total_cost=total, counterparty_item_id=src.id, reason=data.reason, notes=data.notes,
        ai_context={"from": src.location, "to": dst.location}, created_by=current_user.id,
    )
    db.add_all([out_txn, in_txn])
    await db.flush()
    await _audit(db, "feed.transfer", "feed_transaction", out_txn.id, farm.id, current_user.id,
                 {"feed_type": src.feed_type, "quantity_kg": str(data.quantity_kg),
                  "from": src.location, "to": dst.location})
    await db.commit()

    await _maybe_reorder_notification(db, farm, src)

    await db.refresh(src)
    await db.refresh(dst)
    return src, dst


# ── Wastage ───────────────────────────────────────────────────────────────────

async def record_wastage(
    db: AsyncSession, farm: Farm, data: FeedWastageInput, current_user: User
) -> tuple[FeedInventoryItem, FeedTransaction]:
    """Write off spoiled / lost stock, recording the value loss."""
    item = await _get_item_or_404(db, farm.id, data.item_id)
    if data.flock_id is not None:
        await _get_flock_or_404(db, farm.id, data.flock_id)

    if data.quantity_kg > (item.quantity_kg or Decimal("0")):
        raise ValidationException(
            f"Not enough stock: {item.quantity_kg} kg on hand, tried to write off {data.quantity_kg} kg."
        )

    unit_cost = item.avg_cost_per_kg or Decimal("0")
    total = (data.quantity_kg * unit_cost).quantize(_Q_KES)

    item.quantity_kg = (item.quantity_kg - data.quantity_kg).quantize(_Q_KG)
    item.updated_at = datetime.now(tz=timezone.utc)

    txn = FeedTransaction(
        farm_id=farm.id, item_id=item.id, flock_id=data.flock_id, txn_type="wastage",
        direction=-1, txn_date=data.wastage_date, quantity_kg=data.quantity_kg,
        unit_cost_per_kg=unit_cost, total_cost=total, reason=data.reason, notes=data.notes,
        ai_context={"feed_type": item.feed_type, "reason": data.reason}, created_by=current_user.id,
    )
    db.add(txn)
    await db.flush()
    await _audit(db, "feed.wastage", "feed_transaction", txn.id, farm.id, current_user.id,
                 {"feed_type": item.feed_type, "quantity_kg": str(data.quantity_kg),
                  "reason": data.reason})
    await db.commit()

    await _maybe_reorder_notification(db, farm, item)

    await db.refresh(item)
    await db.refresh(txn)
    return item, txn


# ── Transaction ledger ────────────────────────────────────────────────────────

async def list_transactions(
    db: AsyncSession,
    farm_id: uuid.UUID,
    item_id: Optional[uuid.UUID] = None,
    flock_id: Optional[uuid.UUID] = None,
    txn_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedTransactionResponse]:
    filters = [
        FeedTransaction.farm_id == farm_id,
        FeedTransaction.deleted_at.is_(None),
    ]
    if item_id:
        filters.append(FeedTransaction.item_id == item_id)
    if flock_id:
        filters.append(FeedTransaction.flock_id == flock_id)
    if txn_type:
        filters.append(FeedTransaction.txn_type == txn_type)
    if date_from:
        filters.append(FeedTransaction.txn_date >= date_from)
    if date_to:
        filters.append(FeedTransaction.txn_date <= date_to)

    res = await db.execute(
        select(FeedTransaction, FeedInventoryItem.feed_type, FeedInventoryItem.location, Flock.name)
        .join(FeedInventoryItem, FeedTransaction.item_id == FeedInventoryItem.id)
        .outerjoin(Flock, FeedTransaction.flock_id == Flock.id)
        .where(*filters)
        .order_by(FeedTransaction.txn_date.desc(), FeedTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    out: list[FeedTransactionResponse] = []
    for txn, feed_type, location, flock_name in res.all():
        resp = FeedTransactionResponse.model_validate(txn)
        resp.feed_type = feed_type
        resp.location = location
        resp.flock_name = flock_name
        out.append(resp)
    return out


# ── Dashboard ─────────────────────────────────────────────────────────────────

async def get_reorder_alerts(db: AsyncSession, farm_id: uuid.UUID) -> list[FeedReorderAlert]:
    res = await db.execute(
        select(FeedInventoryItem, FeedSupplier.name)
        .outerjoin(FeedSupplier, FeedInventoryItem.supplier_id == FeedSupplier.id)
        .where(
            FeedInventoryItem.farm_id == farm_id,
            FeedInventoryItem.deleted_at.is_(None),
            FeedInventoryItem.is_active.is_(True),
            FeedInventoryItem.reorder_level_kg.is_not(None),
            FeedInventoryItem.quantity_kg <= FeedInventoryItem.reorder_level_kg,
        )
        .order_by((FeedInventoryItem.reorder_level_kg - FeedInventoryItem.quantity_kg).desc())
    )
    alerts: list[FeedReorderAlert] = []
    for item, supplier_name in res.all():
        alerts.append(FeedReorderAlert(
            item_id=item.id,
            feed_type=item.feed_type,
            location=item.location,
            quantity_kg=item.quantity_kg,
            reorder_level_kg=item.reorder_level_kg,
            shortfall_kg=(item.reorder_level_kg - item.quantity_kg).quantize(_Q_KG),
            supplier_id=item.supplier_id,
            supplier_name=supplier_name,
        ))
    return alerts


async def get_expiry_alerts(
    db: AsyncSession, farm_id: uuid.UUID, within_days: int = 14
) -> list["FeedExpiryAlert"]:
    """Items whose current batch is expired or expiring within ``within_days``."""
    from app.schemas.feed import FeedExpiryAlert

    horizon = date.today() + timedelta(days=within_days)
    res = await db.execute(
        select(FeedInventoryItem)
        .where(
            FeedInventoryItem.farm_id == farm_id,
            FeedInventoryItem.deleted_at.is_(None),
            FeedInventoryItem.is_active.is_(True),
            FeedInventoryItem.expiry_date.is_not(None),
            FeedInventoryItem.expiry_date <= horizon,
            FeedInventoryItem.quantity_kg > 0,
        )
        .order_by(FeedInventoryItem.expiry_date.asc())
    )
    alerts: list[FeedExpiryAlert] = []
    for item in res.scalars().all():
        alerts.append(FeedExpiryAlert(
            item_id=item.id,
            feed_type=item.feed_type,
            location=item.location,
            batch_number=item.batch_number,
            quantity_kg=item.quantity_kg,
            expiry_date=item.expiry_date,
            days_to_expiry=item.days_to_expiry,
            is_expired=item.is_expired,
        ))
    return alerts


async def _avg_daily_consumption(
    db: AsyncSession, farm_id: uuid.UUID, window_days: int
) -> dict[uuid.UUID, Decimal]:
    """Average kg/day consumed per inventory item over the trailing window."""
    since = date.today() - timedelta(days=window_days)
    res = await db.execute(
        select(
            FeedTransaction.item_id,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
        )
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "consumption",
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedTransaction.item_id)
    )
    out: dict[uuid.UUID, Decimal] = {}
    for item_id, total in res.all():
        out[item_id] = (Decimal(total) / Decimal(window_days)).quantize(_Q_KG)
    return out


async def get_forecast(
    db: AsyncSession, farm_id: uuid.UUID, window_days: int = 30, lead_time_days: int = 7
) -> FeedForecastResponse:
    """
    Forecast stock depletion from trailing consumption.

    For each stocked item: average daily consumption over ``window_days`` drives
    days-remaining, an expected depletion date, and a recommended purchase date
    (depletion minus a ``lead_time_days`` buffer).
    """
    items = await list_items(db, farm_id)
    avg_daily = await _avg_daily_consumption(db, farm_id, window_days)
    today = date.today()

    forecast_items: list[FeedForecastItem] = []
    soonest_depletion: Optional[date] = None
    next_purchase: Optional[date] = None
    needing = 0

    for it in items:
        qty = it.quantity_kg
        rate = avg_daily.get(it.id, Decimal("0"))
        days_remaining: Optional[int] = None
        depletion: Optional[date] = None
        rec_purchase: Optional[date] = None

        if rate > 0:
            days_remaining = int((qty / rate).to_integral_value(rounding="ROUND_FLOOR"))
            depletion = today + timedelta(days=days_remaining)
            rec_purchase = depletion - timedelta(days=lead_time_days)
            if rec_purchase < today:
                rec_purchase = today
            if soonest_depletion is None or depletion < soonest_depletion:
                soonest_depletion = depletion
            if next_purchase is None or rec_purchase < next_purchase:
                next_purchase = rec_purchase

        # Status classification.
        if rate <= 0:
            status = "no_data"
        elif it.is_low_stock or (days_remaining is not None and days_remaining <= 3):
            status = "critical"; needing += 1
        elif days_remaining is not None and days_remaining <= lead_time_days:
            status = "reorder_soon"; needing += 1
        elif days_remaining is not None and days_remaining <= window_days:
            status = "depleting"
        else:
            status = "ok"

        forecast_items.append(FeedForecastItem(
            item_id=it.id,
            feed_type=it.feed_type,
            location=it.location,
            quantity_kg=qty,
            avg_daily_consumption_kg=rate,
            days_remaining=days_remaining,
            depletion_date=depletion,
            recommended_purchase_date=rec_purchase,
            reorder_level_kg=it.reorder_level_kg,
            status=status,
        ))

    # Surface the most urgent items first.
    forecast_items.sort(key=lambda f: (f.days_remaining is None, f.days_remaining if f.days_remaining is not None else 1_000_000))

    return FeedForecastResponse(
        window_days=window_days,
        lead_time_days=lead_time_days,
        items=forecast_items,
        soonest_depletion_date=soonest_depletion,
        next_purchase_date=next_purchase,
        items_needing_purchase=needing,
    )


async def get_dashboard(
    db: AsyncSession, farm_id: uuid.UUID, window_days: int = 30
) -> FeedDashboardResponse:
    items = await list_items(db, farm_id)
    total_stock = sum((i.quantity_kg for i in items), Decimal("0"))
    total_value = sum((i.stock_value_kes for i in items), Decimal("0"))
    low_count = sum(1 for i in items if i.is_low_stock)

    since = date.today() - timedelta(days=window_days)
    agg_res = await db.execute(
        select(
            FeedTransaction.txn_type,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedTransaction.txn_type)
    )
    by_type = {t: (Decimal(kg), Decimal(cost)) for t, kg, cost in agg_res.all()}
    purchased = by_type.get("purchase", (Decimal("0"), Decimal("0")))
    consumed = by_type.get("consumption", (Decimal("0"), Decimal("0")))
    wasted = by_type.get("wastage", (Decimal("0"), Decimal("0")))

    # Today's + this week's consumption.
    today = date.today()
    week_start = today - timedelta(days=6)
    span_res = await db.execute(
        select(
            func.coalesce(func.sum(
                sa_case((FeedTransaction.txn_date == today, FeedTransaction.quantity_kg), else_=0)
            ), 0),
            func.coalesce(func.sum(
                sa_case((FeedTransaction.txn_date >= week_start, FeedTransaction.quantity_kg), else_=0)
            ), 0),
        ).where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "consumption",
        )
    )
    consumed_today, consumed_week = span_res.one()

    alerts = await get_reorder_alerts(db, farm_id)
    expiry_alerts = await get_expiry_alerts(db, farm_id)
    recent = await list_transactions(db, farm_id, limit=10)
    forecast = await get_forecast(db, farm_id, window_days=window_days)

    # Top consuming flocks over the window.
    top_res = await db.execute(
        select(
            Flock.id, Flock.name,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .join(FeedTransaction, FeedTransaction.flock_id == Flock.id)
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "consumption",
            FeedTransaction.txn_date >= since,
            Flock.deleted_at.is_(None),
        )
        .group_by(Flock.id, Flock.name)
        .order_by(func.sum(FeedTransaction.quantity_kg).desc())
        .limit(5)
    )
    top_flocks = [
        FeedTopFlock(
            flock_id=fid, flock_name=name,
            consumed_kg=Decimal(kg).quantize(_Q_KG), feed_cost_kes=Decimal(cost).quantize(_Q_KES),
        )
        for fid, name, kg, cost in top_res.all()
    ]

    return FeedDashboardResponse(
        total_stock_kg=total_stock.quantize(_Q_KG),
        total_stock_value_kes=total_value.quantize(_Q_KES),
        item_count=len(items),
        low_stock_count=low_count,
        expiring_count=len(expiry_alerts),
        window_days=window_days,
        purchased_kg=purchased[0].quantize(_Q_KG),
        purchased_cost_kes=purchased[1].quantize(_Q_KES),
        consumed_kg=consumed[0].quantize(_Q_KG),
        consumed_cost_kes=consumed[1].quantize(_Q_KES),
        consumed_today_kg=Decimal(consumed_today).quantize(_Q_KG),
        consumed_week_kg=Decimal(consumed_week).quantize(_Q_KG),
        wasted_kg=wasted[0].quantize(_Q_KG),
        wasted_cost_kes=wasted[1].quantize(_Q_KES),
        reorder_alerts=alerts,
        expiry_alerts=expiry_alerts,
        top_flocks=top_flocks,
        forecast=forecast,
        items=items,
        recent_transactions=recent,
    )


# ── Analytics ─────────────────────────────────────────────────────────────────

async def _flock_bird_and_egg_counts(
    db: AsyncSession, farm_id: uuid.UUID, flock: Flock
) -> tuple[int, int]:
    """Live birds and total eggs for a flock (for cost-per-bird / cost-per-egg)."""
    deaths_res = await db.execute(
        select(
            func.coalesce(func.sum(DailyLog.mortality_count), 0),
            func.coalesce(func.sum(DailyLog.culls), 0),
        ).where(DailyLog.flock_id == flock.id, DailyLog.deleted_at.is_(None))
    )
    mortality, culls = deaths_res.one()
    live = max((flock.initial_count or 0) - int(mortality) - int(culls), 0)

    eggs_res = await db.execute(
        select(func.coalesce(func.sum(ProductionRecord.eggs_collected), 0)).where(
            ProductionRecord.flock_id == flock.id, ProductionRecord.deleted_at.is_(None)
        )
    )
    eggs = int(eggs_res.scalar_one())
    return live, eggs


async def _flock_weight_gain_kg(
    db: AsyncSession, flock: Flock, live_birds: int
) -> Optional[Decimal]:
    """
    Total live-weight gain (kg) for a flock, from its most recent weigh-in.

    Approximated as current biomass: live birds × latest average weight. Day-old
    placement weight is negligible against market weight, so this is the standard
    field estimate used for FCR when a flock has not yet been sold.
    """
    res = await db.execute(
        select(WeighinRecord.average_weight_kg)
        .where(WeighinRecord.flock_id == flock.id, WeighinRecord.deleted_at.is_(None))
        .order_by(WeighinRecord.weighed_at.desc())
        .limit(1)
    )
    avg_wt = res.scalar_one_or_none()
    if avg_wt is None or live_birds <= 0:
        return None
    return (Decimal(avg_wt) * Decimal(live_birds)).quantize(_Q_KG)


async def get_analytics(
    db: AsyncSession, farm_id: uuid.UUID, window_days: int = 90
) -> FeedAnalyticsResponse:
    since = date.today() - timedelta(days=window_days)

    # Totals.
    tot_res = await db.execute(
        select(
            FeedTransaction.txn_type,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedTransaction.txn_type)
    )
    totals = {t: (Decimal(kg), Decimal(cost)) for t, kg, cost in tot_res.all()}
    consumed_kg, consumed_cost = totals.get("consumption", (Decimal("0"), Decimal("0")))
    wasted_kg, _ = totals.get("wastage", (Decimal("0"), Decimal("0")))

    wastage_pct = None
    denom = consumed_kg + wasted_kg
    if denom > 0:
        wastage_pct = (wasted_kg / denom * 100).quantize(_Q_KES)
    avg_cost = (consumed_cost / consumed_kg).quantize(_Q_COST) if consumed_kg > 0 else None

    # Usage trend by day.
    trend_res = await db.execute(
        select(
            FeedTransaction.txn_date,
            FeedTransaction.txn_type,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedTransaction.txn_date, FeedTransaction.txn_type)
        .order_by(FeedTransaction.txn_date.asc())
    )
    trend_map: dict[str, dict[str, Decimal]] = {}
    for d, t, kg, cost in trend_res.all():
        key = d.isoformat()
        row = trend_map.setdefault(key, {"c_kg": Decimal("0"), "c_cost": Decimal("0"),
                                         "p_kg": Decimal("0"), "w_kg": Decimal("0")})
        if t == "consumption":
            row["c_kg"] += Decimal(kg); row["c_cost"] += Decimal(cost)
        elif t == "purchase":
            row["p_kg"] += Decimal(kg)
        elif t == "wastage":
            row["w_kg"] += Decimal(kg)
    usage_trend = [
        FeedUsagePoint(
            period=k, consumed_kg=v["c_kg"].quantize(_Q_KG),
            consumed_cost_kes=v["c_cost"].quantize(_Q_KES),
            purchased_kg=v["p_kg"].quantize(_Q_KG), wasted_kg=v["w_kg"].quantize(_Q_KG),
        )
        for k, v in sorted(trend_map.items())
    ]

    # By feed type (consumption).
    type_res = await db.execute(
        select(
            FeedInventoryItem.feed_type,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .join(FeedInventoryItem, FeedTransaction.item_id == FeedInventoryItem.id)
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "consumption",
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedInventoryItem.feed_type)
        .order_by(func.sum(FeedTransaction.total_cost).desc())
    )
    by_feed_type = []
    for ft, kg, cost in type_res.all():
        by_feed_type.append(FeedTypeBreakdown(
            feed_type=ft, consumed_kg=Decimal(kg).quantize(_Q_KG),
            consumed_cost_kes=Decimal(cost).quantize(_Q_KES),
            pct_of_total=(Decimal(cost) / consumed_cost * 100).quantize(_Q_KES)
            if consumed_cost > 0 else None,
        ))

    # By supplier (purchases).
    sup_res = await db.execute(
        select(
            FeedTransaction.supplier_id,
            FeedSupplier.name,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
            func.count(FeedTransaction.id),
        )
        .outerjoin(FeedSupplier, FeedTransaction.supplier_id == FeedSupplier.id)
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "purchase",
            FeedTransaction.txn_date >= since,
        )
        .group_by(FeedTransaction.supplier_id, FeedSupplier.name)
        .order_by(func.sum(FeedTransaction.total_cost).desc())
    )
    by_supplier = [
        FeedSupplierSpend(
            supplier_id=sid, supplier_name=name or "Unattributed",
            total_kg=Decimal(kg).quantize(_Q_KG), total_cost_kes=Decimal(cost).quantize(_Q_KES),
            purchase_count=int(cnt),
        )
        for sid, name, kg, cost, cnt in sup_res.all()
    ]

    # By flock — automatic feed cost per bird and per egg.
    flock_res = await db.execute(
        select(
            Flock,
            func.coalesce(func.sum(FeedTransaction.quantity_kg), 0),
            func.coalesce(func.sum(FeedTransaction.total_cost), 0),
        )
        .join(FeedTransaction, FeedTransaction.flock_id == Flock.id)
        .where(
            FeedTransaction.farm_id == farm_id,
            FeedTransaction.deleted_at.is_(None),
            FeedTransaction.txn_type == "consumption",
            Flock.deleted_at.is_(None),
        )
        .group_by(Flock.id)
    )
    by_flock: list[FeedFlockCost] = []
    for flock, kg, cost in flock_res.all():
        live, eggs = await _flock_bird_and_egg_counts(db, farm_id, flock)
        cost_kes = Decimal(cost)
        consumed = Decimal(kg)

        # Feed conversion — from the latest weigh-in biomass (live birds × avg wt).
        weight_gain = await _flock_weight_gain_kg(db, flock, live)
        fcr = None
        cost_per_kg_gain = None
        if weight_gain and weight_gain > 0:
            fcr = (consumed / weight_gain).quantize(Decimal("0.001"))
            cost_per_kg_gain = (cost_kes / weight_gain).quantize(_Q_KES)

        by_flock.append(FeedFlockCost(
            flock_id=flock.id, flock_name=flock.name,
            consumed_kg=consumed.quantize(_Q_KG), feed_cost_kes=cost_kes.quantize(_Q_KES),
            live_birds=live,
            cost_per_bird_kes=(cost_kes / live).quantize(_Q_KES) if live > 0 else None,
            eggs_collected=eggs,
            cost_per_egg_kes=(cost_kes / eggs).quantize(_Q_KES) if eggs > 0 else None,
            weight_gain_kg=weight_gain.quantize(_Q_KG) if weight_gain else None,
            fcr=fcr,
            cost_per_kg_gain_kes=cost_per_kg_gain,
        ))

    return FeedAnalyticsResponse(
        window_days=window_days,
        total_consumed_kg=consumed_kg.quantize(_Q_KG),
        total_consumed_cost_kes=consumed_cost.quantize(_Q_KES),
        total_wasted_kg=wasted_kg.quantize(_Q_KG),
        wastage_pct=wastage_pct,
        avg_cost_per_kg=avg_cost,
        usage_trend=usage_trend,
        by_feed_type=by_feed_type,
        by_supplier=by_supplier,
        by_flock=by_flock,
    )


# ── AI context ────────────────────────────────────────────────────────────────

async def get_ai_context(
    db: AsyncSession, farm_id: uuid.UUID, window_days: int = 90
) -> FeedAIContext:
    """A structured, Gemini-ready snapshot of the farm's feed operation."""
    items = await list_items(db, farm_id)
    analytics = await get_analytics(db, farm_id, window_days)
    suppliers = await list_suppliers(db, farm_id, include_inactive=True)
    history = await list_transactions(db, farm_id, limit=200)

    inventory = [
        {
            "feed_type": i.feed_type, "location": i.location,
            "quantity_kg": str(i.quantity_kg), "avg_cost_per_kg": str(i.avg_cost_per_kg),
            "stock_value_kes": str(i.stock_value_kes), "is_low_stock": i.is_low_stock,
        }
        for i in items
    ]
    feed_history = [
        {
            "date": t.txn_date.isoformat(), "type": t.txn_type, "feed_type": t.feed_type,
            "quantity_kg": str(t.quantity_kg), "total_cost_kes": str(t.total_cost),
            "flock": t.flock_name,
        }
        for t in history
    ]
    consumption = [
        {
            "flock": fc.flock_name, "consumed_kg": str(fc.consumed_kg),
            "feed_cost_kes": str(fc.feed_cost_kes),
        }
        for fc in analytics.by_flock
    ]
    feed_conversions = [
        {
            "flock": fc.flock_name, "consumed_kg": str(fc.consumed_kg),
            "live_birds": fc.live_birds, "eggs_collected": fc.eggs_collected,
            "cost_per_bird_kes": str(fc.cost_per_bird_kes) if fc.cost_per_bird_kes else None,
            "cost_per_egg_kes": str(fc.cost_per_egg_kes) if fc.cost_per_egg_kes else None,
            "weight_gain_kg": str(fc.weight_gain_kg) if fc.weight_gain_kg else None,
            "fcr": str(fc.fcr) if fc.fcr else None,
            "cost_per_kg_gain_kes": str(fc.cost_per_kg_gain_kes) if fc.cost_per_kg_gain_kes else None,
        }
        for fc in analytics.by_flock
    ]
    forecast = await get_forecast(db, farm_id, window_days=30)
    forecast_context = [
        {
            "feed_type": fi.feed_type, "location": fi.location,
            "quantity_kg": str(fi.quantity_kg),
            "avg_daily_consumption_kg": str(fi.avg_daily_consumption_kg),
            "days_remaining": fi.days_remaining,
            "depletion_date": fi.depletion_date.isoformat() if fi.depletion_date else None,
            "recommended_purchase_date": fi.recommended_purchase_date.isoformat() if fi.recommended_purchase_date else None,
            "status": fi.status,
        }
        for fi in forecast.items
    ]
    supplier_history = [
        {
            "supplier": s.name, "total_spend_kes": str(s.total_spend_kes or 0),
            "total_kg_purchased": str(s.total_kg_purchased or 0),
            "purchase_count": s.purchase_count or 0, "rating": str(s.rating) if s.rating else None,
        }
        for s in suppliers
    ]
    costs = {
        "total_consumed_cost_kes": str(analytics.total_consumed_cost_kes),
        "total_wasted_kg": str(analytics.total_wasted_kg),
        "wastage_pct": str(analytics.wastage_pct) if analytics.wastage_pct is not None else None,
        "avg_cost_per_kg": str(analytics.avg_cost_per_kg) if analytics.avg_cost_per_kg else None,
        "by_feed_type": [
            {"feed_type": b.feed_type, "consumed_cost_kes": str(b.consumed_cost_kes)}
            for b in analytics.by_feed_type
        ],
    }
    performance = {
        "total_stock_kg": str(sum((i.quantity_kg for i in items), Decimal("0"))),
        "total_stock_value_kes": str(sum((i.stock_value_kes for i in items), Decimal("0"))),
        "low_stock_items": [i.feed_type for i in items if i.is_low_stock],
        "expiring_items": [
            {"feed_type": i.feed_type, "expiry_date": i.expiry_date.isoformat(), "days_to_expiry": i.days_to_expiry}
            for i in items if i.is_expiring_soon or i.is_expired
        ],
        "forecast": forecast_context,
        "next_purchase_date": forecast.next_purchase_date.isoformat() if forecast.next_purchase_date else None,
    }

    return FeedAIContext(
        farm_id=farm_id,
        generated_at=datetime.now(tz=timezone.utc),
        window_days=window_days,
        inventory=inventory,
        feed_history=feed_history,
        consumption=consumption,
        costs=costs,
        supplier_history=supplier_history,
        feed_conversions=feed_conversions,
        performance=performance,
    )
