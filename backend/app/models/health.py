"""
Greena — Health Module Models
Covers Migrations 017-018:
  017: vaccination_records
  018: disease_alerts

These are the core health tables for Module 1: Poultry.
VaccinationRecord is farm-scoped (DB-04 Frozen).
DiseaseAlert is platform-wide (no farm_id — county-targeted by admin).
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.farm import Farm
    from app.models.flock import Flock


# ── Alert Enums ───────────────────────────────────────────────────────────────

AlertStatusEnum = Enum(
    "draft", "active", "deactivated",
    name="alert_status",
    create_constraint=True,
)

AlertSeverityEnum = Enum(
    "info", "warning", "critical",
    name="alert_severity",
    create_constraint=True,
)


# ── Migration 017: VaccinationRecord ─────────────────────────────────────────

class VaccinationRecord(AGRIOSBase):
    """
    Records a vaccination event administered to a flock.

    next_due_date drives ARIA proactive health alerts:
      - "Vaccination due soon" when next_due_date is within 3 days
      - "Vaccination overdue" when next_due_date has passed

    Permissions:
      - HEALTH_VACCINATION_LOG: farm_owner, farm_manager, vet_consultant
      - HEALTH_VACCINATION_VIEW: all roles (read-only for worker + viewer)
    """

    __tablename__ = "vaccination_records"

    # ── Core identifiers ──────────────────────────────────────────────────────
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
    species_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("species_profiles.species_key", ondelete="RESTRICT"),
        nullable=False,
        server_default="poultry",
    )

    # ── Vaccine details ───────────────────────────────────────────────────────
    vaccine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    vaccine_brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dose_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # ── Administration details ────────────────────────────────────────────────
    administered_date: Mapped[date] = mapped_column(Date, nullable=False)
    administered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    flock_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Next dose planning ────────────────────────────────────────────────────
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    next_vaccine_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Audit fields ──────────────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # created_at / updated_at inherited from AGRIOSBase (with proper defaults).
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    farm: Mapped["Farm"] = relationship("Farm", foreign_keys=[farm_id], lazy="noload")
    flock: Mapped["Flock"] = relationship("Flock", foreign_keys=[flock_id], lazy="noload")
    administrator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[administered_by], lazy="noload"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="noload"
    )

    @property
    def is_overdue(self) -> bool:
        """True if next_due_date is set and has passed today."""
        if self.next_due_date is None:
            return False
        from datetime import date as dt_date
        return self.next_due_date < dt_date.today()

    @property
    def is_due_soon(self) -> bool:
        """True if next_due_date is within 3 days from today."""
        if self.next_due_date is None:
            return False
        from datetime import date as dt_date
        from datetime import timedelta
        today = dt_date.today()
        return today <= self.next_due_date <= today + timedelta(days=3)


# ── Migration 018: DiseaseAlert ───────────────────────────────────────────────

class DiseaseAlert(AGRIOSBase):
    """
    Platform-wide disease alert published by super_admin.

    Unlike all other operational tables, DiseaseAlert has NO farm_id.
    It is county + species targeted — shown to any farm in that county
    whose species matches.

    Workflow: draft → active (published) → deactivated

    Permissions:
      - ADMIN_ALERT_PUBLISH: super_admin only (publish/deactivate)
      - HEALTH_ALERT_VIEW: all roles (read-only for everyone)
    """

    __tablename__ = "disease_alerts"

    # ── Core identifiers ──────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Targeting (platform-wide — no farm_id) ────────────────────────────────
    county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="NULL = national alert (all counties)",
    )
    species_key: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="NULL = all species",
    )

    # ── Alert content ─────────────────────────────────────────────────────────
    disease_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    brief_guidance: Mapped[str | None] = mapped_column(String(500), nullable=True)
    severity: Mapped[str] = mapped_column(
        AlertSeverityEnum, nullable=False, server_default="warning"
    )
    status: Mapped[str] = mapped_column(
        AlertStatusEnum, nullable=False, server_default="draft"
    )

    # ── Lifecycle timestamps ───────────────────────────────────────────────────
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Admin audit ───────────────────────────────────────────────────────────
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    sms_dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sms_recipient_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Standard audit fields ──────────────────────────────────────────────────
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # created_at / updated_at inherited from AGRIOSBase (with proper defaults).
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
  
)

    # ── Relationships ─────────────────────────────────────────────────────────
    publisher: Mapped["User | None"] = relationship(
        "User", foreign_keys=[published_by], lazy="noload"
    )
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="noload"
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        from datetime import datetime as dt, timezone
        return self.expires_at < dt.now(tz=timezone.utc)


class HealthEvent(AGRIOSBase):
    """
    A flock-scoped health record. One flexible model captures the full health
    workflow — observations, symptoms, diagnoses, treatments, medication,
    mortality investigations, quarantine, vet visits, recovery and follow-ups.

    ``symptoms`` / ``observations`` / ``attachments`` are structured JSONB so
    ARIA can analyse them later without a schema change.
    """

    __tablename__ = "health_events"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flock_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    symptoms: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    observations: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    attachments: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)

    diagnosis: Mapped[str | None] = mapped_column(String(500), nullable=True)
    treatment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    medication_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info", server_default="info")
    affected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vet_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    cost_kes: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
