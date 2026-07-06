"""Migration 033 — create identity_providers (generic OAuth/SSO)

Revision ID: 033
Revises: 032
Create Date: 2026-07-06 00:01:00.000000

Identity-first: one AGRIOS user, many federated identities (Google now;
Apple/Microsoft/GitHub/SSO later add rows, not schema).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("raw_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_identity_provider_subject"
        ),
    )
    op.create_index("ix_identity_providers_id", "identity_providers", ["id"])
    op.create_index("ix_identity_providers_user_id", "identity_providers", ["user_id"])
    op.create_index("ix_identity_providers_provider", "identity_providers", ["provider"])
    op.create_index(
        "ix_identity_providers_deleted_at", "identity_providers", ["deleted_at"]
    )


def downgrade() -> None:
    op.drop_table("identity_providers")
