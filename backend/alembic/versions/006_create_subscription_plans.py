"""Migration 006 — Create subscription_plans table

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:05:00.000000

Seeds 3 plans per Appendix B of the Master Blueprint (Frozen):
  free:    KES 0/month   — 3 houses,  3 flocks,  5 ARIA queries,  90d history, 2 members
  starter: KES 500/month — 10 houses, 10 flocks, 30 ARIA queries, 1y history,  5 members
  pro:     KES 1500/month — unlimited houses/flocks/queries/history, 20 members

-1 in integer limit fields means UNLIMITED.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "name",
            sa.String(50),
            nullable=False,
            unique=True,
            comment="Plan key: free | starter | pro",
        ),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column(
            "price_kes",
            sa.Integer,
            nullable=False,
            comment="Monthly price in Kenyan Shillings. 0 for free plan.",
        ),
        sa.Column(
            "max_farms",
            sa.Integer,
            nullable=False,
            comment="Maximum farms per account. -1 = unlimited.",
        ),
        sa.Column(
            "max_houses_per_farm",
            sa.Integer,
            nullable=False,
            comment="Maximum production houses per farm. -1 = unlimited.",
        ),
        sa.Column(
            "max_active_flocks",
            sa.Integer,
            nullable=False,
            comment="Maximum simultaneously active flocks. -1 = unlimited.",
        ),
        sa.Column(
            "max_aria_queries_per_month",
            sa.Integer,
            nullable=False,
            comment="ARIA AI queries per calendar month. -1 = unlimited.",
        ),
        sa.Column(
            "history_days",
            sa.Integer,
            nullable=False,
            comment="Data history retention in days. -1 = unlimited.",
        ),
        sa.Column(
            "max_team_members",
            sa.Integer,
            nullable=False,
            comment="Maximum farm_members per farm including owner.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Only active plans can be assigned to farms.",
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

    op.create_index("ix_subscription_plans_id", "subscription_plans", ["id"])
    op.create_index(
        "ix_subscription_plans_name",
        "subscription_plans",
        ["name"],
        unique=True,
    )

    # ── Seed Plans ────────────────────────────────────────────────────────────
    # Values are frozen per Appendix B of the Master Blueprint.
    # Do not alter without a formal override.

    subscription_plans_table = sa.table(
        "subscription_plans",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("price_kes", sa.Integer),
        sa.column("max_farms", sa.Integer),
        sa.column("max_houses_per_farm", sa.Integer),
        sa.column("max_active_flocks", sa.Integer),
        sa.column("max_aria_queries_per_month", sa.Integer),
        sa.column("history_days", sa.Integer),
        sa.column("max_team_members", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )

    op.bulk_insert(
        subscription_plans_table,
        [
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "name": "free",
                "display_name": "Free",
                "price_kes": 0,
                "max_farms": 1,
                "max_houses_per_farm": 3,
                "max_active_flocks": 3,
                "max_aria_queries_per_month": 5,
                "history_days": 90,
                "max_team_members": 2,
                "is_active": True,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
                "name": "starter",
                "display_name": "Starter",
                "price_kes": 500,
                "max_farms": 1,
                "max_houses_per_farm": 10,
                "max_active_flocks": 10,
                "max_aria_queries_per_month": 30,
                "history_days": 365,
                "max_team_members": 5,
                "is_active": True,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
                "name": "pro",
                "display_name": "Pro",
                "price_kes": 1500,
                "max_farms": 3,
                "max_houses_per_farm": -1,
                "max_active_flocks": -1,
                "max_aria_queries_per_month": -1,
                "history_days": -1,
                "max_team_members": 20,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("subscription_plans")
