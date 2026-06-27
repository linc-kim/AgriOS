"""create ai_insights

AGRIOS — Migration 025
Tier 6 — AI Module

Table: ai_insights
  Proactively generated farm insights (8 types, generated at 06:00 Nairobi).
  Insights expire — expires_at is set at generation time (typically 24h for
  alerts, 7 days for info).

Insight types (8, from Engineering Constitution Section 7):
  mortality_spike     — today's rate > 2× last 7-day average
  feed_drop           — today's feed < 80% of 7-day average
  vaccination_overdue — next_due_date has passed
  vaccination_due     — next_due_date within 3 days
  fcr_above_standard  — FCR > breed standard + 20%
  harvest_approaching — flock at 80% of expected cycle
  log_missing         — today not logged by 20:00
  market_price_change — price movement > 10% from prior week

Severity: info | warning | alert | reminder

DB-04: farm_id ✓  DB-01: soft deletes ✓  DB-05: metadata JSONB ✓  AD-01: UUID PK ✓
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None

INSIGHT_SEVERITY_ENUM = sa.Enum(
    "info", "warning", "alert", "reminder",
    name="insight_severity",
)


def upgrade() -> None:
    INSIGHT_SEVERITY_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ai_insights",
        # ── Identity ─────────────────────────────────────────────────────────
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            nullable=False,
        ),
        # ── Farm + optional flock scoping ─────────────────────────────────────
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "flock_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # ── Insight content ───────────────────────────────────────────────────
        sa.Column(
            "insight_type",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "severity",
            INSIGHT_SEVERITY_ENUM,
            nullable=False,
        ),
        # Title and body stored in English; Swahili rendering done client-side
        # via i18n keys in insight_type → translation map
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        # Optional action deep-link (e.g. "/farms/:id/flocks/:id/vaccinations/new")
        sa.Column("action_route", sa.String(300), nullable=True),
        sa.Column("action_label", sa.String(100), nullable=True),
        # ── State ─────────────────────────────────────────────────────────────
        sa.Column(
            "is_dismissed",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("dismissed_at", sa.TIMESTAMPTZ, nullable=True),
        # ── Lifecycle ─────────────────────────────────────────────────────────
        # When the insight was generated (may differ from created_at if batched)
        sa.Column(
            "generated_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMPTZ, nullable=True),
        # ── Timestamps + soft delete + metadata ───────────────────────────────
        sa.Column(
            "created_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMPTZ,
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.TIMESTAMPTZ, nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )

    # Primary query: active insights for a farm, newest first
    op.create_index(
        "ix_ai_insights_farm_id",
        "ai_insights",
        ["farm_id"],
    )
    # Filter by severity for alert banners
    op.create_index(
        "ix_ai_insights_farm_severity",
        "ai_insights",
        ["farm_id", "severity"],
    )
    # Batch expiry job: find all insights past expires_at
    op.create_index(
        "ix_ai_insights_expires_at",
        "ai_insights",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_insights_expires_at", table_name="ai_insights")
    op.drop_index("ix_ai_insights_farm_severity", table_name="ai_insights")
    op.drop_index("ix_ai_insights_farm_id", table_name="ai_insights")
    op.drop_table("ai_insights")
    sa.Enum(name="insight_severity").drop(op.get_bind(), checkfirst=True)
