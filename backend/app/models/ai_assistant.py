"""
Greena — AI assistant models (Module 13 Part 8).

`AISettings` is a farm's AI configuration — the switches behind the AI Settings
screen (enable/disable, model, temperature, token limit, modality toggles,
optional monthly budget). One row per farm, created on first read.

`AIDocument` is an uploaded document whose text ARIA extracted deterministically
and kept so it can be retrieved and cited later.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    pass

#: Model options the AI Settings screen offers.
AI_MODELS = ("gemini-flash", "gemini-pro", "offline")


class AISettings(AGRIOSBase):
    __tablename__ = "ai_settings"
    __table_args__ = (UniqueConstraint("farm_id", name="uq_ai_settings_farm"),)

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    model: Mapped[str] = mapped_column(String(40), nullable=False, default="gemini-flash",
                                       server_default="gemini-flash")
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.30,
                                               server_default="0.30")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=512,
                                                   server_default="512")
    allow_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    allow_documents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    monthly_budget_usd: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AISettings farm={self.farm_id} model={self.model} enabled={self.ai_enabled}>"


class AIDocument(AGRIOSBase):
    __tablename__ = "ai_documents"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="generic", server_default="generic")
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    def __repr__(self) -> str:
        return f"<AIDocument {self.filename} farm={self.farm_id} kind={self.kind}>"
