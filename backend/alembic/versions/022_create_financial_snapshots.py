"""Create financial_snapshots table.

Revision ID: 022
Revises: 021
Create Date: 2026-06-26

DESIGN NOTES:
- DB-07 Frozen: financial_snapshots stores PRE-COMPUTED P&L — NEVER real-time
  aggregated in API responses. Snapshots are computed and persisted by the
  finance service whenever expenses/revenue are mutated, and on flock close.
- One snapshot per flock (farm_id + flock_id, UNIQUE).
  Updated in-place rather than versioned. The snapshot is a living summary
  of the flock's current financial state.
- snapshot_at: when the snapshot was last computed.
- Fields capture the full P&L picture:
    total_revenue_kes        — sum of all revenue_records
    total_expenses_kes       — sum of all expenses (flock-linked)
    gross_profit_kes         — total_revenue - total_expenses
    gross_margin_pct         — gross_profit / total_revenue * 100
    cost_per_bird_kes        — total_expenses / initial_bird_count
    revenue_per_bird_kes     — total_revenue / birds_sold (or initial if none)
    feed_cost_kes            — expenses in feed_purchase + feed_supplements categories
    feed_cost_pct            — feed_cost / total_expenses * 100
    doc_cost_kes             — DOC purchase cost
    other_cost_kes           — all non-feed, non-DOC expenses
    fcr_computed             — total_feed_kg / total_live_weight_sold_kg
    break_even_price_kes     — total_expenses / birds_sold (per bird)
    is_profitable            — gross_profit_kes > 0
    days_to_break_even       — computed at service layer (nullable)
- bird_count_snapshot: bird count at time of last snapshot (for FCR denominator).
- total_feed_kg: cumulative feed consumed (from daily logs).
- Indexes: (farm_id, flock_id) UNIQUE, (farm_id, is_profitable).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_snapshots",
        # ── Identity ────────────────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        # ── Scope ───────────────────────────────────────────────────────────────
        sa.Column(
            "farm_id",
            UUID(as_uuid=False),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "flock_id",
            UUID(as_uuid=False),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ── Snapshot Metadata ────────────────────────────────────────────────────
        sa.Column(
            "snapshot_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="When this snapshot was last computed",
        ),
        # ── Revenue ──────────────────────────────────────────────────────────────
        sa.Column(
            "total_revenue_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "revenue_eggs_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "revenue_birds_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "revenue_manure_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "revenue_other_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        # ── Expenses ─────────────────────────────────────────────────────────────
        sa.Column(
            "total_expenses_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "feed_cost_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
            comment="Feed purchase + supplements",
        ),
        sa.Column(
            "doc_cost_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
            comment="Day-old chick purchase cost",
        ),
        sa.Column(
            "vet_health_cost_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
            comment="Vaccination + medication + vet fees",
        ),
        sa.Column(
            "labour_cost_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "other_cost_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
        ),
        # ── P&L Computed Fields ──────────────────────────────────────────────────
        sa.Column(
            "gross_profit_kes",
            sa.Numeric(precision=16, scale=2),
            nullable=False,
            server_default="0",
            comment="total_revenue - total_expenses",
        ),
        sa.Column(
            "gross_margin_pct",
            sa.Numeric(precision=7, scale=4),
            nullable=True,
            comment="gross_profit / total_revenue * 100. NULL if revenue = 0",
        ),
        sa.Column(
            "is_profitable",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # ── Per-Bird Metrics ─────────────────────────────────────────────────────
        sa.Column(
            "cost_per_bird_kes",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment="total_expenses / initial_bird_count",
        ),
        sa.Column(
            "revenue_per_bird_kes",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "break_even_price_kes",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment="total_expenses / birds_sold — price needed to break even per bird",
        ),
        # ── FCR ──────────────────────────────────────────────────────────────────
        sa.Column(
            "total_feed_kg",
            sa.Numeric(precision=12, scale=3),
            nullable=False,
            server_default="0",
            comment="Cumulative feed from daily logs",
        ),
        sa.Column(
            "fcr_computed",
            sa.Numeric(precision=6, scale=3),
            nullable=True,
            comment="total_feed_kg / total_live_weight_sold_kg",
        ),
        # ── Flock State at Snapshot ──────────────────────────────────────────────
        sa.Column(
            "bird_count_snapshot",
            sa.Integer(),
            nullable=True,
            comment="Current bird count at snapshot time",
        ),
        sa.Column(
            "birds_sold_snapshot",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "feed_cost_pct",
            sa.Numeric(precision=7, scale=4),
            nullable=True,
            comment="feed_cost_kes / total_expenses_kes * 100",
        ),
        # ── Audit ───────────────────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # ── Extensibility ───────────────────────────────────────────────────────
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    # One snapshot per flock
    op.create_unique_constraint(
        "uq_financial_snapshots_flock_id",
        "financial_snapshots",
        ["flock_id"],
    )
    op.create_index(
        "ix_financial_snapshots_farm_id",
        "financial_snapshots",
        ["farm_id"],
    )
    op.create_index(
        "ix_financial_snapshots_farm_profitable",
        "financial_snapshots",
        ["farm_id", "is_profitable"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_snapshots_farm_profitable", table_name="financial_snapshots")
    op.drop_index("ix_financial_snapshots_farm_id", table_name="financial_snapshots")
    op.drop_constraint("uq_financial_snapshots_flock_id", "financial_snapshots", type_="unique")
    op.drop_table("financial_snapshots")
