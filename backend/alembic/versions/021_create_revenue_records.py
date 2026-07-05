"""Create revenue_records table.

Revision ID: 021
Revises: 020
Create Date: 2026-06-26

DESIGN NOTES:
- Farm-scoped + flock-scoped (both required for revenue — revenue is always
  tied to a specific flock batch. DB-04 Frozen).
- revenue_type ENUM: eggs | birds | manure | other
  * eggs: daily/weekly egg sale proceeds
  * birds: sale of live birds or slaughtered carcasses
  * manure: manure/litter sale
  * other: miscellaneous income
- unit_price + quantity = amount (denormalised for quick reporting).
  amount is stored explicitly so it can be overridden (e.g. lump-sum deal).
- buyer_name: optional — tracks who bought (useful for repeat buyer analytics).
- For bird sales: birds_sold column tracks head count (separate from quantity).
- No UNIQUE constraint — multiple revenue records per day valid.
- Indexes: (farm_id, revenue_date), (flock_id), (revenue_type, farm_id).
- DB-01: UUID PKs. DB-02: soft deletes. DB-05: metadata JSONB.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
import uuid


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Revenue type enum — postgresql.ENUM so create_type=False is honoured;
    # created once here, then the same object is reused in the column below.
    revenue_type_enum = ENUM(
        "eggs",
        "birds",
        "manure",
        "other",
        name="revenue_type",
        create_type=False,
    )
    revenue_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "revenue_records",
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
            sa.ForeignKey("flocks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # ── Revenue Classification ───────────────────────────────────────────────
        sa.Column(
            "revenue_type",
            revenue_type_enum,
            nullable=False,
        ),
        # ── Core Financials ─────────────────────────────────────────────────────
        sa.Column("revenue_date", sa.Date(), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            comment="Total in KES",
        ),
        # Line-item detail (optional but encouraged for accurate P&L)
        sa.Column(
            "quantity",
            sa.Numeric(precision=12, scale=3),
            nullable=True,
            comment="e.g. number of trays, kg of birds, bags of manure",
        ),
        sa.Column(
            "unit",
            sa.String(20),
            nullable=True,
            comment="tray | kg | bird | bag | piece",
        ),
        sa.Column(
            "unit_price",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
            comment="Price per unit in KES",
        ),
        # ── Bird Sale Fields ─────────────────────────────────────────────────────
        # Only used when revenue_type = 'birds'
        sa.Column(
            "birds_sold",
            sa.Integer(),
            nullable=True,
            comment="Number of birds sold (revenue_type=birds only)",
        ),
        sa.Column(
            "avg_weight_kg",
            sa.Numeric(precision=6, scale=3),
            nullable=True,
            comment="Average live weight per bird at sale",
        ),
        # ── Egg Sale Fields ──────────────────────────────────────────────────────
        # Only used when revenue_type = 'eggs'
        sa.Column(
            "eggs_count",
            sa.Integer(),
            nullable=True,
            comment="Number of eggs sold",
        ),
        sa.Column(
            "trays_count",
            sa.Integer(),
            nullable=True,
            comment="Number of trays (30-egg standard tray)",
        ),
        # ── Buyer Info ───────────────────────────────────────────────────────────
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("buyer_phone", sa.String(20), nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # ── Audit ───────────────────────────────────────────────────────────────
        sa.Column(
            "created_by",
            UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # ── Extensibility ───────────────────────────────────────────────────────
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    op.create_index(
        "ix_revenue_records_farm_date",
        "revenue_records",
        ["farm_id", "revenue_date"],
    )
    op.create_index(
        "ix_revenue_records_flock_id",
        "revenue_records",
        ["flock_id"],
    )
    op.create_index(
        "ix_revenue_records_type_farm",
        "revenue_records",
        ["revenue_type", "farm_id"],
    )
    op.create_index(
        "ix_revenue_records_deleted_at",
        "revenue_records",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_revenue_records_deleted_at", table_name="revenue_records")
    op.drop_index("ix_revenue_records_type_farm", table_name="revenue_records")
    op.drop_index("ix_revenue_records_flock_id", table_name="revenue_records")
    op.drop_index("ix_revenue_records_farm_date", table_name="revenue_records")
    op.drop_table("revenue_records")
    ENUM(name="revenue_type").drop(op.get_bind(), checkfirst=True)
