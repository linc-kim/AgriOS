"""Migration 066 — Rabbit Management Foundation (Module 17, Part 1)

The database backbone for the Rabbit Management module (Spec Part 3).

Like Aviculture (Module 15), the aggregate root is the **individual rabbit**
(Spec Part 3 §4) — every operational record ultimately references a rabbit.
Everything here is historical and soft-deleted only: pedigree, movement,
medical and ownership history are never destroyed (Spec Part 2 §2, Part 3 §21).

Reuse, not duplication (Spec Part 10 §3):
  * The species extensibility engine is the existing ``species_profiles`` table
    (Migration 007), which already seeds a placeholder ``species_key='rabbit'``
    row (id ...0002, ``is_active=False`` — "Future module"). This migration
    **activates** that row rather than inserting a duplicate. The rich,
    data-driven breed reference lives in ``rabbit_breed`` (Spec Part 3 §5).
    Breeds are NEVER hardcoded.
  * Farm-scoped records carry ``farm_id`` and derive organisation isolation
    through ``farms.organization_id`` — the same convention as ``flocks``,
    ``avi_*``, ``bsf_*`` and ``missions``. The breed catalog carries a nullable
    ``organization_id`` (NULL = global system catalog shared by all orgs).

Housing follows the specification's 5-level hierarchy (Spec Part 1 §6,
Part 3 §14): Rabbitry → Building → Room → Row → Cage → Rabbit. Occupancy is
never stored — it is derived from ``rabbit.cage_id`` (Spec Part 3, Housing engine).

Tables (created in dependency order):
  rabbit_breed        — data-driven breed catalog
  rabbit_bloodline    — named genetic line / bloodline
  rabbit_rabbitry     — top-level housing container
  rabbit_building     — building within a rabbitry
  rabbit_room         — room within a building
  rabbit_row          — row within a room
  rabbit_cage         — cage / colony pen / quarantine / isolation unit
  rabbit              — the aggregate root (individual rabbit registry)
  rabbit_event        — append-only rabbit timeline
  rabbit_media        — photos / videos / audio
  rabbit_document     — pedigree certificates, vet reports, invoices…

Enumerated fields are stored as ``String`` with the allowed values documented in
the column comment and enforced at the schema/service layer — matching the
Module 14/15/16 convention.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None

# The placeholder rabbit species profile seeded by Migration 007 has
# id 10000000-0000-0000-0000-000000000002; this migration activates it by
# species_key rather than by id.


def _base() -> list[sa.Column]:
    """Standard AGRIOSBase columns (matches app/models/base.py)."""
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Activate the module in the extensibility engine (Spec Part 10 §3) ───────
    # Migration 007 pre-seeded a placeholder rabbit row (is_active=False). Flip it
    # live and refresh its display metadata now that the module is implemented.
    op.execute(
        sa.text(
            """
            UPDATE species_profiles
               SET is_active = true,
                   display_name = 'Rabbits',
                   description = 'Individual-rabbit management — meat, breeding, fiber, pet '
                                 'and show operations with pedigrees, genetics, litters, '
                                 'growth, health and housing.'
             WHERE species_key = 'rabbit'
            """
        )
    )

    # ── Catalog: rabbit_breed (Spec Part 3 §5) ─────────────────────────────────
    op.create_table(
        "rabbit_breed",
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
            comment="commercial_meat | fiber | pet | dual_purpose | heritage | show | laboratory | other",
        ),
        sa.Column("origin", sa.String(150), nullable=True),
        sa.Column(
            "production_purpose",
            sa.String(30),
            nullable=True,
            comment="meat | breeding | fiber | pet | show | mixed",
        ),
        sa.Column(
            "profile",
            JSONB,
            nullable=False,
            server_default="{}",
            comment="Data-driven breed reference (Spec Part 3 §5): adult weight range, "
            "typical litter size, growth characteristics, temperament, notes.",
        ),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_breed_name", "rabbit_breed", ["name"])

    # ── Catalog: rabbit_bloodline (Spec Part 3 §3, §6) ─────────────────────────
    op.create_table(
        "rabbit_bloodline",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("origin", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_bloodline_farm_code"),
    )

    # ── Housing L1: rabbit_rabbitry (Spec Part 1 §6, Part 3 §14) ────────────────
    op.create_table(
        "rabbit_rabbitry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | inactive | maintenance",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_rabbitry_farm_code"),
    )

    # ── Housing L2: rabbit_building ─────────────────────────────────────────────
    op.create_table(
        "rabbit_building",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbitry_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_rabbitry.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_building_farm_code"),
    )

    # ── Housing L3: rabbit_room ─────────────────────────────────────────────────
    op.create_table(
        "rabbit_room",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("building_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_building.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_room_farm_code"),
    )

    # ── Housing L4: rabbit_row ──────────────────────────────────────────────────
    op.create_table(
        "rabbit_row",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("room_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_room.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_row_farm_code"),
    )

    # ── Housing L5: rabbit_cage (Spec Part 2 §11) ───────────────────────────────
    op.create_table(
        "rabbit_cage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("row_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_row.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column(
            "cage_type",
            sa.String(20),
            nullable=False,
            server_default="cage",
            comment="cage | colony_pen | hutch | grow_out | quarantine | isolation | nest | other",
        ),
        sa.Column(
            "capacity",
            sa.Integer,
            nullable=True,
            comment="Maximum rabbits. Occupancy is DERIVED from rabbit.cage_id, never stored.",
        ),
        sa.Column("dimensions", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="available",
            comment="available | occupied | maintenance | cleaning | out_of_service",
        ),
        sa.Column("maintenance_status", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_rabbit_cage_farm_code"),
    )
    op.create_index("ix_rabbit_cage_type", "rabbit_cage", ["cage_type"])
    op.create_index("ix_rabbit_cage_status", "rabbit_cage", ["status"])

    # ── Aggregate root: rabbit (Spec Part 2 §2, Part 3 §4) ─────────────────────
    op.create_table(
        "rabbit",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("breed_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_breed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("bloodline_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_bloodline.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("cage_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_cage.id", ondelete="SET NULL"), nullable=True, index=True),

        # Identity (Spec Part 1 §5, Part 3 §4)
        sa.Column("internal_ref", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("ear_tag", sa.String(100), nullable=True, index=True),
        sa.Column("tattoo", sa.String(100), nullable=True),
        sa.Column("qr_code", sa.String(200), nullable=True, index=True),
        sa.Column("rfid", sa.String(100), nullable=True),

        # Classification (Spec Part 3 §4)
        sa.Column("variety", sa.String(100), nullable=True),
        sa.Column("color", sa.String(100), nullable=True),
        sa.Column(
            "sex",
            sa.String(10),
            nullable=False,
            server_default="unknown",
            comment="buck | doe | unknown",
        ),
        sa.Column(
            "purpose",
            sa.String(30),
            nullable=False,
            server_default="unknown",
            comment="Primary purpose: meat | breeding | fiber | pet | show | replacement | "
            "genetic_improvement | educational | mixed | unknown",
        ),
        sa.Column(
            "purposes",
            JSONB,
            nullable=False,
            server_default="[]",
            comment="Multiple production purposes may be assigned (Spec Part 1 §7).",
        ),

        # Biology (Spec Part 3 §4)
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("dob_estimated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("birth_weight_g", sa.Numeric(10, 2), nullable=True),
        sa.Column("current_weight_g", sa.Numeric(10, 2), nullable=True),

        # Lifecycle & reproduction (Spec Part 1 §8, Part 3 §4)
        sa.Column(
            "lifecycle_stage",
            sa.String(25),
            nullable=False,
            server_default="unknown",
            comment="kit | weaner | grower | breeding_candidate | breeding_adult | retired | unknown",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="active | sold | transferred | deceased | archived",
        ),
        sa.Column(
            "reproductive_status",
            sa.String(25),
            nullable=False,
            server_default="unknown",
            comment="not_bred | bred | pregnant | lactating | open | resting | proven | unproven | unknown",
        ),
        sa.Column(
            "fertility_status",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="fertile | infertile | unproven | unknown",
        ),
        sa.Column(
            "acquisition_type",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="bred | purchased | donated | transferred | unknown",
        ),
        sa.Column("acquired_on", sa.Date, nullable=True),

        # Pedigree links (deterministic; Spec Part 3 §4, §6). Unknown stays NULL.
        sa.Column("sire_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("dam_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True),

        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "internal_ref", name="uq_rabbit_farm_internal_ref"),
        sa.UniqueConstraint("farm_id", "ear_tag", name="uq_rabbit_farm_ear_tag"),
    )
    op.create_index("ix_rabbit_status", "rabbit", ["status"])
    op.create_index("ix_rabbit_sex", "rabbit", ["sex"])
    op.create_index("ix_rabbit_lifecycle_stage", "rabbit", ["lifecycle_stage"])
    op.create_index("ix_rabbit_farm_status", "rabbit", ["farm_id", "status"])

    # ── Immutable history: rabbit_event (Spec Part 8 §14) ──────────────────────
    op.create_table(
        "rabbit_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
            server_default="note",
            comment="created | updated | status_changed | archived | restored | moved | transferred | "
            "sold | purchased | died | bred | kindled | weaned | weight_recorded | health_recorded | "
            "vaccination_recorded | media_added | document_added | note",
        ),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_event_type", "rabbit_event", ["event_type"])

    # ── Attachments: rabbit_media (Spec Part 8 §15) ────────────────────────────
    op.create_table(
        "rabbit_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
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

    # ── Attachments: rabbit_document (Spec Part 8 §15) ─────────────────────────
    op.create_table(
        "rabbit_document",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "document_type",
            sa.String(30),
            nullable=False,
            server_default="other",
            comment="pedigree_certificate | health_certificate | registration | lab_report | "
            "vet_report | purchase_record | sale_document | invoice | other",
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
    op.drop_table("rabbit_document")
    op.drop_table("rabbit_media")
    op.drop_table("rabbit_event")
    op.drop_table("rabbit")
    op.drop_table("rabbit_cage")
    op.drop_table("rabbit_row")
    op.drop_table("rabbit_room")
    op.drop_table("rabbit_building")
    op.drop_table("rabbit_rabbitry")
    op.drop_table("rabbit_bloodline")
    op.drop_table("rabbit_breed")
    # Revert the species profile to its Migration 007 placeholder state
    # (the row itself belongs to Migration 007 and is never deleted here).
    op.execute(
        sa.text(
            """
            UPDATE species_profiles
               SET is_active = false,
                   display_name = 'Rabbit',
                   description = 'Rabbit breeding and meat production. (Future module)'
             WHERE species_key = 'rabbit'
            """
        )
    )
