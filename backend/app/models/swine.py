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
# Biological birth sex of a piglet, recorded at birth before class assignment.
BIRTH_SEX_VALUES = ("male", "female", "unknown")
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
    # The birth litter this pig belongs to (added in Migration 082, Milestone 4).
    # Individual (individualized) management links each young pig to its litter;
    # litter-level-only farms simply leave this NULL and track the cohort on
    # ``swine_litter``. ``nurse_dam_id`` records a foster (nursing) sow different from
    # the birth dam. Both SET NULL so a pig survives the litter/sow being removed.
    litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_litter.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    nurse_dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"),
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
    # ``sex`` is the management class (boar/sow/gilt/barrow), assigned at/after
    # weaning; ``birth_sex`` (male/female) is the biological sex recorded at birth for
    # a piglet before it is classified.
    sex: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    birth_sex: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
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


# ── Movement history (Swine Doc 2 §16, Doc 3 §19) — dedicated audit trail ──────
# A pig's current pen/group lives on ``swine_pig``; this table is the permanent,
# append-only record of every move — never overwritten. It underpins disease
# tracing, biosecurity investigations, welfare monitoring and audit history
# (a current-assignment field can never replace this trail).
MOVEMENT_TYPE_VALUES = (
    "arrival", "pen_transfer", "group_change", "stage_transition", "isolation",
    "farrowing_move", "weaning_move", "hospital", "loading", "farm_transfer",
    "departure", "other",
)


class SwineMovement(AGRIOSBase):
    """One recorded movement of a pig between pens and/or groups (Swine Doc 2 §16).

    Captures the previous and new location, who moved it, when and why. Location FKs
    use SET NULL so the movement history survives a pen/group being removed. This is
    the source of truth for movement history; the pig's timeline may also note it.
    """

    __tablename__ = "swine_movement"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pen_transfer")
    from_pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    to_pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    from_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    to_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    moved_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    moved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineMovement pig={self.pig_id} type={self.movement_type} on={self.moved_on}>"


# ── Breeding & pregnancy (Swine Doc 2 §7, Doc 3 §7-9) — Milestone 3 ─────────────
# ONE breeding table covers natural mating AND artificial insemination, distinguished
# by ``method`` (the AI workspace is the ``method='artificial'`` slice). Pregnancy is
# a distinct LIFECYCLE STAGE, not a breeding event, so it lives in its own
# ``swine_pregnancy`` table linked to the breeding — this cleanly supports
# confirmation, rechecks, loss, false pregnancy and farrowing linkage. Embryo
# transfer is schema-ready but deferred.
BREEDING_METHOD_VALUES = ("natural", "artificial", "embryo_transfer")
# Service-cycle status only (the pregnancy has its own lifecycle below).
BREEDING_STATUS_VALUES = ("planned", "serviced", "closed", "cancelled")
BREEDING_OUTCOME_VALUES = ("pending", "pregnant", "not_pregnant", "failed", "unknown")

# Pregnancy lifecycle (Swine Doc 3 §9). A pregnancy is confirmed from a breeding,
# may be rechecked, and resolves to farrowed or lost (incl. abortion/resorption) —
# or is found to be a false pregnancy (pseudopregnancy).
PREGNANCY_STATUS_VALUES = ("unconfirmed", "confirmed", "lost", "farrowed", "false_pregnancy")
PREGNANCY_RESULT_VALUES = ("unknown", "pregnant", "not_pregnant")
# How a pregnancy was confirmed. ``non_return`` = no return to heat.
PREGNANCY_CHECK_METHOD_VALUES = (
    "palpation", "ultrasound", "blood_test", "non_return", "visual", "other",
)
PREGNANCY_RISK_VALUES = ("low", "moderate", "high", "unknown")
PREGNANCY_LOSS_REASON_VALUES = (
    "abortion", "resorption", "mummification", "stillbirth", "disease",
    "injury", "unknown", "other",
)


