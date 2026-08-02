"""Migration 072 — Small Ruminant Foundation (Modules 18 Goat + 19 Sheep, Milestone 1)

The database backbone for the unified **Small Ruminant** subsystem (Goat Doc 2,
Sheep Doc 2). Goat and sheep are built once on a shared ``sr_*`` schema carrying a
``species`` discriminator ('goat' | 'sheep'), not as two parallel modules — the
directive's core principle. Per-species vocabulary and biology live in
``app/services/small_ruminant_species_config.py``.

Like Rabbit (Module 17) and Aviculture (Module 15), the aggregate root is the
**individual animal** (``sr_animal``). Everything here is historical and
soft-deleted only: pedigree, movement, medical and ownership history are never
destroyed (Goat Doc 2 §2/§21).

Reuse, not duplication (Goat Doc 9 §2, §15):
  * The species extensibility engine is the existing ``species_profiles`` table
    (Migration 007, frozen DB-03). Migration 007 seeds no goat/sheep placeholder,
    so this migration **inserts** two new active rows (``goat`` id …0008, ``sheep``
    id …0009) — the same pattern Aviculture (…0006) and BSF (…0007) used. The rich,
    data-driven breed reference lives in ``sr_breed`` (Goat Doc 2 §7); breeds are
    NEVER hardcoded.
  * Farm-scoped records carry ``farm_id`` and derive organisation isolation through
    ``farms.organization_id`` — the same convention as ``flocks``, ``avi_*``,
    ``bsf_*``, ``rabbit`` and ``missions``. The breed catalog carries a nullable
    ``organization_id`` (NULL = global system catalog shared by all orgs).

Structure follows the specification hierarchy (Goat Doc 1 §5, Doc 2 §3):
Farm → Herd/Flock → Group → Pen / Pasture → Individual. Animal-and-genetics tables
(breed/bloodline/herd/group) are species-scoped; physical infrastructure
(pen/pasture) is farm-scoped and species-neutral so a barn or paddock can be shared
(e.g. co-grazing). Occupancy is never stored — it is derived from the animal's
location FKs (the Housing engine, Milestone 2).

Tables (created in dependency order):
  sr_breed      — data-driven, species-scoped breed catalog
  sr_bloodline  — named genetic line / bloodline (farm-scoped)
  sr_herd       — herd (goat) / flock (sheep) management container
  sr_group      — dynamic production/management group within a herd
  sr_pen        — physical housing unit (barn/pen/shed/paddock/quarantine…)
  sr_pasture    — grazing area / paddock
  sr_animal     — the aggregate root (individual animal registry)
  sr_event      — append-only animal timeline
  sr_media      — photos / videos / audio
  sr_document   — pedigree certificates, vet reports, invoices…

Enumerated fields are stored as ``String`` with the allowed values documented in
the column comment and enforced at the schema/service layer — matching the
Module 15/16/17 convention.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None

# New species_profiles rows. Taken ids: …0001 poultry, …0002 rabbit, …0003 dairy,
# …0004 fish, …0005 crop, …0006 aviculture, …0007 bsf. Goat/sheep take …0008/…0009.
GOAT_SPECIES_PROFILE_ID = uuid.UUID("10000000-0000-0000-0000-000000000008")
SHEEP_SPECIES_PROFILE_ID = uuid.UUID("10000000-0000-0000-0000-000000000009")


def _base() -> list[sa.Column]:
    """Standard AGRIOSBase columns (matches app/models/base.py)."""
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Register the two workspaces in the extensibility engine (DB-03) ─────────
    species_profiles_table = sa.table(
        "species_profiles",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("species_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("display_name_sw", sa.String),
        sa.column("icon", sa.String),
        sa.column("module_accent_hex", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        species_profiles_table,
        [
            {
                "id": GOAT_SPECIES_PROFILE_ID,
                "species_key": "goat",
                "display_name": "Goats",
                "display_name_sw": "Mbuzi",
                "icon": "🐐",
                "module_accent_hex": "#B45309",
                "is_active": True,
                "sort_order": 8,
                "description": "Individual-goat management — meat, dairy, fiber and breeding "
                "operations with herds, breeding, kidding, lactation, growth, health and grazing.",
            },
            {
                "id": SHEEP_SPECIES_PROFILE_ID,
                "species_key": "sheep",
                "display_name": "Sheep",
                "display_name_sw": "Kondoo",
                "icon": "🐑",
                "module_accent_hex": "#6D28D9",
                "is_active": True,
                "sort_order": 9,
                "description": "Individual-sheep management — wool, meat, dairy and breeding "
                "operations with flocks, breeding, lambing, shearing, growth, health and grazing.",
            },
        ],
    )

    # ── Catalog: sr_breed (Goat Doc 2 §7) — species-scoped ─────────────────────
    op.create_table(
        "sr_breed",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True,
                  comment="goat | sheep"),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
            comment="NULL = global/system catalog shared by all organisations.",
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column(
            "category",
            sa.String(30),
            nullable=False,
            server_default="other",
            comment="dairy | meat | fiber | wool | dual_purpose | indigenous | heritage | show | crossbreed | other",
        ),
        sa.Column("origin", sa.String(150), nullable=True),
        sa.Column(
            "production_purpose",
            sa.String(30),
            nullable=True,
            comment="meat | dairy | fiber | wool | breeding | mixed",
        ),
        sa.Column(
            "profile",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="Data-driven breed reference (Goat Doc 2 §7): adult weight range, milk/"
            "growth/fiber characteristics, temperament, climate suitability, production "
            "benchmarks, optional gestation_days override.",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_sr_breed_name", "sr_breed", ["name"])

    # ── Catalog: sr_bloodline (Goat Doc 2 §7, §19) ─────────────────────────────
    op.create_table(
        "sr_bloodline",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("origin", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_sr_bloodline_farm_code"),
    )

    # ── Management: sr_herd (Goat Doc 1 §8, Doc 2 §6) — species-scoped ──────────
    op.create_table(
        "sr_herd",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("herd_type", sa.String(20), nullable=False, server_default="mixed",
                  comment="breeding | dairy | meat | fiber | wool | mixed | replacement | commercial | other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | inactive | archived"),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_sr_herd_farm_code"),
    )

    # ── Management: sr_group (Goat Doc 1 §7-8) — dynamic membership ─────────────
    op.create_table(
        "sr_group",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("herd_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_herd.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("group_type", sa.String(20), nullable=False, server_default="general",
                  comment="breeding | milking | dry | lactating | growing | weaning | replacement | "
                  "quarantine | isolation | sale | males | females | young | general | other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_sr_group_farm_code"),
    )

    # ── Physical housing: sr_pen (Goat Doc 2 §14) — species-neutral ────────────
    op.create_table(
        "sr_pen",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("pen_type", sa.String(20), nullable=False, server_default="pen",
                  comment="barn | pen | shed | paddock | shelter | yard | quarantine | isolation | "
                  "kidding_pen | lambing_pen | other"),
        sa.Column("capacity", sa.Integer, nullable=True,
                  comment="Maximum head. Occupancy is DERIVED from sr_animal.pen_id, never stored."),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="available",
                  comment="available | occupied | maintenance | cleaning | out_of_service"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_sr_pen_farm_code"),
    )
    op.create_index("ix_sr_pen_type", "sr_pen", ["pen_type"])
    op.create_index("ix_sr_pen_status", "sr_pen", ["status"])

    # ── Physical housing: sr_pasture (Goat Doc 2 §14) — species-neutral ────────
    op.create_table(
        "sr_pasture",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("area_hectares", sa.Numeric(12, 3), nullable=True),
        sa.Column("carrying_capacity", sa.Integer, nullable=True,
                  comment="Recorded stocking reference. Occupancy is DERIVED from sr_animal.pasture_id."),
        sa.Column("grass_species", sa.String(255), nullable=True),
        sa.Column("browse_species", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="available",
                  comment="available | grazing | resting | closed | maintenance"),
        sa.Column("profile", JSONB, nullable=False, server_default="{}",
                  comment="Rotation schedule, rest period, condition assessment (Goat Doc 2 §14)."),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_sr_pasture_farm_code"),
    )
    op.create_index("ix_sr_pasture_status", "sr_pasture", ["status"])

    # ── Aggregate root: sr_animal (Goat Doc 2 §2, §5) ──────────────────────────
    op.create_table(
        "sr_animal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True, comment="goat | sheep"),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("bloodline_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_bloodline.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("herd_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_herd.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pen_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_pen.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pasture_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_pasture.id", ondelete="SET NULL"), nullable=True, index=True),

        # Identity (Goat Doc 1 §6, Doc 2 §5)
        sa.Column("internal_ref", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("ear_tag", sa.String(100), nullable=True, index=True),
        sa.Column("tattoo", sa.String(100), nullable=True),
        sa.Column("qr_code", sa.String(200), nullable=True, index=True),
        sa.Column("rfid", sa.String(100), nullable=True),
        sa.Column("visual_id", sa.String(150), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=True),

        # Classification (Goat Doc 2 §5)
        sa.Column("variety", sa.String(100), nullable=True),
        sa.Column("color", sa.String(100), nullable=True),
        sa.Column("sex", sa.String(10), nullable=False, server_default="unknown",
                  comment="goat: buck | doe | wether; sheep: ram | ewe | wether; else unknown"),
        sa.Column("purpose", sa.String(30), nullable=False, server_default="unknown",
                  comment="meat | dairy | fiber | wool | breeding | show | pet | replacement | "
                  "genetic_improvement | conservation | educational | mixed | unknown"),
        sa.Column("purposes", JSONB, nullable=False, server_default="[]",
                  comment="Multiple production purposes may be assigned (Goat Doc 1 §7)."),
        sa.Column("horn_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="horned | polled | disbudded | scurred | dehorned | unknown"),
        sa.Column("registration_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="registered | unregistered | pending | commercial | recorded | unknown"),

        # Biology (Goat Doc 2 §5). Weights in kilograms (small-ruminant scale).
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("dob_estimated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("birth_type", sa.String(15), nullable=False, server_default="unknown",
                  comment="single | twin | triplet | quadruplet | quintuplet | unknown"),
        sa.Column("birth_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("current_weight_kg", sa.Numeric(8, 3), nullable=True),

        # Lifecycle & reproduction (Goat Doc 1 §9, Doc 2 §5)
        sa.Column("lifecycle_stage", sa.String(20), nullable=False, server_default="unknown",
                  comment="newborn | weaner | grower | yearling | replacement | breeding_adult | "
                  "mature | cull | retired | unknown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | sold | transferred | deceased | culled | archived"),
        sa.Column("reproductive_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="not_bred | bred | pregnant | lactating | open | dry | resting | "
                  "proven | unproven | unknown"),
        sa.Column("fertility_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="fertile | infertile | unproven | unknown"),
        sa.Column("acquisition_type", sa.String(20), nullable=False, server_default="unknown",
                  comment="bred | purchased | donated | transferred | unknown"),
        sa.Column("acquired_on", sa.Date, nullable=True),

        # Pedigree links (deterministic; Goat Doc 2 §19). Unknown stays NULL.
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),

        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "internal_ref", name="uq_sr_animal_farm_internal_ref"),
        sa.UniqueConstraint("farm_id", "ear_tag", name="uq_sr_animal_farm_ear_tag"),
    )
    op.create_index("ix_sr_animal_status", "sr_animal", ["status"])
    op.create_index("ix_sr_animal_sex", "sr_animal", ["sex"])
    op.create_index("ix_sr_animal_lifecycle_stage", "sr_animal", ["lifecycle_stage"])
    op.create_index("ix_sr_animal_farm_species_status", "sr_animal", ["farm_id", "species", "status"])

    # ── Immutable history: sr_event (Goat Doc 2 §18) ───────────────────────────
    op.create_table(
        "sr_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(30), nullable=False, server_default="note",
                  comment="created | updated | status_changed | moved | transferred | sold | "
                  "died | culled | bred | kidded | lambed | weaned | weight_recorded | "
                  "milk_recorded | sheared | health_recorded | note …"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_sr_event_type", "sr_event", ["event_type"])

    # ── Attachments: sr_media (Goat Doc 2 §17) ─────────────────────────────────
    op.create_table(
        "sr_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("media_type", sa.String(20), nullable=False, server_default="photo",
                  comment="photo | video | audio"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("captured_on", sa.Date, nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Attachments: sr_document (Goat Doc 2 §17) ──────────────────────────────
    op.create_table(
        "sr_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_type", sa.String(30), nullable=False, server_default="other",
                  comment="pedigree_certificate | health_certificate | registration | lab_report | "
                  "vet_report | movement_record | purchase_record | sale_document | invoice | other"),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("issued_on", sa.Date, nullable=True),
        sa.Column("expires_on", sa.Date, nullable=True, index=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("sr_document")
    op.drop_table("sr_media")
    op.drop_table("sr_event")
    op.drop_table("sr_animal")
    op.drop_table("sr_pasture")
    op.drop_table("sr_pen")
    op.drop_table("sr_group")
    op.drop_table("sr_herd")
    op.drop_table("sr_bloodline")
    op.drop_table("sr_breed")
    # Remove the species rows this migration inserted (owned here, unlike the
    # Migration-007 placeholders that Rabbit merely re-activates).
    op.execute(sa.text("DELETE FROM species_profiles WHERE species_key IN ('goat', 'sheep')"))
