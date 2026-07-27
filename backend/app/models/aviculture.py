"""
Greena — Aviculture Models (Module 15, Part 1: Foundation)

Individual-bird management for ornamental, exhibition, companion, conservation
and specialty birds (Doc 01). The aggregate root is :class:`AviBird` (Doc 03 §3);
every other entity ultimately references a bird or a breeding pair.

Design rules honoured here:
  * Everything inherits :class:`AGRIOSBase` → soft-delete only, JSONB metadata,
    audit timestamps. Lineage, medical history and ownership are never destroyed
    (Doc 02 §26, Doc 04 §6).
  * Species/breed/mutation are **data-driven catalog rows**, never hardcoded
    (Doc 02 §6-8, Doc 16). The module itself is registered in the existing
    ``species_profiles`` extensibility engine as ``species_key='aviculture'``.
  * Farm-scoped records carry ``farm_id`` (organisation isolation flows through
    ``farms.organization_id`` — same convention as Flock/Mission).
  * Enumerated fields are plain strings validated at the schema/service layer,
    with allowed values published as the ``*_VALUES`` tuples below (matching the
    Module 14 convention). No business calculations live in models.

Tables map 1:1 to Migration 053.
"""

import uuid
from datetime import date, datetime, timezone
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

SPECIES_GROUP_VALUES = (
    "parrot", "finch", "canary", "softbill", "pigeon", "dove", "quail",
    "pheasant", "peafowl", "waterfowl", "ornamental_chicken", "other",
)
MUTATION_INHERITANCE_VALUES = (
    "dominant", "recessive", "sex_linked", "co_dominant", "polygenic", "unknown",
)
AVIARY_TYPE_VALUES = (
    "indoor", "outdoor", "mixed", "flight", "walk_in", "cage", "brooder", "quarantine",
)
AVIARY_STATUS_VALUES = ("active", "inactive", "quarantine", "maintenance")
AVIARY_PURPOSE_VALUES = (
    "general", "breeding", "quarantine", "nursery", "display", "flight", "holding",
)
AVIARY_BIOSECURITY_VALUES = ("none", "standard", "high", "quarantine")

AVIARY_ZONE_TYPE_VALUES = ("zone", "section", "flight", "nursery", "holding", "other")
FIXTURE_TYPE_VALUES = (
    "nest_box", "perch", "feeder", "drinker", "feed_station", "water_station",
    "equipment", "plant", "other",
)
FIXTURE_STATUS_VALUES = ("active", "needs_maintenance", "out_of_service", "removed")
AVIARY_TASK_TYPE_VALUES = (
    "cleaning", "disinfection", "maintenance", "inspection", "repair", "other",
)
AVIARY_TASK_STATUS_VALUES = ("scheduled", "in_progress", "completed", "cancelled")
AVIARY_TASK_RECURRENCE_VALUES = (
    "none", "daily", "weekly", "monthly", "quarterly", "seasonal",
)

BIRD_SEX_VALUES = ("male", "female", "unknown")
BIRD_SEX_METHOD_VALUES = ("visual", "dna", "surgical", "estimated", "unknown")
BIRD_DNA_STATUS_VALUES = ("sexed", "unsexed", "pending", "unknown")
BIRD_LIFECYCLE_STAGE_VALUES = ("chick", "juvenile", "adult", "breeding", "retired", "unknown")
BIRD_STATUS_VALUES = ("active", "archived", "sold", "transferred", "deceased")
BIRD_ACQUISITION_TYPE_VALUES = ("bred", "purchased", "donated", "transferred", "unknown")

MUTATION_ZYGOSITY_VALUES = ("visual", "split", "homozygous", "heterozygous", "unknown")

PAIR_FORMATION_TYPE_VALUES = ("natural", "artificial")
PAIR_STATUS_VALUES = ("active", "suspended", "dissolved")

BREEDING_STRATEGY_VALUES = (
    "outcross", "line_breeding", "inbreeding", "conservation", "exhibition", "mixed",
)
BREEDING_PROGRAM_STATUS_VALUES = ("active", "paused", "completed", "archived")
BREEDING_GOAL_STATUS_VALUES = ("open", "achieved", "abandoned")
PAIR_EVENT_TYPE_VALUES = ("formed", "suspended", "resumed", "dissolved", "clutch", "note")

