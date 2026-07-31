"""Migration 061 — Black Soldier Fly (BSF) Foundation (Module 16, Part 1)

The database backbone for the Black Soldier Fly module (Spec Part 3).

Unlike Poultry (flocks) or Aviculture (individual birds), the aggregate root is
the **Production Batch** (Spec Part 3 §2): every operational record ultimately
relates to one or more batches. Everything here is historical and soft-deleted
only — lineage (split/merge), lifecycle history and production records are never
destroyed (Spec Part 3 §8-10, §21).

Reuse, not duplication (Spec Part 10 §3):
  * The species extensibility engine is the existing ``species_profiles`` table
    (Migration 007). We register ``species_key='bsf'`` there and hold the rich,
    data-driven biological reference in ``bsf_species`` (Spec Part 3 §5). Species
    are NEVER hardcoded.
  * Farm-scoped records carry ``farm_id`` and derive organisation isolation
    through ``farms.organization_id`` — the same convention as ``flocks``,
    ``avi_*`` and ``missions``. The species catalog carries a nullable
    ``organization_id`` (NULL = global system catalog shared by all orgs).

Tables (created in dependency order):
  bsf_species            — data-driven biological reference / strain catalog
  bsf_production_unit    — housing (bin/tray/rack/incubator/dryer…)
  bsf_colony             — adult breeding colony (breeding engine is a later Part)
  bsf_batch              — the aggregate root (Production Batch)
  bsf_lifecycle_event    — immutable lifecycle-transition snapshots
  bsf_batch_event        — append-only batch timeline
  bsf_batch_media        — photos / videos / audio
  bsf_batch_document     — lab reports, invoices, certificates…

Enumerated fields are stored as ``String`` with the allowed values documented in
the column comment and enforced at the schema/service layer — matching the
Module 14/15 (Migrations 052/053) convention.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None


BSF_SPECIES_PROFILE_ID = uuid.UUID("10000000-0000-0000-0000-000000000007")


def _base() -> list[sa.Column]:
    """Standard AGRIOSBase columns (matches app/models/base.py)."""
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Register the module in the extensibility engine (Spec Part 10 §3) ───────
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
                "id": BSF_SPECIES_PROFILE_ID,
                "species_key": "bsf",
                "display_name": "Black Soldier Fly",
                "display_name_sw": "Nzi wa Askari Weusi",
                "icon": "🪰",
                "module_accent_hex": "#4D7C0F",
                "is_active": True,
                "sort_order": 7,
                "description": "Batch-centric Black Soldier Fly production — breeding colonies, "
                "larvae and prepupae rearing, frass, feedstock conversion and waste recycling.",
            }
        ],
    )

    # ── Catalog: bsf_species (Spec Part 3 §5) ──────────────────────────────────
    op.create_table(
        "bsf_species",
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
        sa.Column("strain", sa.String(150), nullable=True),
        sa.Column(
            "production_type",
            sa.String(30),
            nullable=False,
            server_default="larvae",
            comment="larvae | frass | breeding | mixed",
        ),
        sa.Column(
            "profile",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="Data-driven biological reference (Spec Part 3 §5): lifecycle "
            "parameters, recommended environmental ranges, feeding guidelines, "
            "expected development times, target moisture, expected conversion ratios.",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_species_common_name", "bsf_species", ["common_name"])

    # ── Housing: bsf_production_unit (Spec Part 2 §4, Part 3 §6) ────────────────
    op.create_table(
        "bsf_production_unit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column(
            "unit_type",
            sa.String(30),
            nullable=False,
            server_default="bin",
            comment="bin | tray | rack | cage | chamber | container | shelf | "
            "incubator | drying_unit | nursery | love_cage | other",
        ),
        sa.Column("facility", sa.String(200), nullable=True),
        sa.Column("production_area", sa.String(200), nullable=True),
        sa.Column("capacity_grams", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="available",
            comment="available | in_use | cleaning | maintenance | out_of_service",
        ),
        sa.Column("environment_profile", JSONB, nullable=False, server_default="{}"),
        sa.Column("maintenance_status", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_bsf_unit_farm_code"),
    )
    op.create_index("ix_bsf_unit_status", "bsf_production_unit", ["status"])

    # ── Breeding: bsf_colony (Spec Part 2 §7) ──────────────────────────────────
    op.create_table(
        "bsf_colony",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_species.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("production_unit_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_production_unit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="bred | purchased | donated | transferred | wild | unknown",
        ),
        sa.Column("established_on", sa.Date, nullable=True),
        sa.Column("population_estimate", sa.BigInteger, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | declining | rotating | retired",
        ),
        sa.Column("retired_on", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_bsf_colony_farm_code"),
    )
    op.create_index("ix_bsf_colony_status", "bsf_colony", ["status"])

    # ── Aggregate root: bsf_batch (Spec Part 3 §7) ─────────────────────────────
    op.create_table(
        "bsf_batch",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("species_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_species.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("source_colony_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_colony.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("parent_batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("production_unit_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_production_unit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("batch_number", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column(
            "batch_type",
            sa.String(20),
            nullable=False,
            server_default="production",
            comment="production | breeding | egg | nursery | mixed",
        ),
        sa.Column(
            "lifecycle_stage",
            sa.String(20),
            nullable=False,
            server_default="egg",
            comment="egg | hatchling | feeding_larvae | mature_larvae | prepupae | pupae | adult | unknown",
        ),
        sa.Column("stage_started_on", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | harvested | completed | split | merged | terminated | archived",
        ),
        sa.Column("started_on", sa.Date, nullable=True),
        sa.Column("completed_on", sa.Date, nullable=True),
        sa.Column("population_estimate", sa.BigInteger, nullable=True),
        sa.Column("biomass_estimate_g", sa.Numeric(14, 2), nullable=True),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "batch_number", name="uq_bsf_batch_farm_number"),
    )
    op.create_index("ix_bsf_batch_stage", "bsf_batch", ["lifecycle_stage"])
    op.create_index("ix_bsf_batch_status", "bsf_batch", ["status"])
    op.create_index("ix_bsf_batch_farm_status", "bsf_batch", ["farm_id", "status"])

    # ── Immutable history: bsf_lifecycle_event (Spec Part 3 §8) ────────────────
    op.create_table(
        "bsf_lifecycle_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("previous_stage", sa.String(20), nullable=True),
        sa.Column("new_stage", sa.String(20), nullable=False),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("population_estimate", sa.BigInteger, nullable=True),
        sa.Column("biomass_estimate_g", sa.Numeric(14, 2), nullable=True),
        sa.Column("survival_rate_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="manual",
            comment="manual | automated | correction",
        ),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Immutable history: bsf_batch_event (Spec Part 3 §19) ───────────────────
    op.create_table(
        "bsf_batch_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
            server_default="note",
            comment="created | stage_changed | moved | split | merged | population_adjusted | "
            "biomass_recorded | status_changed | media_added | document_added | terminated | note",
        ),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("related_batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_batch_event_type", "bsf_batch_event", ["event_type"])

    # ── Attachments: bsf_batch_media (Spec Part 3 §18) ─────────────────────────
    op.create_table(
        "bsf_batch_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
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

    # ── Attachments: bsf_batch_document (Spec Part 3 §18) ──────────────────────
    op.create_table(
        "bsf_batch_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "document_type",
            sa.String(30),
            nullable=False,
            server_default="other",
            comment="lab_report | environmental_report | invoice | receipt | "
            "certificate | inspection_report | permit | other",
        ),
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
    op.drop_table("bsf_batch_document")
    op.drop_table("bsf_batch_media")
    op.drop_table("bsf_batch_event")
    op.drop_table("bsf_lifecycle_event")
    op.drop_table("bsf_batch")
    op.drop_table("bsf_colony")
    op.drop_table("bsf_production_unit")
    op.drop_table("bsf_species")
    op.execute(sa.text("DELETE FROM species_profiles WHERE species_key = 'bsf'"))
