"""Migration 007 — Create species_profiles table

Revision ID: 007
Revises: 006
Create Date: 2025-01-01 00:06:00.000000

The species_profiles table is the AGRIOS extensibility engine.
Adding a new agricultural module NEVER requires modifying existing tables.
Activating a species = UPDATE species_profiles SET is_active = TRUE.

V1 seed: Poultry is_active=TRUE. All others is_active=FALSE.

DB-03 (Frozen): species_profiles is the extensibility engine.
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "species_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "species_key",
            sa.String(50),
            nullable=False,
            unique=True,
            comment="Stable identifier used as FK in species-specific tables. Never rename.",
        ),
        sa.Column(
            "display_name",
            sa.String(100),
            nullable=False,
            comment="Human-readable name shown in the UI.",
        ),
        sa.Column(
            "display_name_sw",
            sa.String(100),
            nullable=True,
            comment="Swahili display name for the species.",
        ),
        sa.Column(
            "icon",
            sa.String(50),
            nullable=False,
            comment="Emoji or icon key used in the UI.",
        ),
        sa.Column(
            "module_accent_hex",
            sa.String(7),
            nullable=False,
            comment="Brand accent color for this module per AGRIOS Design System v1.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
            comment="Only super_admin can set to TRUE. Activating adds the module to all farms.",
        ),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "description",
            sa.Text,
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

    op.create_index("ix_species_profiles_id", "species_profiles", ["id"])
    op.create_index(
        "ix_species_profiles_species_key",
        "species_profiles",
        ["species_key"],
        unique=True,
    )
    op.create_index(
        "ix_species_profiles_is_active",
        "species_profiles",
        ["is_active"],
    )

    # ── Seed Species ──────────────────────────────────────────────────────────
    # Module accent colors are from the AGRIOS Design System v1, Section 9.

    species_profiles_table = sa.table(
        "species_profiles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("species_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("display_name_sw", sa.String),
        sa.column("icon", sa.String),
        sa.column("module_accent_hex", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
        sa.column("description", sa.Text),
    )

    op.bulk_insert(
        species_profiles_table,
        [
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
                "species_key": "poultry",
                "display_name": "Poultry",
                "display_name_sw": "Kuku",
                "icon": "🐔",
                "module_accent_hex": "#076524",
                "is_active": True,
                "sort_order": 1,
                "description": "Broiler, layer, breeder and pullet chicken operations.",
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
                "species_key": "rabbit",
                "display_name": "Rabbit",
                "display_name_sw": "Sungura",
                "icon": "🐰",
                "module_accent_hex": "#D97706",
                "is_active": False,
                "sort_order": 2,
                "description": "Rabbit breeding and meat production. (Future module)",
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
                "species_key": "dairy",
                "display_name": "Dairy",
                "display_name_sw": "Maziwa",
                "icon": "🐄",
                "module_accent_hex": "#0284C7",
                "is_active": False,
                "sort_order": 3,
                "description": "Dairy cattle milk production and herd management. (Future module)",
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000004"),
                "species_key": "fish",
                "display_name": "Fish",
                "display_name_sw": "Samaki",
                "icon": "🐟",
                "module_accent_hex": "#0D9488",
                "is_active": False,
                "sort_order": 4,
                "description": "Aquaculture and fish pond management. (Future module)",
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000005"),
                "species_key": "crop",
                "display_name": "Crop",
                "display_name_sw": "Mazao",
                "icon": "🌾",
                "module_accent_hex": "#92400E",
                "is_active": False,
                "sort_order": 5,
                "description": "Crop farming and field management. (Future module)",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("species_profiles")