# Incubation (Part 5)
EGG_FERTILITY_VALUES = ("unknown", "fertile", "infertile", "early_death", "late_death")
EGG_QUALITY_VALUES = ("good", "fair", "poor", "cracked", "damaged", "soft_shell")
EGG_SOURCE_VALUES = ("natural", "artificial", "foster")
EGG_STATUS_VALUES = (
    "collected", "stored", "set", "candled", "lockdown", "hatched", "failed", "discarded",
)
INCUBATION_METHOD_VALUES = ("natural", "artificial", "foster")
INCUBATION_BATCH_STATUS_VALUES = ("setting", "incubating", "lockdown", "completed", "cancelled")
CANDLING_RESULT_VALUES = (
    "developing", "fertile", "infertile", "early_death", "late_death", "unclear",
)
HATCH_OUTCOME_VALUES = ("hatched", "assisted", "dead_in_shell", "failed", "discarded")

OWNER_TYPE_VALUES = ("internal", "customer", "supplier", "breeder", "other")
OWNERSHIP_ACQUISITION_VALUES = ("bred", "purchased", "transferred", "donated", "unknown")

# Bird timeline event types (Doc 06 §4). Append-only history.
BIRD_EVENT_TYPE_VALUES = (
    "created", "updated", "status_changed", "archived", "restored",
    "transferred", "sold", "purchased", "died", "paired", "unpaired",
    "media_added", "document_added", "health_recorded", "note",
)

MEDIA_TYPE_VALUES = ("photo", "video", "audio")
DOCUMENT_TYPE_VALUES = (
    "dna_certificate", "health_certificate", "import_permit", "export_permit",
    "lab_report", "ownership", "invoice", "contract", "other",
)
HEALTH_RECORD_TYPE_VALUES = (
    "observation", "exam", "weight", "treatment", "medication", "vaccination",
    "deworming", "supplement", "vet_visit", "lab_report", "surgery", "injury",
    "quarantine", "necropsy", "preventive", "biosecurity",
)
HEALTH_RECORD_STATUS_VALUES = ("recorded", "open", "ongoing", "resolved")
HEALTH_SEVERITY_VALUES = ("info", "mild", "moderate", "severe", "critical")
QUARANTINE_STATUS_VALUES = ("active", "released")
DISEASE_EVENT_STATUS_VALUES = ("suspected", "confirmed", "contained", "resolved")

# Valuation (Part 7)
VALUATION_METHOD_VALUES = (
    "appraised", "market", "insured", "purchase", "sale", "breeding_value",
)

# Workflows (Part 9)
WORKFLOW_TYPE_VALUES = (
    "intake", "quarantine", "treatment", "incubation", "sale", "purchase",
    "transfer", "exhibition",
)
WORKFLOW_STATUS_VALUES = ("active", "completed", "cancelled")

# Bird statuses that count as "no longer in the active collection" (Doc 02 §4).
BIRD_TERMINAL_STATUSES = ("sold", "transferred", "deceased")


# ── Catalog: Species ──────────────────────────────────────────────────────────

