"""
AGRIOS — Finance Module Models
Covers Migrations 019-022:
  019: expense_categories  (with 17 seeded system categories)
  020: expenses
  021: revenue_records
  022: financial_snapshots (pre-computed P&L — DB-07 Frozen)

All finance tables are farm-scoped (DB-04 Frozen).
revenue_records and financial_snapshots are also flock-scoped.
financial_snapshots are NEVER computed in real-time — always read from the
pre-computed snapshot row that the service maintains.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.farm import Farm
    from app.models.flock import Flock


# ── Revenue Type Enum ─────────────────────────────────────────────────────────

RevenueTypeEnum = Enum(
    "eggs",
    "birds",
    "manure",
    "other",
    name="revenue_type",
    create_constraint=True,
)


# ── Migration 019: ExpenseCategory ────────────────────────────────────────────

class ExpenseCategory(AGRIOSBase):
    """
    Expense category — shared system categories (farm_id=NULL) plus
    optional custom per-farm categories.

    is_system rows are seeded at migration time and cannot be deleted via API.
    Custom categories have farm_id set and is_system=False.

    RBAC: any farm member can read categories.
          farm_owner/manager can create custom categories.
          super_admin manages system categories.
    """

    __tablename__ = "expense_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # NULL = system category; UUID = custom farm category
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    icon: Mapped[str | None] = mapped_column(String(10), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # hex
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Soft delete (system rows: deleted_at is never set by API)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Standard timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Relationships
    farm: Mapped["Farm | None"] = relationship(
        "Farm", foreign_keys=[farm_id], lazy="noload"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="category", lazy="noload"
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# ── Migration 020: Expense ────────────────────────────────────────────────────

class Expense(AGRIOSBase):
    """
    Records a farm expense. Farm-scoped. Optionally flock-scoped for P&L.

    amount is in KES (V1 currency is KES — locked).
    payment_method: cash | mpesa | bank_transfer | credit

    The finance_service.recompute_snapshot() must be called after any
    create/update/delete to keep the financial_snapshot current.

    RBAC:
      FINANCE_RECORD: farm_owner, farm_manager
      FINANCE_VIEW: all roles
    """

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional — links expense to a specific flock for per-flock P&L
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Core fields
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2), nullable=False
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)

    # Optional enrichment
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=3), nullable=True
    )
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Relationships
    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    flock: Mapped["Flock | None"] = relationship(
        "Flock", foreign_keys=[flock_id], lazy="noload"
    )
    category: Mapped["ExpenseCategory"] = relationship(
        "ExpenseCategory", back_populates="expenses", lazy="joined"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="noload"
    )


# ── Migration 021: RevenueRecord ──────────────────────────────────────────────

class RevenueRecord(AGRIOSBase):
    """
    Records a revenue event for a farm + flock combination.

    revenue_type: eggs | birds | manure | other

    For birds: birds_sold and avg_weight_kg are populated.
    For eggs: eggs_count and trays_count are populated.
    amount is always stored explicitly (total in KES).
    unit_price * quantity = amount is a guideline — amount overrides.

    RBAC same as Expense.
    """

    __tablename__ = "revenue_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    revenue_type: Mapped[str] = mapped_column(
        RevenueTypeEnum, nullable=False
    )

    # Core financials
    revenue_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2), nullable=False
    )
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=3), nullable=True
    )
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )

    # Bird sale fields
    birds_sold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=6, scale=3), nullable=True
    )

    # Egg sale fields
    eggs_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trays_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Buyer info
    buyer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buyer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Relationships
    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    flock: Mapped["Flock"] = relationship(
        "Flock", foreign_keys=[flock_id], lazy="noload"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="noload"
    )


# ── Migration 022: FinancialSnapshot ─────────────────────────────────────────

class FinancialSnapshot(AGRIOSBase):
    """
    Pre-computed P&L snapshot for a flock (DB-07 Frozen).

    ONE row per flock. Updated in-place by finance_service.recompute_snapshot()
    whenever expenses or revenue are mutated, and on flock close.

    NEVER compute P&L in real-time from aggregate queries — always read from
    this table. This is a hard architectural constraint (DB-07 Frozen).

    The snapshot_at timestamp tells callers how fresh the data is.
    """

    __tablename__ = "financial_snapshots"

    __table_args__ = (
        UniqueConstraint("flock_id", name="uq_financial_snapshots_flock_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Revenue breakdown
    total_revenue_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    revenue_eggs_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    revenue_birds_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    revenue_manure_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    revenue_other_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )

    # Expense breakdown
    total_expenses_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    feed_cost_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    doc_cost_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    vet_health_cost_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    labour_cost_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    other_cost_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )

    # P&L
    gross_profit_kes: Mapped[Decimal] = mapped_column(
        Numeric(precision=16, scale=2), nullable=False, default=Decimal("0")
    )
    gross_margin_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=7, scale=4), nullable=True
    )
    is_profitable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Per-bird metrics
    cost_per_bird_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )
    revenue_per_bird_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )
    break_even_price_kes: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True
    )

    # FCR
    total_feed_kg: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=3), nullable=False, default=Decimal("0")
    )
    fcr_computed: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=6, scale=3), nullable=True
    )

    # Flock state at snapshot time
    bird_count_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birds_sold_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feed_cost_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=7, scale=4), nullable=True
    )

    # Standard timestamps (no soft delete on snapshots — they are always current)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )

    # Relationships
    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    flock: Mapped["Flock"] = relationship(
        "Flock", foreign_keys=[flock_id], lazy="noload"
    )

    @property
    def is_deleted(self) -> bool:
        """Snapshots are never deleted — satisfy AGRIOSBase interface."""
        return False
