"""Migration 089 — Commercial Policy: trial fields on subscriptions (C2)

Explicit trial metadata on ``subscriptions`` so the trial is not overloaded onto
``status`` (which stays active/expired/cancelled). ``is_trial`` marks a running
trial; ``trial_ends_at`` is when it lapses (also mirrored in current_period_end
so the existing expiry sweep downgrades it). One 21-day Professional trial per
organization, granted at creation.
"""

import sqlalchemy as sa
from alembic import op

revision = "089"
down_revision = "088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("is_trial", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "trial_ends_at")
    op.drop_column("subscriptions", "is_trial")
