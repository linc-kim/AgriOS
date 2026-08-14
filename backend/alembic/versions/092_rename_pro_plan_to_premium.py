"""Rename the 'pro' plan display name to 'Premium'.

The paid trial and the primary paid tier are marketed as **Greena Premium**
(KES 1,499/mo). The plan's internal key stays ``pro`` (code references it by
name); only the customer-facing ``display_name`` changes, so the website, the
in-app trial messaging and checkout all read one consistent name via the public
plans endpoint. Data-only and reversible — no schema change.

Revision ID: 092
Revises: 091
Create Date: 2026-08-14
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only touch the row if it still carries the old display name, so a manual
    # rename or re-run is idempotent and nothing else is disturbed.
    op.execute(
        "UPDATE subscription_plans "
        "SET display_name = 'Premium' "
        "WHERE name = 'pro' AND display_name = 'Professional'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE subscription_plans "
        "SET display_name = 'Professional' "
        "WHERE name = 'pro' AND display_name = 'Premium'"
    )
