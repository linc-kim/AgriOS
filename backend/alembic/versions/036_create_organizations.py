"""Migration 036 — organizations + organization_members; farms.organization_id

Revision ID: 036
Revises: 035
Create Date: 2026-07-07 00:00:00.000000

Workspace-first: Organization owns Farms. Additive & backward-compatible —
farms.organization_id is nullable so existing farms keep working; new farms
created via onboarding set it. Reuses the existing member_status enum.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None

member_status = postgresql.ENUM(
    "pending", "active", "suspended", name="member_status", create_type=False
)


def _base_cols() -> list:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        *_base_cols(),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_owner_id", "organizations", ["owner_id"])
    op.create_index("ix_organizations_deleted_at", "organizations", ["deleted_at"])

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("status", member_status, nullable=False, server_default="active"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index("ix_organization_members_id", "organization_members", ["id"])
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])
    op.create_index("ix_organization_members_deleted_at", "organization_members", ["deleted_at"])

    op.add_column(
        "farms",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True),
    )
    op.create_index("ix_farms_organization_id", "farms", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_farms_organization_id", table_name="farms")
    op.drop_column("farms", "organization_id")
    op.drop_table("organization_members")
    op.drop_table("organizations")
