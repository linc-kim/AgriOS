"""Migration 013 — Create daily_logs table

Revision ID: 013
Revises: 012
Create Date: 2025-01-01 00:12:00.000000

Daily logs are the primary data-entry mechanism for DAL (Daily Active Loggers),
the sole MVP success metric.

DB-06 Frozen: UNIQUE(flock_id, log_date) — enables safe daily log upsert
pattern (INSERT ... ON CONFLICT DO UPDATE SET ...).

Captured fields (MVP):
  - morning_count    : bird head count at first check
  - mortality_count  : birds that died during the day
  - mortality_cause  : optional cause of death
  - feed_consumed_kg : total feed given (kg)
  - water_litres     : total water given (litres)
  - house_temp_am    : house temperature at morning check (°C)
  - house_temp_pm    : house temperature at evening check (°C)

Support fields:
  - is_corrected     : TRUE if the log was amended after submission
  - corrected_by     : who corrected it (OPS_LOG_CORRECT permission)
  - corrected_at     : when correction happened
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
            comment="DB-04: farm_id on all operational tables",
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flocks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "log_date",
            sa.Date,
            nullable=False,
            comment="The date this log covers (not the submission time).",
        ),
        sa.Column(
            "morning_count",
            sa.Integer,
            nullable=True,
            comment="Bird head count at morning check. Optional.",
        ),
        sa.Column(
            "mortality_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "mortality_cause",
            sa.String(100),
            nullable=True,
            comment="Free-text cause, e.g. 'Heat stress', 'Coccidiosis'",
        ),
        sa.Column(
            "feed_consumed_kg",
            sa.Numeric(10, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "water_litres",
            sa.Numeric(10, 3),
            nullable=True,
        ),
        sa.Column(
            "house_temp_am",
            sa.Numeric(5, 2),
            nullable=True,
            comment="House temperature (°C) at morning check",
        ),
        sa.Column(
            "house_temp_pm",
            sa.Numeric(5, 2),
            nullable=True,
            comment="House temperature (°C) at evening check",
        ),
        sa.Column(
            "notes",
            sa.Text,
            nullable=True,
        ),
        sa.Column(
            "logged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_corrected",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "corrected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "corrected_at",
            sa.DateTime(timezone=True),
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

    # DB-06 Frozen: UNIQUE(flock_id, log_date) — enables upsert pattern
    op.create_unique_constraint(
        "uq_daily_logs_flock_date",
        "daily_logs",
        ["flock_id", "log_date"],
    )

    # Indexes
    op.create_index("ix_daily_logs_id", "daily_logs", ["id"])
    op.create_index("ix_daily_logs_farm_id", "daily_logs", ["farm_id"])
    op.create_index("ix_daily_logs_flock_id", "daily_logs", ["flock_id"])
    op.create_index("ix_daily_logs_log_date", "daily_logs", ["log_date"])
    op.create_index("ix_daily_logs_deleted_at", "daily_logs", ["deleted_at"])
    op.create_index(
        "ix_daily_logs_flock_date",
        "daily_logs",
        ["flock_id", "log_date"],
        comment="Primary operational query: flock history chronologically",
    )


def downgrade() -> None:
    op.drop_table("daily_logs")
