"""Create expense_categories table with seeded system categories.

Revision ID: 019
Revises: 018
Create Date: 2026-06-26

DESIGN NOTES:
- 17 system categories seeded at migration time.
- is_system=True rows cannot be deleted via API (enforced at service layer).
- farm_id=NULL on system rows — they are shared across all farms.
- Custom categories have farm_id set (farm-scoped, non-system).
- DB-01 Frozen: UUID v4 PKs.
- DB-02 Frozen: soft deletes (deleted_at).
- DB-04 Frozen: farm_id on operational tables (system rows use NULL).
- DB-05 Frozen: metadata JSONB.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


SYSTEM_CATEGORIES = [
    # Feed & Nutrition
    {"id": str(uuid.uuid4()), "name": "Feed Purchase", "slug": "feed_purchase", "icon": "🌾", "color": "#16a34a"},
    {"id": str(uuid.uuid4()), "name": "Feed Supplements", "slug": "feed_supplements", "icon": "💊", "color": "#16a34a"},
    # Veterinary & Health
    {"id": str(uuid.uuid4()), "name": "Vaccination", "slug": "vaccination", "icon": "💉", "color": "#0891b2"},
    {"id": str(uuid.uuid4()), "name": "Medication & Treatment", "slug": "medication", "icon": "🩺", "color": "#0891b2"},
    {"id": str(uuid.uuid4()), "name": "Veterinary Fees", "slug": "vet_fees", "icon": "👨‍⚕️", "color": "#0891b2"},
    # Labour
    {"id": str(uuid.uuid4()), "name": "Labour / Wages", "slug": "labour", "icon": "👷", "color": "#7c3aed"},
    # Utilities
    {"id": str(uuid.uuid4()), "name": "Electricity", "slug": "electricity", "icon": "⚡", "color": "#d97706"},
    {"id": str(uuid.uuid4()), "name": "Water", "slug": "water", "icon": "💧", "color": "#0284c7"},
    # Equipment & Maintenance
    {"id": str(uuid.uuid4()), "name": "Equipment Purchase", "slug": "equipment", "icon": "🔧", "color": "#64748b"},
    {"id": str(uuid.uuid4()), "name": "Repairs & Maintenance", "slug": "repairs", "icon": "🛠️", "color": "#64748b"},
    # Chicks & Stock
    {"id": str(uuid.uuid4()), "name": "Day-Old Chicks (DOC)", "slug": "doc_purchase", "icon": "🐥", "color": "#ca8a04"},
    # Biosecurity
    {"id": str(uuid.uuid4()), "name": "Biosecurity Supplies", "slug": "biosecurity", "icon": "🧴", "color": "#059669"},
    # Transport & Logistics
    {"id": str(uuid.uuid4()), "name": "Transport / Logistics", "slug": "transport", "icon": "🚛", "color": "#dc2626"},
    # Insurance & Compliance
    {"id": str(uuid.uuid4()), "name": "Insurance", "slug": "insurance", "icon": "🛡️", "color": "#4f46e5"},
    {"id": str(uuid.uuid4()), "name": "Licensing & Compliance", "slug": "licensing", "icon": "📋", "color": "#4f46e5"},
    # Bedding
    {"id": str(uuid.uuid4()), "name": "Bedding / Litter", "slug": "bedding", "icon": "🪹", "color": "#92400e"},
    # Miscellaneous
    {"id": str(uuid.uuid4()), "name": "Other", "slug": "other", "icon": "📦", "color": "#6b7280"},
]


def upgrade() -> None:
    op.create_table(
        "expense_categories",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        # NULL farm_id = system category shared across all farms
        sa.Column(
            "farm_id",
            UUID(as_uuid=False),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(10), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),  # hex colour e.g. #16a34a
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        # Soft delete
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # Audit
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Extensibility
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )

    # Unique: (farm_id, slug) for custom; (NULL farm_id, slug) for system
    op.create_index(
        "ix_expense_categories_slug",
        "expense_categories",
        ["slug"],
        unique=False,  # slug not globally unique — custom farms can reuse
    )
    op.create_index(
        "ix_expense_categories_farm_id",
        "expense_categories",
        ["farm_id"],
    )

    # Seed system categories
    op.bulk_insert(
        sa.table(
            "expense_categories",
            sa.column("id", sa.String),
            sa.column("farm_id", sa.String),
            sa.column("name", sa.String),
            sa.column("slug", sa.String),
            sa.column("icon", sa.String),
            sa.column("color", sa.String),
            sa.column("is_system", sa.Boolean),
        ),
        [
            {
                "id": cat["id"],
                "farm_id": None,
                "name": cat["name"],
                "slug": cat["slug"],
                "icon": cat["icon"],
                "color": cat["color"],
                "is_system": True,
            }
            for cat in SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_expense_categories_farm_id", table_name="expense_categories")
    op.drop_index("ix_expense_categories_slug", table_name="expense_categories")
    op.drop_table("expense_categories")
