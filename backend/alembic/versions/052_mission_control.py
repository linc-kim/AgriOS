"""Migration 052 — Mission Control (Module 14)

The strategic layer on top of the deterministic engines. Two tables:

  * missions           — a farmer's long-term goal, its metrics, constraints,
                         priorities, editable assumptions and policies, and the
                         baseline captured at creation. Roadmap, business plan,
                         daily mission, progress and reports are all COMPUTED
                         live from this plus recorded facts, so they never go
                         stale and no projection is ever frozen into a table.
  * mission_revisions  — an append-only history of plan revisions. The original
                         is never overwritten (Part 7 of the spec); each replan
                         snapshots the assumptions it was based on.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def _base():
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.create_table(
        "missions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        # draft | active | achieved | archived
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("success_metrics", JSONB, nullable=False, server_default="[]"),
        sa.Column("constraints", JSONB, nullable=False, server_default="[]"),
        sa.Column("priorities", JSONB, nullable=False, server_default="[]"),
        sa.Column("assumptions", JSONB, nullable=False, server_default="[]"),
        sa.Column("policies", JSONB, nullable=False, server_default="[]"),
        # Snapshot of the metrics at creation, so progress has an honest baseline.
        sa.Column("baseline", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "mission_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("mission_id", UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        # manual | assumption_drift | metric_change
        sa.Column("trigger", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("mission_id", "revision_number", name="uq_mission_revision_number"),
    )


def downgrade() -> None:
    op.drop_table("mission_revisions")
    op.drop_table("missions")
