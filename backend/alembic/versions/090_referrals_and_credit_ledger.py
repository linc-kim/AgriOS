"""Migration 090 — Commercial Policy: referrals + credit ledger (C3-C6)

Referral system and an immutable credit ledger. Each organization gets a unique
shareable ``referral_code``. A ``referrals`` row records who referred whom (one
per referred org, immutable once accepted). ``credit_ledger`` is append-only:
referral rewards and admin adjustments are new rows, never updates/deletes;
each row carries the running ``balance_after``.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "090"
down_revision = "089"
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
    op.add_column(
        "organizations",
        sa.Column("referral_code", sa.String(32), nullable=True,
                  comment="Unique shareable referral code, generated at org creation"),
    )
    op.create_unique_constraint("uq_organizations_referral_code", "organizations", ["referral_code"])

    # ── referrals — one per referred organization ─────────────────────────────
    op.create_table(
        "referrals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("referred_org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("referrer_org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("code_used", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reward_status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | granted"),
        sa.Column("reward_payment_reference", sa.String(100), nullable=True),
        *_base(),
        sa.UniqueConstraint("referred_org_id", name="uq_referrals_referred_org"),
    )

    # ── credit_ledger — immutable, append-only ────────────────────────────────
    op.create_table(
        "credit_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("amount_kes", sa.Integer, nullable=False,
                  comment="Signed: positive = credit granted, negative = adjustment/spend"),
        sa.Column("source", sa.String(30), nullable=False,
                  comment="referral_reward | admin_adjustment"),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("balance_after", sa.Integer, nullable=False),
        *_base(),
    )


def downgrade() -> None:
    op.drop_table("credit_ledger")
    op.drop_table("referrals")
    op.drop_constraint("uq_organizations_referral_code", "organizations", type_="unique")
    op.drop_column("organizations", "referral_code")