class SwineBreeding(AGRIOSBase):
    """A single breeding service — natural mating or artificial insemination
    (Swine Doc 2 §7).

    ``method`` distinguishes natural mating from AI; for AI the on-farm ``sire_id``
    may be NULL and the semen source/batch/technician are recorded instead
    (traceable, Swine Doc 3 §8). Repeat services link back via ``repeat_of_id``.
    Dam/sire use SET NULL so breeding history survives a pig's soft-deletion.
    ``planned_farrowing_date`` is a FORECAST derived from the service date and the
    species/breed gestation (~114d) — never a recorded fact. Whether the service
    resulted in pregnancy is a distinct lifecycle stage in :class:`SwinePregnancy`;
    ``outcome`` mirrors the resolved result for quick reporting.
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SwinePig | None"] = relationship(foreign_keys=[dam_id], lazy="noload")
    sire: Mapped["SwinePig | None"] = relationship(foreign_keys=[sire_id], lazy="noload")

    @property
    def is_open(self) -> bool:
        """True while the service cycle is unresolved (blocks a dam from re-service)."""
        return self.status in ("planned", "serviced")

    def __repr__(self) -> str:
        return f"<SwineBreeding dam={self.dam_id} sire={self.sire_id} method={self.method} status={self.status}>"


class SwinePregnancy(AGRIOSBase):
    """A pregnancy — a lifecycle stage confirmed from a breeding service (Swine Doc 3 §9).

    Kept separate from the breeding event so confirmation, rechecks, pregnancy loss
    (abortion / resorption), false pregnancy and farrowing linkage each have a clear
    home. ``expected_farrowing_date`` is a forecast (service date + gestation);
    ``actual_farrowing_date`` is set when the farrowing is recorded (Milestone 4).
    ``dam_id`` is denormalised from the breeding for fast querying of a sow's
    pregnancies. Only one active (unconfirmed/confirmed) pregnancy per dam is allowed
    by the service layer.
    """

    __tablename__ = "swine_pregnancy"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    breeding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unconfirmed")
    confirmation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confirmation_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expected_farrowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    loss_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    loss_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_farrowing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    breeding: Mapped["SwineBreeding | None"] = relationship(foreign_keys=[breeding_id], lazy="noload")
    dam: Mapped["SwinePig | None"] = relationship(foreign_keys=[dam_id], lazy="noload")

    @property
    def is_active(self) -> bool:
        """True while the pregnancy is ongoing (blocks a duplicate active pregnancy)."""
        return self.status in ("unconfirmed", "confirmed")

    def __repr__(self) -> str:
        return f"<SwinePregnancy dam={self.dam_id} status={self.status} due={self.expected_farrowing_date}>"


# ── Farrowing, litters & fostering (Swine Doc 2 §8-10, Doc 3 §10-12) — M4 ───────
# The farrowing is the birthing EVENT (assistance, complications); the litter is the
# resulting offspring COHORT (counts, weaning). Litters carry aggregate figures so a
# smallholder can manage at litter level; a commercial farm additionally creates
# individual ``swine_pig`` rows linked via ``swine_pig.litter_id`` (both workflows
# supported — neither forced). Fostering moves piglets (one, several, or a whole
# litter) between nursing sows while preserving birth-litter traceability.
FARROWING_STATUS_VALUES = ("recorded", "active", "closed")
COLOSTRUM_STATUS_VALUES = ("received", "partial", "not_received", "unknown")
LITTER_STATUS_VALUES = ("active", "weaned", "closed")
PIGLET_DEATH_CAUSE_VALUES = (
    "stillborn", "crushed", "starvation", "chilled", "scours", "disease",
    "savaging", "congenital", "low_viability", "unknown", "other",
)


class SwineFarrowing(AGRIOSBase):
    """A farrowing — one sow's birthing event (Swine Doc 2 §8, Doc 3 §10).

    Records the event circumstances (assistance, complications, colostrum) and links
    to the pregnancy/breeding it resolves. The offspring counts live on the
    associated :class:`SwineLitter` (1:1). ``parity`` is the sow's litter number.
    """

    __tablename__ = "swine_farrowing"
    __table_args__ = (
        UniqueConstraint("farm_id", "farrowing_code", name="uq_swine_farrowing_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    breeding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    pregnancy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pregnancy.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    farrowing_code: Mapped[str] = mapped_column(String(50), nullable=False)
    farrowing_date: Mapped[date] = mapped_column(Date, nullable=False)
    parity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assistance_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    complications: Mapped[str | None] = mapped_column(Text, nullable=True)
    colostrum_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recorded")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SwinePig | None"] = relationship(foreign_keys=[dam_id], lazy="noload")
    sire: Mapped["SwinePig | None"] = relationship(foreign_keys=[sire_id], lazy="noload")

    def __repr__(self) -> str:
        return f"<SwineFarrowing {self.farrowing_code} dam={self.dam_id} date={self.farrowing_date}>"


class SwineLitter(AGRIOSBase):
    """The offspring cohort of a farrowing (Swine Doc 2 §9, Doc 3 §11).

    Holds the recorded birth statistics (born alive / stillborn / mummified) and the
    weaning outcome. Performance (live-birth rate, pre-wean survival) is calculated
    by the deterministic engine, never stored. Individual pigs, when tracked, link
    here via ``swine_pig.litter_id``. ``nurse_dam_id`` is the current nursing sow,
    which may differ from the birth ``dam_id`` after fostering.
    """

    __tablename__ = "swine_litter"
    __table_args__ = (
        UniqueConstraint("farm_id", "litter_code", name="uq_swine_litter_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    farrowing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_farrowing.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    nurse_dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    litter_code: Mapped[str] = mapped_column(String(50), nullable=False)
    total_born: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    born_alive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stillborn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mummified: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weaned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mortality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fostered_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fostered_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    litter_birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(9, 3), nullable=True)
    weaning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    avg_weaning_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SwinePig | None"] = relationship(foreign_keys=[dam_id], lazy="noload")

    @property
    def nursed_count(self) -> int:
        """Piglets currently nursing on this litter's sow (born alive − out + in)."""
        return max(self.born_alive - self.fostered_out + self.fostered_in, 0)

    def __repr__(self) -> str:
        return f"<SwineLitter {self.litter_code} alive={self.born_alive} weaned={self.weaned}>"


