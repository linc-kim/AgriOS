"""Migration 053 — Aviculture Foundation (Module 15, Part 1)

The database backbone for the Aviculture (Ornamental & Specialty Birds) module.

This module manages **individual birds** rather than commercial flocks
(Doc 01 §7). The aggregate root is the bird (Doc 03 §3); every other entity
ultimately references a bird or a breeding pair. Everything here is historical
and soft-deleted only — lineage, medical history and ownership are never
destroyed (Doc 02 §26, Doc 04 §6).

Reuse, not duplication (Doc 14 §1):
  * The species extensibility engine is the existing ``species_profiles`` table
    (Migration 007). We register ``species_key='aviculture'`` there and build
    the rich, data-driven bird taxonomy in ``avi_species/avi_breed/avi_mutation``
    (Doc 02 §6-8, Doc 16). Species are NEVER hardcoded.
  * Farm-scoped records carry ``farm_id`` and derive organisation isolation
    through ``farms.organization_id`` — the same convention as ``flocks`` and
    ``missions``. Catalog tables carry a nullable ``organization_id``
    (NULL = global system catalog shared by every organisation).

Tables (created in dependency order):
  avi_species, avi_breed, avi_mutation      — data-driven catalog
  avi_aviary                                — housing (full mgmt is Part 3)
  avi_bird                                  — the aggregate root
  avi_bird_mutation                         — genetics (M:N + zygosity)
  avi_pair                                  — breeding pair (first-class entity)
  avi_bird_media                            — photos / videos / audio
  avi_bird_document                         — DNA certs, permits, lab reports…
  avi_health_record                         — foundation health log (Part 6 extends)

Enumerated fields are stored as ``String`` with the allowed values documented in
the column comment and enforced at the schema/service layer — matching the
Module 14 (Migration 052) convention.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


AVICULTURE_SPECIES_PROFILE_ID = uuid.UUID("10000000-0000-0000-0000-000000000006")


def _base() -> list[sa.Column]:
    """Standard AGRIOSBase columns (matches app/models/base.py)."""
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Register the module in the extensibility engine (Doc 14 §1) ────────────
    species_profiles = sa.table(
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
        species_profiles,
        [
            {
                "id": AVICULTURE_SPECIES_PROFILE_ID,
                "species_key": "aviculture",
                "display_name": "Aviculture",
                "display_name_sw": "Ndege wa Mapambo",
                "icon": "🦜",
                "module_accent_hex": "#7C3AED",
                "is_active": True,
                "sort_order": 6,
                "description": "Individual management of ornamental, exhibition, companion, "
                "conservation and specialty birds — breeding, genetics, pedigrees and collections.",
            }
        ],
    )

    # ── Catalog: avi_species (Doc 02 §6, Doc 16 §4) ───────────────────────────
    op.create_table(
        "avi_species",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
            comment="NULL = global/system catalog shared by all organisations.",
        ),
        sa.Column("common_name", sa.String(150), nullable=False),
        sa.Column("scientific_name", sa.String(200), nullable=True),
        sa.Column(
            "species_group",
            sa.String(50),
            nullable=False,
            server_default="other",
            comment="parrot | finch | canary | softbill | pigeon | dove | quail | "
            "pheasant | peafowl | waterfowl | ornamental_chicken | other",
        ),
        sa.Column("conservation_status", sa.String(50), nullable=True,
                  comment="e.g. CITES I/II, Least Concern, Endangered."),
        sa.Column(
            "profile",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="Data-driven husbandry knowledge (Doc 16 §4): lifespan, weight, "
            "housing, environment, diet, breeding, health, legal, biosecurity.",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false",
                  comment="True for the seeded global catalog; org custom entries are False."),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_species_common_name", "avi_species", ["common_name"])
    op.create_index("ix_avi_species_group", "avi_species", ["species_group"])

    # ── Catalog: avi_breed (Doc 02 §7, Doc 16 §3) ─────────────────────────────
    op.create_table(
        "avi_breed",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_species.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_breed_name", "avi_breed", ["name"])

    # ── Catalog: avi_mutation (Doc 02 §8) ─────────────────────────────────────
    op.create_table(
        "avi_mutation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_species.id", ondelete="CASCADE"), nullable=True, index=True,
                  comment="NULL = mutation not tied to a single species."),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column(
            "inheritance",
            sa.String(40),
            nullable=False,
            server_default="unknown",
            comment="dominant | recessive | sex_linked | co_dominant | polygenic | unknown",
        ),
        sa.Column("profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_mutation_name", "avi_mutation", ["name"])

    # ── Infrastructure: avi_aviary (Doc 02 §15; full mgmt is Part 3) ──────────
    op.create_table(
        "avi_aviary",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True, comment="Optional short label / location code."),
        sa.Column(
            "aviary_type",
            sa.String(40),
            nullable=False,
            server_default="mixed",
            comment="indoor | outdoor | mixed | flight | walk_in | cage | brooder | quarantine",
        ),
        sa.Column("capacity", sa.Integer, nullable=True, comment="Recommended maximum occupancy."),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}",
                  comment="{length_m, width_m, height_m, area_m2}."),
        sa.Column("environment", JSONB, nullable=False, server_default="{}",
                  comment="Target environment: temp, humidity, lighting, enrichment."),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="active",
            comment="active | inactive | quarantine | maintenance",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Aggregate root: avi_bird (Doc 02 §5, Doc 03 §3) ───────────────────────
    op.create_table(
        "avi_bird",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_species.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="SET NULL"), nullable=True, index=True),
        # ── Identity ──
        sa.Column("internal_ref", sa.String(50), nullable=False,
                  comment="System-generated stable identifier, unique per farm."),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("ring_number", sa.String(100), nullable=True, index=True),
        sa.Column("band_number", sa.String(100), nullable=True),
        sa.Column("microchip", sa.String(100), nullable=True, index=True),
        sa.Column("colour_description", sa.String(200), nullable=True),
        sa.Column(
            "sex",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="male | female | unknown",
        ),
        sa.Column(
            "sex_method",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="visual | dna | surgical | estimated | unknown (Doc 02 §9).",
        ),
        sa.Column(
            "dna_status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="sexed | unsexed | pending | unknown.",
        ),
        sa.Column("hatch_date", sa.Date, nullable=True),
        sa.Column("hatch_date_estimated", sa.Boolean, nullable=False, server_default="false"),
        # ── Pedigree links (deterministic; Doc 04 §4 — never invent ancestry) ──
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="Father. NULL = unknown ancestry (kept unknown, never invented)."),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="Mother. NULL = unknown ancestry."),
        # ── Lifecycle (Doc 02 §4) ──
        sa.Column(
            "lifecycle_stage",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="chick | juvenile | adult | breeding | retired | unknown.",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | archived | sold | transferred | deceased (Part 2 drives transitions).",
        ),
        sa.Column(
            "acquisition_type",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="bred | purchased | donated | transferred | unknown.",
        ),
        sa.Column("acquired_on", sa.Date, nullable=True),
        sa.Column("tags", JSONB, nullable=False, server_default="[]",
                  comment="Free-form string tags (Doc 13 Part 2)."),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "internal_ref", name="uq_avi_bird_farm_internal_ref"),
    )
    op.create_index("ix_avi_bird_status", "avi_bird", ["status"])
    op.create_index("ix_avi_bird_lifecycle_stage", "avi_bird", ["lifecycle_stage"])

    # ── Genetics: avi_bird_mutation (recorded facts only; Doc 04 §7) ──────────
    op.create_table(
        "avi_bird_mutation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("mutation_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_mutation.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column(
            "zygosity",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="visual | split | homozygous | heterozygous | unknown.",
        ),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("bird_id", "mutation_id", name="uq_avi_bird_mutation"),
    )

    # ── Breeding: avi_pair (first-class; Doc 02 §10; pairings permanent §3) ────
    op.create_table(
        "avi_pair",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("male_bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("female_bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column(
            "formation_type",
            sa.String(20),
            nullable=False,
            server_default="natural",
            comment="natural | artificial (Doc 04 §3).",
        ),
        sa.Column("formed_on", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | suspended | dissolved. Dissolution is soft — pairings are permanent.",
        ),
        sa.Column("dissolved_on", sa.Date, nullable=True),
        sa.Column("dissolution_reason", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_pair_status", "avi_pair", ["status"])

    # ── Media: avi_bird_media (storage-reference pattern; Doc 03 §14) ──────────
    op.create_table(
        "avi_bird_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "media_type",
            sa.String(20),
            nullable=False,
            server_default="photo",
            comment="photo | video | audio.",
        ),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("taken_on", sa.Date, nullable=True),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Documents: avi_bird_document (independent restriction; Doc 10 §7) ──────
    op.create_table(
        "avi_bird_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "document_type",
            sa.String(40),
            nullable=False,
            server_default="other",
            comment="dna_certificate | health_certificate | import_permit | export_permit | "
            "lab_report | ownership | invoice | contract | other.",
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("issued_on", sa.Date, nullable=True),
        sa.Column("expires_on", sa.Date, nullable=True, index=True,
                  comment="Drives permit-renewal reminders (Doc 11 §5)."),
        sa.Column("is_restricted", sa.Boolean, nullable=False, server_default="false",
                  comment="Protected documents may be restricted independently (Doc 10 §7)."),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Health: avi_health_record (foundation; Part 6 Health Engine extends) ───
    op.create_table(
        "avi_health_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "record_type",
            sa.String(30),
            nullable=False,
            server_default="observation",
            comment="observation | weight | treatment | vaccination | medication | "
            "vet_visit | lab_report | quarantine | necropsy.",
        ),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("weight_grams", sa.Numeric(10, 2), nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_health_record_type", "avi_health_record", ["record_type"])


def downgrade() -> None:
    op.drop_table("avi_health_record")
    op.drop_table("avi_bird_document")
    op.drop_table("avi_bird_media")
    op.drop_table("avi_pair")
    op.drop_table("avi_bird_mutation")
    op.drop_table("avi_bird")
    op.drop_table("avi_aviary")
    op.drop_table("avi_mutation")
    op.drop_table("avi_breed")
    op.drop_table("avi_species")
    op.execute(
        sa.text("DELETE FROM species_profiles WHERE species_key = 'aviculture'")
    )
