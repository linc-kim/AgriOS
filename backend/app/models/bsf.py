"""
Greena — Black Soldier Fly (BSF) Models (Module 16, Part 1: Foundation)

Batch-centric management for Black Soldier Fly (*Hermetia illucens*) production
(Spec Part 1). Unlike Poultry (flocks) or Aviculture (individual birds), the
aggregate root here is the **Production Batch** (Spec Part 3 §2): every
operational record ultimately relates to one or more batches.

Design rules honoured here (mirroring the Aviculture module):
  * Everything inherits :class:`AGRIOSBase` → soft-delete only, JSONB metadata,
    audit timestamps. Lineage (split/merge), lifecycle history and production
    records are never destroyed (Spec Part 3 §8-10, §21).
  * Species/strain reference is a **data-driven catalog row** (:class:`BsfSpecies`),
    never hardcoded (Spec Part 3 §5). The module registers itself in the existing
    ``species_profiles`` extensibility engine as ``species_key='bsf'``.
  * Farm-scoped records carry ``farm_id``; organisation isolation flows through
    ``farms.organization_id`` — the same convention as Flock / Aviculture /
    Mission Control. Catalog rows carry a nullable ``organization_id``
    (NULL = global system catalog shared by every organisation).
  * Enumerated fields are plain strings validated at the schema/service layer,
    with allowed values published as the ``*_VALUES`` tuples below (matching the
    Module 14/15 convention). No business calculations live in models — those
    belong to the deterministic engines (Spec Part 4).

Tables map 1:1 to Migration 061.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase


# ── Allowed enumerated values (validated at the schema/service layer) ─────────

# Species / strain reference (Spec Part 3 §5)
BSF_PRODUCTION_TYPE_VALUES = ("larvae", "frass", "breeding", "mixed")

# Production Unit — the smallest operational entity (Spec Part 2 §4, Part 3 §6)
UNIT_TYPE_VALUES = (
    "bin", "tray", "rack", "cage", "chamber", "container", "shelf",
    "incubator", "drying_unit", "nursery", "love_cage", "other",
)
UNIT_STATUS_VALUES = (
    "available", "in_use", "cleaning", "maintenance", "out_of_service",
)

# Adult breeding colony (Spec Part 2 §7)
COLONY_STATUS_VALUES = ("active", "declining", "rotating", "retired")
COLONY_SOURCE_VALUES = ("bred", "purchased", "donated", "transferred", "wild", "unknown")

# Production Batch — the aggregate root (Spec Part 3 §7)
BATCH_TYPE_VALUES = ("production", "breeding", "egg", "nursery", "mixed")
BATCH_STATUS_VALUES = (
    "active", "harvested", "completed", "split", "merged", "terminated", "archived",
)

# Lifecycle stages (Spec Part 2 §6, Part 4 §5). Ordered egg → adult.
LIFECYCLE_STAGE_VALUES = (
    "egg", "hatchling", "feeding_larvae", "mature_larvae",
    "prepupae", "pupae", "adult", "unknown",
)

# Immutable lifecycle-transition source (Spec Part 3 §8)
LIFECYCLE_TRANSITION_SOURCE_VALUES = ("manual", "automated", "correction")

# Batch timeline event types (Spec Part 3 §19; append-only history)
BATCH_EVENT_TYPE_VALUES = (
    "created", "stage_changed", "moved", "split", "merged",
    "population_adjusted", "biomass_recorded", "status_changed",
    "media_added", "document_added", "terminated", "note",
)

MEDIA_TYPE_VALUES = ("photo", "video", "audio")
DOCUMENT_TYPE_VALUES = (
    "lab_report", "environmental_report", "invoice", "receipt",
    "certificate", "inspection_report", "permit", "other",
)


# ── Catalog: BSF species / strain (Spec Part 3 §5) ────────────────────────────

class BsfSpecies(AGRIOSBase):
    """Data-driven biological reference for a BSF species or production strain.

    Reference data only — operational records never overwrite these biological
    values (Spec Part 3 §5). ``profile`` (JSONB) holds the rich, extensible
    husbandry knowledge: lifecycle parameters, recommended environmental ranges,
    feeding guidelines, expected development times, target moisture and expected
    conversion ratios.
    """

    __tablename__ = "bsf_species"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    common_name: Mapped[str] = mapped_column(String(150), nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    strain: Mapped[str | None] = mapped_column(String(150), nullable=True)
    production_type: Mapped[str] = mapped_column(String(30), nullable=False, default="larvae")
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BsfSpecies {self.common_name!r} strain={self.strain!r}>"


# ── Housing: Production Unit (Spec Part 2 §4, Part 3 §6) ───────────────────────

class BsfProductionUnit(AGRIOSBase):
    """The smallest operational entity — the physical location a batch occupies
    (bin, tray, rack, incubator, drying unit…). Occupancy is derived from
    :class:`BsfBatch.production_unit_id` and never stored here (Spec Part 3 §20)."""

    __tablename__ = "bsf_production_unit"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_bsf_unit_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_type: Mapped[str] = mapped_column(String(30), nullable=False, default="bin")
    facility: Mapped[str | None] = mapped_column(String(200), nullable=True)
    production_area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    capacity_grams: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="available")
    environment_profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    maintenance_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<BsfProductionUnit {self.name!r} type={self.unit_type} status={self.status}>"


# ── Breeding: Adult Colony (Spec Part 2 §7) ───────────────────────────────────

class BsfColony(AGRIOSBase):
    """An adult breeding colony (population of egg-laying flies). Foundation table;
    the Breeding engine (later Part) evaluates egg production / fertility / hatch
    success. Retirement is a soft status change — history is permanent."""

    __tablename__ = "bsf_colony"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_bsf_colony_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_species.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    production_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_production_unit.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    established_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    population_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    retired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    species: Mapped["BsfSpecies | None"] = relationship(foreign_keys=[species_id], lazy="noload")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<BsfColony {self.name!r} status={self.status}>"


# ── Aggregate root: Production Batch (Spec Part 3 §7) ──────────────────────────

class BsfBatch(AGRIOSBase):
    """The Production Batch — aggregate root of the BSF module (Spec Part 3 §2, §7).

    Lineage is stored as deterministic links: ``parent_batch_id`` (split/merge
    source) and ``source_colony_id`` (originating breeding colony). Unknown
    origin stays NULL and is never invented. Population/biomass carried here are
    the *current* estimates; historical values live in immutable
    :class:`BsfLifecycleEvent` snapshots (Spec Part 3 §8, §20).
    """

    __tablename__ = "bsf_batch"
    __table_args__ = (
        UniqueConstraint("farm_id", "batch_number", name="uq_bsf_batch_farm_number"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_species.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    source_colony_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_colony.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    parent_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    production_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_production_unit.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Identity (Spec Part 2 §5)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    batch_type: Mapped[str] = mapped_column(String(20), nullable=False, default="production")

    # Lifecycle & state (Spec Part 2 §6)
    lifecycle_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="egg")
    stage_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Current estimates (recorded facts; supports millions of insects — Spec Part 9 §3)
    population_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    biomass_estimate_g: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships (all lazy=noload; services opt in explicitly)
    species: Mapped["BsfSpecies | None"] = relationship(foreign_keys=[species_id], lazy="noload")
    source_colony: Mapped["BsfColony | None"] = relationship(foreign_keys=[source_colony_id], lazy="noload")
    production_unit: Mapped["BsfProductionUnit | None"] = relationship(
        foreign_keys=[production_unit_id], lazy="noload"
    )
    parent_batch: Mapped["BsfBatch | None"] = relationship(
        foreign_keys=[parent_batch_id], remote_side="BsfBatch.id", lazy="noload"
    )
    lifecycle_events: Mapped[list["BsfLifecycleEvent"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="noload"
    )
    events: Mapped[list["BsfBatchEvent"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="noload",
        foreign_keys="BsfBatchEvent.batch_id",
    )
    media: Mapped[list["BsfBatchMedia"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["BsfBatchDocument"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_live(self) -> bool:
        """True while the batch is an active, in-production batch."""
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<BsfBatch {self.batch_number} stage={self.lifecycle_stage} status={self.status}>"


# ── Immutable history: Lifecycle transitions (Spec Part 3 §8) ──────────────────

class BsfLifecycleEvent(AGRIOSBase):
    """An immutable lifecycle-transition snapshot. Records the stage change and
    the population/biomass estimate at that moment (Spec Part 3 §8). History is
    never edited — corrections are appended as new rows."""

    __tablename__ = "bsf_lifecycle_event"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    previous_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_stage: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    population_estimate: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    biomass_estimate_g: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    survival_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped["BsfBatch"] = relationship(back_populates="lifecycle_events", lazy="noload")

    def __repr__(self) -> str:
        return f"<BsfLifecycleEvent batch={self.batch_id} {self.previous_stage}->{self.new_stage}>"


# ── Immutable history: Batch timeline (Spec Part 3 §19, Part 8 §14) ────────────

class BsfBatchEvent(AGRIOSBase):
    """Append-only operational timeline for a batch (created, moved, split,
    merged, note…). Complements platform Timeline/Audit; carries BSF-specific
    payload in ``details`` (JSONB)."""

    __tablename__ = "bsf_batch_event"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    related_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped["BsfBatch"] = relationship(
        foreign_keys=[batch_id], back_populates="events", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<BsfBatchEvent batch={self.batch_id} type={self.event_type}>"


# ── Attachments (Spec Part 3 §18; reuse Greena file platform) ──────────────────

class BsfBatchMedia(AGRIOSBase):
    """Photos / videos / audio for a batch. Binary lives in the platform file
    store; this row references it (storage_path/url), mirroring avi_bird_media."""

    __tablename__ = "bsf_batch_media"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="photo")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    captured_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped["BsfBatch"] = relationship(back_populates="media", lazy="noload")


class BsfBatchDocument(AGRIOSBase):
    """Lab reports, invoices, certificates and other documents attached to a batch."""

    __tablename__ = "bsf_batch_document"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bsf_batch.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    batch: Mapped["BsfBatch"] = relationship(back_populates="documents", lazy="noload")
