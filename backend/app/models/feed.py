"""
Greena — Feed Management Module Models (Phase 3, Module 4)
Migration 041.

Three tables form a small, event-sourced feed system:

  feed_suppliers        — a farm's directory of feed vendors.
  feed_inventory_items  — a running stock line per feed type + storage location,
                          carrying quantity on hand and a weighted-average cost
                          (the basis for stock valuation).
  feed_transactions     — an immutable ledger of every stock movement
                          (purchase, consumption, transfer, wastage, adjustment).
                          The inventory item's quantity/cost are derived from —
                          and kept in step with — this ledger by the service layer.

All three carry an ``ai_context`` JSONB column so ARIA / Gemini can consume feed
history, consumption and supplier performance without a schema change.

Everything is farm-scoped (DB-04 Frozen) and soft-deleted (DB-02 Frozen).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.farm import Farm
    from app.models.flock import Flock


# Feed transaction types — the ledger's verbs.
#   purchase       (+) buying feed into a store
#   consumption    (-) feeding a flock
#   transfer_out   (-) leaving one store/location
#   transfer_in    (+) arriving at another store/location
#   wastage        (-) spoilage, spillage, contamination, theft
#   adjustment     (±) stock-take correction (direction carries the sign)
FEED_TXN_TYPES = (
    "purchase",
    "consumption",
    "transfer_out",
    "transfer_in",
    "wastage",
    "adjustment",
)


class FeedSupplier(AGRIOSBase):
    """A feed vendor a farm buys from. Powers supplier management + spend history."""

    __tablename__ = "feed_suppliers"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    feed_types: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False,
        comment="Feed types this supplier provides, e.g. ['broiler_starter'].",
    )
    rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True, comment="0.00–5.00 quality/reliability rating."
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")

    def __repr__(self) -> str:
        return f"<FeedSupplier farm={self.farm_id} name={self.name!r}>"


class FeedInventoryItem(AGRIOSBase):
    """
    A stock line: how much of one feed type is held at one storage location, and
    what it is worth (weighted-average cost).

    quantity_kg and avg_cost_per_kg are maintained by the service layer from the
    feed_transactions ledger — never written to directly by clients.
    """

    __tablename__ = "feed_inventory_items"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feed_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. broiler_starter, broiler_finisher, layer_mash, grower.",
    )
    name: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="Optional display name / brand."
    )
    location: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="main_store",
        comment="Storage location / store name.",
    )
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="kg"
    )
    quantity_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    avg_cost_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    reorder_level_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True,
        comment="Reorder alert threshold. NULL = no alert configured.",
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feed_suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_context: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    supplier: Mapped["FeedSupplier | None"] = relationship(
        "FeedSupplier", foreign_keys=[supplier_id], lazy="noload"
    )

    @property
    def stock_value_kes(self) -> Decimal:
        """Current value of stock on hand (quantity × weighted-average cost)."""
        return (self.quantity_kg * self.avg_cost_per_kg).quantize(Decimal("0.01"))

    @property
    def is_low_stock(self) -> bool:
        """True when a reorder level is set and stock has fallen to/under it."""
        if self.reorder_level_kg is None:
            return False
        return self.quantity_kg <= self.reorder_level_kg

    def __repr__(self) -> str:
        return (
            f"<FeedInventoryItem farm={self.farm_id} type={self.feed_type} "
            f"loc={self.location} qty={self.quantity_kg}kg>"
        )


class FeedTransaction(AGRIOSBase):
    """
    One movement of feed stock. The append-only ledger behind every inventory
    quantity, valuation and analytic. ``direction`` (+1 in / -1 out) carries the
    sign so aggregate maths stays explicit; ``quantity_kg`` is always positive.
    """

    __tablename__ = "feed_transactions"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feed_inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="+1 stock in, -1 stock out."
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0",
        comment="Denormalised quantity_kg × unit_cost_per_kg at insert.",
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feed_suppliers.id", ondelete="SET NULL"),
        nullable=True,
    )
    counterparty_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feed_inventory_items.id", ondelete="SET NULL"),
        nullable=True,
        comment="For transfers: the paired item on the other side of the move.",
    )
    reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Wastage reason, transfer note, or adjustment justification.",
    )
    reference: Mapped[str | None] = mapped_column(
        String(150), nullable=True, comment="Invoice / batch / delivery reference."
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="Finance expense booked for a purchase (integration link).",
    )
    ai_context: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    item: Mapped["FeedInventoryItem"] = relationship(
        "FeedInventoryItem", foreign_keys=[item_id], lazy="noload"
    )
    flock: Mapped["Flock | None"] = relationship(
        "Flock", foreign_keys=[flock_id], lazy="noload"
    )

    @property
    def signed_quantity_kg(self) -> Decimal:
        return self.quantity_kg * self.direction

    def __repr__(self) -> str:
        return (
            f"<FeedTransaction farm={self.farm_id} type={self.txn_type} "
            f"qty={self.quantity_kg}kg dir={self.direction}>"
        )
