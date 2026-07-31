"""Migration 064 — BSF Mortality (Module 16, Part 5)

Adds ``bsf_mortality_event`` — an immutable record of estimated population loss
in a batch (Spec Part 3 §17). Mortality feeds deterministic health analytics
(survival, mortality trends). Farm-scoped; enumerated ``cause`` validated at the
schema/service layer.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.create_table(
        "bsf_mortality_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("estimated_loss", sa.BigInteger, nullable=False),
        sa.Column("cause", sa.String(20), nullable=False, server_default="unknown",
                  comment="disease | environmental | predation | handling | contamination | "
                  "cannibalism | starvation | unknown | other"),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_mortality_batch_on", "bsf_mortality_event", ["batch_id", "occurred_on"])


def downgrade() -> None:
    op.drop_table("bsf_mortality_event")
