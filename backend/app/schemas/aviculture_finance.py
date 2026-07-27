"""
Greena — Aviculture Finance Schemas (Module 15, Part 7)

Contracts for collection valuations and the computed aviculture finance summary.
Operational costs reuse the shared Finance/Inventory modules; only collection
valuation (a recorded aviculture fact) and the computed P&L view live here.
Derived figures are honesty-labelled by the pure valuation engine.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models import aviculture as avi
from app.schemas.aviculture import _one_of
from app.schemas.base import AGRIOSSchema, TimestampedSchema


class ValuationCreate(AGRIOSSchema):
    bird_id: UUID | None = None
    amount: Decimal = Field(..., ge=0)
    currency: str = Field("KES", max_length=8)
    method: str = Field("appraised")
    valued_on: date | None = None
    source: str | None = Field(None, max_length=200)
    notes: str | None = None

    _m = field_validator("method")(_one_of("method", avi.VALUATION_METHOD_VALUES))


class ValuationResponse(TimestampedSchema):
    farm_id: UUID
    bird_id: UUID | None
    valued_on: date
    amount: Decimal
    currency: str
    method: str
    source: str | None
    notes: str | None


class PurchaseExpenseCreate(AGRIOSSchema):
    """Post a bird-purchase (or aviculture operational) cost to the shared finance
    ledger. Reuses ``finance_service`` — no aviculture expense table."""

    bird_id: UUID | None = None
    amount: Decimal = Field(..., gt=0)
    category_slug: str = Field("other", max_length=100)
    description: str = Field(..., min_length=1, max_length=300)
    expense_date: date | None = None


class CollectionValuationResponse(AGRIOSSchema):
    total_value: dict
    birds_valued: dict
    birds_unvalued: dict
    by_basis: dict


class FinanceSummaryResponse(AGRIOSSchema):
    sale_income: dict
    purchase_costs: dict
    operational_expenses: dict
    net: dict
    collection_value: dict | None
