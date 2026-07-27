"""Migration 059 — Aviculture Valuation (Module 15, Part 7)

Part 7 reuses the existing Greena Finance and Inventory engines rather than
duplicating them (Doc 13 Part 7: "No duplicated finance engine"):

  * Operational costs (feed, medication, equipment, bird purchases) post to the
    shared ``expenses`` ledger via ``finance_service.log_expense`` (flock_id=None).
  * Feed/medication/equipment stock, consumption, suppliers and assets reuse the
    existing farm-level Inventory module as-is.

The one genuinely aviculture-specific financial concept the platform does not
already provide is **collection valuation** — appraised/insured/market values of
individual birds (championship stock, rare species, breeding birds). That is not
an expense or revenue, so it gets its own recorded-fact table. The valuation
*calculation* lives in a pure engine; this table only stores recorded values.

Table:
  avi_valuation — a recorded valuation of a bird (or the whole collection).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "avi_valuation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("bird_id", UUID(as_uuid=True), sa.ForeignKey("avi_bird.id", ondelete="CASCADE"),
                  nullable=True, index=True, comment="NULL = a collection-level valuation."),
        sa.Column("valued_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="KES"),
        sa.Column("method", sa.String(20), nullable=False, server_default="appraised",
                  comment="appraised | market | insured | purchase | sale | breeding_value"),
        sa.Column("source", sa.String(200), nullable=True, comment="Who/what set the value."),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_avi_valuation_bird_current", "avi_valuation", ["bird_id", "valued_on"])


def downgrade() -> None:
    op.drop_table("avi_valuation")
