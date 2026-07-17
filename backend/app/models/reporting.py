"""
Greena — Reporting & Business Intelligence Models (Module 7).
Migration 045.

  saved_reports — a user's saved / pinned report configurations.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.farm import Farm


class SavedReport(AGRIOSBase):
    """A saved report configuration (type + period), optionally pinned."""

    __tablename__ = "saved_reports"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