class AviSpecies(AGRIOSBase):
    """Data-driven bird species catalog (Doc 02 §6, Doc 16 §4).

    ``organization_id IS NULL`` marks a global/system entry shared by every
    organisation; a non-null value is an organisation's custom species.
    """

    __tablename__ = "avi_species"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    common_name: Mapped[str] = mapped_column(String(150), nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    species_group: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    conservation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    breeds: Mapped[list["AviBreed"]] = relationship(
        back_populates="species", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AviSpecies {self.common_name} group={self.species_group}>"


class AviBreed(AGRIOSBase):
    """A breed within a species (Doc 02 §7, Doc 16 §3)."""

    __tablename__ = "avi_breed"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    species_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    species: Mapped["AviSpecies"] = relationship(back_populates="breeds", lazy="noload")

    def __repr__(self) -> str:
        return f"<AviBreed {self.name} species={self.species_id}>"


class AviMutation(AGRIOSBase):
    """A genetic mutation / trait (Doc 02 §8). Recorded, never invented (Doc 04 §7)."""

    __tablename__ = "avi_mutation"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    inheritance: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<AviMutation {self.name} inheritance={self.inheritance}>"


# ── Infrastructure: Aviary ────────────────────────────────────────────────────

class AviAviary(AGRIOSBase):
    """Housing infrastructure (Doc 02 §15). Table only in Part 1; Part 3 adds
    zones, nest boxes, feeders, cleaning and environmental records."""

    __tablename__ = "avi_aviary"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aviary_type: Mapped[str] = mapped_column(String(40), nullable=False, default="mixed")
    building: Mapped[str | None] = mapped_column(String(150), nullable=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    biosecurity_level: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    environment: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    zones: Mapped[list["AviAviaryZone"]] = relationship(
        back_populates="aviary", cascade="all, delete-orphan", lazy="noload"
    )
    fixtures: Mapped[list["AviAviaryFixture"]] = relationship(
        back_populates="aviary", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AviAviary '{self.name}' farm={self.farm_id} purpose={self.purpose}>"


# ── Aggregate root: Bird ──────────────────────────────────────────────────────

class AviBird(AGRIOSBase):
    """The individual bird — aggregate root of the Aviculture module (Doc 03 §3).

    Pedigree is stored as deterministic parent links (``sire_id``/``dam_id``);
    unknown ancestry stays NULL and is never invented (Doc 04 §4). The Pedigree
    engine (Part 4) computes ancestry/inbreeding from these links.
    """

    __tablename__ = "avi_bird"
    __table_args__ = (
        UniqueConstraint("farm_id", "internal_ref", name="uq_avi_bird_farm_internal_ref"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    species_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_breed.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    aviary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Identity (Doc 02 §5)
    internal_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ring_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    band_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    microchip: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    colour_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sex: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    sex_method: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    dna_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    hatch_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    hatch_date_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Pedigree links (deterministic; Doc 04 §4)
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Lifecycle (Doc 02 §4)
    lifecycle_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships (all lazy=noload; services opt in explicitly)
    species: Mapped["AviSpecies"] = relationship(foreign_keys=[species_id], lazy="noload")
    breed: Mapped["AviBreed | None"] = relationship(foreign_keys=[breed_id], lazy="noload")
    aviary: Mapped["AviAviary | None"] = relationship(foreign_keys=[aviary_id], lazy="noload")
    sire: Mapped["AviBird | None"] = relationship(
        foreign_keys=[sire_id], remote_side="AviBird.id", lazy="noload"
    )
    dam: Mapped["AviBird | None"] = relationship(
        foreign_keys=[dam_id], remote_side="AviBird.id", lazy="noload"
    )
    mutations: Mapped[list["AviBirdMutation"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )
    media: Mapped[list["AviBirdMedia"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["AviBirdDocument"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )
    health_records: Mapped[list["AviHealthRecord"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )
    ownership_records: Mapped[list["AviBirdOwnership"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )
    events: Mapped[list["AviBirdEvent"]] = relationship(
        back_populates="bird", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_in_collection(self) -> bool:
        """True while the bird is part of the live, active collection."""
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<AviBird {self.internal_ref} name={self.name!r} status={self.status}>"


class AviBirdMutation(AGRIOSBase):
    """Recorded genetics for a bird (M:N with zygosity). Facts only (Doc 04 §7)."""

    __tablename__ = "avi_bird_mutation"
    __table_args__ = (
        UniqueConstraint("bird_id", "mutation_id", name="uq_avi_bird_mutation"),
    )

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    mutation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_mutation.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    zygosity: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="mutations", lazy="noload")
    mutation: Mapped["AviMutation"] = relationship(foreign_keys=[mutation_id], lazy="noload")


# ── Breeding: Pair ────────────────────────────────────────────────────────────

class AviPair(AGRIOSBase):
    """A breeding pair — a first-class entity, not merely two birds (Doc 02 §10).

    Dissolution is a soft status change; historical pairings are permanent
    records (Doc 04 §3). Bird references use SET NULL so a bird's soft-deletion
    or reassignment never destroys the pair's history.
    """

    __tablename__ = "avi_pair"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    male_bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    female_bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    formation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="natural")
    formed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    dissolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    dissolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_breeding_program.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    male_bird: Mapped["AviBird | None"] = relationship(foreign_keys=[male_bird_id], lazy="noload")
    female_bird: Mapped["AviBird | None"] = relationship(foreign_keys=[female_bird_id], lazy="noload")

    def __repr__(self) -> str:
        return f"<AviPair {self.name!r} status={self.status} farm={self.farm_id}>"


# ── Media & Documents ─────────────────────────────────────────────────────────

class AviBirdMedia(AGRIOSBase):
    """Photo / video / audio attached to a bird (Doc 03 §14)."""

    __tablename__ = "avi_bird_media"

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="photo")
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    taken_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="media", lazy="noload")


class AviBirdDocument(AGRIOSBase):
    """A document attached to a bird (DNA cert, permit, lab report, invoice…).

    Protected documents may be restricted independently of the bird (Doc 10 §7);
    ``expires_on`` drives permit-renewal reminders (Doc 11 §5).
    """

    __tablename__ = "avi_bird_document"

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    is_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="documents", lazy="noload")


# ── Health (foundation; Part 6 Health Engine extends) ─────────────────────────

class AviHealthRecord(AGRIOSBase):
    """A permanent health log entry for a bird (Doc 04 §6 — never removed).

    Part 1 provides the historical table so a bird's medical timeline exists from
    day one; the full Health Engine (weights, vaccinations, treatments, quarantine,
    laboratory reports, necropsy) is built out in Part 6.
    """

    __tablename__ = "avi_health_record"

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    record_type: Mapped[str] = mapped_column(String(30), nullable=False, default="observation")
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    body_condition: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recorded")
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="health_records", lazy="noload")


# ── Collection Management (Part 2) ────────────────────────────────────────────

class AviBirdOwnership(AGRIOSBase):
    """A single link in a bird's chain of custody (Doc 02 §26).

    Ownership is append-only: a change closes the current record (``to_date`` +
    ``is_current=False``) and opens a new one. History is never overwritten.
    """

    __tablename__ = "avi_bird_ownership"

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    owner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_contact: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    acquisition: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    to_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="ownership_records", lazy="noload")

    def __repr__(self) -> str:
        return f"<AviBirdOwnership bird={self.bird_id} owner={self.owner_name!r} current={self.is_current}>"


class AviBirdEvent(AGRIOSBase):
    """One immutable entry in a bird's timeline (Doc 06 §4, Doc 02 §4).

    Every meaningful change appends an event. ``data`` holds structured recorded
    facts (counterparty, price, document ids, field changes) — never a
    calculation. The timeline is the audit-friendly life history of the bird.
    """

    __tablename__ = "avi_bird_event"

    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    bird: Mapped["AviBird"] = relationship(back_populates="events", lazy="noload")

    def __repr__(self) -> str:
        return f"<AviBirdEvent bird={self.bird_id} type={self.event_type} on={self.occurred_on}>"


# ── Aviary Management (Part 3) ────────────────────────────────────────────────

class AviAviaryZone(AGRIOSBase):
    """A subdivision of an aviary — a zone, section, flight or nursery (Doc 02 §15)."""

    __tablename__ = "avi_aviary_zone"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(30), nullable=False, default="zone")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    aviary: Mapped["AviAviary"] = relationship(back_populates="zones", lazy="noload")


class AviAviaryFixture(AGRIOSBase):
    """Physical infrastructure inside an aviary — nest boxes, perches, feeders,
    drinkers, feed/water stations, equipment, plants (Doc 02 §15, Doc 03 §7).

    A single discriminated table (``fixture_type``) rather than many near-identical
    ones — the same modelling choice used for the timeline events."""

    __tablename__ = "avi_aviary_fixture"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary_zone.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    fixture_type: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    aviary: Mapped["AviAviary"] = relationship(back_populates="fixtures", lazy="noload")


class AviEnvironmentalReading(AGRIOSBase):
    """A point-in-time environmental measurement for an aviary (Doc 02 §15, Doc 16 §8).

    Recorded facts only. The pure engine summarises these against species targets;
    it never invents a reading."""

    __tablename__ = "avi_environmental_reading"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  default=lambda: datetime.now(timezone.utc))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    light_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    air_quality: Mapped[str | None] = mapped_column(String(50), nullable=True)
    noise_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AviAviaryTask(AGRIOSBase):
    """A cleaning or maintenance task for an aviary — schedule and history in one
    record (Doc 11 §5-6). Recurrence lets it seed the next occurrence."""

    __tablename__ = "avi_aviary_task"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="scheduled")
    scheduled_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AviAviaryEvent(AGRIOSBase):
    """One immutable entry in an aviary's timeline (Doc 06 §5)."""

    __tablename__ = "avi_aviary_event"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AviAviaryMedia(AGRIOSBase):
    """Photo / video / document attached to an aviary (Doc 03 §14)."""

    __tablename__ = "avi_aviary_media"

    aviary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="photo")
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# ── Breeding programmes (Part 4) ──────────────────────────────────────────────

class AviBreedingProgram(AGRIOSBase):
    """An objective-driven breeding programme (Doc 02 §11). Pedigrees and genetic
    calculations are NOT stored here — they are computed live by the pedigree
    engine. This entity holds the *intent* (objective, strategy, target traits)."""

    __tablename__ = "avi_breeding_program"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    strategy: Mapped[str] = mapped_column(String(30), nullable=False, default="outcross")
    target_traits: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    goals: Mapped[list["AviBreedingGoal"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<AviBreedingProgram {self.name!r} strategy={self.strategy}>"


class AviBreedingGoal(AGRIOSBase):
    """A measurable goal within a breeding programme."""

    __tablename__ = "avi_breeding_goal"

    program_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_breeding_program.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    target_metric: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped["AviBreedingProgram"] = relationship(back_populates="goals", lazy="noload")


class AviPairEvent(AGRIOSBase):
    """One immutable entry in a breeding pair's history (Doc 03 §5 PairHistory)."""

    __tablename__ = "avi_pair_event"

    pair_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_pair.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# ── Incubation (Part 5) ───────────────────────────────────────────────────────

class AviClutch(AGRIOSBase):
    """A group of eggs laid by a pair (Doc 02 §16). Eggs reference their clutch."""

    __tablename__ = "avi_clutch"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    pair_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_pair.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    laid_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_eggs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AviIncubationBatch(AGRIOSBase):
    """An incubation run (Doc 02 §13). Its schedule (lockdown, hatch, turning,
    targets) is computed deterministically by the incubation engine from the
    species profile — never stored as a source of truth beyond the snapshot."""

    __tablename__ = "avi_incubation_batch"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="artificial")
    incubator_label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    set_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    incubation_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    target_humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    expected_lockdown_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_hatch_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    turning_schedule: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="setting")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AviEgg(AGRIOSBase):
    """The individual egg — aggregate of the hatch process (Doc 03 §6). Every
    lifecycle transition is timestamped; history is never destroyed (Doc 04 §5)."""

    __tablename__ = "avi_egg"
    __table_args__ = (
        UniqueConstraint("farm_id", "identifier", name="uq_avi_egg_farm_identifier"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    clutch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_clutch.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_incubation_batch.id", ondelete="SET NULL"), nullable=True, index=True)
    pair_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_pair.id", ondelete="SET NULL"), nullable=True, index=True)
    species_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_species.id", ondelete="SET NULL"), nullable=True, index=True)
    identifier: Mapped[str] = mapped_column(String(50), nullable=False)
    laid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    fertility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="good")
    storage_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="natural")
    set_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collected")
    hatched_bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<AviEgg {self.identifier} status={self.status}>"


class AviIncubationLog(AGRIOSBase):
    """A daily temperature / humidity / turning log entry for a batch (Doc 02 §13)."""

    __tablename__ = "avi_incubation_log"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_incubation_batch.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    turns_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AviCandlingRecord(AGRIOSBase):
    """A candling observation for an egg (Doc 02 §13). Recorded fact only."""

    __tablename__ = "avi_candling_record"

    egg_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_egg.id", ondelete="CASCADE"), nullable=False, index=True)
    candled_on: Mapped[date] = mapped_column(Date, nullable=False)
    day_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="unclear")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AviHatchEvent(AGRIOSBase):
    """A hatch or failure for an egg (Doc 02 §14). Links the chick it produced."""

    __tablename__ = "avi_hatch_event"

    egg_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_egg.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_incubation_batch.id", ondelete="SET NULL"), nullable=True, index=True)
    hatched_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    assisted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    chick_bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True)
    hatch_weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(150), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ── Health Engine (Part 6) ────────────────────────────────────────────────────

