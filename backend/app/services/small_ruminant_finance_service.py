"""
Greena — Small Ruminant Finance Service (Modules 18/19, Milestone 8)

Sales recording and the computed goat/sheep P&L. It does NOT duplicate the Finance
engine:

  * Operational costs post to the SHARED ``expenses`` ledger via
    ``finance_service.record_category_expense(flock_id=None)`` and are tagged
    ``metadata_["module"]=<species>`` — the Aviculture/BSF/Rabbit pattern. No
    small-ruminant cost table, no change to the Finance platform.
  * Sale revenue stays a RECORDED FACT on ``sr_sale`` (the platform revenue ledger
    is flock-scoped, frozen DB-07).
  * Feed cost for the P&L is the recorded consumption allocation
    (``sr_feed_record.cost``) — already expensed at Inventory stock-in, so it is
    not re-posted (no double-count).

The P&L / unit economics are *computed* on demand by the pure
:mod:`small_ruminant_finance_engine`; nothing is stored as a competing snapshot.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense, ExpenseCategory
from app.models.small_ruminant import (
    SmallRuminant,
    SmallRuminantFeedRecord,
    SmallRuminantFleece,
    SmallRuminantMilkRecord,
    SmallRuminantSale,
)
from app.schemas.small_ruminant import OperationalExpenseCreate, SaleCreate
from app.services import audit_service, finance_service
from app.services import small_ruminant_finance_engine as fin_eng
from app.services.small_ruminant_service import _append_event, _get_animal_or_404

_VET_SLUGS = ("vaccination", "medication", "vet_fees")


def _tag_module(expense: Expense, species: str) -> None:
    meta = dict(expense.metadata_ or {})
    meta["module"] = species
    expense.metadata_ = meta


# ── Sales ──────────────────────────────────────────────────────────────────────

async def record_sale(db, farm: Farm, species: str, data: SaleCreate, user: User) -> SmallRuminantSale:
    animal = None
    if data.animal_id is not None:
        animal = await _get_animal_or_404(db, farm.id, species, data.animal_id)

    total = data.total_price
    if total is None and data.unit_price is not None:
        total = (Decimal(str(data.unit_price)) * Decimal(str(data.quantity))).quantize(Decimal("0.01"))
    if total is None:
        total = Decimal("0")

    sale = SmallRuminantSale(
        id=uuid.uuid4(), species=species, farm_id=farm.id, animal_id=data.animal_id,
        sale_type=data.sale_type, buyer_name=data.buyer_name, buyer_contact=data.buyer_contact,
        sale_date=data.sale_date, quantity=data.quantity, unit=data.unit, weight_kg=data.weight_kg,
        unit_price=data.unit_price, total_price=total, currency=data.currency,
        invoice_reference=data.invoice_reference, notes=data.notes, recorded_by=user.id,
    )
    db.add(sale)
    await db.flush()

    # Selling an active animal transitions it to sold (product sales don't).
    if animal is not None and animal.status == "active" and data.sale_type in ("live", "breeding", "meat", "cull"):
        animal.status = "sold"
        animal.group_id = None
        animal.pen_id = None
        animal.pasture_id = None
        await _append_event(
            db, animal.id, "sold", f"Sold ({data.sale_type}) to {data.buyer_name or 'buyer'}",
            occurred_at=datetime.combine(data.sale_date, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"sale_id": str(sale.id), "total_price": str(total)},
        )
    await audit_service.log_action(
        db, action=f"sr.{species}.sale.record", resource_type="sr_sale",
        resource_id=sale.id, farm_id=farm.id, user_id=user.id,
        new_value={"sale_type": data.sale_type, "total_price": str(total)},
    )
    await db.commit()
    await db.refresh(sale)
    return sale


async def list_sales(db, farm_id, species, *, sale_type=None, animal_id=None, limit=100, offset=0):
    conds = [SmallRuminantSale.farm_id == farm_id, SmallRuminantSale.species == species,
             SmallRuminantSale.deleted_at.is_(None)]
    if sale_type:
        conds.append(SmallRuminantSale.sale_type == sale_type)
    if animal_id:
        conds.append(SmallRuminantSale.animal_id == animal_id)
    total = (await db.execute(select(func.count(SmallRuminantSale.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(SmallRuminantSale).where(*conds)
        .order_by(SmallRuminantSale.sale_date.desc(), SmallRuminantSale.created_at.desc())
        .limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


# ── Cost posting (reuse the shared Finance ledger) ─────────────────────────────

async def post_operational_expense(db, farm: Farm, species: str, data: OperationalExpenseCreate, user: User):
    """Post an operating cost (vet, labour, housing, utilities…) to the SHARED
    expenses ledger, tagged by species for attribution."""
    expense = await finance_service.record_category_expense(
        db, farm_id=farm.id, flock_id=None, category_slug=data.category_slug,
        amount=data.amount, description=data.description, current_user=user,
        expense_date=data.expense_date,
    )
    if expense is None:
        raise NotFoundException(f"Expense category '{data.category_slug}' not available on this platform.")
    _tag_module(expense, species)
    await db.flush()
    await audit_service.log_action(
        db, action=f"sr.{species}.finance.operational_expense", resource_type="expense",
        resource_id=expense.id, farm_id=farm.id, user_id=user.id,
        new_value={"category": data.category_slug, "amount": str(data.amount)},
    )
    await db.commit()
    await db.refresh(expense)
    return expense


# ── Computed P&L ───────────────────────────────────────────────────────────────

async def finance_summary(db, farm_id, species) -> dict:
    """Computed goat/sheep P&L + unit economics over recorded facts (no snapshot)."""
    async def _sum(col, *conds):
        return (await db.execute(select(func.coalesce(func.sum(col), 0)).where(*conds))).scalar_one()

    async def _count(col, *conds):
        return (await db.execute(select(func.count(col)).where(*conds))).scalar_one()

    sale_conds = (SmallRuminantSale.farm_id == farm_id, SmallRuminantSale.species == species,
                  SmallRuminantSale.deleted_at.is_(None))
    revenue = await _sum(SmallRuminantSale.total_price, *sale_conds)
    sales_count = await _count(SmallRuminantSale.id, *sale_conds)
    sold_weight = await _sum(SmallRuminantSale.weight_kg, *sale_conds)
    currency = (await db.execute(
        select(SmallRuminantSale.currency).where(*sale_conds, SmallRuminantSale.currency.is_not(None)).limit(1)
    )).scalar_one_or_none()

    feed_conds = (SmallRuminantFeedRecord.farm_id == farm_id, SmallRuminantFeedRecord.species == species,
                  SmallRuminantFeedRecord.deleted_at.is_(None))
    feed_cost = await _sum(SmallRuminantFeedRecord.cost, *feed_conds)
    feed_events = await _count(SmallRuminantFeedRecord.id, *feed_conds, SmallRuminantFeedRecord.cost.is_not(None))

    # Operating cost — species-tagged shared-ledger expenses.
    tagged = (Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
              Expense.metadata_["module"].astext == species)
    operating_cost = await _sum(Expense.amount, *tagged)
    operating_entries = await _count(Expense.id, *tagged)
    vet_cost = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .select_from(Expense).join(ExpenseCategory, Expense.category_id == ExpenseCategory.id)
        .where(*tagged, ExpenseCategory.slug.in_(_VET_SLUGS))
    )).scalar_one()

    # Denominators (recorded quantities) for unit economics.
    animal_count = await _count(SmallRuminant.id, SmallRuminant.farm_id == farm_id,
                                SmallRuminant.species == species, SmallRuminant.deleted_at.is_(None))
    milk_litres = await _sum(SmallRuminantMilkRecord.quantity_liters,
                             SmallRuminantMilkRecord.farm_id == farm_id,
                             SmallRuminantMilkRecord.species == species,
                             SmallRuminantMilkRecord.deleted_at.is_(None))
    wool_kg = await _sum(SmallRuminantFleece.greasy_weight_kg,
                         SmallRuminantFleece.farm_id == farm_id,
                         SmallRuminantFleece.species == species,
                         SmallRuminantFleece.deleted_at.is_(None))

    pnl = fin_eng.pnl_summary(
        revenue=revenue, revenue_events=int(sales_count), feed_cost=feed_cost, feed_events=int(feed_events),
        operating_cost=operating_cost, operating_entries=int(operating_entries), currency=currency,
    )
    total_cost = Decimal(str(feed_cost or 0)) + Decimal(str(operating_cost or 0))
    economics = fin_eng.unit_economics(
        revenue=revenue, total_cost=total_cost, feed_cost=feed_cost, vet_cost=vet_cost,
        animal_count=int(animal_count), sold_weight_kg=sold_weight,
        milk_litres=milk_litres if fin_eng._d(milk_litres) > 0 else None,
        wool_kg=wool_kg if fin_eng._d(wool_kg) > 0 else None,
    )
    return {"pnl": pnl, "unit_economics": economics}
