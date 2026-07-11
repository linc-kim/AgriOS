"""Migration 039 — daily_logs: add culls

Phase 3 (Daily Operations): record birds culled per day, distinct from
mortality. Culls reduce the live bird count just like mortality.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_logs",
        sa.Column(
            "culls",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("daily_logs", "culls")