class AviQuarantine(AGRIOSBase):
    """A quarantine / isolation episode for a bird (Doc 02 §17, Doc 03 §8)."""

    __tablename__ = "avi_quarantine"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    bird_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True)
    aviary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="SET NULL"), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    expected_end_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class AviDiseaseEvent(AGRIOSBase):
    """A farm-level disease / outbreak / biosecurity event (Doc 09 §12, Doc 11)."""

    __tablename__ = "avi_disease_event"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    aviary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_aviary.id", ondelete="SET NULL"), nullable=True, index=True)
    disease_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suspected")
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    affected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_notifiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ── Valuation (Part 7) ────────────────────────────────────────────────────────

class AviValuation(AGRIOSBase):
    """A recorded valuation of a bird (or the whole collection). A recorded fact
    only — the collection value is *computed* by the pure valuation engine, never
    stored (Doc 14 §2, Doc 13 Part 7). Not an expense or revenue, so it does not
    belong in the shared finance ledger."""

    __tablename__ = "avi_valuation"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=True, index=True)
    valued_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="KES")
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="appraised")
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


# ── Workflows (Part 9) ────────────────────────────────────────────────────────

class AviWorkflow(AGRIOSBase):
    """A staged operational process on a bird/entity (Doc 11 §8). Stage templates
    and valid transitions are deterministic (in the pure automation engine); this
    table records the current position and, via events, the permanent history."""

    __tablename__ = "avi_workflow"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    bird_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(30), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        return f"<AviWorkflow {self.workflow_type} stage={self.current_stage} status={self.status}>"


class AviWorkflowEvent(AGRIOSBase):
    """One immutable stage transition in a workflow's history (Doc 11 §8)."""

    __tablename__ = "avi_workflow_event"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("avi_workflow.id", ondelete="CASCADE"), nullable=False, index=True)
    from_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
