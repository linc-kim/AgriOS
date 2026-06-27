"""create_notifications

Revision ID: 028
Revises: 027
Create Date: 2026-06-26

Sprint 7 — Platform Layer (Tier 7)
Table: notifications — In-app notification storage per user/farm.

Columns:
  - id (UUID PK)
  - farm_id (FK → farms, CASCADE)
  - user_id (FK → users, CASCADE) — recipient
  - notification_type (String 50) — e.g. "vaccination_reminder", "disease_alert", "daily_log_reminder", "weekly_summary", "system"
  - title (String 200)
  - body (Text)
  - action_route (String 300, nullable) — deep link for the farmer PWA
  - is_read (Boolean, default false)
  - read_at (TIMESTAMPTZ, nullable)
  - source (String 50, nullable) — "aria", "scheduler", "admin", "system"
  - created_at, updated_at, deleted_at (via AGRIOSBase)
  - metadata JSONB
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("action_route", sa.String(300), nullable=True),
        sa.Column("is_read", sa.Boolean, default=False, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        # AGRIOSBase columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_", JSONB, nullable=False, server_default="{}"),
    )

    # Indexes
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_notifications_farm_id",
        "notifications",
        ["farm_id"],
    )
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "ix_notifications_deleted_at",
        "notifications",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_deleted_at", table_name="notifications")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_farm_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
