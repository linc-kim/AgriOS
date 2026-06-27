"""Create expenses table.

Revision ID: 020
Revises: 019
Create Date: 2026-06-26

DESIGN NOTES:
- Farm-scoped (DB-04 Frozen).
- Optional flock_id: ties expense to a specific flock for per-flock P&L.
- amount in KES (currency locked to KES for V1).
- expense_date (Date) — when the expense was incurred, not when recorded.
- receipt_url: optional S3/storage URL for receipt image.
- payment_method: cash | mpesa | bank_transfer | credit
- No UNIQUE constraint — same category/date/amount can occur multiple times (valid).
- Indexes optimised for:
    (farm_id, expense_date) — dashboard date-range queries
    (farm_id, category_id) — category breakdown
    (flock_id) — per-flock P&L
- DB-01: UUID PKs. DB-02: soft deletes. DB-05: metadata JSONB.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expenses",
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
        # Optional — ties expense to a specific flock for per-flock P&L
        sa.Column(
            "flock_id",
            UUID(as_uuid=False),
            sa.ForeignKey("flocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ── Category ────────────────────────────────────────────────────────────
        sa.Column(
            "category_id",
            UUID(as_uuid=False),
            sa.ForeignKey("expense_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # ── Core Fields ─────────────────────────────────────────────────────────
        sa.Column(
            "expense_date",
            sa.Date(),
            nullable=False,
        ),
        # Amount in KES (smallest unit = 1 KES; two decimal places for precision)
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
        ),
        sa.Column("description", sa.String(300), nullable=False),
        # ── Optional Enrichment ─────────────────────────────────────────────────
        sa.Column(
            "payment_method",
            sa.String(20),
            nullable=True,
            comment="cash | mpesa | bank_transfer | credit",
        ),
        sa.Column("receipt_url", sa.String(500), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),  # kg, litres, pieces, etc.
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

    # Primary query pattern: farm dashboard date range
    op.create_index(
        "ix_expenses_farm_date",
        "expenses",
        ["farm_id", "expense_date"],
    )
    # Category breakdown queries
    op.create_index(
        "ix_expenses_farm_category",
        "expenses",
        ["farm_id", "category_id"],
    )
    # Per-flock P&L
    op.create_index(
        "ix_expenses_flock_id",
        "expenses",
        ["flock_id"],
    )
    # Soft delete filter
    op.create_index(
        "ix_expenses_deleted_at",
        "expenses",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_expenses_deleted_at", table_name="expenses")
    op.drop_index("ix_expenses_flock_id", table_name="expenses")
    op.drop_index("ix_expenses_farm_category", table_name="expenses")
    op.drop_index("ix_expenses_farm_date", table_name="expenses")
    op.drop_table("expenses")
