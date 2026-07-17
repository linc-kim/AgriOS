"""Migration 043 — add 'chicks' to the revenue_type enum

Module 5 (Finance) adds chick sales as a first-class revenue type. This is a
purely additive change to the existing native ``revenue_type`` enum — no data
is altered. ``ALTER TYPE ... ADD VALUE`` runs in its own autocommit block
because a new enum value cannot be added and used inside the same transaction.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE revenue_type ADD VALUE IF NOT EXISTS 'chicks'")


def downgrade() -> None:
    # Postgres does not support removing a value from an enum type; this is a
    # one-way additive migration. Downgrade is a no-op.
    pass
