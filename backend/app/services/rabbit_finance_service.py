"""
Greena — Rabbit Finance Service (Module 17, Milestone 6)

Sales recording and the computed rabbit P&L. It does NOT duplicate the Finance
engine (ledger CON-M6):

  * Operational costs post to the SHARED ``expenses`` ledger via
    ``finance_service.record_category_expense(flock_id=None)`` and are tagged
    ``metadata_["module"]="rabbit"`` — exactly the Aviculture/BSF pattern. No
    rabbit cost table, no change to the Finance platform.
  * Sale revenue stays a RECORDED FACT on ``rabbit_sale`` (the platform revenue
    ledger is flock-scoped, frozen DB-07).
  * Feed cost for the P&L is the recorded consumption allocation
    (``rabbit_feed_record.cost``) — already expensed at Inventory stock-in, so it
    is not re-posted (no double-count, CON-M6-3).

The P&L / unit economics are *computed* on demand by the pure
:mod:`rabbit_finance_engine`; nothing is stored as a competing snapshot.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense, ExpenseCategory
from app.models.rabbit import (
    Rabbit,
    RabbitBreeding,
    RabbitFeedRecord,
    RabbitLitter,
    RabbitSale,
)
from app.schemas.rabbit import OperationalExpenseCreate, SaleCreate
from app.services import audit_service, finance_service
from app.services import rabbit_finance_engine as fin_eng
from app.services import rabbit_service

_MODULE_TAG = "rabbit"
_VET_SLUGS = ("vaccination", "medication", "vet_fees")


def _tag_module(expense: Expense, **extra) -> None:
    meta = dict(expense.metadata_ or {})
    meta["module"] = _MODULE_TAG
    meta.update({k: str(v) for k, v in extra.items() if v is not None})
    expense.metadata_ = meta


# ── Sales ────────────────────────────────────────────────────────────────────────

async def record_sale(db: AsyncSession, farm: Farm, data: SaleCreate, user: User) -> RabbitSale:
    rabbit = None
    if data.rabbit_id is not None:
        rabbit = await rabbit_service._get_rabbit_or_404(db, farm.id, data.rabbit_id)

    total = data.total_price
    if total is None and data.unit_price is not None:
        total = (Decimal(str(data.unit_price)) * Decimal(str(data.quantity))).quantize(Decimal("0.01"))
    if total is None:
        total = Decimal("0")

    sale = RabbitSale(
        id=uuid.uuid4(), farm_id=farm.id, rabbit_id=data.rabbit_id, sale_type=data.sale_type,
        buyer_name=data.buyer_name, buyer_contact=data.buyer_contact, sale_date=data.sale_date,
        quantity=data.quantity, weight_kg=data.weight_kg, unit_price=data.unit_price,
        total_price=total, currency=data.currency, invoice_reference=data.invoice_reference,
        notes=data.notes, recorded_by=user.id,
    )
    db.add(sale)
    await db.flush()

    # Recording a sale of an active rabbit transitions it to sold (CON-M6-5).
    if rabbit is not None and rabbit.status == "active":
        rabbit.status = "sold"
        rabbit.cage_id = None
        await rabbit_service._append_event(
            db, rabbit.id, "sold", f"Sold ({data.sale_type}) to {data.buyer_name or 'buyer'}",
            occurred_at=datetime.combine(data.sale_date, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"sale_id": str(sale.id), "total_price": str(total)},
        )
    await audit_service.log_action(
        db, action="rabbit.sale.record", resource_type="rabbit_sale",
        resource_id=sale.id, farm_id=farm.id, user_id=user.id,
        new_value={"sale_type": data.sale_type, "total_price": str(total)},
    )
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales(db, farm_id, *, sale_type=None, rabbit_id=None, limit=100, offset=0):
    conds = [RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None)]
    if sale_type:
        conds.append(RabbitSale.sale_type == sale_type)
    if rabbit_id:
        conds.append(RabbitSale.rabbit_id == rabbit_id)
    total = (await db.execute(select(func.count(RabbitSale.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(RabbitSale).where(*conds)
        .order_by(RabbitSale.sale_date.desc(), RabbitSale.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


# ── Cost posting (reuse the shared Finance ledger) ─────────────────────────────

async def post_operational_expense(db: AsyncSession, farm: Farm, data: OperationalExpenseCreate, user: User) -> Expense:
    """Post a rabbit operating cost (vet, labour, housing, utilities…) to the
    SHARED expenses ledger, tagged for attribution (ledger CON-M6-1)."""
    expense = await finance_service.record_category_expense(
        db, farm_id=farm.id, flock_id=None, category_slug=data.category_slug,
        amount=data.amount, description=data.description, current_user=user,
        expense_date=data.expense_date,
    )
    if expense is None:
        raise NotFoundException(f"Expense category '{data.category_slug}' not available on this platform.")
    _tag_module(expense)
    await db.flush()
    await audit_service.log_action(
        db, action="rabbit.finance.operational_expense", resource_type="expense",
        resource_id=expense.id, farm_id=farm.id, user_id=user.id,
        new_value={"category": data.category_slug, "amount": str(data.amount)},
    )
    await db.commit()
    await db.refresh(expense)
    return expense


# ── Computed P&L (Spec Part 4 §12, Part 7 §9) ──────────────────────────────────

async def finance_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Computed rabbit P&L + unit economics over recorded facts (no snapshot)."""
    async def _sum(col, *conds):
        return (await db.execute(select(func.coalesce(func.sum(col), 0)).where(*conds))).scalar_one()

    async def _count(col, *conds):
        return (await db.execute(select(func.count(col)).where(*conds))).scalar_one()

    # Revenue — recorded sale facts.
    revenue = await _sum(RabbitSale.total_price, RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None))
    sales_count = await _count(RabbitSale.id, RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None))
    sold_weight = await _sum(RabbitSale.weight_kg, RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None))
    currency = (await db.execute(
        select(RabbitSale.currency).where(
            RabbitSale.farm_id == farm_id, RabbitSale.deleted_at.is_(None), RabbitSale.currency.is_not(None)
        ).limit(1)
    )).scalar_one_or_none()

    # Feed cost — recorded consumption allocation (not re-posted to the ledger).
    feed_cost = await _sum(RabbitFeedRecord.cost, RabbitFeedRecord.farm_id == farm_id,
                           RabbitFeedRecord.deleted_at.is_(None))
    feed_events = await _count(RabbitFeedRecord.id, RabbitFeedRecord.farm_id == farm_id,
                               RabbitFeedRecord.deleted_at.is_(None), RabbitFeedRecord.cost.is_not(None))

    # Operating cost — rabbit-tagged shared-ledger expenses.
    tagged = (Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
              Expense.metadata_["module"].astext == _MODULE_TAG)
    operating_cost = await _sum(Expense.amount, *tagged)
    operating_entries = await _count(Expense.id, *tagged)
    vet_cost = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .select_from(Expense).join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*tagged, ExpenseCategory.slug.in_(_VET_SLUGS))
    )).scalar_one()

    # Denominators (recorded counts) for unit economics.
    rabbit_count = await _count(Rabbit.id, Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None))
    litters = await _count(RabbitLitter.id, RabbitLitter.farm_id == farm_id, RabbitLitter.deleted_at.is_(None))
    breeding_does = (await db.execute(
        select(func.count(func.distinct(RabbitBreeding.doe_id))).where(
            RabbitBreeding.farm_id == farm_id, RabbitBreeding.deleted_at.is_(None),
            RabbitBreeding.doe_id.is_not(None))
    )).scalar_one()

    pnl = fin_eng.pnl_summary(
        revenue=revenue, revenue_events=int(sales_count), feed_cost=feed_cost, feed_events=int(feed_events),
        operating_cost=operating_cost, operating_entries=int(operating_entries), currency=currency,
    )
    total_cost = Decimal(str(feed_cost or 0)) + Decimal(str(operating_cost or 0))
    economics = fin_eng.unit_economics(
        revenue=revenue, total_cost=total_cost, feed_cost=feed_cost, vet_cost=vet_cost,
        rabbit_count=int(rabbit_count), sold_weight_kg=sold_weight, litters=int(litters),
        breeding_does=int(breeding_does),
    )
    return {"pnl": pnl, "unit_economics": economics}
