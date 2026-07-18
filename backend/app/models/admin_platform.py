"""
Greena — Admin Platform Models (Module 10).
Migration 048.

  feature_flags   — per-module toggles, global or organization-scoped.
  system_config   — a single global platform configuration row (maintenance
                    mode, AI provider priority, senders, currency, limits…).
  background_jobs — a history of background job executions for the ops dashboard.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AGRIOSBase

FLAG_MODULES = (
    "aria", "automation", "feed", "finance", "health", "inventory", "notifications", "reporting",
)


class FeatureFlag(AGRIOSBase):
    """A module toggle. organization_id NULL = global default; set = org override."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("flag_key", "organization_id", name="uq_feature_flag_key_org"),
    )

    flag_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class SystemConfig(AGRIOSBase):
    """Single-row global platform configuration."""

    __tablename__ = "system_config"

    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    read_only_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    banner_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenance_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_provider_priority: Mapped[list] = mapped_column(
        JSONB, default=lambda: ["gemini", "claude", "offline"],
        server_default='["gemini", "claude", "offline"]', nullable=False,
    )
    email_sender: Mapped[str] = mapped_column(String(200), nullable=False, server_default="noreply@greena.app")
    sms_sender: Mapped[str] = mapped_column(String(50), nullable=False, server_default="GREENA")
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="KES")
    default_timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Africa/Nairobi")
    data_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3650")
    limits: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BackgroundJob(AGRIOSBase):
    """A record of a background job execution (ops dashboard)."""

    __tablename__ = "background_jobs"

    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued", index=True)  # queued|running|success|failed
    queue: Mapped[str] = mapped_column(String(60), nullable=False, server_default="default")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
