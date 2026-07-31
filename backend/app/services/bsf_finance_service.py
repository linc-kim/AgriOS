"""
Greena — BSF Finance Service (Module 16, Part 5)

Integration + computed-report layer. It does NOT duplicate the Finance engine
(see docs/MODULE_16_BSF_LEDGER.md → Integration Contract → Finance):

  * Operational costs post to the SHARED ``expenses`` ledger via
    ``finance_service.record_category_expense`` (``flock_id=None``) and are tagged
    ``metadata_["module"]="bsf"`` for attribution — exactly the Aviculture pattern.
    No BSF cost/revenue table is created.
  * Harvest revenue stays a RECORDED FACT on ``bsf_harvest_event`` (the platform
    revenue ledger is flock-scoped).

The P&L is *computed* on demand by the pure :mod:`bsf_finance_engine` from those
recorded facts — confirmed records and any projection are kept distinct and
honesty-labelled. Nothing is stored as a competing snapshot.
"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.bsf import BsfFeedstockLot, BsfHarvestEvent
from app.models.finance import Expense
from app.schemas.bsf import OperationalExpenseCreate
from app.services import audit_service, finance_service
from app.services import bsf_finance_engine as fin_eng

_MODULE_TAG = "bsf"


def _tag_module(expense: Expense, **extra) -> None:
    """Attribute a shared-ledger expense to BSF without a parallel table."""
    meta = dict(expense.metadata_ or {})
    meta["module"] = _MODULE_TAG
    meta.update({k: str(v) for k, v in extra.items() if v is not None})
    expense.metadata_ = meta


async def post_feedstock_expense(
    db: AsyncSession, farm_id: uuid.UUID, lot_id: uuid.UUID, user: User,
) -> Expense | None:
    """Post a feedstock lot's recorded cost to the SHARED expenses ledger (once).

    Idempotent: the lot records the resulting ``expense_id`` in its metadata;
    a second call is a no-op. Reuses ``finance_service.record_category_expense``.
    """
    lot = (await db.execute(select(BsfFeedstockLot).where(
        BsfFeedstockLot.id == lot_id, BsfFeedstockLot.farm_id == farm_id,
        BsfFeedstockLot.deleted_at.is_(None),
    ))).scalar_one_or_none()
    if lot is None:
        raise NotFoundException(f"Feedstock lot {lot_id} not found on this farm.")
    if lot.cost is None or lot.cost <= 0:
        raise ConflictException("Feedstock lot has no recorded cost to post.")
    if (lot.metadata_ or {}).get("expense_id"):
        raise ConflictException("This feedstock lot's cost has already been posted to the ledger.")

    expense = await finance_service.record_category_expense(
        db, farm_id=farm_id, flock_id=None, category_slug="feed_purchase",
        amount=lot.cost, description=f"BSF feedstock: {lot.name}", current_user=user,
        expense_date=lot.delivery_date or lot.collection_date,
    )
    if expense is None:
        raise NotFoundException("Expense category 'feed_purchase' not available on this platform.")
    _tag_module(expense, source="feedstock_lot", lot_id=lot.id)
    # Record the link on the lot for idempotency (soft reference; no schema change).
    lot.metadata_ = {**(lot.metadata_ or {}), "expense_id": str(expense.id)}
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.finance.feedstock_expense", resource_type="expense",
        resource_id=expense.id, farm_id=farm_id, user_id=user.id,
        new_value={"lot": lot.name, "amount": str(lot.cost)},
    )
    await db.commit()
    await db.refresh(expense)
    return expense


async def post_operational_expense(
    db: AsyncSession, farm_id: uuid.UUID, data: OperationalExpenseCreate, user: User,
) -> Expense:
    """Post a BSF operational cost (labour, utilities, other) to the shared ledger."""
    expense = await finance_service.record_category_expense(
        db, farm_id=farm_id, flock_id=None, category_slug=data.category_slug,
        amount=data.amount, description=data.description, current_user=user,
        expense_date=data.expense_date,
    )
    if expense is None:
        raise NotFoundException(f"Expense category '{data.category_slug}' not available on this platform.")
    _tag_module(expense)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.finance.operational_expense", resource_type="expense",
        resource_id=expense.id, farm_id=farm_id, user_id=user.id,
        new_value={"category": data.category_slug, "amount": str(data.amount)},
    )
    await db.commit()
    await db.refresh(expense)
    return expense


async def finance_summary(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Computed BSF P&L over recorded facts (no stored snapshot).

    Revenue = recorded harvest revenue facts; operating cost = BSF-tagged entries
    in the shared expenses ledger; derivations are calculated and labelled.
    """
    revenue = (await db.execute(
        select(func.coalesce(func.sum(BsfHarvestEvent.revenue_amount), 0))
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None))
    )).scalar_one()
    revenue_events = (await db.execute(
        select(func.count(BsfHarvestEvent.id))
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None),
               BsfHarvestEvent.revenue_amount.is_not(None))
    )).scalar_one()
    harvested_kg = (await db.execute(
        select(func.coalesce(func.sum(BsfHarvestEvent.quantity_kg), 0))
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None))
    )).scalar_one()
    currency = (await db.execute(
        select(BsfHarvestEvent.currency)
        .where(BsfHarvestEvent.farm_id == farm_id, BsfHarvestEvent.deleted_at.is_(None),
               BsfHarvestEvent.currency.is_not(None))
        .limit(1)
    )).scalar_one_or_none()

    operating_cost = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
            Expense.metadata_["module"].astext == _MODULE_TAG)
    )).scalar_one()
    cost_entries = (await db.execute(
        select(func.count(Expense.id)).where(
            Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
            Expense.metadata_["module"].astext == _MODULE_TAG)
    )).scalar_one()

    return fin_eng.pnl_summary(
        revenue=Decimal(str(revenue or 0)), revenue_events=int(revenue_events),
        operating_cost=Decimal(str(operating_cost or 0)), cost_entries=int(cost_entries),
        harvested_kg=Decimal(str(harvested_kg or 0)), currency=currency,
    )