class SwineFosterTransfer(AGRIOSBase):
    """A cross-fostering event — piglets moved from one nursing sow to another
    (Swine Doc 2 §10, Doc 3 §12).

    Operates at the individual-piglet grain: ``piglet_count`` is always recorded, and
    ``pig_ids`` lists the specific ``swine_pig`` rows moved when the farm tracks
    individuals (one, several, or a whole litter). A permanent fact on both litters;
    each moved pig keeps its birth litter and gains a ``nurse_dam_id`` for full
    birth-sow → foster-sow traceability.
    """

    __tablename__ = "swine_foster_transfer"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source_litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dest_litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    source_dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dest_dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    piglet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pig_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineFosterTransfer {self.source_litter_id}→{self.dest_litter_id} n={self.piglet_count}>"


# ── Feed & nutrition (Swine Doc 2 §13, Doc 3 §17, Doc 5 §6) — Milestone 5 ───────
# The feed catalog is data-driven reference (like breeds). Feeding CONSUMPTION reuses
# the platform Inventory module — a feeding that references an inventory item posts a
# consumption movement (stock decrement) and snapshots its cost; feed is expensed
# ONCE at stock-in, never re-posted (frozen finance rule). Feed plans map a
# production stage to a feed and a daily target.
FEED_CATEGORY_VALUES = (
    "starter", "creep", "nursery", "grower", "finisher", "developer",
    "gestation", "lactation", "boar", "mineral", "supplement", "medicated", "other",
)
FEED_FORM_VALUES = ("pellet", "crumble", "mash", "meal", "liquid", "paste", "other")


class SwineFeed(AGRIOSBase):
    """Data-driven pig feed catalog (Swine Doc 2 §13).

    Reference data: name, category (phase), physical form, and a nutrient ``profile``
    (JSONB: crude protein %, ME, lysine, etc.). ``organization_id IS NULL`` is a
    global/system feed shared by all orgs. Medicated feeds carry a withdrawal period.
    """

    __tablename__ = "swine_feed"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    form: Mapped[str] = mapped_column(String(20), nullable=False, default="pellet")
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_medicated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    withdrawal_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineFeed {self.name!r} category={self.category}>"


class SwineFeedPlan(AGRIOSBase):
    """A feeding-plan entry: for a named plan and a production stage, the intended
    feed and daily target (Swine Doc 3 §17, Doc 6 §10).

    A "plan" is the set of entries sharing ``plan_name`` on a farm — one entry per
    production stage / phase. Targets are recorded references the deterministic feed
    engine compares actual consumption against; nothing here is a fact about an
    animal.
    """

    __tablename__ = "swine_feed_plan"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    plan_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    production_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    phase_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_feed.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    daily_amount_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    age_start_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_end_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_start_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    target_weight_end_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineFeedPlan {self.plan_name!r} stage={self.production_stage}>"


