"""Migration 049 — add the missing metadata column to ai_messages

Every Greena model inherits AGRIOSBase, which maps a "metadata" JSONB column,
so the ORM emits ai_messages.metadata in every SELECT against AIMessage.
Migration 024 deliberately omitted the column ("messages are immutable content
records"), so the table never had it and every AIMessage query failed with:

    UndefinedColumnError: column ai_messages.metadata does not exist

That took out conversation detail, conversation delete, and the insight/
recommendation reads that join messages — a 500 on each. ai_messages was the
only table in the schema without the column.

Fixed by adding the column rather than by excluding it from the model: the base
class contract is that every table carries metadata, and honouring 024's note
instead would mean splitting the model hierarchy for this one table.

Additive and reversible — new column, NOT NULL with a '{}' server default, so
existing rows backfill without a table rewrite.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_messages",
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("ai_messages", "metadata")
