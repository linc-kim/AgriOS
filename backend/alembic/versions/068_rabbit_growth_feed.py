"""Migration 068 — Rabbit Growth, Weight & Feed (Module 17, Milestone 4)

Weight recording and feeding (Spec Part 2 §7-9, Part 3 §9-10, Part 4 §8-10).

Weight history is immutable — historical records are never overwritten (Spec
Part 3 §9); ``rabbit.current_weight_g`` (added in Migration 066) only mirrors the
latest for fast display. Growth (ADG, percentiles, deviations) is computed by the
deterministic engine on read, never stored.

Feed **reuses the platform Inventory module** (ledger CON-M4-1): ``rabbit_feed_record``
is a domain feeding log, not a duplicate inventory. When a feeding references an
Inventory feed item, the service posts a ``consumption`` movement (decrement, no
new expense); ``inventory_item_id`` / ``inventory_movement_id`` are SOFT references
into Inventory (no FK — modules stay decoupled).

Tables:
  rabbit_weight       — immutable weight measurements
  rabbit_feed_record  — feeding log (rabbit / cage / farm-level), Inventory-linked
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "068"
down_revision = "067"
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
    # ── Immutable weight measurements (Spec Part 3 §9) ─────────────────────────
    op.create_table(
        "rabbit_weight",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("weight_g", sa.Numeric(10, 2), nullable=False),
        sa.Column("age_days", sa.Integer, nullable=True,
                  comment="Age at recording, if the rabbit's DOB is known (recorded snapshot)."),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_weight_rabbit_date", "rabbit_weight", ["rabbit_id", "recorded_on"])

    # ── Feeding log (reuses platform Inventory — ledger CON-M4-1) ───────────────
    op.create_table(
        "rabbit_feed_record",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rabbit_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit.id", ondelete="SET NULL"), nullable=True, index=True,
                  comment="NULL for group/cage/farm-level feeding (Spec Part 3 §10)."),
        sa.Column("cage_id", UUID(as_uuid=True),
                  sa.ForeignKey("rabbit_cage.id", ondelete="SET NULL"), nullable=True, index=True),
        # Soft references into the platform Inventory module (no FK — decoupled).
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("feed_type", sa.String(150), nullable=True),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("fed_on", sa.Date, nullable=False),
        sa.Column("cost", sa.Numeric(14, 2), nullable=True,
                  comment="Cost allocation snapshot (qty × avg_cost, or manual). "
                          "NOT re-posted to finance — feed is expensed once at stock_in."),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_rabbit_feed_farm_date", "rabbit_feed_record", ["farm_id", "fed_on"])


def downgrade() -> None:
    op.drop_table("rabbit_feed_record")
    op.drop_table("rabbit_weight")
