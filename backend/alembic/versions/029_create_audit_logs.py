"""create_audit_logs

Revision ID: 029
Revises: 028
Create Date: 2026-06-26

Sprint 7 — Platform Layer (Tier 7)
Table: audit_logs — Immutable append-only mutation log.

DB-08 (Frozen): audit_logs is append-only. No UPDATE or DELETE endpoint
exists or will be created.

Intentional deviations from AGRIOSBase (documented exceptions):
  - Does NOT inherit AGRIOSBase — no soft delete, no updated_at, no metadata JSONB
  - created_at only (immutable cost record)
  - No deleted_at — records are never removed
  - farm_id is nullable (some audit events are platform-level, not farm-scoped)

Columns:
  - id (UUID PK)
  - farm_id (FK → farms, SET NULL, nullable) — null for platform-level events
  - user_id (FK → users, SET NULL, nullable) — null for system-generated events
  - action (String 100) — e.g. "flock.create", "expense.delete", "member.invite"
  - resource_type (String 50) — e.g. "flock", "expense", "farm_member"
  - resource_id (UUID, nullable) — the affected record's PK
  - old_value (JSONB, nullable) — snapshot before mutation
  - new_value (JSONB, nullable) — snapshot after mutation
  - ip_address (String 45, nullable)
  - user_agent (String 500, nullable)
  - created_at (TIMESTAMPTZ) — immutable timestamp
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "farm_id",
            UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        # Immutable timestamp — no updated_at
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Indexes optimised for admin audit queries
    op.create_index(
        "ix_audit_logs_farm_id",
        "audit_logs",
        ["farm_id"],
    )
    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
    )
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
    )
    op.create_index(
        "ix_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
    )
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_farm_id", table_name="audit_logs")
    op.drop_table("audit_logs")
