"""Migration 018 — Create disease_alerts table

Revision ID: 018
Revises: 017
Create Date: 2025-01-01 00:17:00.000000
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
    op.create_table(
        "disease_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),

        # Targeting
        sa.Column(
            "county",
            sa.String(100),
            nullable=True,
            comment="Kenya county this alert targets. NULL = national.",
        ),
        sa.Column(
            "species_key",
            sa.String(50),
            nullable=True,
            comment="Species this alert targets. NULL = all species.",
        ),

        # Content
        sa.Column(
            "disease_name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(300),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text,
            nullable=False,
        ),
        sa.Column(
            "brief_guidance",
            sa.String(500),
            nullable=True,
        ),

        sa.Column(
            "severity",
            sa.Enum(
                *ALERT_SEVERITY_VALUES,
                name="alert_severity",
            ),
            nullable=False,
            server_default="warning",
        ),

        sa.Column(
            "status",
            sa.Enum(
                *ALERT_STATUS_VALUES,
                name="alert_status",
            ),
            nullable=False,
            server_default="draft",
        ),

        # Lifecycle
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        # Admin
        sa.Column(
            "published_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sms_dispatched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "sms_recipient_count",
            sa.Integer,
            nullable=True,
        ),

        # Standard fields
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
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_disease_alerts_id",
        "disease_alerts",
        ["id"],
    )

    op.create_index(
        "ix_disease_alerts_status",
        "disease_alerts",
        ["status"],
    )

    op.create_index(
        "ix_disease_alerts_county",
        "disease_alerts",
        ["county"],
    )

    op.create_index(
        "ix_disease_alerts_species_key",
        "disease_alerts",
        ["species_key"],
    )

    op.create_index(
        "ix_disease_alerts_county_status",
        "disease_alerts",
        ["county", "status"],
    )

    op.create_index(
        "ix_disease_alerts_published_at",
        "disease_alerts",
        ["published_at"],
    )

    op.create_index(
        "ix_disease_alerts_expires_at",
        "disease_alerts",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_table("disease_alerts")

    sa.Enum(
        name="alert_severity"
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )

    sa.Enum(
        name="alert_status"
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )