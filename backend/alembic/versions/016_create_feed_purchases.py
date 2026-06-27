"""Migration 016 — Create feed_purchases table

Revision ID: 016
Revises: 015
Create Date: 2025-01-01 00:15:00.000000

Feed purchases track stock buying events at the farm or flock level.
flock_id is nullable — a purchase can be farm-wide stock not yet assigned
to a specific flock, or it can be tied to an active flock.

Feed type examples:
  - Starter (0–14 days)
  - Grower (15–28 days)
  - Finisher (29+ days)
  - Layer Mash
  - Pre-Lay

total_cost is denormalised at insert time (quantity_kg * price_per_kg).
This protects historical records from future price changes.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional: link purchase to a specific active flock.",
        ),
        sa.Column("purchase_date", sa.Date, nullable=False),
        sa.Column(
            "feed_type",
            sa.String(100),
            nullable=False,
            comment="e.g. Starter, Grower, Finisher, Layer Mash",
        ),
        sa.Column(
            "quantity_kg",
            sa.Numeric(10, 3),
            nullable=False,
        ),
        sa.Column(
            "price_per_kg",
            sa.Numeric(10, 2),
            nullable=False,
            comment="KES per kg at time of purchase.",
        ),
        sa.Column(
            "total_cost",
            sa.Numeric(12, 2),
            nullable=False,
            comment="Denormalised: quantity_kg * price_per_kg at insert time.",
        ),
        sa.Column(
            "supplier",
            sa.String(255),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "recorded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.create_index("ix_feed_purchases_id", "feed_purchases", ["id"])
    op.create_index("ix_feed_purchases_farm_id", "feed_purchases", ["farm_id"])
    op.create_index("ix_feed_purchases_flock_id", "feed_purchases", ["flock_id"])
    op.create_index(
        "ix_feed_purchases_farm_date",
        "feed_purchases",
        ["farm_id", "purchase_date"],
    )
    op.create_index("ix_feed_purchases_deleted_at", "feed_purchases", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("feed_purchases")
