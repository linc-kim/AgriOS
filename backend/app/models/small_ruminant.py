"""
Greena — Small Ruminant Models (Modules 18 Goat + 19 Sheep, Milestone 1: Foundation)

A **single** Small Ruminant foundation shared by two species — goat and sheep —
rather than two parallel modules (the directive's core principle). Every
animal-facing table carries a ``species`` discriminator ('goat' | 'sheep'); the
per-species vocabulary and biology live in
:mod:`app.services.small_ruminant_species_config`. Goat-specific dairy and
sheep-specific wool arrive as later milestones on this same schema.

Like Aviculture (Module 15) and Rabbit (Module 17), the aggregate root is the
**individual animal** (:class:`SmallRuminant`); every operational record
ultimately references one animal, a group or a housing location.

Design rules honoured here (mirroring the Rabbit / Aviculture / BSF modules):
  * Everything inherits :class:`AGRIOSBase` → soft-delete only, JSONB metadata,
    audit timestamps. Pedigree, movement, medical and ownership history are never
    destroyed (Goat Doc 2 §2/§21).
  * Breed reference is a **data-driven catalog row** (:class:`SmallRuminantBreed`),
    never hardcoded (Goat Doc 2 §7). The subsystem registers itself in the existing
    ``species_profiles`` extensibility engine as ``goat`` and ``sheep``.
  * Farm-scoped records carry ``farm_id``; organisation isolation flows through
    ``farms.organization_id`` — the same convention as Flock / Aviculture / BSF /
    Rabbit. The breed catalog carries a nullable ``organization_id`` (NULL = global
    system catalog shared by every organisation).
  * Structure follows the specification hierarchy (Goat Doc 1 §5, Doc 2 §3):
    Farm → Herd/Flock → Group → Pen / Pasture → Individual. Animal-and-genetics
    tables (breed/bloodline/herd/group) are species-scoped; physical infrastructure
    (pen/pasture) is farm-scoped and species-neutral so a barn or paddock can be
    shared (e.g. co-grazing). Occupancy is DERIVED from ``sr_animal`` location FKs
    and never stored (the Housing engine, Milestone 2, computes it).
  * Enumerated fields are plain strings validated at the schema/service layer, with
    allowed values published as the ``*_VALUES`` tuples below. No business
    calculations live in models — those belong to the deterministic engines.

Tables map 1:1 to Migration 072.
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

# The species discriminator vocabulary is owned by the pure config module so
# migrations, models and engines share one source of truth.
SPECIES_VALUES = ("goat", "sheep")

# ── Allowed enumerated values (validated at the schema/service layer) ─────────

# Breed catalog (Goat Doc 2 §7). Breeds are species-specific (a Saanen is a goat,
# a Merino is a sheep) so the catalog carries the ``species`` discriminator.
BREED_CATEGORY_VALUES = (
    "dairy", "meat", "fiber", "wool", "dual_purpose", "indigenous",
    "heritage", "show", "crossbreed", "other",
)
BREED_PURPOSE_VALUES = ("meat", "dairy", "fiber", "wool", "breeding", "mixed")

# Herd / flock (Goat Doc 1 §8, Doc 2 §6). One management container per species.
HERD_TYPE_VALUES = (
    "breeding", "dairy", "meat", "fiber", "wool", "mixed",
    "replacement", "commercial", "other",
)
HERD_STATUS_VALUES = ("active", "inactive", "archived")

# Group — dynamic production/management grouping within a herd (Goat Doc 1 §7-8).
GROUP_TYPE_VALUES = (
    "breeding", "milking", "dry", "lactating", "growing", "weaning",
    "replacement", "quarantine", "isolation", "sale", "males", "females",
    "young", "general", "other",
)
GROUP_STATUS_VALUES = ("active", "inactive", "archived")

# Physical housing (Goat Doc 2 §14-15). Species-neutral farm infrastructure.
PEN_TYPE_VALUES = (
    "barn", "pen", "shed", "paddock", "shelter", "yard",
    "quarantine", "isolation", "kidding_pen", "lambing_pen", "other",
)
PEN_STATUS_VALUES = ("available", "occupied", "maintenance", "cleaning", "out_of_service")
PASTURE_STATUS_VALUES = ("available", "grazing", "resting", "closed", "maintenance")

# Animal identity / classification (Goat Doc 2 §5). ``sex`` is a species-restricted
# token — the union across species is validated per-species against the config's
# ``allowed_sex_values`` (goat: buck/doe/wether; sheep: ram/ewe/wether).
SEX_VALUES = ("buck", "doe", "ram", "ewe", "wether", "unknown")
PURPOSE_VALUES = (
    "meat", "dairy", "fiber", "wool", "breeding", "show", "pet",
    "replacement", "genetic_improvement", "conservation", "educational",
    "mixed", "unknown",
)
HORN_STATUS_VALUES = ("horned", "polled", "disbudded", "scurred", "dehorned", "unknown")
REGISTRATION_STATUS_VALUES = (
    "registered", "unregistered", "pending", "commercial", "recorded", "unknown",
)
# Birth type — number born at parturition (Goat Doc 2 §5, §9).
BIRTH_TYPE_VALUES = (
    "single", "twin", "triplet", "quadruplet", "quintuplet", "unknown",
)

# Lifecycle & reproduction (Goat Doc 1 §9, Doc 2 §5). Stages are generic; the
# young-animal display noun (kid / lamb) comes from the species config.
LIFECYCLE_STAGE_VALUES = (
    "newborn", "weaner", "grower", "yearling", "replacement",
    "breeding_adult", "mature", "cull", "retired", "unknown",
)
STATUS_VALUES = ("active", "sold", "transferred", "deceased", "culled", "archived")
# Statuses that count as "no longer in the active herd/flock" (Goat Doc 2 §2).
TERMINAL_STATUSES = ("sold", "transferred", "deceased", "culled")
REPRODUCTIVE_STATUS_VALUES = (
    "not_bred", "bred", "pregnant", "lactating", "open", "dry", "resting",
    "proven", "unproven", "unknown",
)
FERTILITY_STATUS_VALUES = ("fertile", "infertile", "unproven", "unknown")
ACQUISITION_TYPE_VALUES = ("bred", "purchased", "donated", "transferred", "unknown")

# Animal timeline event types (Goat Doc 2 §18). Append-only history. Covers the
# whole shared lifecycle plus species-specific events (kidding/lambing, shearing,
# milk) so later milestones need no schema change to this table.
EVENT_TYPE_VALUES = (
    "created", "updated", "status_changed", "archived", "restored", "moved",
    "transferred", "sold", "purchased", "died", "culled", "bred",
    "pregnancy_checked", "kidded", "lambed", "weaned", "weight_recorded",
    "milk_recorded", "sheared", "health_recorded", "vaccination_recorded",
    "deworming_recorded", "hoof_care_recorded", "media_added", "document_added",
    "note",
)

MEDIA_TYPE_VALUES = ("photo", "video", "audio")
DOCUMENT_TYPE_VALUES = (
    "pedigree_certificate", "health_certificate", "registration", "lab_report",
    "vet_report", "movement_record", "purchase_record", "sale_document",
    "invoice", "other",
)

# ── Breeding cycle (Goat Doc 2 §8, Doc 3 §7) — Milestone 3 ─────────────────────
# Embryo transfer is schema-ready but deferred (Goat Doc 2 §8 "future-ready").
BREEDING_METHOD_VALUES = ("natural", "artificial", "embryo_transfer")
BREEDING_STATUS_VALUES = (
    "planned", "serviced", "pregnant", "not_pregnant", "birthed", "failed", "closed", "cancelled",
)
PREGNANCY_RESULT_VALUES = ("unknown", "pregnant", "not_pregnant")
BREEDING_OUTCOME_VALUES = ("successful", "failed", "aborted", "reabsorbed", "unknown")

# Birth (kidding / lambing) record (Goat Doc 2 §9). One row per parturition.
BIRTH_STATUS_VALUES = ("active", "weaned", "closed")
COLOSTRUM_STATUS_VALUES = ("received", "partial", "not_received", "unknown")

# Growth & feed (Goat Doc 2 §11, §13) — Milestone 4. Weights in kilograms.
WEIGHT_METHOD_VALUES = ("scale", "tape", "estimate", "unknown")
BODY_CONDITION_MIN = 1  # BCS 1–5 scale for small ruminants (Goat Doc 2 §11)
BODY_CONDITION_MAX = 5
FEED_UNIT_VALUES = ("kg", "g", "bale", "flake")

# Health, vaccination, deworming, hoof care & mortality (Goat Doc 2 §12/§15/§16) — M5
HEALTH_EVENT_TYPE_VALUES = (
    "observation", "exam", "illness", "injury", "treatment", "medication",
    "surgery", "vet_visit", "recovery", "quarantine", "isolation", "lab_result", "note",
)
HEALTH_STATUS_VALUES = ("recorded", "open", "ongoing", "resolved")
HEALTH_SEVERITY_VALUES = ("info", "mild", "moderate", "severe", "critical")
# Deworming (Goat Doc 1 §12, Doc 2 §12) — parasite control is first-class for
# small ruminants; FAMACHA is a recorded anaemia score (1–5), never inferred.
DEWORMING_METHOD_VALUES = ("oral_drench", "injectable", "pour_on", "bolus", "feed_additive", "other")
FAMACHA_MIN = 1
FAMACHA_MAX = 5
# Hoof care (Goat Doc 2 §15). Lameness is a recorded score (0–5), never inferred.
HOOF_ACTION_VALUES = ("inspection", "trimming", "treatment", "foot_bath", "other")
HOOF_CONDITION_VALUES = ("healthy", "overgrown", "foot_rot", "foot_scald", "abscess", "injury", "other", "unknown")
# Mortality (Goat Doc 2 §16)
MORTALITY_CAUSE_VALUES = (
    "disease", "parasites", "injury", "predation", "environmental", "congenital",
    "digestive", "respiratory", "dystocia", "poisoning", "heat_stress", "starvation",
    "unknown", "other",
)

# Dairy — lactation & milk (Goat Doc 2 §10) — Milestone 6. Gated by the species
# ``produces_milk`` capability (goats primarily; dairy sheep also supported).
LACTATION_STATUS_VALUES = ("active", "dry", "completed")
MILK_SESSION_VALUES = ("am", "pm", "midday", "total", "once")


# ── Catalog: Breed (Goat Doc 2 §7) ─────────────────────────────────────────────

class SmallRuminantBreed(AGRIOSBase):
    """Data-driven breed catalog, species-scoped (Goat Doc 2 §7).

    Reference data only — operational records never overwrite breed values.
    ``organization_id IS NULL`` marks a global/system entry shared by every
    organisation; a non-null value is an organisation's custom breed. ``profile``
    (JSONB) holds the rich, extensible reference: adult weight range, milk/growth/
    fiber characteristics, temperament, climate suitability, production benchmarks
    and an optional ``gestation_days`` override read by the breeding engine.
    """

    __tablename__ = "sr_breed"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
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
        return f"<SmallRuminantBreed {self.species}:{self.name!r} category={self.category}>"


# ── Catalog: Bloodline / genetic line (Goat Doc 2 §7, §19) ─────────────────────

class SmallRuminantBloodline(AGRIOSBase):
    """A named genetic line / bloodline within a farm, species-scoped.

    Bloodlines group animals for genetic tracking and performance-based selection;
    the Genetics engine (Milestone 3) evaluates line performance. Farm-scoped: a
    bloodline belongs to one farm's breeding programme.
    """

    __tablename__ = "sr_bloodline"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_sr_bloodline_farm_code"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_breed.id", ondelete="SET NULL"),
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
        return f"<SmallRuminantBloodline {self.species}:{self.name!r}>"


# ── Management grouping (Goat Doc 1 §8, Doc 2 §6) ──────────────────────────────
# Herd/Flock → Group. Species-scoped: a herd is "the goat herd" or "the flock".

class SmallRuminantHerd(AGRIOSBase):
    """The top-level management container — a herd (goat) or flock (sheep).

    Species-scoped; the display noun (herd/flock) comes from the species config.
    A herd contains dynamic groups and production categories; membership of the
    animals below it changes over time without destroying history (Goat Doc 2 §6).
    """

    __tablename__ = "sr_herd"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_sr_herd_farm_code"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
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
        return f"<SmallRuminantHerd {self.species}:{self.name!r} type={self.herd_type}>"


class SmallRuminantGroup(AGRIOSBase):
    """A dynamic production/management group within a herd (Goat Doc 1 §7-8).

    Groups model the specification's dynamic categories — breeding groups, milking
    groups, dry does, quarantine/isolation, sale groups, etc. Membership is dynamic
    (via ``sr_animal.group_id``); an animal moves between groups without losing
    history. Species-scoped and optionally nested under a herd.
    """

    __tablename__ = "sr_group"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_sr_group_farm_code"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    herd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_herd.id", ondelete="SET NULL"),
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
        return f"<SmallRuminantGroup {self.species}:{self.name!r} type={self.group_type}>"


# ── Physical housing (Goat Doc 2 §14-15) — species-neutral farm infrastructure ─
# Pens (barns/sheds/paddocks) and pastures can be shared across species (e.g.
# co-grazing), so they are farm-scoped, not species-scoped. Occupancy is DERIVED
# from the animals located here and never stored.

class SmallRuminantPen(AGRIOSBase):
    """A physical housing unit — barn, pen, shed, shelter, paddock, quarantine or
    isolation unit, or a dedicated kidding/lambing pen (Goat Doc 2 §14).

    ``capacity`` is the maximum head; occupancy is DERIVED from the count of active
    animals with ``pen_id`` pointing here (the Housing engine, Milestone 2). Shared
    across species — a pen is a pen.
    """

    __tablename__ = "sr_pen"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_sr_pen_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pen_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pen")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantPen {self.name!r} type={self.pen_type} status={self.status}>"


class SmallRuminantPasture(AGRIOSBase):
    """A grazing area / paddock (Goat Doc 2 §14).

    Carries area and carrying capacity for the Grazing engine (a later milestone):
    rotation timing, grazing pressure, overstock risk. ``carrying_capacity`` is a
    recorded reference; occupancy is DERIVED from animals with ``pasture_id`` here.
    Rotation schedule / rest-period detail lives in ``profile`` (JSONB).
    """

    __tablename__ = "sr_pasture"
    __table_args__ = (
        UniqueConstraint("farm_id", "code", name="uq_sr_pasture_farm_code"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    area_hectares: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    carrying_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grass_species: Mapped[str | None] = mapped_column(String(255), nullable=True)
    browse_species: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantPasture {self.name!r} status={self.status}>"


# ── Aggregate root: SmallRuminant animal (Goat Doc 2 §2, §5) ───────────────────

class SmallRuminant(AGRIOSBase):
    """The individual small-ruminant animal — aggregate root of the subsystem.

    One shared model for goats and sheep, distinguished by ``species``. Pedigree is
    stored as deterministic parent links (``sire_id``/``dam_id``); unknown ancestry
    stays NULL and is never invented (Goat Doc 2 §19). Location is expressed as
    optional group (management) and pen/pasture (physical) links — an animal moves
    freely without losing history. ``current_weight_kg`` mirrors the latest weight
    record for fast display; authoritative weight history lives in the weight table
    (Milestone 4).
    """

    __tablename__ = "sr_animal"
    __table_args__ = (
        UniqueConstraint("farm_id", "internal_ref", name="uq_sr_animal_farm_internal_ref"),
        UniqueConstraint("farm_id", "ear_tag", name="uq_sr_animal_farm_ear_tag"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_breed.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    bloodline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_bloodline.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    herd_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_herd.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_group.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    pen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_pen.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    pasture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_pasture.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Birth event this animal was born in (Goat Doc 2 §9; added in Migration 073).
    # Offspring keep this link permanently. SET NULL preserves the animal if the
    # birth record is ever removed.
    birth_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_birth.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Identity (Goat Doc 1 §6, Doc 2 §5)
    internal_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ear_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tattoo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    rfid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visual_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Classification (Goat Doc 2 §5)
    variety: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sex: Mapped[str] = mapped_column(String(10), nullable=False, default="unknown")
    purpose: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    purposes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    horn_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    registration_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")

    # Biology (Goat Doc 2 §5). Weights in kilograms (small-ruminant scale).
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    dob_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    birth_type: Mapped[str] = mapped_column(String(15), nullable=False, default="unknown")
    birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    current_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)

    # Lifecycle & reproduction (Goat Doc 1 §9, Doc 2 §5)
    lifecycle_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    reproductive_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    fertility_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Pedigree links (deterministic; Goat Doc 2 §19). Unknown ancestry stays NULL.
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships (all lazy=noload; services opt in explicitly)
    breed: Mapped["SmallRuminantBreed | None"] = relationship(foreign_keys=[breed_id], lazy="noload")
    bloodline: Mapped["SmallRuminantBloodline | None"] = relationship(foreign_keys=[bloodline_id], lazy="noload")
    herd: Mapped["SmallRuminantHerd | None"] = relationship(foreign_keys=[herd_id], lazy="noload")
    group: Mapped["SmallRuminantGroup | None"] = relationship(foreign_keys=[group_id], lazy="noload")
    pen: Mapped["SmallRuminantPen | None"] = relationship(foreign_keys=[pen_id], lazy="noload")
    pasture: Mapped["SmallRuminantPasture | None"] = relationship(foreign_keys=[pasture_id], lazy="noload")
    sire: Mapped["SmallRuminant | None"] = relationship(
        foreign_keys=[sire_id], remote_side="SmallRuminant.id", lazy="noload"
    )
    dam: Mapped["SmallRuminant | None"] = relationship(
        foreign_keys=[dam_id], remote_side="SmallRuminant.id", lazy="noload"
    )
    events: Mapped[list["SmallRuminantEvent"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan", lazy="noload"
    )
    media: Mapped[list["SmallRuminantMedia"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["SmallRuminantDocument"]] = relationship(
        back_populates="animal", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_in_herd(self) -> bool:
        """True while the animal is part of the live, active herd/flock."""
        return self.status == "active"

    def __repr__(self) -> str:
        return (
            f"<SmallRuminant {self.species}:{self.internal_ref} "
            f"name={self.name!r} sex={self.sex} status={self.status}>"
        )


# ── Immutable history: animal timeline (Goat Doc 2 §18) ────────────────────────

class SmallRuminantEvent(AGRIOSBase):
    """Append-only operational timeline for an animal (created, moved, bred, kidded/
    lambed, weaned, sheared, note…). Complements platform Timeline/Audit; carries
    species-specific payload in ``details`` (JSONB). History is never edited."""

    __tablename__ = "sr_event"

    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, default="note")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    animal: Mapped["SmallRuminant"] = relationship(back_populates="events", lazy="noload")

    def __repr__(self) -> str:
        return f"<SmallRuminantEvent animal={self.animal_id} type={self.event_type}>"


# ── Attachments (Goat Doc 2 §17; reuse Greena file platform) ───────────────────

class SmallRuminantMedia(AGRIOSBase):
    """Photos / videos / audio for an animal. Binary lives in the platform file
    store; this row references it (storage_path/url), mirroring rabbit_media."""

    __tablename__ = "sr_media"

    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"),
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

    animal: Mapped["SmallRuminant"] = relationship(back_populates="media", lazy="noload")


class SmallRuminantDocument(AGRIOSBase):
    """Pedigree certificates, movement records, vet reports, invoices and other
    documents attached to an animal (Goat Doc 2 §17)."""

    __tablename__ = "sr_document"

    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"),
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

    animal: Mapped["SmallRuminant"] = relationship(back_populates="documents", lazy="noload")


# ── Breeding cycle (Goat Doc 2 §8, Doc 3 §7) — Milestone 3 ──────────────────────

class SmallRuminantBreeding(AGRIOSBase):
    """A single mating cycle: service → pregnancy check → birth (Goat Doc 2 §8).

    One shared model for goats and sheep. Repeat services link back via
    ``repeat_of_id``. Dam/sire use SET NULL so breeding history survives an animal's
    soft-deletion. ``planned_birth_date`` is a FORECAST derived from the service
    date and the species/breed gestation — never a recorded fact. The engine
    validates dam=female-of-species and sire=male-of-species via the species config
    (goat doe×buck, sheep ewe×ram), so no breeding logic is forked per species.
    """

    __tablename__ = "sr_breeding"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    repeat_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="natural")
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pregnancy_checked_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    pregnancy_result: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    prep_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SmallRuminant | None"] = relationship(foreign_keys=[dam_id], lazy="noload")
    sire: Mapped["SmallRuminant | None"] = relationship(foreign_keys=[sire_id], lazy="noload")

    @property
    def is_open(self) -> bool:
        """True while the cycle is unresolved (blocks a dam from being re-serviced)."""
        return self.status in ("planned", "serviced", "pregnant")

    def __repr__(self) -> str:
        return f"<SmallRuminantBreeding {self.species} dam={self.dam_id} sire={self.sire_id} status={self.status}>"


class SmallRuminantBirth(AGRIOSBase):
    """A birth event — a kidding (goat) or lambing (sheep) (Goat Doc 2 §9).

    Birth statistics are recorded facts; performance (live-birth rate, weaning
    survival) is calculated by the deterministic engine, never stored. Offspring
    reference this row via ``sr_animal.birth_id`` and remain linked permanently.
    The event verb (kidding/lambing) is derived from the species config.
    """

    __tablename__ = "sr_birth"
    __table_args__ = (
        UniqueConstraint("farm_id", "birth_code", name="uq_sr_birth_farm_code"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    breeding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_breeding.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    dam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    sire_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    birth_code: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_type: Mapped[str] = mapped_column(String(15), nullable=False, default="unknown")
    total_born: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    live_born: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stillborn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weaned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mortality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    weaning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assistance_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    complications: Mapped[str | None] = mapped_column(Text, nullable=True)
    colostrum_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    dam: Mapped["SmallRuminant | None"] = relationship(foreign_keys=[dam_id], lazy="noload")
    sire: Mapped["SmallRuminant | None"] = relationship(foreign_keys=[sire_id], lazy="noload")

    def __repr__(self) -> str:
        return f"<SmallRuminantBirth {self.birth_code} {self.species} born={self.total_born} status={self.status}>"


# ── Growth: weight measurements (Goat Doc 2 §11) — Milestone 4 ──────────────────

class SmallRuminantWeight(AGRIOSBase):
    """An immutable weight measurement for an animal (Goat Doc 2 §11). Historical
    records are never overwritten. Weights are in kilograms (small-ruminant scale).
    Growth (ADG, percentiles, deviations) is computed from these records by the
    deterministic engine — never stored. Body condition score (1–5) is an optional
    recorded assessment."""

    __tablename__ = "sr_weight"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    method: Mapped[str] = mapped_column(String(15), nullable=False, default="scale")
    body_condition_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    heart_girth_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    body_length_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantWeight animal={self.animal_id} {self.weight_kg}kg on {self.recorded_on}>"


# ── Feed: feeding log (reuses platform Inventory — Goat Doc 2 §13) ──────────────

class SmallRuminantFeedRecord(AGRIOSBase):
    """A feeding event for an animal, group or the farm (Goat Doc 2 §13). Feed stock
    and purchase costs live in the platform Inventory module; this row is the domain
    feeding log. ``inventory_item_id`` / ``inventory_movement_id`` are SOFT
    references into Inventory (no FK — modules stay decoupled). ``cost`` is a
    snapshot allocation, never re-posted to finance (feed is expensed once at
    Inventory stock-in)."""

    __tablename__ = "sr_feed_record"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_group.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    inventory_movement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    feed_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    fed_on: Mapped[date] = mapped_column(Date, nullable=False)
    is_mineral: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantFeedRecord animal={self.animal_id} group={self.group_id} {self.quantity_kg}kg>"


# ── Health, vaccination, deworming, hoof care & mortality (Goat Doc 2 §12/§15/§16) M5

class SmallRuminantHealthRecord(AGRIOSBase):
    """A chronological clinical event for an animal (Goat Doc 2 §12): illness,
    injury, treatment, medication, surgery, vet visit, recovery, quarantine…
    ``diagnosis`` holds a **recorded veterinary input only** — it is never inferred
    by the platform (frozen §4.4). Records remain permanently attached, ordered
    chronologically."""

    __tablename__ = "sr_health_record"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, default="observation")
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recorded")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    medication: Mapped[str | None] = mapped_column(String(255), nullable=True)
    withdrawal_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    veterinarian: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recovery_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantHealthRecord animal={self.animal_id} type={self.event_type} status={self.status}>"


class SmallRuminantVaccination(AGRIOSBase):
    """A vaccination record (Goat Doc 2 §12). Follow-ups reuse the platform Reminder
    engine — ``reminder_id`` is a SOFT reference to the created reminder (no FK)."""

    __tablename__ = "sr_vaccination"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    vaccine: Mapped[str] = mapped_column(String(150), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    administered_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    administrator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantVaccination animal={self.animal_id} {self.vaccine!r} on {self.administered_on}>"


class SmallRuminantDeworming(AGRIOSBase):
    """A deworming / anthelmintic treatment (Goat Doc 1 §12, Doc 2 §12). Parasite
    control is first-class for small ruminants. ``famacha_score`` is a recorded
    anaemia assessment (1–5), never inferred. Follow-ups reuse the platform Reminder
    engine via the soft ``reminder_id``. Withdrawal period is a recorded fact."""

    __tablename__ = "sr_deworming"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    product: Mapped[str] = mapped_column(String(150), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="oral_drench")
    dose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    famacha_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    administered_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    withdrawal_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    administrator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantDeworming animal={self.animal_id} {self.product!r} on {self.administered_on}>"


class SmallRuminantHoofCare(AGRIOSBase):
    """A hoof inspection / trimming / treatment (Goat Doc 2 §15). ``lameness_score``
    is a recorded assessment (0–5), never inferred. The Operations Planner schedules
    recurring hoof care; follow-ups reuse the platform Reminder engine."""

    __tablename__ = "sr_hoof_care"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False, default="inspection")
    condition: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    lameness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_on: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantHoofCare animal={self.animal_id} action={self.action} condition={self.condition}>"


class SmallRuminantMortality(AGRIOSBase):
    """An immutable death record (Goat Doc 2 §16). Recording mortality transitions
    the animal to ``deceased``. Mortality analytics (rates, trends, cause breakdown)
    are computed by the deterministic engine — never stored. One per animal."""

    __tablename__ = "sr_mortality"
    __table_args__ = (
        UniqueConstraint("animal_id", name="uq_sr_mortality_animal"),
    )

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cause: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    suspected_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postmortem_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantMortality animal={self.animal_id} cause={self.cause} on {self.occurred_on}>"


# ── Dairy: lactation & milk (Goat Doc 2 §10) — Milestone 6 ──────────────────────

class SmallRuminantLactation(AGRIOSBase):
    """A lactation cycle for a dairy female (Goat Doc 2 §10). Begins at freshening
    (parturition) and ends at dry-off. Production trends are retained permanently;
    yields (total, peak, 305-day projection) are computed by the deterministic
    engine from the milk records — never stored. ``expected_dry_off_date`` is a
    forecast. Linked to the birth that freshened her when known."""

    __tablename__ = "sr_lactation"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    birth_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_birth.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    lactation_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    freshening_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_dry_off_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dry_off_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    milking_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<SmallRuminantLactation animal={self.animal_id} #{self.lactation_number} status={self.status}>"


class SmallRuminantMilkRecord(AGRIOSBase):
    """A milk-yield measurement (Goat Doc 2 §10). One row per milking session (or a
    daily total). Quantities in litres. Quality metrics (fat/protein) are optional
    recorded facts; somatic cell count is future-ready. Never overwritten."""

    __tablename__ = "sr_milk_record"

    species: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    animal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    lactation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_lactation.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    session: Mapped[str] = mapped_column(String(10), nullable=False, default="total")
    quantity_liters: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    fat_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    protein_pct: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    somatic_cell_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SmallRuminantMilkRecord animal={self.animal_id} {self.quantity_liters}L {self.session} on {self.recorded_on}>"
