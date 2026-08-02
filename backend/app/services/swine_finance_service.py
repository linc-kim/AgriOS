"""
Greena — Swine Finance Service (Module 20, Milestone 8)

Sales recording and the computed swine P&L / unit economics. It does NOT duplicate
the Finance engine:

  * Operational costs (vet, medication, labour, housing, utilities) post to the
    SHARED ``expenses`` ledger via ``finance_service.record_category_expense``
    (flock_id=None), tagged ``metadata_["module"]="swine"`` — the SR/Rabbit/BSF
    pattern. No swine cost table; no change to the Finance platform.
  * Sale revenue is a RECORDED FACT on ``swine_sale`` (the platform revenue ledger is
    flock-scoped, frozen DB-07).
  * Feed cost for the P&L is the recorded consumption allocation
    (``swine_feed_record.cost``) — already expensed at Inventory stock-in, so it is
    not re-posted (no double-count).

The P&L / unit economics are *computed* on demand by the pure
:mod:`swine_finance_engine`; nothing is stored as a competing snapshot. Every cost is
traceable to its source (feed records, or specific tagged ledger expenses).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense, ExpenseCategory
from app.models.swine import (
    SALE_SOLD_TYPES,
    SALE_TRANSFER_TYPES,
    SwineFeedRecord,
    SwinePig,
    SwineSale,
)
from app.schemas.swine import OperationalExpenseCreate, SaleCreate
from app.services import audit_service, finance_service
from app.services import swine_finance_engine as fin_eng
from app.services.swine_service import _append_event, _get_pig_or_404

# Shared-ledger expense categories treated as swine "health" cost for unit economics.
_HEALTH_SLUGS = ("vaccination", "medication", "vet_fees", "health")


def _tag_module(expense: Expense) -> None:
    meta = dict(expense.metadata_ or {})
    meta["module"] = "swine"
    expense.metadata_ = meta


# ── Sales (business events) ────────────────────────────────────────────────────

async def record_sale(db, farm: Farm, data: SaleCreate, user: User) -> SwineSale:
    pig = None
    if data.pig_id is not None:
        pig = await _get_pig_or_404(db, farm.id, data.pig_id)

    total = data.total_price
    if total is None and data.unit_price is not None:
        total = (Decimal(str(data.unit_price)) * Decimal(str(data.quantity))).quantize(Decimal("0.01"))
    if total is None:
        total = Decimal("0")

    sale = SwineSale(
        id=uuid.uuid4(), farm_id=farm.id, pig_id=data.pig_id, sale_type=data.sale_type,
        buyer_name=data.buyer_name, buyer_contact=data.buyer_contact, destination=data.destination,
        sale_date=data.sale_date, head_count=data.head_count, quantity=data.quantity, unit=data.unit,
        weight_kg=data.weight_kg, unit_price=data.unit_price, total_price=total, currency=data.currency,
        invoice_reference=data.invoice_reference, notes=data.notes, recorded_by=user.id,
    )
    db.add(sale)
    await db.flush()

    # A sale is a business event: it updates the pig's status (ownership transition).
    if pig is not None and pig.status == "active":
        if data.sale_type in SALE_TRANSFER_TYPES:
            pig.status = "transferred"
            event_type, verb = "transferred", "Transferred"
        elif data.sale_type in SALE_SOLD_TYPES:
            pig.status = "sold"
            event_type, verb = "sold", "Sold"
        else:
            event_type = None
        if event_type is not None:
            pig.group_id = None
            pig.pen_id = None
            await _append_event(
                db, pig.id, event_type, f"{verb} ({data.sale_type}) to {data.buyer_name or 'buyer'}",
                occurred_at=datetime.combine(data.sale_date, datetime.min.time(), tzinfo=timezone.utc),
                operator_id=user.id, details={"sale_id": str(sale.id), "total_price": str(total)})
    await audit_service.log_action(
        db, action="swine.sale.record", resource_type="swine_sale",
        resource_id=sale.id, farm_id=farm.id, user_id=user.id,
        new_value={"sale_type": data.sale_type, "total_price": str(total)})
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales(db, farm_id, *, sale_type=None, pig_id=None, limit=100, offset=0):
    conds = [SwineSale.farm_id == farm_id, SwineSale.deleted_at.is_(None)]
    if sale_type:
        conds.append(SwineSale.sale_type == sale_type)
    if pig_id:
        conds.append(SwineSale.pig_id == pig_id)
    total = (await db.execute(select(func.count(SwineSale.id)).where(*conds))).scalar_one()
    r = await db.execute(select(SwineSale).where(*conds)
                         .order_by(SwineSale.sale_date.desc(), SwineSale.created_at.desc())
                         .limit(limit).offset(offset))
    return list(r.scalars().all()), total


# ── Cost posting (reuse the shared Finance ledger) ─────────────────────────────

async def post_operational_expense(db, farm: Farm, data: OperationalExpenseCreate, user: User):
    """Post an operating cost (vet, medication, labour, housing, utilities…) to the
    SHARED expenses ledger, tagged ``module=swine`` for attribution. No parallel
    swine cost store — the transaction lives once in the Finance module."""
    expense = await finance_service.record_category_expense(
        db, farm_id=farm.id, flock_id=None, category_slug=data.category_slug,
        amount=data.amount, description=data.description or f"Swine {data.category_slug}",
        current_user=user, expense_date=data.expense_date,
    )
    if expense is None:
        raise NotFoundException(f"Expense category '{data.category_slug}' not available on this platform.")
    _tag_module(expense)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.finance.operational_expense", resource_type="expense",
        resource_id=expense.id, farm_id=farm.id, user_id=user.id,
        new_value={"category": data.category_slug, "amount": str(data.amount)})
    await db.commit()
    await db.refresh(expense)
    return expense


# ── Computed P&L / unit economics ──────────────────────────────────────────────

async def finance_summary(db, farm_id) -> dict:
    """Computed swine P&L + unit economics over recorded facts (no snapshot). Every
    figure traces to a source: revenue → swine_sale; feed cost → feed records;
    operating/health cost → swine-tagged shared-ledger expenses."""
    async def _sum(col, *conds):
        return (await db.execute(select(func.coalesce(func.sum(col), 0)).where(*conds))).scalar_one()

    async def _count(col, *conds):
        return (await db.execute(select(func.count(col)).where(*conds))).scalar_one()

    # Revenue = external sales only (internal transfers are not income).
    external = (SwineSale.farm_id == farm_id, SwineSale.deleted_at.is_(None),
                SwineSale.sale_type.not_in(SALE_TRANSFER_TYPES))
    revenue = await _sum(SwineSale.total_price, *external)
    sales_count = await _count(SwineSale.id, *external)
    sold_weight = await _sum(SwineSale.weight_kg, *external)
    sold_head = await _sum(SwineSale.head_count, *external)
    currency = (await db.execute(
        select(SwineSale.currency).where(*external, SwineSale.currency.is_not(None)).limit(1)
    )).scalar_one_or_none()

    feed_conds = (SwineFeedRecord.farm_id == farm_id, SwineFeedRecord.deleted_at.is_(None))
    feed_cost = await _sum(SwineFeedRecord.cost, *feed_conds)
    feed_events = await _count(SwineFeedRecord.id, *feed_conds, SwineFeedRecord.cost.is_not(None))

    tagged = (Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
              Expense.metadata_["module"].astext == "swine")
    operating_cost = await _sum(Expense.amount, *tagged)
    operating_entries = await _count(Expense.id, *tagged)
    health_cost = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .select_from(Expense).join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*tagged, ExpenseCategory.slug.in_(_HEALTH_SLUGS))
    )).scalar_one()

    pig_count = await _count(SwinePig.id, SwinePig.farm_id == farm_id,
                             SwinePig.status == "active", SwinePig.deleted_at.is_(None))

    pnl = fin_eng.pnl_summary(
        revenue=revenue, revenue_events=int(sales_count), feed_cost=feed_cost, feed_events=int(feed_events),
        operating_cost=operating_cost, operating_entries=int(operating_entries), currency=currency)
    total_cost = Decimal(str(feed_cost or 0)) + Decimal(str(operating_cost or 0))
    economics = fin_eng.unit_economics(
        revenue=revenue, total_cost=total_cost, feed_cost=feed_cost, health_cost=health_cost,
        pig_count=int(pig_count), sold_weight_kg=sold_weight, sold_head=int(sold_head or 0))
    return {"pnl": pnl, "unit_economics": economics,
            "cost_sources": {"feed_cost": "swine_feed_record.cost (already expensed at Inventory stock-in)",
                             "operating_cost": "shared expenses ledger, metadata.module=swine",
                             "revenue": "swine_sale.total_price (recorded fact, DB-07)"}}
