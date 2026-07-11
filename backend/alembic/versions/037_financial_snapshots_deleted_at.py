"""Migration 037 — add missing deleted_at to financial_snapshots

FinancialSnapshot inherits AGRIOSBase, which provides the soft-delete
``deleted_at`` column, but migration 022 never created it. Every soft-delete
filtered query (e.g. the finance dashboard and per-flock snapshot reads) then
fails with "column financial_snapshots.deleted_at does not exist". This adds the
column so the table matches the model.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financial_snapshots",
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_financial_snapshots_deleted_at",
        "financial_snapshots",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_snapshots_deleted_at", table_name="financial_snapshots"
    )
    op.drop_column("financial_snapshots", "deleted_at")
