"""Migration 042 — feed inventory batch / brand / expiry

Phase 3, Module 4 (Feed Management) extension. Adds brand, batch number and
expiry date to feed_inventory_items so stock carries its current batch and the
system can raise expiry warnings.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feed_inventory_items", sa.Column("brand", sa.String(length=150), nullable=True))
    op.add_column("feed_inventory_items", sa.Column("batch_number", sa.String(length=100), nullable=True))
    op.add_column("feed_inventory_items", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.create_index("ix_feed_inventory_expiry", "feed_inventory_items", ["expiry_date"])


def downgrade() -> None:
    op.drop_index("ix_feed_inventory_expiry", table_name="feed_inventory_items")
    op.drop_column("feed_inventory_items", "expiry_date")
    op.drop_column("feed_inventory_items", "batch_number")
    op.drop_column("feed_inventory_items", "brand")
