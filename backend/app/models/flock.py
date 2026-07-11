"""
Greena — Flock & Operations Models
Covers Migrations 012-016:
  012: flocks
  013: daily_logs
  014: production_records
  015: weighin_records
  016: feed_purchases

These are the core operational tables for Module 1: Poultry.
All records are farm-scoped (DB-04 Frozen).
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
    from app.models.farm import Farm, ProductionHouse


# ── Flock Status Enum ─────────────────────────────────────────────────────────

FLOCK_STATUS_VALUES = ("active", "sold", "closed", "culled")
FlockStatusEnum = Enum(
    *FLOCK_STATUS_VALUES,
    name="flock_status",
    create_constraint=True,
)


# ── Migration 012: Flocks ─────────────────────────────────────────────────────

class Flock(AGRIOSBase):
    """
    Central operational unit of Greena.

    Every daily log, weighin, production record, and feed purchase
    references a flock_id.

    Lifecycle: active → sold | closed | culled
    One active flock per production house at a time (application-layer enforced).
    Plan limit: max_active_flocks per subscription plan (-1 = unlimited).
    """

    __tablename__ = "flocks"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_houses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    species_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("species_profiles.species_key", ondelete="RESTRICT"),
        nullable=False,
        default="poultry",
        comment="Always 'poultry' in V1. FK to species_profiles extensibility engine.",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name, e.g. 'Batch 3 – Broiler May 2025'",
    )
    breed: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Bird breed, e.g. Ross 308, Cobb 500, ISA Brown",
    )
    source: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Where the birds came from — hatchery / supplier name",
    )
    batch_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Optional farmer-assigned batch reference",
    )
    initial_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of birds placed at start",
    )
    placement_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    expected_cycle_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=42,
        comment="42 for broilers, 350+ for layers",
    )
    expected_close_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="placement_date + expected_cycle_days. Computed at creation.",
    )
    status: Mapped[str] = mapped_column(
        FlockStatusEnum,
        nullable=False,
        default="active",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when the flock is archived (hidden from active lists).",
    )
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sale_price_per_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="KES per kg. Populated when status=sold.",
    )
    total_birds_sold: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Populated when status=sold.",
    )
    closing_weight_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
        comment="Average live weight at close (kg per bird).",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    farm: Mapped["Farm"] = relationship(
        foreign_keys=[farm_id],
        lazy="noload",
    )
    house: Mapped["ProductionHouse"] = relationship(
        foreign_keys=[house_id],
        lazy="noload",
    )
    daily_logs: Mapped[list["DailyLog"]] = relationship(
        back_populates="flock",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    production_records: Mapped[list["ProductionRecord"]] = relationship(
        back_populates="flock",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    weighin_records: Mapped[list["WeighinRecord"]] = relationship(
        back_populates="flock",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    feed_purchases: Mapped[list["FeedPurchase"]] = relationship(
        back_populates="flock",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_closed(self) -> bool:
        return self.status in ("sold", "closed", "culled")

    def __repr__(self) -> str:
        return f"<Flock '{self.name}' status={self.status} farm={self.farm_id}>"


# ── Migration 013: Daily Logs ─────────────────────────────────────────────────

class DailyLog(AGRIOSBase):
    """
    Primary data-entry record. One per flock per day.
    DB-06 Frozen: UNIQUE(flock_id, log_date) enables safe upsert pattern.
    Submitting is the DAL (Daily Active Logger) event.
    """

    __tablename__ = "daily_logs"
    __table_args__ = (
        UniqueConstraint(
            "flock_id",
            "log_date",
            name="uq_daily_logs_flock_date",
        ),
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
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    morning_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mortality_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    mortality_cause: Mapped[str | None] = mapped_column(String(100), nullable=True)
    feed_consumed_kg: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=Decimal("0")
    )
    water_litres: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    house_temp_am: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    house_temp_pm: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_corrected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    flock: Mapped["Flock"] = relationship(back_populates="daily_logs")

    def __repr__(self) -> str:
        return f"<DailyLog flock={self.flock_id} date={self.log_date}>"


# ── Migration 014: Production Records ────────────────────────────────────────

class ProductionRecord(AGRIOSBase):
    """
    Egg production record for layer flocks. One per flock per day.
    Broiler flocks do not use this table — validated at API layer.
    """

    __tablename__ = "production_records"
    __table_args__ = (
        UniqueConstraint(
            "flock_id",
            "record_date",
            name="uq_production_records_flock_date",
        ),
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
    record_date: Mapped[date] = mapped_column(Date, nullable=False)
    eggs_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broken_eggs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saleable_eggs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="eggs_collected - broken_eggs. Computed at insert.",
    )
    hen_day_production: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
        comment="eggs_collected / current flock count. App-computed.",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    flock: Mapped["Flock"] = relationship(back_populates="production_records")

    def __repr__(self) -> str:
        return f"<ProductionRecord flock={self.flock_id} date={self.record_date} eggs={self.eggs_collected}>"


# ── Migration 015: Weigh-In Records ──────────────────────────────────────────

class WeighinRecord(AGRIOSBase):
    """
    Live-weight sample from a subset of the flock.
    Multiple allowed per day (no date unique constraint).
    Used to compute FCR and track growth against breed targets.
    """

    __tablename__ = "weighin_records"

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
    weighed_at: Mapped[date] = mapped_column(Date, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    average_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    min_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    total_biomass_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True,
        comment="average_weight_kg * flock.current_count. App-computed.",
    )
    fcr_to_date: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3),
        nullable=True,
        comment="total_feed_consumed_kg / total_biomass_kg",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    flock: Mapped["Flock"] = relationship(back_populates="weighin_records")

    def __repr__(self) -> str:
        return (
            f"<WeighinRecord flock={self.flock_id} date={self.weighed_at} "
            f"avg={self.average_weight_kg}kg>"
        )


# ── Migration 016: Feed Purchases ─────────────────────────────────────────────

class FeedPurchase(AGRIOSBase):
    """
    Records a feed buying event.
    flock_id is optional — a purchase can be farm-wide stock not yet tied to a flock.
    total_cost is denormalised at insert to protect against future price changes.
    """

    __tablename__ = "feed_purchases"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("flocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    feed_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. Starter, Grower, Finisher, Layer Mash",
    )
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Denormalised: quantity_kg * price_per_kg at insert time.",
    )
    supplier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    flock: Mapped["Flock | None"] = relationship(back_populates="feed_purchases")

    def __repr__(self) -> str:
        return (
            f"<FeedPurchase farm={self.farm_id} type={self.feed_type} "
            f"qty={self.quantity_kg}kg KES{self.total_cost}>"
        )
