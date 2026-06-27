"""
AGRIOS — Platform Models (Sprint 7)
Covers: Notification, AuditLog, MarketPrice

Design notes:
  - Notification inherits AGRIOSBase (soft-delete supported)
  - AuditLog inherits Base directly (append-only, DB-08 Frozen)
  - MarketPrice inherits Base directly (historical, DB-09 Frozen)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import AGRIOSBase


# ── Notification ──────────────────────────────────────────────────────────────

class Notification(AGRIOSBase):
    """
    In-app notification for a specific user on a specific farm.
    Soft-deletable (AGRIOSBase).

    notification_type values:
      vaccination_reminder | vaccination_overdue | daily_log_reminder
      disease_alert | weekly_summary | aria_insight | system | farm_invite
    """

    __tablename__ = "notifications"

    # Recipient
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_route: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Read state
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Origin
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────
    farm: Mapped["Farm"] = relationship("Farm", lazy="joined", foreign_keys=[farm_id])  # type: ignore[name-defined]
    user: Mapped["User"] = relationship("User", lazy="joined", foreign_keys=[user_id])  # type: ignore[name-defined]

    # ── Methods ───────────────────────────────────────────────────────────

    def mark_read(self) -> None:
        """Mark this notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = func.now()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# ── AuditLog ──────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Immutable platform audit log.
    DB-08 (Frozen): append-only. No UPDATE, no DELETE, no soft delete.
    Does NOT inherit AGRIOSBase by design.

    action format: "resource_type.verb" e.g. "flock.create", "expense.delete"
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Context — nullable because platform-level events may have no farm/user
    farm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Event description
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Before/after snapshots (JSONB)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Immutable timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Enforce immutability at model layer
    @property
    def is_deleted(self) -> bool:
        return False  # Audit logs are never deleted


# ── MarketPrice ───────────────────────────────────────────────────────────────

class MarketPrice(Base):
    """
    Admin-curated market price data.
    DB-09 (Frozen): historical — new rows only, existing rows are NEVER updated.
    Does NOT inherit AGRIOSBase by design.

    Platform-wide (no farm_id — documented exception to DB-04).
    Correction = new row with updated price and same commodity/date.

    commodity values (not an ENUM — extensible by admin):
      broiler_live | layer_egg_tray | day_old_chick_broiler | day_old_chick_layer
      feed_growers_50kg | feed_layers_50kg | feed_broilers_50kg | maize_90kg
    """

    __tablename__ = "market_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    commodity: Mapped[str] = mapped_column(String(100), nullable=False)
    price_kes: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    county: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    valid_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    recorded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Immutable timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @property
    def is_deleted(self) -> bool:
        return False  # Market prices are immutable historical records
