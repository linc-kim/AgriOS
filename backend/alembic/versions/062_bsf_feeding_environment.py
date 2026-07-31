"""Migration 062 — BSF Feedstock, Feeding & Environment (Module 16, Part 3)

Adds the input and environmental-monitoring tables for the BSF module:

  bsf_feedstock_lot         — organic feedstock managed as first-class lots
                              (Spec Part 2 §8, Part 3 §11)
  bsf_feeding_event         — immutable feeding operations consuming a lot
                              (Spec Part 2 §9, Part 3 §12)
  bsf_environmental_reading — immutable temp/humidity/moisture/airflow readings
                              for a production unit (Spec Part 2 §10, Part 3 §13)

Farm-scoped (organisation isolation via ``farms.organization_id``); enumerated
fields are strings validated at the schema/service layer.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "062"
down_revision = "061"
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
    # ── bsf_feedstock_lot ──────────────────────────────────────────────────────
    op.create_table(
        "bsf_feedstock_lot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column(
            "category", sa.String(40), nullable=False, server_default="organic_waste",
            comment="fruit_waste | vegetable_waste | market_waste | brewery_waste | "
            "food_processing_waste | agricultural_byproduct | manure | organic_waste | other",
        ),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("supplier", sa.String(200), nullable=True),
        sa.Column("collection_date", sa.Date, nullable=True),
        sa.Column("delivery_date", sa.Date, nullable=True),
        sa.Column("weight_kg", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("remaining_kg", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("moisture_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("quality", sa.String(20), nullable=False, server_default="unknown",
                  comment="excellent | good | fair | poor | spoiled | unknown"),
        sa.Column("storage_location", sa.String(200), nullable=True),
        sa.Column("cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="available",
                  comment="available | in_use | depleted | spoiled | discarded"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("farm_id", "code", name="uq_bsf_feedstock_farm_code"),
    )
    op.create_index("ix_bsf_feedstock_status", "bsf_feedstock_lot", ["status"])
    op.create_index("ix_bsf_feedstock_farm_status", "bsf_feedstock_lot", ["farm_id", "status"])

    # ── bsf_feeding_event ──────────────────────────────────────────────────────
    op.create_table(
        "bsf_feeding_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("feedstock_lot_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_feedstock_lot.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("quantity_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("feeding_method", sa.String(20), nullable=False, server_default="manual",
                  comment="manual | automated | top_dressing | single_dose | continuous | other"),
        sa.Column("fed_on", sa.Date, nullable=False),
        sa.Column("observations", sa.Text, nullable=True),
        sa.Column("operator_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_feeding_batch_fed_on", "bsf_feeding_event", ["batch_id", "fed_on"])

    # ── bsf_environmental_reading ──────────────────────────────────────────────
    op.create_table(
        "bsf_environmental_reading",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("production_unit_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_production_unit.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("batch_id", UUID(as_uuid=True),
                  sa.ForeignKey("bsf_batch.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Numeric(6, 2), nullable=True),
        sa.Column("humidity_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("moisture_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("airflow_mps", sa.Numeric(6, 2), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual",
                  comment="manual | sensor | scheduled"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_bsf_env_unit_recorded_at", "bsf_environmental_reading",
                    ["production_unit_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("bsf_environmental_reading")
    op.drop_table("bsf_feeding_event")
    op.drop_table("bsf_feedstock_lot")
