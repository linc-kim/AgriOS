"""Migration 018 — Create disease_alerts table

Revision ID: 018
Revises: 017
Create Date: 2025-01-01 00:17:00.000000

Disease alerts are platform-wide announcements published by the AGRIOS admin
(super_admin role). They are NOT farm-specific — they target a county and/or
species.

Key design decisions:
- NO farm_id — alerts apply to all farms in a county. This is a platform-level
  table, not an operational farm table. DB-04 Frozen does not apply here.
- `county` is nullable — a null county means the alert applies to all counties
  (national alert).
- `species_key` is nullable — a null species_key means the alert applies to
  all species (future-proofing for when other species modules are active).
- `status`: draft → active → deactivated (admin workflow)
- `severity`: info, warning, critical
- `sms_dispatched_at`: set when bulk SMS was sent to all targeted farm owners.
  Null until dispatched. Enforces idempotent SMS dispatch (don't re-send).
- Published by `published_by` (FK to users — super_admin only at application layer).
- Expiry: `expires_at` is optional. Alerts without an expiry remain active
  until explicitly deactivated.
- Historical: alerts are never deleted — only deactivated. `deleted_at` is
  kept for consistency with the schema convention but should never be set
  by application code.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

ALERT_STATUS_VALUES = ("draft", "active", "deactivated")
ALERT_SEVERITY_VALUES = ("info", "warning", "critical")


def upgrade() -> None:
    # ── Alert status ENUM ──────────────────────────────────────────────────────
    alert_status_enum = sa.Enum(
        *ALERT_STATUS_VALUES,
        name="alert_status",
        create_constraint=True,
    )
    alert_status_enum.create(op.get_bind(), checkfirst=True)

    # ── Alert severity ENUM ────────────────────────────────────────────────────
    alert_severity_enum = sa.Enum(
        *ALERT_SEVERITY_VALUES,
        name="alert_severity",
        create_constraint=True,
    )
    alert_severity_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "disease_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # ── Targeting (no farm_id — platform-wide) ─────────────────────────────
        sa.Column(
            "county",
            sa.String(100),
            nullable=True,
            comment=(
                "Kenya county this alert targets. NULL = national (all counties). "
                "Matches farms.county for dispatch targeting."
            ),
        ),
        sa.Column(
            "species_key",
            sa.String(50),
            nullable=True,
            comment="Species this alert targets. NULL = all species. FK to species_profiles.",
        ),
        # ── Alert content ──────────────────────────────────────────────────────
        sa.Column(
            "disease_name",
            sa.String(200),
            nullable=False,
            comment="e.g. Newcastle Disease, Avian Influenza H5N1, Gumboro",
        ),
        sa.Column(
            "title",
            sa.String(300),
            nullable=False,
            comment="Short alert title for notification display.",
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=False,
            comment="Full alert description with guidance.",
        ),
        sa.Column(
            "brief_guidance",
            sa.String(500),
            nullable=True,
            comment="Short actionable guidance for SMS dispatch (max ~160 chars).",
        ),
        sa.Column(
            "severity",
            alert_severity_enum,
            nullable=False,
            server_default="warning",
        ),
        sa.Column(
            "status",
            alert_status_enum,
            nullable=False,
            server_default="draft",
        ),
        # ── Lifecycle timestamps ───────────────────────────────────────────────
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when status changed to active.",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Optional expiry. Null = alert remains active until explicitly deactivated.",
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when status changed to deactivated.",
        ),
        # ── Admin audit ───────────────────────────────────────────────────────
        sa.Column(
            "published_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="super_admin user who published this alert.",
        ),
        sa.Column(
            "sms_dispatched_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "Timestamp when bulk SMS was sent to all farms in the target county. "
                "Null until SMS dispatch completes. Prevents duplicate SMS sends."
            ),
        ),
        sa.Column(
            "sms_recipient_count",
            sa.Integer,
            nullable=True,
            comment="Count of farms that received the SMS dispatch.",
        ),
        # ── Standard fields ────────────────────────────────────────────────────
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    op.create_index("ix_disease_alerts_id", "disease_alerts", ["id"])
    op.create_index("ix_disease_alerts_status", "disease_alerts", ["status"])
    op.create_index("ix_disease_alerts_county", "disease_alerts", ["county"])
    op.create_index("ix_disease_alerts_species_key", "disease_alerts", ["species_key"])
    op.create_index(
        "ix_disease_alerts_county_status",
        "disease_alerts",
        ["county", "status"],
        comment="Primary query path: active alerts for a given county.",
    )
    op.create_index(
        "ix_disease_alerts_published_at", "disease_alerts", ["published_at"]
    )
    op.create_index("ix_disease_alerts_expires_at", "disease_alerts", ["expires_at"])


def downgrade() -> None:
    op.drop_table("disease_alerts")
    sa.Enum(name="alert_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="alert_status").drop(op.get_bind(), checkfirst=True)
