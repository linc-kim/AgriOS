"""Migration 050 — production readiness: backups, restores, imports, exports, releases

Module 11 (Production Readiness & Launch).

  backups         — point-in-time snapshots, with checksum + retention expiry
  restore_runs    — restore attempts (dry run or applied)
  import_jobs     — bulk imports with per-row validation results
  export_jobs     — generated exports, kept as download history
  release_records — deployed releases, for deployment / rollback verification
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def _base():
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="farm", index=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("record_counts", JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.String(20), nullable=False, server_default="1"),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True, index=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "restore_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("backup_id", UUID(as_uuid=True), sa.ForeignKey("backups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("checksum_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("safety_backup_id", UUID(as_uuid=True), sa.ForeignKey("backups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("entity", sa.String(40), nullable=False, index=True),
        sa.Column("source_format", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", JSONB, nullable=False, server_default="[]"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("dataset", sa.String(40), nullable=False, index=True),
        sa.Column("export_format", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )

    op.create_table(
        "release_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, index=True),
        sa.Column("environment", sa.String(20), nullable=False, index=True),
        sa.Column("git_sha", sa.String(40), nullable=True),
        sa.Column("migration_revision", sa.String(40), nullable=True),
        sa.Column("previous_version", sa.String(20), nullable=True),
        sa.Column("is_rollback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deployed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"), index=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verification", JSONB, nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("release_records")
    op.drop_table("export_jobs")
    op.drop_table("import_jobs")
    op.drop_table("restore_runs")
    op.drop_table("backups")
