"""Migration 038 — flocks: add source + archived_at

Phase 3 (Flock Management): record where a flock's birds came from (hatchery /
supplier) and support archiving a flock (hiding it from the active list without
altering its lifecycle status). Archiving is orthogonal to status, so it is a
nullable timestamp rather than a new status enum value.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "flocks",
        sa.Column("source", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "flocks",
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_flocks_archived_at", "flocks", ["archived_at"])


def downgrade() -> None:
    op.drop_index("ix_flocks_archived_at", table_name="flocks")
    op.drop_column("flocks", "archived_at")
    op.drop_column("flocks", "source")
