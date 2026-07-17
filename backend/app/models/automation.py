"""
Greena — Automation & Notifications Module Models (Module 8).
Migration 046.

  automation_rules — if/then rules: a trigger + conditions + one or more actions.
  reminders        — one-time and recurring reminders (calendar-ready).

Notifications themselves reuse the existing Notification model (extended in
Module 8 with priority + archive state).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.farm import Farm

# Built-in trigger types the automation engine evaluates.
TRIGGER_TYPES = (
    "low_feed", "low_inventory", "vaccination_due", "health_alert",
    "mortality_spike", "maintenance_due", "financial_anomaly", "tasks_overdue",
)


class AutomationRule(AGRIOSBase):
    """An if/then automation rule bound to a trigger."""

    __tablename__ = "automation_rules"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # conditions: {"threshold": <n>, "severity": "critical", ...} — trigger-specific.
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    # actions: list of {"type": "notify"|"create_reminder", ...}.
    actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")


class Reminder(AGRIOSBase):
    """A one-time or recurring reminder that fires an in-app notification."""

    __tablename__ = "reminders"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # none | daily | weekly | monthly
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, server_default="none")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")

    @property
    def is_overdue(self) -> bool:
        if self.is_done:
            return False
        from datetime import datetime as dt, timezone
        return self.due_at < dt.now(tz=timezone.utc)
