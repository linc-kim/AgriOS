"""create_market_prices

Revision ID: 030
Revises: 029
Create Date: 2026-06-26

Sprint 7 — Platform Layer (Tier 7) — FINAL MIGRATION
Table: market_prices — Admin-curated price data.

DB-09 (Frozen): market_prices is historical — new rows only, existing rows
are NEVER updated. This is enforced at the application layer (no PATCH/PUT
endpoint exists). Correction = new row.

Intentional deviations from AGRIOSBase (documented exceptions):
  - No soft delete (deleted_at) — prices are immutable historical records
  - No updated_at — records are never updated
  - No metadata JSONB — not extensible per DB-09 historical constraint
  - No farm_id — market prices are platform-wide, not farm-scoped (documented exception to DB-04)

Columns:
  - id (UUID PK)
  - commodity (String 100) — e.g. "broiler_live", "layer_egg_tray", "day_old_chick"
  - price_kes (Numeric 14,2) — price in KES
  - unit (String 50) — e.g. "per_kg", "per_tray_30", "per_chick"
  - county (String 100, nullable) — null = national average
  - source (String 200, nullable) — e.g. "Kenya Poultry Farmers Association"
  - valid_date (Date) — the date this price is valid for
  - recorded_by_id (FK → users SET NULL, nullable) — admin who recorded it
  - created_at (TIMESTAMPTZ) — immutable
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import Numeric

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_prices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("commodity", sa.String(100), nullable=False),
        sa.Column("price_kes", Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("valid_date", sa.Date, nullable=False),
        sa.Column(
            "recorded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Immutable timestamp — no updated_at, no deleted_at
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Indexes
    op.create_index(
        "ix_market_prices_commodity_date",
        "market_prices",
        ["commodity", "valid_date"],
    )
    op.create_index(
        "ix_market_prices_valid_date",
        "market_prices",
        ["valid_date"],
    )
    op.create_index(
        "ix_market_prices_county",
        "market_prices",
        ["county"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_prices_county", table_name="market_prices")
    op.drop_index("ix_market_prices_valid_date", table_name="market_prices")
    op.drop_index("ix_market_prices_commodity_date", table_name="market_prices")
    op.drop_table("market_prices")
