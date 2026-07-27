"""
Greena — Aviculture Finance Service (Module 15, Part 7)

Integration + computed-report layer. It does NOT duplicate the Finance engine:
  * Operational costs post to the shared ``expenses`` ledger via
    ``finance_service.record_category_expense`` (flock_id=None), tagged
    ``metadata.module='aviculture'`` for attribution.
  * Feed/medication/equipment stock, consumption, suppliers and assets reuse the
    existing farm-level Inventory module unchanged.

The only stored aviculture-specific financial fact is the collection valuation
(``avi_valuation``). Collection value and the P&L summary are *computed* by the
pure ``valuation_engine`` from recorded facts (sale/purchase events + shared
ledger), never stored as a competing snapshot.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.finance import Expense
from app.models.aviculture import AviBird, AviBirdEvent, AviValuation
from app.schemas.aviculture_finance import PurchaseExpenseCreate, ValuationCreate
from app.services import audit_service, finance_service, valuation_engine


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ── Valuations (recorded facts) ───────────────────────────────────────────────

async def record_valuation(db, farm: Farm, data: ValuationCreate, user: User) -> AviValuation:
    if data.bird_id is not None:
        b = (await db.execute(select(AviBird.id).where(
            AviBird.id == data.bird_id, AviBird.farm_id == farm.id, AviBird.deleted_at.is_(None)))).scalar_one_or_none()
        if b is None:
            raise NotFoundException("Bird not found on this farm.")
    v = AviValuation(id=uuid.uuid4(), farm_id=farm.id, bird_id=data.bird_id, valued_on=data.valued_on or date.today(),
                     amount=data.amount, currency=data.currency, method=data.method, source=data.source,
                     notes=data.notes, created_by=user.id)
    db.add(v)
    await db.flush()
    await audit_service.log_action(db, action="avi.valuation.record", resource_type="avi_valuation",
                                   resource_id=v.id, farm_id=farm.id, user_id=user.id,
                                   new_value={"amount": str(data.amount), "method": data.method})
    await db.commit()
    await db.refresh(v)
    return v


async def list_valuations(db, farm_id, bird_id=None) -> list[AviValuation]:
    conds = [AviValuation.farm_id == farm_id, AviValuation.deleted_at.is_(None)]
    if bird_id:
        conds.append(AviValuation.bird_id == bird_id)
    return list((await db.execute(select(AviValuation).where(*conds).order_by(
        AviValuation.valued_on.desc(), AviValuation.created_at.desc()))).scalars().all())


# ── Expenses (reuse the shared finance ledger) ────────────────────────────────

async def record_purchase_expense(db, farm: Farm, data: PurchaseExpenseCreate, user: User) -> Expense | None:
    """Post an aviculture operational/purchase cost to the SHARED expense ledger.
    Reuses finance_service; tags aviculture attribution in metadata."""
    if data.bird_id is not None:
        b = (await db.execute(select(AviBird.id).where(
            AviBird.id == data.bird_id, AviBird.farm_id == farm.id, AviBird.deleted_at.is_(None)))).scalar_one_or_none()
        if b is None:
            raise NotFoundException("Bird not found on this farm.")
    expense = await finance_service.record_category_expense(
        db, farm_id=farm.id, flock_id=None, category_slug=data.category_slug, amount=data.amount,
        description=data.description, current_user=user, expense_date=data.expense_date)
    if expense is None:
        raise NotFoundException(f"Expense category '{data.category_slug}' not available.")
    # Attribute to aviculture without a parallel table.
    meta = dict(expense.metadata_ or {})
    meta["module"] = "aviculture"
    if data.bird_id:
        meta["bird_id"] = str(data.bird_id)
    expense.metadata_ = meta
    await db.flush()
    await audit_service.log_action(db, action="avi.expense.post", resource_type="expense",
                                   resource_id=expense.id, farm_id=farm.id, user_id=user.id,
                                   new_value={"amount": str(data.amount), "category": data.category_slug})
    await db.commit()
    await db.refresh(expense)
    return expense


# ── Computed valuation & summary (pure engine over recorded facts) ────────────

async def _event_amount_sum(db, farm_id, event_type: str) -> Decimal:
    """Sum recorded prices from bird events of a type (e.g. sold / purchased)."""
    rows = await db.execute(
        select(AviBirdEvent.data).select_from(AviBirdEvent)
        .join(AviBird, AviBird.id == AviBirdEvent.bird_id)
        .where(AviBird.farm_id == farm_id, AviBirdEvent.event_type == event_type,
               AviBirdEvent.deleted_at.is_(None)))
    total = Decimal("0")
    for (data,) in rows:
        amt = _to_decimal((data or {}).get("price"))
        if amt is not None:
            total += amt
    return total


async def _purchase_price_by_bird(db, farm_id) -> dict:
    rows = await db.execute(
        select(AviBirdEvent.bird_id, AviBirdEvent.data)
        .join(AviBird, AviBird.id == AviBirdEvent.bird_id)
        .where(AviBird.farm_id == farm_id, AviBirdEvent.event_type == "purchased",
               AviBirdEvent.deleted_at.is_(None)))
    out: dict = {}
    for bird_id, data in rows:
        amt = _to_decimal((data or {}).get("price"))
        if amt is not None:
            out[bird_id] = amt
    return out


async def collection_valuation(db, farm_id) -> dict:
    """Compute the current collection value from recorded per-bird values."""
    bird_ids = [r[0] for r in (await db.execute(
        select(AviBird.id).where(AviBird.farm_id == farm_id, AviBird.status == "active",
                                 AviBird.deleted_at.is_(None)))).all()]

    by_bird: dict = {}
    if bird_ids:
        val_rows = await db.execute(
            select(AviValuation.bird_id, AviValuation.method, AviValuation.amount, AviValuation.valued_on).where(
                AviValuation.bird_id.in_(bird_ids), AviValuation.deleted_at.is_(None)))
        for bird_id, method, amount, valued_on in val_rows:
            by_bird.setdefault(bird_id, []).append(
                {"method": method, "amount": amount, "valued_on": valued_on.isoformat() if valued_on else ""})

    purchase = await _purchase_price_by_bird(db, farm_id) if bird_ids else {}
    bird_values = [
        valuation_engine.bird_value(by_bird.get(bid, []), purchase_amount=purchase.get(bid))
        for bid in bird_ids
    ]
    result = valuation_engine.collection_valuation(bird_values)

    # A top-down collection-level appraisal (bird_id IS NULL), if recorded, is the
    # authoritative total — it is a recorded fact, not a bottom-up estimate. The
    # per-bird coverage counts are kept for transparency.
    appraisal = (await db.execute(
        select(AviValuation).where(
            AviValuation.farm_id == farm_id, AviValuation.bird_id.is_(None),
            AviValuation.deleted_at.is_(None))
        .order_by(AviValuation.valued_on.desc(), AviValuation.created_at.desc()).limit(1))).scalar_one_or_none()
    if appraisal is not None:
        result["total_value"] = {
            "label": valuation_engine.RECORDED, "value": float(appraisal.amount),
            "detail": f"Recorded {appraisal.method} collection valuation ({appraisal.valued_on}).",
        }
    return result


async def finance_summary(db: AsyncSession, farm_id) -> dict:
    """Computed aviculture P&L view over recorded facts (no stored snapshot)."""
    sale_income = await _event_amount_sum(db, farm_id, "sold")
    purchase_costs = await _event_amount_sum(db, farm_id, "purchased")
    opex = (await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.farm_id == farm_id, Expense.deleted_at.is_(None),
            Expense.metadata_["module"].astext == "aviculture"))).scalar_one()
    coll = await collection_valuation(db, farm_id)
    return valuation_engine.finance_summary(
        sale_income=sale_income, purchase_costs=purchase_costs,
        operational_expenses=Decimal(str(opex or 0)), collection_value=coll)
