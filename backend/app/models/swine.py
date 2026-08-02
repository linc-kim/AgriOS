"""
Greena — Swine Models (Module 20, Pig Framework, Milestone 1: Foundation)

The database backbone for the **Swine Framework** (Swine Doc 2). Unlike the unified
Small Ruminant subsystem, swine is a single species, so there is no ``species``
discriminator — but every other convention is shared with the Rabbit (Module 17)
and Small Ruminant (Modules 18/19) individual-animal modules, which are the closest
templates. The aggregate root is the **individual pig** (:class:`SwinePig`); every
operational record ultimately references one pig, a group, or a housing location.

Design rules honoured here (mirroring the Rabbit / Small Ruminant modules):
  * Everything inherits :class:`AGRIOSBase` → soft-delete only, JSONB metadata,
    audit timestamps. Pedigree, movement, medical and ownership history are never
    destroyed (Swine Doc 2 §19/§23).
  * Breed reference is a **data-driven catalog row** (:class:`SwineBreed`), never
    hardcoded (Swine Doc 1 §7). The framework registers itself in the existing
    ``species_profiles`` extensibility engine as ``swine`` (Migration 079).
  * Farm-scoped records carry ``farm_id``; organisation isolation flows through
    ``farms.organization_id`` — the same convention as Flock / Aviculture / BSF /
    Rabbit / Small Ruminant. The breed catalog carries a nullable
    ``organization_id`` (NULL = global system catalog shared by every organisation).
  * Structure follows the specification hierarchy (Swine Doc 1 §5, Doc 2 §3, §18):
    Farm → Herd → Group → Pen → Individual. Pigs are a **housed** species, so there
    is no pasture table (the Small Ruminant grazing concept); physical infrastructure
    is the pen/shed/crate (:class:`SwinePen`), which carries a biosecurity status
    (Swine Doc 2 §6). Occupancy is DERIVED from ``swine_pig`` location FKs and never
    stored (the Housing engine, Milestone 2, computes it).
  * The per-species vocabulary — sex/class tokens (boar/sow/gilt/barrow), the
    production-stage progression and gestation default — lives in the pure
    :mod:`app.services.swine_config`, so migrations, models, services and engines
    share one source of truth.
  * Enumerated fields are plain strings validated at the schema/service layer, with
    allowed values published as the ``*_VALUES`` tuples below. No business
    calculations live in models — those belong to the deterministic engines.

Tables map 1:1 to Migration 079.
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

# Breed catalog (Swine Doc 1 §7, Doc 2 §3). Pig breeds classify by breeding role in
# a crossbreeding programme — maternal lines (Large White, Landrace), terminal sire
# lines (Duroc, Pietrain, Hampshire), plus indigenous / heritage / crossbred stock.
BREED_CATEGORY_VALUES = (
    "maternal", "terminal", "dual_purpose", "indigenous", "heritage",
    "crossbreed", "show", "other",
)
BREED_PURPOSE_VALUES = ("meat", "breeding", "maternal", "terminal", "mixed")

# Herd — the top-level management container (Swine Doc 2 §5). Its type mirrors the
# production scope the framework supports (Swine Doc 1 §4).
HERD_TYPE_VALUES = (
    "breeding", "farrow_to_finish", "farrow_to_weaner", "weaner", "grower",
    "finisher", "boar_stud", "multiplier", "commercial", "mixed", "other",
)
HERD_STATUS_VALUES = ("active", "inactive", "archived")

# Group — dynamic production/management grouping within a herd (Swine Doc 1 §5-6,
# Doc 2 §12). The nursery / grower / finisher production groups (Milestone 5) are
# groups of this kind; the type also covers the breeding-herd sub-groups.
GROUP_TYPE_VALUES = (
    "breeding", "gestation", "farrowing", "lactation", "nursery", "weaner",
    "grower", "finisher", "replacement", "boar", "quarantine", "isolation",
    "hospital", "sale", "general", "other",
)
GROUP_STATUS_VALUES = ("active", "inactive", "archived")

# Physical housing (Swine Doc 2 §6). A pen is a housed unit — a farrowing crate,
# gestation stall, breeding/nursery/grower/finisher pen, quarantine/hospital pen,
# etc. — optionally within a named building/shed. Biosecurity status is first-class.
PEN_TYPE_VALUES = (
    "farrowing_crate", "farrowing_pen", "gestation_stall", "gestation_pen",
    "breeding_pen", "dry_sow_pen", "nursery_pen", "weaner_pen", "grower_pen",
    "finisher_pen", "boar_pen", "quarantine", "isolation", "hospital",
    "loading", "pen", "shed", "other",
)
PEN_STATUS_VALUES = ("available", "occupied", "maintenance", "cleaning", "out_of_service")
# Biosecurity status of a pen/zone (Swine Doc 2 §6, Doc 5 §8). A recorded
# assessment, never inferred.
BIOSECURITY_STATUS_VALUES = (
    "secure", "monitored", "restricted", "quarantine", "compromised", "unknown",
)

# Animal identity / classification (Swine Doc 2 §4). ``sex`` is the class token
# boar/sow/gilt/barrow validated against swine_config; horn status is irrelevant to
# pigs (dropped vs the small-ruminant model).
SEX_VALUES = ("boar", "sow", "gilt", "barrow", "unknown")
PURPOSE_VALUES = (
    "meat", "breeding", "replacement", "show", "genetic_improvement", "mixed", "unknown",
)
REGISTRATION_STATUS_VALUES = (
    "registered", "unregistered", "pending", "commercial", "recorded", "unknown",
)

# Lifecycle / production stage (Swine Doc 1 §5-6, Doc 2 §4). The full set lives in
# swine_config.PRODUCTION_STAGE_VALUES; re-exported here for the schema layer.
PRODUCTION_STAGE_VALUES = (
    "piglet", "weaner", "nursery", "grower", "finisher", "breeding",
    "replacement", "cull", "retired", "unknown",
)
STATUS_VALUES = ("active", "sold", "transferred", "deceased", "culled", "archived")
# Statuses that count as "no longer in the active herd" (Swine Doc 2 §4, §19).
TERMINAL_STATUSES = ("sold", "transferred", "deceased", "culled")
# Reproductive status through the sow/gilt cycle (Swine Doc 2 §4, §7).
REPRODUCTIVE_STATUS_VALUES = (
    "not_bred", "bred", "pregnant", "lactating", "open", "dry", "weaned",
    "proven", "unproven", "unknown",
)
FERTILITY_STATUS_VALUES = ("fertile", "infertile", "unproven", "unknown")
# Market status of a growing/finishing pig (Swine Doc 2 §4).
MARKET_STATUS_VALUES = ("growing", "market_ready", "sold", "held", "unknown")
ACQUISITION_TYPE_VALUES = ("bred", "purchased", "donated", "transferred", "unknown")

# Animal timeline event types (Swine Doc 2 §16, §18). Append-only history covering
# the whole lifecycle plus the swine-specific reproductive events (inseminated,
# farrowed, fostered, weaned) so later milestones need no schema change to this table.
EVENT_TYPE_VALUES = (
    "created", "updated", "status_changed", "archived", "restored", "moved",
    "transferred", "sold", "purchased", "died", "culled", "bred", "inseminated",
    "pregnancy_checked", "farrowed", "fostered", "weaned", "weight_recorded",
    "feed_recorded", "health_recorded", "vaccination_recorded", "treatment_recorded",
    "market_ready", "media_added", "document_added", "note",
)

MEDIA_TYPE_VALUES = ("photo", "video", "audio")
DOCUMENT_TYPE_VALUES = (
    "pedigree_certificate", "health_certificate", "registration", "lab_report",
    "vet_report", "movement_record", "purchase_record", "sale_document",
    "breeding_certificate", "invoice", "other",
)


# ── Catalog: Breed (Swine Doc 1 §7, Doc 2 §3) ──────────────────────────────────

class SwineBreed(AGRIOSBase):
    """Data-driven pig breed catalog (Swine Doc 1 §7).

    Reference data only — operational records never overwrite breed values.
    ``organization_id IS NULL`` marks a global/system entry shared by every
    organisation; a non-null value is an organisation's custom breed. ``profile``
    (JSONB) holds the rich, extensible reference: mature weight range, litter-size
    and growth benchmarks, backfat/lean characteristics, temperament, climate
    suitability and an optional ``gestation_days`` override read by the breeding
    engine. Breeds are NEVER hardcoded.
    """

    __tablename__ = "swine_breed"

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
        return f"<SwineBreed {self.name!r} category={self.category}>"


# ── Catalog: Bloodline / genetic line (Swine Doc 2 §7, §18) ────────────────────

class SwineBloodline(AGRIOSBase):
    """A named genetic line / bloodline within a farm.

    Bloodlines group animals for genetic tracking and performance-based selection
    (boar/sow line performance, Swine Doc 6 §7). Farm-scoped: a bloodline belongs to
    one farm's breeding programme.
    """

    __tablename__ = "swine_bloodline"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_swine_bloodline_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_breed.id", ondelete="SET NULL"),
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
        return f"<SwineBloodline {self.name!r}>"


# ── Management grouping (Swine Doc 2 §5-6, §12) ────────────────────────────────
# Herd → Group. A herd is the top-level container; groups are dynamic production
# and management sub-groupings (breeding, gestation, farrowing, nursery, grower,
# finisher, quarantine, sale…).

class SwineHerd(AGRIOSBase):
    """The top-level management container — a pig herd (Swine Doc 2 §5).

    A herd contains dynamic groups and production categories; the membership of the
    animals below it changes over time without destroying history (Swine Doc 2 §19).
    ``herd_type`` reflects the production system (farrow-to-finish, weaner, boar
    stud, …) the framework supports (Swine Doc 1 §4).
    """

    __tablename__ = "swine_herd"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_swine_herd_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    herd_type: Mapped[str] = mapped_column(String(20), nullable=False, default="mixed")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineHerd {self.name!r} type={self.herd_type}>"


class SwineGroup(AGRIOSBase):
    """A dynamic production/management group within a herd (Swine Doc 2 §12).

    Groups model the specification's production groupings — breeding, gestation and
    farrowing groups, nursery / grower / finisher production groups (Milestone 5),
    quarantine / isolation, sale groups, etc. Membership is dynamic (via
    ``swine_pig.group_id``); an animal moves between groups without losing history.
    Optionally nested under a herd.
    """

    __tablename__ = "swine_group"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_swine_group_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    herd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_herd.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    group_type: Mapped[str] = mapped_column(String(20), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineGroup {self.name!r} type={self.group_type}>"


# ── Physical housing (Swine Doc 2 §6) ──────────────────────────────────────────
# Pigs are housed, not pastured, so the physical unit is the pen/crate/stall/shed.
# Occupancy is DERIVED from the pigs located here and never stored.

class SwinePen(AGRIOSBase):
    """A physical housing unit — a farrowing crate/pen, gestation stall/pen,
    breeding / nursery / grower / finisher pen, boar pen, or quarantine / hospital
    pen, optionally within a named building or shed (Swine Doc 2 §6).

    ``capacity`` is the maximum head; occupancy is DERIVED from the count of active
    pigs with ``pen_id`` pointing here (the Housing engine, Milestone 2).
    ``biosecurity_status`` is a recorded assessment used by the health/biosecurity
    milestone, never inferred.
    """

    __tablename__ = "swine_pen"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_swine_pen_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    building: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pen_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pen")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    biosecurity_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwinePen {self.name!r} type={self.pen_type} status={self.status}>"


# ── Aggregate root: SwinePig animal (Swine Doc 2 §4) ───────────────────────────

class SwinePig(AGRIOSBase):
    """The individual pig — aggregate root of the Swine Framework.

    Pedigree is stored as deterministic parent links (``sire_id``/``dam_id``);
    unknown ancestry stays NULL and is never invented (Swine Doc 2 §18, Doc 3 §23).
    Location is expressed as optional group (management) and pen (physical) links —
    a pig moves freely without losing history. ``current_weight_kg`` mirrors the
    latest weight record for fast display; authoritative weight history lives in the
    weight table (Milestone 6). ``parity`` caches a sow's completed-litter count for
    fast display; the authoritative reproductive history is derived from farrowing
    records (Milestone 4). The ``litter_id`` link to the birth (farrowing) record is
    added in Migration 081 (Milestone 4), mirroring how Small Ruminant added
    ``birth_id`` in a later migration.
    """

    __tablename__ = "swine_pig"
    __table_args__ = (
        UniqueConstraint("farm_id", "internal_ref", name="uq_swine_pig_farm_internal_ref"),
        UniqueConstraint("farm_id", "ear_tag", name="uq_swine_pig_farm_ear_tag"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_breed.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    bloodline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_bloodline.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    herd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_herd.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Identity (Swine Doc 2 §4). Ear notch is the traditional litter/pig marking.
    internal_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ear_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ear_notch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tattoo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    rfid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visual_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Classification (Swine Doc 2 §4)
    line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    purposes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    registration_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")

    # Biology (Swine Doc 2 §4). Weights in kilograms.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    dob_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    current_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)

    # Lifecycle & reproduction (Swine Doc 1 §5-6, Doc 2 §4)
    production_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    reproductive_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    fertility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    market_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    parity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Pedigree links (deterministic; Swine Doc 2 §18). Unknown ancestry stays NULL.
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships (all lazy=noload; services opt in explicitly)
    breed: Mapped["SwineBreed | None"] = relationship(foreign_keys=[breed_id], lazy="noload")
    bloodline: Mapped["SwineBloodline | None"] = relationship(foreign_keys=[bloodline_id], lazy="noload")
    herd: Mapped["SwineHerd | None"] = relationship(foreign_keys=[herd_id], lazy="noload")
    group: Mapped["SwineGroup | None"] = relationship(foreign_keys=[group_id], lazy="noload")
    pen: Mapped["SwinePen | None"] = relationship(foreign_keys=[pen_id], lazy="noload")
    sire: Mapped["SwinePig | None"] = relationship(
        foreign_keys=[sire_id], remote_side="SwinePig.id", lazy="noload"
    )
    dam: Mapped["SwinePig | None"] = relationship(
        foreign_keys=[dam_id], remote_side="SwinePig.id", lazy="noload"
    )
    events: Mapped[list["SwineEvent"]] = relationship(
        back_populates="pig", cascade="all, delete-orphan", lazy="noload"
    )
    media: Mapped[list["SwineMedia"]] = relationship(
        back_populates="pig", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["SwineDocument"]] = relationship(
        back_populates="pig", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_in_herd(self) -> bool:
        """True while the pig is part of the live, active herd."""
        return self.status == "active"

    def __repr__(self) -> str:
        return (
            f"<SwinePig {self.internal_ref} name={self.name!r} "
            f"sex={self.sex} stage={self.production_stage} status={self.status}>"
        )


# ── Immutable history: animal timeline (Swine Doc 2 §16, §18) ──────────────────

class SwineEvent(AGRIOSBase):
    """Append-only operational timeline for a pig (created, moved, bred, inseminated,
    farrowed, weaned, note…). Complements platform Timeline/Audit; carries the
    event payload in ``details`` (JSONB). History is never edited.

    Movement records (Swine Doc 2 §16, Doc 3 §19) are captured here as ``moved`` /
    ``transferred`` events whose ``details`` hold previous/new location, reason and
    responsible user — the dedicated movement view is derived from this timeline
    rather than duplicating history in a second table.
    """

    __tablename__ = "swine_event"

    pig_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    pig: Mapped["SwinePig"] = relationship(back_populates="events", lazy="noload")

    def __repr__(self) -> str:
        return f"<SwineEvent pig={self.pig_id} type={self.event_type}>"


# ── Attachments (Swine Doc 5 §13; reuse Greena file platform) ──────────────────

class SwineMedia(AGRIOSBase):
    """Photos / videos / audio for a pig. Binary lives in the platform file store;
    this row references it (storage_path/url), mirroring rabbit_media / sr_media."""

    __tablename__ = "swine_media"

    pig_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="CASCADE"),
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

    pig: Mapped["SwinePig"] = relationship(back_populates="media", lazy="noload")


class SwineDocument(AGRIOSBase):
    """Pedigree certificates, health certificates, movement/purchase/sale records,
    vet & lab reports, invoices and other documents attached to a pig (Swine
    Doc 5 §13)."""

    __tablename__ = "swine_document"

    pig_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="CASCADE"),
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

    pig: Mapped["SwinePig"] = relationship(back_populates="documents", lazy="noload")


# ── Breeding cycle (Swine Doc 2 §7, Doc 3 §7-9) — Milestone 3 ───────────────────
# Natural mating and artificial insemination share ONE cycle table, distinguished
# by ``method`` (the AI workspace is the ``method='artificial'`` slice). Pregnancy
# confirmation, expected farrowing and risk are tracked inline on the same row — the
# Pregnancy workspace is the ``status='pregnant'`` slice. Embryo transfer is
# schema-ready but deferred. Mirrors the Small Ruminant single-cycle design.
BREEDING_METHOD_VALUES = ("natural", "artificial", "embryo_transfer")
BREEDING_STATUS_VALUES = (
    "planned", "serviced", "pregnant", "not_pregnant", "farrowed", "failed", "closed", "cancelled",
)
PREGNANCY_RESULT_VALUES = ("unknown", "pregnant", "not_pregnant")
# How a pregnancy was confirmed (Swine Doc 3 §9). ``non_return`` = no return to heat.
PREGNANCY_CHECK_METHOD_VALUES = (
    "palpation", "ultrasound", "blood_test", "non_return", "visual", "other",
)
PREGNANCY_RISK_VALUES = ("low", "moderate", "high", "unknown")
BREEDING_OUTCOME_VALUES = ("successful", "failed", "aborted", "reabsorbed", "unknown")


class SwineBreeding(AGRIOSBase):
    """A single breeding cycle: service → pregnancy check → farrowing (Swine Doc 2 §7).

    ``method`` distinguishes natural mating from artificial insemination; for AI the
    on-farm ``sire_id`` may be NULL and the semen source/batch/technician are
    recorded instead (traceable, Swine Doc 3 §8). Repeat services link back via
    ``repeat_of_id``. Dam/sire use SET NULL so breeding history survives a pig's
    soft-deletion. ``planned_farrowing_date`` is a FORECAST derived from the service
    date and the species/breed gestation (~114d) — never a recorded fact. Pregnancy
    confirmation is tracked inline (the Pregnancy workspace is the ``pregnant``
    slice); the actual farrowing links here in Milestone 4.
    """

    __tablename__ = "swine_breeding"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    repeat_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="natural")
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_farrowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Artificial insemination detail (traceable; used when method='artificial').
    semen_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    semen_batch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    technician: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Pregnancy confirmation (inline; the Pregnancy workspace reads this).
    pregnancy_checked_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    pregnancy_check_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pregnancy_result: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    confirmed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    actual_farrowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SwinePig | None"] = relationship(foreign_keys=[dam_id], lazy="noload")
    sire: Mapped["SwinePig | None"] = relationship(foreign_keys=[sire_id], lazy="noload")

    @property
    def is_open(self) -> bool:
        """True while the cycle is unresolved (blocks a dam from being re-serviced)."""
        return self.status in ("planned", "serviced", "pregnant")

    def __repr__(self) -> str:
        return f"<SwineBreeding dam={self.dam_id} sire={self.sire_id} method={self.method} status={self.status}>"