class SwineFeedRecord(AGRIOSBase):
    """A feeding event for a pig, group or the farm (Swine Doc 2 §13).

    Feed stock and purchase cost live in the platform Inventory module; this row is
    the domain feeding log. ``inventory_item_id`` / ``inventory_movement_id`` are SOFT
    references (no FK — modules stay decoupled). ``cost`` is a snapshot allocation,
    never re-posted to finance (feed is expensed once at Inventory stock-in).
    """

    __tablename__ = "swine_feed_record"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    feed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_feed.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inventory_movement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    feed_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    fed_on: Mapped[date] = mapped_column(Date, nullable=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineFeedRecord pig={self.pig_id} group={self.group_id} {self.quantity_kg}kg>"


# ── Health & biosecurity (Swine Doc 2 §15, Doc 3 §18, Doc 6 §11) — Milestone 6 ──
# Health is modelled as INDEPENDENT clinical events, each its own historical record
# linked to a pig (and/or a group), never fields on the pig — so a complete medical
# history is preserved. Distinct clinical event types are distinct tables (not one
# generic "medical record"): disease cases (group-capable), vaccination, treatment
# (therapeutic + preventive medication via ``intent``), procedure (surgical/routine),
# observation (exam/assessment), and lab test. Mortality, isolation and operational
# biosecurity are their own historical records. Per the frozen constitution §4.4, a
# ``diagnosis`` is a RECORDED veterinary input only — the platform never infers it.
DISEASE_SCOPE_VALUES = ("individual", "litter", "group", "pen", "multi_pen", "farm")
DISEASE_STATUS_VALUES = ("suspected", "confirmed", "resolved", "chronic", "ruled_out")
HEALTH_SEVERITY_VALUES = ("info", "mild", "moderate", "severe", "critical")
ADMIN_ROUTE_VALUES = (
    "intramuscular", "subcutaneous", "oral", "in_feed", "in_water", "intranasal",
    "topical", "intravenous", "other",
)
TREATMENT_INTENT_VALUES = ("therapeutic", "preventive", "metaphylactic")
TREATMENT_OUTCOME_VALUES = ("recovered", "improving", "ongoing", "no_response", "died", "unknown")
PROCEDURE_TYPE_VALUES = (
    "castration", "tail_docking", "teeth_clipping", "iron_injection", "ear_notching",
    "hernia_repair", "surgery", "euthanasia", "other",
)
OBSERVATION_TYPE_VALUES = (
    "routine_check", "examination", "vet_assessment", "body_condition", "temperature",
    "lameness", "note",
)
LAB_STATUS_VALUES = ("pending", "completed", "cancelled")
LAB_RESULT_VALUES = ("positive", "negative", "inconclusive", "pending", "not_recorded")
MORTALITY_CAUSE_CATEGORY_VALUES = (
    "disease", "respiratory", "digestive", "injury", "crushing", "starvation",
    "congenital", "heat_stress", "sudden_death", "culled", "unknown", "other",
)
DISPOSAL_METHOD_VALUES = (
    "incineration", "burial", "composting", "rendering", "knackery", "other", "unknown",
)
ISOLATION_REASON_VALUES = (
    "disease", "injury", "quarantine_intake", "observation", "biosecurity", "other",
)
ISOLATION_STATUS_VALUES = ("active", "cleared", "ended")
BIOSECURITY_RECORD_TYPE_VALUES = (
    "visitor_log", "vehicle_entry", "equipment_disinfection", "staff_sanitation",
    "pen_cleaning", "rodent_control", "deadstock_disposal", "quarantine", "inspection", "other",
)


class SwineDiseaseCase(AGRIOSBase):
    """An illness / injury / disease case (Swine Doc 2 §15).

    Group-capable: ``scope`` records whether it affects an individual, a litter, a
    group, a pen, multiple pens, or the whole farm, with the relevant FK(s) set.
    ``diagnosis`` is a recorded veterinary input only — never inferred (§4.4).
    """

    __tablename__ = "swine_disease_case"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="individual")
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    disease_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pathogen: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suspected")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="mild")
    onset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mortality_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineDiseaseCase {self.disease_name!r} scope={self.scope} status={self.status}>"


class SwineVaccination(AGRIOSBase):
    """A vaccination event — preventive immunisation (Swine Doc 2 §15). Distinct from
    treatment. May target an individual or a group; the vaccine product may draw from
    Inventory (soft reference)."""

    __tablename__ = "swine_vaccination"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    vaccine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    disease_targeted: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dose: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    route: Mapped[str | None] = mapped_column(String(20), nullable=True)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    administered_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    administered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    animal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inventory_movement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineVaccination {self.vaccine_name!r} on={self.administered_on}>"


