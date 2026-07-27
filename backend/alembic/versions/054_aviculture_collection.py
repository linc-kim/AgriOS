"""Migration 054 — Aviculture Collection Management (Module 15, Part 2)

Part 1 gave every bird an identity. Part 2 gives it a complete, permanent
**digital life history** (Doc 13 Part 2; Doc 02 §4). Two append-only tables are
added on top of the Part 1 aggregate — nothing in Part 1 is modified:

  avi_bird_ownership — the chain of custody. Ownership is never overwritten
                       (Doc 02 §26); each change closes the current record
                       (``to_date``, ``is_current=false``) and opens a new one.
  avi_bird_event     — the bird timeline (Doc 06 §4). Every meaningful change —
                       creation, edits, status transitions, ownership events
                       (transfer / sale / purchase / death), pairing, media and
                       documents — appends an immutable event. This is how the
                       lifecycle is "preserved permanently" (Doc 02 §4).

Ownership transitions (sale / purchase / transfer / death) are recorded as
collection facts here (counterparty, optional price, documents). Financial
posting is deliberately NOT done here — it is reused from the Greena Finance
engine in Part 7 (Doc 13 Part 7: "No duplicated finance engine"). Price is stored
as a recorded fact so Part 7 can read it without a competing ledger.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def _base() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
    ]


def upgrade() -> None:
    # ── Ownership history (Doc 02 §26 — never overwritten) ────────────────────
    op.create_table(
        "avi_bird_ownership",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "owner_type",
            sa.String(20),
            nullable=False,
            server_default="internal",
            comment="internal | customer | supplier | breeder | other.",
        ),
        sa.Column("owner_name", sa.String(200), nullable=False),
        sa.Column("owner_contact", JSONB, nullable=False, server_default="{}",
                  comment="Optional contact detail (phone/email/address). PII — Doc 10 §13."),
        sa.Column(
            "acquisition",
            sa.String(20),
            nullable=False,
            server_default="unknown",
            comment="bred | purchased | transferred | donated | unknown.",
        ),
        sa.Column("from_date", sa.Date(), nullable=True),
        sa.Column("to_date", sa.Date(), nullable=True,
                  comment="NULL while current; set when ownership ends."),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_bird_ownership_is_current", "avi_bird_ownership", ["bird_id", "is_current"])

    # ── Timeline (Doc 06 §4; Doc 02 §4 — lifecycle preserved permanently) ─────
    op.create_table(
        "avi_bird_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("bird_id", UUID(as_uuid=True),
                  sa.ForeignKey("avi_bird.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "event_type",
            sa.String(40),
            nullable=False,
            comment="created | updated | status_changed | archived | restored | "
            "transferred | sold | purchased | died | paired | unpaired | "
            "media_added | document_added | health_recorded | note.",
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data", JSONB, nullable=False, server_default="{}",
                  comment="Structured event detail: counterparty, price, doc ids, "
                  "field changes. Recorded facts only — never a calculation."),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_base(),
    )
    op.create_index("ix_avi_bird_event_bird_occurred", "avi_bird_event", ["bird_id", "occurred_on"])
    op.create_index("ix_avi_bird_event_type", "avi_bird_event", ["event_type"])


def downgrade() -> None:
    op.drop_table("avi_bird_event")
    op.drop_table("avi_bird_ownership")
