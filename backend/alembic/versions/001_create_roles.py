"""Migration 001 — Create roles table and seed 8 platform roles

Revision ID: 001
Revises: (none — first migration)
Create Date: 2025-01-01 00:00:00.000000

Engineering Constitution: 8 roles seeded at database creation.
Role names match the RBAC matrix exactly.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# Role seed data — locked per Engineering Constitution
ROLES = [
    {
        "name": "super_admin",
        "display_name": "Super Admin",
        "description": "Full platform access. Founder only. Not assignable via UI.",
        "is_platform_role": True,
    },
    {
        "name": "platform_admin",
        "display_name": "Platform Admin",
        "description": "Platform management access. Reserved for future AGRIOS staff.",
        "is_platform_role": True,
    },
    {
        "name": "enterprise_owner",
        "display_name": "Enterprise Owner",
        "description": "Multi-farm enterprise account owner. Deferred to V2.",
        "is_platform_role": False,
    },
    {
        "name": "farm_owner",
        "display_name": "Farm Owner",
        "description": "Full access to a single farm. Default role for new users.",
        "is_platform_role": False,
    },
    {
        "name": "farm_manager",
        "display_name": "Farm Manager",
        "description": "All farm operations. Cannot delete farm or change ownership.",
        "is_platform_role": False,
    },
    {
        "name": "vet_consultant",
        "display_name": "Vet / Consultant",
        "description": "Read-only access to health data for a single farm.",
        "is_platform_role": False,
    },
    {
        "name": "farm_worker",
        "display_name": "Farm Worker",
        "description": "Daily operations only: log feed, mortality, production, weighins.",
        "is_platform_role": False,
    },
    {
        "name": "viewer",
        "display_name": "Viewer",
        "description": "Read-only access to non-financial farm data.",
        "is_platform_role": False,
    },
]


def upgrade() -> None:
    roles_table = op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_platform_role", sa.Boolean, nullable=False, server_default="false"),
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

    op.create_index("ix_roles_id", "roles", ["id"])
    op.create_index("ix_roles_name", "roles", ["name"])
    op.create_index("ix_roles_deleted_at", "roles", ["deleted_at"])

    # Seed all 8 roles
    import uuid
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        roles_table,
        [
            {
                "id": uuid.uuid4(),
                "name": role["name"],
                "display_name": role["display_name"],
                "description": role["description"],
                "is_platform_role": role["is_platform_role"],
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
                "metadata": "{}",
            }
            for role in ROLES
        ],
    )


def downgrade() -> None:
    op.drop_table("roles")
