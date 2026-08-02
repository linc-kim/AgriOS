"""Migration 083 — Swine Feed & Nutrition (Module 20, Milestone 5)

Feed catalog, feed plans by production stage, and the feeding consumption log
(Swine Doc 2 §13, Doc 3 §17, Doc 5 §6). Consumption REUSES the platform Inventory
module: a feeding that references an inventory item posts a stock-decrement movement
and snapshots its cost — feed is expensed ONCE at stock-in and never re-posted
(frozen finance rule). ``inventory_item_id`` / ``inventory_movement_id`` are soft
references (no FK) so the modules stay decoupled.

Tables:
  swine_feed        — data-driven feed catalog (org-scoped; nutrient profile)
  swine_feed_plan   — feeding-plan entries (plan_name × production_stage → feed + target)
  swine_feed_record — feeding events (pig/group; inventory-linked; cost snapshot)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "083"
down_revision = "082"
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
    op.create_table(
        "swine_feed",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True,
                  comment="NULL = global/system feed shared by all organisations."),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="other",
                  comment="starter | creep | nursery | grower | finisher | developer | gestation | "
                  "lactation | boar | mineral | supplement | medicated | other"),
        sa.Column("form", sa.String(20), nullable=False, server_default="pellet",
                  comment="pellet | crumble | mash | meal | liquid | paste | other"),
        sa.Column("profile", JSONB, nullable=False, server_default="{}",
                  comment="Nutrient reference: crude protein %, ME, lysine, etc."),
        sa.Column("is_medicated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("withdrawal_days", sa.Integer, nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_feed_name", "swine_feed", ["name"])

    op.create_table(
        "swine_feed_plan",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_name", sa.String(150), nullable=False, index=True),
        sa.Column("production_stage", sa.String(20), nullable=False, server_default="unknown",
                  comment="piglet | weaner | nursery | grower | finisher | breeding | ... | unknown"),
        sa.Column("phase_label", sa.String(100), nullable=True),
        sa.Column("feed_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_feed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("daily_amount_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("age_start_days", sa.Integer, nullable=True),
        sa.Column("age_end_days", sa.Integer, nullable=True),
        sa.Column("target_weight_start_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("target_weight_end_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "swine_feed_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("pig_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_pig.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("feed_id", UUID(as_uuid=True),
                  sa.ForeignKey("swine_feed.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True,
                  comment="Soft reference into the platform Inventory module (no FK)."),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("feed_name", sa.String(150), nullable=True),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("fed_on", sa.Date, nullable=False),
        sa.Column("cost", sa.Numeric(14, 2), nullable=True,
                  comment="Snapshot allocation; never re-posted to finance (expensed at stock-in)."),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_swine_feed_record_fed_on", "swine_feed_record", ["fed_on"])


def downgrade() -> None:
    op.drop_table("swine_feed_record")
    op.drop_table("swine_feed_plan")
    op.drop_table("swine_feed")
