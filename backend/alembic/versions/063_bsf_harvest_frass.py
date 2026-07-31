"""Migration 063 — BSF Harvest & Frass (Module 16, Part 4)

Adds the production-output tables:

  bsf_harvest_event   — harvests of larvae/prepupae/pupae/adults/frass from a
                        batch (Spec Part 2 §11, Part 3 §15). Revenue is a recorded
                        fact here (finance ledger is flock-scoped — see the
                        integration contract). Harvested stock optionally references
                        a platform Inventory movement via soft-reference columns.
  bsf_frass_production — frass collected from a batch, traceable to its origin
                        (Spec Part 2 §12, Part 3 §16).

Farm-scoped; enumerated fields are strings validated at the schema/service layer.
``inventory_item_id`` / ``inventory_movement_id`` are deliberately NOT foreign keys
— they are soft references into the Inventory module, keeping BSF decoupled from
the Inventory schema (BSF never owns stock rows).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "063"
down_revision = "062"
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
    # ── bsf_harvest_event ──────────────────────────────────────────────────────
    op.create_table(
        "bsf_harvest_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("harvest_type", sa.String(20), nullable=False, server_default="larvae",
                  comment="larvae | prepupae | pupae | adult | frass | mixed"),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("harvested_on", sa.Date, nullable=False),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("population_estimate", sa.BigInteger, nullable=True),
        sa.Column("quality_grade", sa.String(20), nullable=False, server_default="ungraded",
                  comment="premium | standard | low | reject | ungraded"),
        sa.Column("destination", sa.String(20), nullable=False, server_default="inventory",
                  comment="inventory | sale | feed | processing | disposal | other"),
        sa.Column("revenue_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("buyer_name", sa.String(200), nullable=True),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True,
                  comment="Soft reference into the Inventory module (no FK)."),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True,
                  comment="Soft reference into the Inventory module (no FK)."),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_harvest_batch_on", "bsf_harvest_event", ["batch_id", "harvested_on"])
    op.create_index("ix_bsf_harvest_farm_on", "bsf_harvest_event", ["farm_id", "harvested_on"])

    # ── bsf_frass_production ───────────────────────────────────────────────────
    op.create_table(
        "bsf_frass_production",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collected_on", sa.Date, nullable=False),
        sa.Column("weight_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("moisture_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("quality", sa.String(20), nullable=False, server_default="ungraded"),
        sa.Column("storage_location", sa.String(200), nullable=True),
        sa.Column("inventory_item_id", UUID(as_uuid=True), nullable=True),
        sa.Column("inventory_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_frass_batch_on", "bsf_frass_production", ["batch_id", "collected_on"])


def downgrade() -> None:
    op.drop_table("bsf_frass_production")
    op.drop_table("bsf_harvest_event")
