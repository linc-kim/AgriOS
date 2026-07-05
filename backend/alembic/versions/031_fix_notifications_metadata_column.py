"""Migration 031 — Correct the notifications JSONB column name

Revision ID: 031
Revises: 030
Create Date: 2026-07-05

Corrective migration (first of the post-V1 sequence).

Migration 028 created the notifications JSONB extensibility column physically
named "metadata_". Every other table (via AGRIOSBase) maps the Python
attribute `metadata_` to a physical column literally named "metadata". As a
result the Notification ORM model selected/wrote a column `notifications.metadata`
that did not exist, raising asyncpg UndefinedColumnError on any read or write —
confirmed reproducible against a live PostgreSQL 16 run.

This renames the physical column to "metadata" so the schema matches the model
and the project-wide convention. Data is preserved (RENAME COLUMN is metadata-
only). Migrations 001–030 are left untouched.
"""

from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("notifications", "metadata_", new_column_name="metadata")


def downgrade() -> None:
    op.alter_column("notifications", "metadata", new_column_name="metadata_")
