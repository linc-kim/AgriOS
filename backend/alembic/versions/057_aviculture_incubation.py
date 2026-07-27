"""Migration 057 — Aviculture Incubation Engine (Module 15, Part 5)

Digitises the whole hatch process (Doc 02 §13-14, Doc 03 §6, Doc 13 Part 5). The
egg lifecycle — collected → stored → set → candled → lockdown → hatched | failed
— is timestamped at every transition (Doc 04 §5) and never loses history.

Deterministic, species-aware by design (Doc 16 §5): incubation period, humidity,
temperature, turning and lockdown timing are read from ``avi_species.profile`` by
the pure ``incubation_engine`` and are never hardcoded. Hatch/fertility statistics
are computed live and honesty-labelled — an empty batch reports "not enough
recorded data", never a fabricated rate.

Tables:
  avi_clutch            — a group of eggs from a pair
  avi_incubation_batch  — an incubation run (natural / artificial / foster)
  avi_egg               — the individual egg (aggregate of the hatch process)
  avi_incubation_log    — daily temperature / humidity / turning log per batch
  avi_candling_record   — candling observations per egg
  avi_hatch_event       — hatch or failure per egg; links the resulting chick
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "057"
down_revision = "056"
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
    # ── Clutch ────────────────────────────────────────────────────────────────
    op.create_table(
        "avi_clutch",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("pair_id", UUID(as_uuid=True), sa.ForeignKey("avi_pair.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("laid_start", sa.Date(), nullable=True),
        sa.Column("expected_eggs", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Incubation batch ──────────────────────────────────────────────────────
    op.create_table(
        "avi_incubation_batch",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("species_id", UUID(as_uuid=True), sa.ForeignKey("avi_species.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="artificial",
                  comment="natural | artificial | foster"),
        sa.Column("incubator_label", sa.String(150), nullable=True),
        sa.Column("set_on", sa.Date(), nullable=True),
        sa.Column("incubation_days", sa.Integer(), nullable=True,
                  comment="From the species profile when known; overridable."),
        sa.Column("target_temperature_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("target_humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("expected_lockdown_on", sa.Date(), nullable=True, comment="Computed by the engine at set time."),
        sa.Column("expected_hatch_on", sa.Date(), nullable=True, comment="Computed by the engine at set time."),
        sa.Column("turning_schedule", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="setting",
                  comment="setting | incubating | lockdown | completed | cancelled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_batch_status", "avi_incubation_batch", ["status"])

    # ── Egg ───────────────────────────────────────────────────────────────────
    op.create_table(
        "avi_egg",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("clutch_id", UUID(as_uuid=True), sa.ForeignKey("avi_clutch.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("avi_incubation_batch.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("pair_id", UUID(as_uuid=True), sa.ForeignKey("avi_pair.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("species_id", UUID(as_uuid=True), sa.ForeignKey("avi_species.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("identifier", sa.String(50), nullable=False, comment="System reference, unique per farm."),
        sa.Column("laid_on", sa.Date(), nullable=True),
        sa.Column("fertility_status", sa.String(20), nullable=False, server_default="unknown",
                  comment="unknown | fertile | infertile | early_death | late_death"),
        sa.Column("weight_grams", sa.Numeric(8, 2), nullable=True),
        sa.Column("length_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column("width_mm", sa.Numeric(6, 2), nullable=True),
        sa.Column("quality", sa.String(20), nullable=False, server_default="good",
                  comment="good | fair | poor | cracked | damaged | soft_shell"),
        sa.Column("storage_location", sa.String(150), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="natural",
                  comment="natural | artificial | foster"),
        sa.Column("set_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="collected",
                  comment="collected | stored | set | candled | lockdown | hatched | failed | discarded"),
        sa.Column("hatched_bird_id", UUID(as_uuid=True), sa.ForeignKey("avi_bird.id", ondelete="SET NULL"),
                  nullable=True, index=True, comment="The chick this egg produced (chick assignment)."),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "identifier", name="uq_avi_egg_farm_identifier"),
    )
    op.create_index("ix_avi_egg_status", "avi_egg", ["status"])

    # ── Daily incubation log ──────────────────────────────────────────────────
    op.create_table(
        "avi_incubation_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("avi_incubation_batch.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=True),
        sa.Column("humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("turns_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_inclog_batch_date", "avi_incubation_log", ["batch_id", "log_date"])

    # ── Candling ──────────────────────────────────────────────────────────────
    op.create_table(
        "avi_candling_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("egg_id", UUID(as_uuid=True), sa.ForeignKey("avi_egg.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("candled_on", sa.Date(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=True, comment="Day of incubation (computed)."),
        sa.Column("result", sa.String(20), nullable=False, server_default="unclear",
                  comment="developing | fertile | infertile | early_death | late_death | unclear"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    # ── Hatch event ───────────────────────────────────────────────────────────
    op.create_table(
        "avi_hatch_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("egg_id", UUID(as_uuid=True), sa.ForeignKey("avi_egg.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("avi_incubation_batch.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("hatched_on", sa.Date(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False,
                  comment="hatched | assisted | dead_in_shell | failed | discarded"),
        sa.Column("assisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("chick_bird_id", UUID(as_uuid=True), sa.ForeignKey("avi_bird.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("hatch_weight_grams", sa.Numeric(8, 2), nullable=True),
        sa.Column("failure_reason", sa.String(150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("avi_hatch_event")
    op.drop_table("avi_candling_record")
    op.drop_table("avi_incubation_log")
    op.drop_table("avi_egg")
    op.drop_table("avi_incubation_batch")
    op.drop_table("avi_clutch")