class SwineTreatment(AGRIOSBase):
    """A medication treatment — therapeutic or preventive (Swine Doc 2 §15).

    ``intent`` separates a therapeutic treatment from preventive / metaphylactic
    medication (the same action — administering a product — differing in intent),
    following the single-table-with-discriminator pattern used for breeding. Surgical
    work is a :class:`SwineProcedure`, not a treatment. Links its disease case, records
    the meat withdrawal date, and may draw product from Inventory (soft reference).
    """

    __tablename__ = "swine_treatment"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    disease_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    intent: Mapped[str] = mapped_column(String(20), nullable=False, default="therapeutic")
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    drug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dose: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    dose_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    route: Mapped[str | None] = mapped_column(String(20), nullable=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    withdrawal_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    administered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="ongoing")
    animal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inventory_movement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineTreatment {self.product_name!r} intent={self.intent} outcome={self.outcome}>"


class SwineProcedure(AGRIOSBase):
    """A surgical or routine husbandry procedure (Swine Doc 2 §15): castration, tail
    docking, teeth clipping, iron injection, ear notching, hernia repair, euthanasia."""

    __tablename__ = "swine_procedure"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    procedure_type: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    performed_on: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    anesthesia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analgesia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    animal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineProcedure {self.procedure_type} on={self.performed_on}>"


class SwineObservation(AGRIOSBase):
    """A health observation / examination / veterinary assessment (Swine Doc 2 §15).

    ``findings`` is recorded text — never an inferred diagnosis (§4.4). Temperature and
    body-condition score are optional recorded measurements."""

    __tablename__ = "swine_observation"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    observation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="routine_check")
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    body_condition_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineObservation {self.observation_type} on={self.observed_on}>"


class SwineLabTest(AGRIOSBase):
    """A laboratory test and its recorded result (Swine Doc 2 §15). Results are
    recorded facts from the lab — never inferred."""

    __tablename__ = "swine_lab_test"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    disease_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sample_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    laboratory: Mapped[str | None] = mapped_column(String(200), nullable=True)
    collected_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    result_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineLabTest {self.test_name!r} result={self.result}>"


class SwineMortality(AGRIOSBase):
    """A mortality event preserving full cause history (Swine Doc 2 §15).

    A pig's death creates this record AND transitions the pig to ``deceased`` — the
    pig row is never destroyed, so it stays historically traceable. Captures suspected
    vs confirmed cause, location, related disease/treatment/vet and disposal method.
    ``litter_id`` covers pre-wean piglet mortality where no individual pig row exists.
    """

    __tablename__ = "swine_mortality"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    litter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_litter.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    disease_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    treatment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_treatment.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    died_on: Mapped[date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cause_category: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    suspected_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vet_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    disposal_method: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineMortality pig={self.pig_id} on={self.died_on} cause={self.cause_category}>"


class SwineIsolation(AGRIOSBase):
    """A historical isolation / quarantine period (Swine Doc 2 §15).

    Never a boolean flag — start, end, location, reason and clearance are recorded so
    disease tracing is possible. An open period has ``ended_on IS NULL``.
    """

    __tablename__ = "swine_isolation"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    pig_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    disease_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_disease_case.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    reason: Mapped[str] = mapped_column(String(20), nullable=False, default="observation")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    cleared_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    clearance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active" and self.ended_on is None

    def __repr__(self) -> str:
        return f"<SwineIsolation pig={self.pig_id} status={self.status} start={self.started_on}>"


class SwineBiosecurityRecord(AGRIOSBase):
    """An operational biosecurity record (Swine Doc 2 §15, Doc 5 §8): visitor and
    vehicle logs, equipment disinfection, staff sanitation, pen cleaning, rodent
    control, dead-stock disposal, quarantine and inspections.

    ``reminder_id`` is a soft link to a Greena Operations reminder/task (no FK) so
    recurring biosecurity routines integrate with Operations without coupling.
    """

    __tablename__ = "swine_biosecurity_record"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    record_type: Mapped[str] = mapped_column(String(30), nullable=False, default="inspection")
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    party_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_used: Mapped[str | None] = mapped_column(String(200), nullable=True)
    compliant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SwineBiosecurityRecord {self.record_type} on={self.occurred_on}>"
