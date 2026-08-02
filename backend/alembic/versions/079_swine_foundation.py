"""Migration 079 — Swine Foundation (Module 20, Pig Framework, Milestone 1)

The database backbone for the **Swine Framework** (Swine Doc 2). Swine is a single
species (no ``species`` discriminator, unlike the unified Small Ruminant subsystem),
but otherwise follows the individual-animal conventions of Rabbit (Module 17) and
Small Ruminant (Modules 18/19): the aggregate root is the individual pig
(``swine_pig``), and everything here is historical and soft-deleted only — pedigree,
movement, medical and ownership history are never destroyed (Swine Doc 2 §19/§23).

Reuse, not duplication (Swine Doc 5 §2, §4):
  * The species extensibility engine is the existing ``species_profiles`` table
    (Migration 007, frozen DB-03). This migration **inserts** one new active row
    (``swine`` id …0010) — the same pattern Aviculture (…0006), BSF (…0007) and the
    Small Ruminant rows (…0008 goat / …0009 sheep) used. The rich, data-driven breed
    reference lives in ``swine_breed`` (Swine Doc 1 §7); breeds are NEVER hardcoded.
  * Farm-scoped records carry ``farm_id`` and derive organisation isolation through
    ``farms.organization_id`` — the same convention as ``flocks``, ``avi_*``,
    ``bsf_*``, ``rabbit`` and ``sr_*``. The breed catalog carries a nullable
    ``organization_id`` (NULL = global system catalog shared by all orgs).

Structure follows the specification hierarchy (Swine Doc 1 §5, Doc 2 §3, §18):
Farm → Herd → Group → Pen → Individual. Pigs are a **housed** species, so there is
no pasture table; the physical unit is the pen/crate/stall/shed (``swine_pen``),
which carries a biosecurity status (Swine Doc 2 §6). Occupancy is never stored — it
is derived from the pig's location FKs (the Housing engine, Milestone 2).

Tables (created in dependency order):
  swine_breed      — data-driven pig breed catalog
  swine_bloodline  — named genetic line / bloodline (farm-scoped)
  swine_herd       — herd management container
  swine_group      — dynamic production/management group within a herd
  swine_pen        — physical housing unit (crate/stall/pen/shed) + biosecurity
  swine_pig        — the aggregate root (individual pig registry)
  swine_event      — append-only pig timeline (movements recorded here)
  swine_media      — photos / videos / audio
  swine_document   — pedigree/health certificates, vet reports, invoices…

Enumerated fields are stored as ``String`` with the allowed values documented in
the column comment and enforced at the schema/service layer — matching the
Module 15/16/17/18-19 convention.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None

# New species_profiles row. Taken ids: …0001 poultry, …0002 rabbit, …0003 dairy,
# …0004 fish, …0005 crop, …0006 aviculture, …0007 bsf, …0008 goat, …0009 sheep.
# Swine takes …0010.
SWINE_SPECIES_PROFILE_ID = uuid.UUID("10000000-0000-0000-0000-000000000010")


def _base() -> list[sa.Column]:
    """Standard AGRIOSBase columns (matches app/models/base.py)."""
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Register the workspace in the extensibility engine (DB-03) ──────────────
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
                "id": SWINE_SPECIES_PROFILE_ID,
                "species_key": "swine",
                "display_name": "Pigs",
                "display_name_sw": "Nguruwe",
                "icon": "🐖",
                "module_accent_hex": "#BE185D",
                "is_active": True,
                "sort_order": 10,
                "description": "Commercial & smallholder pig production — breeding, "
                "artificial insemination, pregnancy, farrowing, piglets, weaning, "
                "nursery/grower/finisher production, feed, health, growth, sales and finance.",
            },
        ],
    )

    # ── Catalog: swine_breed (Swine Doc 1 §7) ──────────────────────────────────
    op.create_table(
        "swine_breed",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
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
            comment="maternal | terminal | dual_purpose | indigenous | heritage | crossbreed | show | other",
        ),
        sa.Column("origin", sa.String(150), nullable=True),
        sa.Column(
            "production_purpose",
            sa.String(30),
            nullable=True,
            comment="meat | breeding | maternal | terminal | mixed",
        ),
        sa.Column(
            "profile",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="Data-driven breed reference (Swine Doc 1 §7): mature weight range, "
            "litter-size / growth benchmarks, backfat/lean characteristics, temperament, "
            "climate suitability, optional gestation_days override.",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_breed_name", "swine_breed", ["name"])

    # ── Catalog: swine_bloodline (Swine Doc 2 §7, §18) ─────────────────────────
    op.create_table(
        "swine_bloodline",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("origin", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_swine_bloodline_farm_code"),
    )

    # ── Management: swine_herd (Swine Doc 2 §5) ─────────────────────────────────
    op.create_table(
        "swine_herd",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("herd_type", sa.String(20), nullable=False, server_default="mixed",
                  comment="breeding | farrow_to_finish | farrow_to_weaner | weaner | grower | "
                  "finisher | boar_stud | multiplier | commercial | mixed | other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | inactive | archived"),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_swine_herd_farm_code"),
    )

    # ── Management: swine_group (Swine Doc 2 §12) — dynamic membership ──────────
    op.create_table(
        "swine_group",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("herd_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_herd.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("group_type", sa.String(20), nullable=False, server_default="general",
                  comment="breeding | gestation | farrowing | lactation | nursery | weaner | "
                  "grower | finisher | replacement | boar | quarantine | isolation | hospital | "
                  "sale | general | other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_swine_group_farm_code"),
    )

    # ── Physical housing: swine_pen (Swine Doc 2 §6) ───────────────────────────
    op.create_table(
        "swine_pen",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("building", sa.String(200), nullable=True,
                  comment="Optional named building / shed the pen sits within (Swine Doc 2 §6)."),
        sa.Column("pen_type", sa.String(20), nullable=False, server_default="pen",
                  comment="farrowing_crate | farrowing_pen | gestation_stall | gestation_pen | "
                  "breeding_pen | dry_sow_pen | nursery_pen | weaner_pen | grower_pen | "
                  "finisher_pen | boar_pen | quarantine | isolation | hospital | loading | pen | shed | other"),
        sa.Column("capacity", sa.Integer, nullable=True,
                  comment="Maximum head. Occupancy is DERIVED from swine_pig.pen_id, never stored."),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="available",
                  comment="available | occupied | maintenance | cleaning | out_of_service"),
        sa.Column("biosecurity_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="secure | monitored | restricted | quarantine | compromised | unknown"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_swine_pen_farm_code"),
    )
    op.create_index("ix_swine_pen_type", "swine_pen", ["pen_type"])
    op.create_index("ix_swine_pen_status", "swine_pen", ["status"])

    # ── Aggregate root: swine_pig (Swine Doc 2 §4) ─────────────────────────────
    op.create_table(
        "swine_pig",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("bloodline_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_bloodline.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("herd_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_herd.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("pen_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pen.id", ondelete="SET NULL"), nullable=True, index=True),

        # Identity (Swine Doc 2 §4)
        sa.Column("internal_ref", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("ear_tag", sa.String(100), nullable=True, index=True),
        sa.Column("ear_notch", sa.String(100), nullable=True),
        sa.Column("tattoo", sa.String(100), nullable=True),
        sa.Column("qr_code", sa.String(200), nullable=True, index=True),
        sa.Column("rfid", sa.String(100), nullable=True),
        sa.Column("visual_id", sa.String(150), nullable=True),
        sa.Column("registration_number", sa.String(100), nullable=True),

        # Classification (Swine Doc 2 §4)
        sa.Column("line", sa.String(100), nullable=True),
        sa.Column("color", sa.String(100), nullable=True),
        sa.Column("sex", sa.String(10), nullable=False, server_default="unknown",
                  comment="boar (intact male) | sow (farrowed female) | gilt (unbred female) | "
                  "barrow (castrated male) | unknown"),
        sa.Column("purpose", sa.String(30), nullable=False, server_default="unknown",
                  comment="meat | breeding | replacement | show | genetic_improvement | mixed | unknown"),
        sa.Column("purposes", JSONB, nullable=False, server_default="[]",
                  comment="Multiple production purposes may be assigned."),
        sa.Column("registration_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="registered | unregistered | pending | commercial | recorded | unknown"),

        # Biology (Swine Doc 2 §4). Weights in kilograms.
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("dob_estimated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("birth_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("current_weight_kg", sa.Numeric(8, 3), nullable=True,
                  comment="Mirrors the latest weight record for fast display (Milestone 6 is authoritative)."),

        # Lifecycle & reproduction (Swine Doc 1 §5-6, Doc 2 §4)
        sa.Column("production_stage", sa.String(20), nullable=False, server_default="unknown",
                  comment="piglet | weaner | nursery | grower | finisher | breeding | "
                  "replacement | cull | retired | unknown"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | sold | transferred | deceased | culled | archived"),
        sa.Column("reproductive_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="not_bred | bred | pregnant | lactating | open | dry | weaned | "
                  "proven | unproven | unknown"),
        sa.Column("fertility_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="fertile | infertile | unproven | unknown"),
        sa.Column("market_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="growing | market_ready | sold | held | unknown"),
        sa.Column("parity", sa.Integer, nullable=True,
                  comment="Cached completed-litter count for a sow; authoritative history is derived "
                  "from farrowing records (Milestone 4)."),
        sa.Column("acquisition_type", sa.String(20), nullable=False, server_default="unknown",
                  comment="bred | purchased | donated | transferred | unknown"),
        sa.Column("acquired_on", sa.Date, nullable=True),

        # Pedigree links (deterministic; Swine Doc 2 §18). Unknown ancestry stays NULL.
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),

        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "internal_ref", name="uq_swine_pig_farm_internal_ref"),
        sa.UniqueConstraint("farm_id", "ear_tag", name="uq_swine_pig_farm_ear_tag"),
    )
    op.create_index("ix_swine_pig_sex", "swine_pig", ["sex"])
    op.create_index("ix_swine_pig_production_stage", "swine_pig", ["production_stage"])
    op.create_index("ix_swine_pig_status", "swine_pig", ["status"])

    # ── Immutable history: swine_event (Swine Doc 2 §16, §18) ──────────────────
    op.create_table(
        "swine_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(30), nullable=False, server_default="note",
                  comment="created | updated | status_changed | archived | restored | moved | "
                  "transferred | sold | purchased | died | culled | bred | inseminated | "
                  "pregnancy_checked | farrowed | fostered | weaned | weight_recorded | feed_recorded | "
                  "health_recorded | vaccination_recorded | treatment_recorded | market_ready | "
                  "media_added | document_added | note"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_event_type", "swine_event", ["event_type"])

    # ── Attachments: swine_media (Swine Doc 5 §13) ─────────────────────────────
    op.create_table(
        "swine_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
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

    # ── Attachments: swine_document (Swine Doc 5 §13) ──────────────────────────
    op.create_table(
        "swine_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_type", sa.String(30), nullable=False, server_default="other",
                  comment="pedigree_certificate | health_certificate | registration | lab_report | "
                  "vet_report | movement_record | purchase_record | sale_document | "
                  "breeding_certificate | invoice | other"),
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
    op.drop_table("swine_document")
    op.drop_table("swine_media")
    op.drop_table("swine_event")
    op.drop_table("swine_pig")
    op.drop_table("swine_pen")
    op.drop_table("swine_group")
    op.drop_table("swine_herd")
    op.drop_table("swine_bloodline")
    op.drop_table("swine_breed")
    # Remove the species row this migration inserted (owned here).
    op.execute(sa.text("DELETE FROM species_profiles WHERE species_key = 'swine'"))
