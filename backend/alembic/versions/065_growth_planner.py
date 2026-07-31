"""Migration 065 — Growth Planner (Platform, introduced by Module 16)

The canonical, cross-module long-term-growth store (see the Growth Planner
Contract in docs/MODULE_16_BSF_LEDGER.md). NOT bsf_-prefixed — a ``module``
discriminator lets every Greena agricultural module share one planner.

Tables:
  growth_plan            — a farm's plan for one module (aggregate root)
  growth_goal            — measurable targets (metric_key → target by date)
  growth_milestone       — ordered steps toward the goals
  growth_plan_revision   — immutable version-history snapshots (mirrors
                           mission_revisions, Migration 052)

Farm-scoped (org isolation via farms.organization_id); enumerated fields are
strings validated at the schema/service layer.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "065"
down_revision = "064"
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
        "growth_plan",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True),
                  sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module", sa.String(40), nullable=False, index=True,
                  comment="Owning module: bsf | aviculture | poultry | …"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | achieved | archived"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("current_revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_growth_plan_farm_module", "growth_plan", ["farm_id", "module"])

    op.create_table(
        "growth_goal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("baseline_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("target_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open",
                  comment="open | achieved | abandoned"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "growth_milestone",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | in_progress | achieved | blocked | skipped"),
        sa.Column("target_metric_key", sa.String(80), nullable=True),
        sa.Column("target_metric_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("expected_impact", sa.Text, nullable=True),
        sa.Column("dependencies", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_growth_milestone_plan_seq", "growth_milestone", ["plan_id", "sequence"])

    op.create_table(
        "growth_plan_revision",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("growth_plan.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("trigger", sa.String(40), nullable=False, server_default="manual",
                  comment="manual | adaptive | goal_change | milestone_update"),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("plan_id", "revision_number", name="uq_growth_plan_revision_number"),
    )


def downgrade() -> None:
    op.drop_table("growth_plan_revision")
    op.drop_table("growth_milestone")
    op.drop_table("growth_goal")
    op.drop_table("growth_plan")
