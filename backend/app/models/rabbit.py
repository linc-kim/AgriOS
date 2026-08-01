"""
Greena — Rabbit Management Models (Module 17, Part 1: Foundation)

Individual-rabbit management for meat, breeding, fiber, pet and show operations
(Spec Part 1). Like Aviculture (Module 15), the aggregate root is the
**individual rabbit** (:class:`Rabbit`, Spec Part 3 §4); every other entity
ultimately references a rabbit, a litter or a housing location.

Design rules honoured here (mirroring the Aviculture / BSF modules):
  * Everything inherits :class:`AGRIOSBase` → soft-delete only, JSONB metadata,
    audit timestamps. Pedigree, movement, medical and ownership history are never
    destroyed (Spec Part 2 §2, Part 3 §21).
  * Breed reference is a **data-driven catalog row** (:class:`RabbitBreed`),
    never hardcoded (Spec Part 3 §5). The module registers itself in the existing
    ``species_profiles`` extensibility engine as ``species_key='rabbit'``.
  * Farm-scoped records carry ``farm_id``; organisation isolation flows through
    ``farms.organization_id`` — the same convention as Flock / Aviculture / BSF /
    Mission Control. The breed catalog carries a nullable ``organization_id``
    (NULL = global system catalog shared by every organisation).
  * Housing follows the 5-level hierarchy (Spec Part 1 §6): Rabbitry → Building →
    Room → Row → Cage → Rabbit. Cage occupancy is DERIVED from ``rabbit.cage_id``
    and never stored (the Housing Capacity engine, a later Part, computes it).
  * Enumerated fields are plain strings validated at the schema/service layer,
    with allowed values published as the ``*_VALUES`` tuples below. No business
    calculations live in models — those belong to the deterministic engines
    (Spec Part 4).

Tables map 1:1 to Migration 066.
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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase


# ── Allowed enumerated values (validated at the schema/service layer) ─────────

# Breed catalog (Spec Part 3 §5, Part 1 §4)
BREED_CATEGORY_VALUES = (
    "commercial_meat", "fiber", "pet", "dual_purpose", "heritage",
    "show", "laboratory", "other",
)
BREED_PURPOSE_VALUES = ("meat", "breeding", "fiber", "pet", "show", "mixed")

# Housing hierarchy (Spec Part 1 §6, Part 3 §14)
HOUSING_STATUS_VALUES = ("active", "inactive", "maintenance")
CAGE_TYPE_VALUES = (
    "cage", "colony_pen", "hutch", "grow_out", "quarantine", "isolation", "nest", "other",
)
CAGE_STATUS_VALUES = (
    "available", "occupied", "maintenance", "cleaning", "out_of_service",
)

# Rabbit identity / classification (Spec Part 3 §4)
RABBIT_SEX_VALUES = ("buck", "doe", "unknown")
RABBIT_PURPOSE_VALUES = (
    "meat", "breeding", "fiber", "pet", "show", "replacement",
    "genetic_improvement", "educational", "mixed", "unknown",
)

# Lifecycle & reproduction (Spec Part 1 §8, Part 3 §4)
RABBIT_LIFECYCLE_STAGE_VALUES = (
    "kit", "weaner", "grower", "breeding_candidate", "breeding_adult", "retired", "unknown",
)
RABBIT_STATUS_VALUES = ("active", "sold", "transferred", "deceased", "archived")
# Statuses that count as "no longer in the active herd" (Spec Part 2 §2).
RABBIT_TERMINAL_STATUSES = ("sold", "transferred", "deceased")
REPRODUCTIVE_STATUS_VALUES = (
    "not_bred", "bred", "pregnant", "lactating", "open", "resting",
    "proven", "unproven", "unknown",
)
FERTILITY_STATUS_VALUES = ("fertile", "infertile", "unproven", "unknown")
RABBIT_ACQUISITION_TYPE_VALUES = ("bred", "purchased", "donated", "transferred", "unknown")

# Rabbit timeline event types (Spec Part 8 §14). Append-only history.
RABBIT_EVENT_TYPE_VALUES = (
    "created", "updated", "status_changed", "archived", "restored", "moved",
    "transferred", "sold", "purchased", "died", "bred", "kindled", "weaned",
    "weight_recorded", "health_recorded", "vaccination_recorded",
    "media_added", "document_added", "note",
)

MEDIA_TYPE_VALUES = ("photo", "video", "audio")
DOCUMENT_TYPE_VALUES = (
    "pedigree_certificate", "health_certificate", "registration", "lab_report",
    "vet_report", "purchase_record", "sale_document", "invoice", "other",
)

# Breeding cycle (Spec Part 3 §7, Part 4 §6)
BREEDING_METHOD_VALUES = ("natural", "artificial")
BREEDING_STATUS_VALUES = (
    "planned", "serviced", "pregnant", "not_pregnant", "kindled", "failed", "closed", "cancelled",
)
PREGNANCY_RESULT_VALUES = ("unknown", "pregnant", "not_pregnant")
BREEDING_OUTCOME_VALUES = ("successful", "failed", "aborted", "reabsorbed", "unknown")

# Litter (Spec Part 3 §8)
LITTER_STATUS_VALUES = ("active", "weaned", "closed")

# Default rabbit gestation in days (ledger CON-M3-4); overridable per breed via
# ``rabbit_breed.profile["gestation_days"]``.
DEFAULT_GESTATION_DAYS = 31


# ── Catalog: Breed (Spec Part 3 §5) ───────────────────────────────────────────

class RabbitBreed(AGRIOSBase):
    """Data-driven breed catalog (Spec Part 3 §5, Part 1 §4).

    Reference data only — operational records never overwrite breed values.
    ``organization_id IS NULL`` marks a global/system entry shared by every
    organisation; a non-null value is an organisation's custom breed. ``profile``
    (JSONB) holds the rich, extensible reference: adult weight range, typical
    litter size, growth characteristics, temperament and notes.
    """

    __tablename__ = "rabbit_breed"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    origin: Mapped[str | None] = mapped_column(String(150), nullable=True)
    production_purpose: Mapped[str | None] = mapped_column(String(30), nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitBreed {self.name!r} category={self.category}>"


# ── Catalog: Bloodline / genetic line (Spec Part 3 §3, §6) ────────────────────

class RabbitBloodline(AGRIOSBase):
    """A named genetic line / bloodline within a farm (Spec Part 3 §3, §6).

    Bloodlines group rabbits for genetic tracking and performance-based
    selection; the Genetics engine (a later Part) evaluates line performance.
    Farm-scoped: a bloodline belongs to one farm's breeding programme.
    """

    __tablename__ = "rabbit_bloodline"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_bloodline_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_breed.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitBloodline {self.name!r}>"


# ── Housing hierarchy (Spec Part 1 §6, Part 3 §14) ────────────────────────────
# Rabbitry → Building → Room → Row → Cage → Rabbit. Each level carries farm_id
# directly for efficient farm-scoped queries, plus a parent FK for the hierarchy.

class RabbitRabbitry(AGRIOSBase):
    """Top-level housing container — a rabbitry (Spec Part 1 §6)."""

    __tablename__ = "rabbit_rabbitry"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_rabbitry_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitRabbitry {self.name!r} farm={self.farm_id}>"


class RabbitBuilding(AGRIOSBase):
    """A building within a rabbitry (Spec Part 1 §6)."""

    __tablename__ = "rabbit_building"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_building_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    rabbitry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_rabbitry.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitBuilding {self.name!r} rabbitry={self.rabbitry_id}>"


class RabbitRoom(AGRIOSBase):
    """A room within a building (Spec Part 1 §6)."""

    __tablename__ = "rabbit_room"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_room_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_building.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitRoom {self.name!r} building={self.building_id}>"


class RabbitRow(AGRIOSBase):
    """A row within a room (Spec Part 1 §6)."""

    __tablename__ = "rabbit_row"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_row_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_room.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitRow {self.name!r} room={self.room_id}>"


class RabbitCage(AGRIOSBase):
    """The smallest housing unit a rabbit occupies (Spec Part 1 §6, Part 2 §11).

    Also models colony pens, quarantine and isolation units via ``cage_type``.
    ``capacity`` is the maximum rabbits; **occupancy is derived** from the count
    of active rabbits with ``cage_id`` pointing here and is never stored (the
    Housing Capacity engine computes it in a later Part). A cage may sit directly
    under a farm (``row_id`` NULL) for simple, hobby-scale setups.
    """

    __tablename__ = "rabbit_cage"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_rabbit_cage_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    row_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_row.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cage_type: Mapped[str] = mapped_column(String(20), nullable=False, default="cage")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    maintenance_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<RabbitCage {self.name!r} type={self.cage_type} status={self.status}>"


# ── Aggregate root: Rabbit (Spec Part 2 §2, Part 3 §4) ─────────────────────────

class Rabbit(AGRIOSBase):
    """The individual rabbit — aggregate root of the module (Spec Part 3 §4).

    Pedigree is stored as deterministic parent links (``sire_id``/``dam_id``);
    unknown ancestry stays NULL and is never invented (Spec Part 3 §6). The
    Pedigree / Genetics engines (a later Part) compute ancestry, inbreeding and
    breeding value from these links. Location is a single ``cage_id`` — the full
    Rabbitry→Building→Room→Row path is derived through the cage, never denormalised.
    ``current_weight_g`` mirrors the latest weight record for fast display;
    authoritative weight history lives in the weight-records table (a later Part).
    """

    __tablename__ = "rabbit"
    __table_args__ = (
        UniqueConstraint("farm_id", "internal_ref", name="uq_rabbit_farm_internal_ref"),
        UniqueConstraint("farm_id", "ear_tag", name="uq_rabbit_farm_ear_tag"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_breed.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    bloodline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_bloodline.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    cage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_cage.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Birth litter (Spec Part 3 §8; added in Migration 067). Kits keep this link
    # permanently. SET NULL preserves the rabbit if its litter is ever removed.
    litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_litter.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Identity (Spec Part 1 §5, Part 3 §4)
    internal_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ear_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tattoo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    rfid: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Classification (Spec Part 3 §4)
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    purposes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Biology (Spec Part 3 §4)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    dob_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    birth_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    current_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Lifecycle & reproduction (Spec Part 1 §8, Part 3 §4)
    lifecycle_stage: Mapped[str] = mapped_column(String(25), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    reproductive_status: Mapped[str] = mapped_column(String(25), nullable=False, default="unknown")
    fertility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Pedigree links (deterministic; Spec Part 3 §6). Unknown ancestry stays NULL.
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships (all lazy=noload; services opt in explicitly)
    breed: Mapped["RabbitBreed | None"] = relationship(foreign_keys=[breed_id], lazy="noload")
    bloodline: Mapped["RabbitBloodline | None"] = relationship(foreign_keys=[bloodline_id], lazy="noload")
    cage: Mapped["RabbitCage | None"] = relationship(foreign_keys=[cage_id], lazy="noload")
    sire: Mapped["Rabbit | None"] = relationship(
        foreign_keys=[sire_id], remote_side="Rabbit.id", lazy="noload"
    )
    dam: Mapped["Rabbit | None"] = relationship(
        foreign_keys=[dam_id], remote_side="Rabbit.id", lazy="noload"
    )
    events: Mapped[list["RabbitEvent"]] = relationship(
        back_populates="rabbit", cascade="all, delete-orphan", lazy="noload"
    )
    media: Mapped[list["RabbitMedia"]] = relationship(
        back_populates="rabbit", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["RabbitDocument"]] = relationship(
        back_populates="rabbit", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_in_herd(self) -> bool:
        """True while the rabbit is part of the live, active herd."""
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<Rabbit {self.internal_ref} name={self.name!r} sex={self.sex} status={self.status}>"


# ── Immutable history: Rabbit timeline (Spec Part 8 §14) ───────────────────────

class RabbitEvent(AGRIOSBase):
    """Append-only operational timeline for a rabbit (created, moved, bred,
    weaned, note…). Complements platform Timeline/Audit; carries rabbit-specific
    payload in ``details`` (JSONB). History is never edited."""

    __tablename__ = "rabbit_event"

    rabbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    rabbit: Mapped["Rabbit"] = relationship(back_populates="events", lazy="noload")

    def __repr__(self) -> str:
        return f"<RabbitEvent rabbit={self.rabbit_id} type={self.event_type}>"


# ── Attachments (Spec Part 8 §15; reuse Greena file platform) ──────────────────

class RabbitMedia(AGRIOSBase):
    """Photos / videos / audio for a rabbit. Binary lives in the platform file
    store; this row references it (storage_path/url), mirroring avi_bird_media."""

    __tablename__ = "rabbit_media"

    rabbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="CASCADE"),
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

    rabbit: Mapped["Rabbit"] = relationship(back_populates="media", lazy="noload")


class RabbitDocument(AGRIOSBase):
    """Pedigree certificates, vet reports, invoices and other documents attached
    to a rabbit (Spec Part 8 §15)."""

    __tablename__ = "rabbit_document"

    rabbit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="CASCADE"),
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

    rabbit: Mapped["Rabbit"] = relationship(back_populates="documents", lazy="noload")


# ── Breeding cycle (Spec Part 3 §7, Part 4 §6) ─────────────────────────────────

class RabbitBreeding(AGRIOSBase):
    """A single mating attempt / breeding cycle: service → pregnancy check →
    kindling (Spec Part 3 §7). Repeat services link back to the previous attempt
    via ``repeat_of_id``. Buck/doe use SET NULL so breeding history survives a
    rabbit's soft-deletion. ``planned_kindling_date`` is a FORECAST derived from
    the service date and breed gestation — never a recorded fact."""

    __tablename__ = "rabbit_breeding"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    doe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    buck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    repeat_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="natural")
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_kindling_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pregnancy_checked_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    pregnancy_result: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    nest_box_prepared_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_kindling_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    doe: Mapped["Rabbit | None"] = relationship(foreign_keys=[doe_id], lazy="noload")
    buck: Mapped["Rabbit | None"] = relationship(foreign_keys=[buck_id], lazy="noload")

    @property
    def is_open(self) -> bool:
        """True while the cycle is unresolved (blocks a doe from being re-serviced)."""
        return self.status in ("planned", "serviced", "pregnant")

    def __repr__(self) -> str:
        return f"<RabbitBreeding doe={self.doe_id} buck={self.buck_id} status={self.status}>"


# ── Litter (Spec Part 3 §8) ────────────────────────────────────────────────────

class RabbitLitter(AGRIOSBase):
    """A litter produced at kindling (Spec Part 3 §8). Birth statistics are
    recorded facts; performance (survival, mortality rate) is calculated by the
    deterministic engine, never stored. Kits reference this row via
    ``rabbit.litter_id`` and remain linked permanently."""

    __tablename__ = "rabbit_litter"
    __table_args__ = (
        UniqueConstraint("farm_id", "litter_code", name="uq_rabbit_litter_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    breeding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    doe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    buck_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    litter_code: Mapped[str] = mapped_column(String(50), nullable=False)
    kindling_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_kits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    live_kits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stillbirths: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fostered_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fostered_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weaned_kits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mortality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_birth_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    weaning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    doe: Mapped["Rabbit | None"] = relationship(foreign_keys=[doe_id], lazy="noload")
    buck: Mapped["Rabbit | None"] = relationship(foreign_keys=[buck_id], lazy="noload")

    def __repr__(self) -> str:
        return f"<RabbitLitter {self.litter_code} kits={self.total_kits} status={self.status}>"
