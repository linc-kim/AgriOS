"""
Greena — ARIA AI Platform Models (Module 9).
Migration 047.

  ai_response_cache — caches assistant answers (prompt hash → response) to cut
  cost and latency; records which provider served it (gemini / claude / offline).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.farm import Farm


class AIResponseCache(AGRIOSBase):
    """A cached AI answer keyed by (farm, prompt hash)."""

    __tablename__ = "ai_response_cache"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_context: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)

    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
