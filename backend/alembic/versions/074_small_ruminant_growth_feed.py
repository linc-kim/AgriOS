"""Migration 074 — Small Ruminant Growth, Weight & Feed (Modules 18/19, Milestone 4)

Growth tracking and the feeding log, shared by goats and sheep (Goat Doc 2 §11,
§13). Weights are immutable and in kilograms; the feeding log reuses the platform
Inventory module via SOFT references (no FK) — feed is expensed once at Inventory
stock-in, never re-posted here.

Tables:
  sr_weight       — immutable weight/body-condition measurements (kg)
  sr_feed_record  — feeding log (soft Inventory refs)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "074"
down_revision = "073"
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
        "sr_weight",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=False),
        sa.Column("method", sa.String(15), nullable=False, server_default="scale",
                  comment="scale | tape | estimate | unknown"),
        sa.Column("body_condition_score", sa.Numeric(3, 1), nullable=True, comment="BCS 1–5"),
        sa.Column("heart_girth_cm", sa.Numeric(6, 1), nullable=True),
        sa.Column("height_cm", sa.Numeric(6, 1), nullable=True),
        sa.Column("body_length_cm", sa.Numeric(6, 1), nullable=True),
        sa.Column("age_days", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "sr_feed_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("species", sa.String(10), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("animal_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_animal.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("group_id", UUID(as_uuid=True),
                  sa.ForeignKey("sr_group.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True,
                  comment="SOFT ref into platform Inventory (no FK)."),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True,
                  comment="SOFT ref to the consumption movement (no FK)."),
        sa.Column("feed_type", sa.String(150), nullable=True),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("fed_on", sa.Date, nullable=False),
        sa.Column("is_mineral", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cost", sa.Numeric(14, 2), nullable=True,
                  comment="Snapshot allocation (already expensed at Inventory stock-in). Never re-posted."),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("sr_feed_record")
    op.drop_table("sr_weight")
