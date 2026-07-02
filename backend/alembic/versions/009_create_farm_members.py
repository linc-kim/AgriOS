"""Migration 009 — Create farm_members table

Revision ID: 009
Revises: 008
Create Date: 2025-01-01 00:08:00.000000

Tracks who has access to each farm and at what role.
Supports invite-by-phone: a member record can be created before the invitee
has an AGRIOS account (user_id is NULL while status = 'pending').

Constraint: UNIQUE(farm_id, user_id) — one active role per user per farm.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

MEMBER_STATUSES = ("pending", "active", "suspended")


def upgrade() -> None:
    # Create member_status enum type
    member_status_enum = postgresql.ENUM(
        *MEMBER_STATUSES,
        name="member_status",
    )
  

    op.create_table(
        "farm_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            comment="NULL when invite is pending and invitee has no AGRIOS account yet.",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "phone",
            sa.String(20),
            nullable=True,
            comment="Phone number used for invite. Required when user_id is NULL.",
        ),
        sa.Column(
            "status",
            member_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="pending → active on acceptance. suspended by owner/manager.",
        ),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="The user who sent the invite.",
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when invitee accepted. NULL for pending/suspended.",
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
        # One active membership per user per farm
        sa.UniqueConstraint(
            "farm_id",
            "user_id",
            name="uq_farm_members_farm_user",
        ),
    )

    op.create_index("ix_farm_members_id", "farm_members", ["id"])
    op.create_index("ix_farm_members_farm_id", "farm_members", ["farm_id"])
    op.create_index("ix_farm_members_user_id", "farm_members", ["user_id"])
    op.create_index("ix_farm_members_phone", "farm_members", ["phone"])
    op.create_index("ix_farm_members_status", "farm_members", ["status"])
    op.create_index("ix_farm_members_deleted_at", "farm_members", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("farm_members")
    postgresql.ENUM(
        *MEMBER_STATUSES,
        name="member_status",
    ).drop(op.get_bind(), checkfirst=True)
