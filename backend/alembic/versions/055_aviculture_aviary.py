"""Migration 055 — Aviculture Aviary Management (Module 15, Part 3)

Part 1 gave every bird an identity; Part 3 digitises the facility that houses
them (Doc 02 §15, Doc 03 §7). Everything extends the Part 1 ``avi_aviary`` root —
nothing already built is redesigned.

Design notes:
  * Occupancy is NEVER stored — it is computed live from the birds that reference
    an aviary (``avi_bird.aviary_id``) by the pure ``aviary_engine`` (Doc 14 §2-3).
    Storing it would duplicate a fact already recorded on the bird.
  * "Buildings" and "biosecurity zones" are modelled as attributes on the aviary
    (``building``, ``biosecurity_level``, ``purpose``) rather than separate
    entities — a grouping label and a classification, not their own aggregates.
  * Nest boxes, perches, feed/water stations, equipment and plants share one
    discriminated ``avi_aviary_fixture`` table (``fixture_type``) instead of five
    near-identical tables — the same modelling choice used for bird events.

New tables:
  avi_aviary_zone           — zones / sections / flights within an aviary
  avi_aviary_fixture        — nest boxes, perches, feeders, drinkers, equipment…
  avi_environmental_reading — temperature / humidity / light monitoring
  avi_aviary_task           — cleaning & maintenance schedule + history
  avi_aviary_event          — aviary timeline
  avi_aviary_media          — photos / videos / documents of the aviary
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Extend the Part 1 aviary root ─────────────────────────────────────────
    op.add_column("avi_aviary", sa.Column("building", sa.String(150), nullable=True,
                  comment="Optional grouping label (e.g. 'Breeding Barn A')."))
    op.add_column("avi_aviary", sa.Column("purpose", sa.String(30), nullable=False, server_default="general",
                  comment="general | breeding | quarantine | nursery | display | flight | holding"))
    op.add_column("avi_aviary", sa.Column("biosecurity_level", sa.String(20), nullable=False, server_default="standard",
                  comment="none | standard | high | quarantine (Doc 16 §7 biosecurity)."))

    # ── Zones / sections / flights ────────────────────────────────────────────
    op.create_table(
        "avi_aviary_zone",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("zone_type", sa.String(30), nullable=False, server_default="zone",
                  comment="zone | section | flight | nursery | holding | other"),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Fixtures (nest boxes, perches, feeders, drinkers, equipment, plants) ──
    op.create_table(
        "avi_aviary_fixture",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("zone_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary_zone.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("fixture_type", sa.String(30), nullable=False,
                  comment="nest_box | perch | feeder | drinker | feed_station | "
                  "water_station | equipment | plant | other"),
        sa.Column("label", sa.String(150), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active",
                  comment="active | needs_maintenance | out_of_service | removed"),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_fixture_type", "avi_aviary_fixture", ["fixture_type"])

    # ── Environmental monitoring ──────────────────────────────────────────────
    op.create_table(
        "avi_environmental_reading",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("temperature_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("light_hours", sa.Numeric(4, 1), nullable=True),
        sa.Column("air_quality", sa.String(50), nullable=True),
        sa.Column("noise_level", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_env_aviary_time", "avi_environmental_reading", ["aviary_id", "recorded_at"])

    # ── Cleaning & maintenance (schedule + history) ───────────────────────────
    op.create_table(
        "avi_aviary_task",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_type", sa.String(30), nullable=False,
                  comment="cleaning | disinfection | maintenance | inspection | repair | other"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled",
                  comment="scheduled | in_progress | completed | cancelled"),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="none",
                  comment="none | daily | weekly | monthly | quarterly | seasonal"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("performed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_task_aviary_status", "avi_aviary_task", ["aviary_id", "status"])

    # ── Aviary timeline ───────────────────────────────────────────────────────
    op.create_table(
        "avi_aviary_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_aviary_event_time", "avi_aviary_event", ["aviary_id", "occurred_on"])

    # ── Aviary media / attachments ────────────────────────────────────────────
    op.create_table(
        "avi_aviary_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("aviary_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_aviary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("media_type", sa.String(20), nullable=False, server_default="photo"),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("avi_aviary_media")
    op.drop_table("avi_aviary_event")
    op.drop_table("avi_aviary_task")
    op.drop_table("avi_environmental_reading")
    op.drop_table("avi_aviary_fixture")
    op.drop_table("avi_aviary_zone")
    op.drop_column("avi_aviary", "biosecurity_level")
    op.drop_column("avi_aviary", "purpose")
    op.drop_column("avi_aviary", "building")
