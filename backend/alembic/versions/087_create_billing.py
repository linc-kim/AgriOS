"""Migration 087 — Billing: subscriptions & payment_transactions (Inc 8)

Organization-scoped billing. An organization owns at most one ``subscriptions``
row (its current entitlement, enforced by a UNIQUE on organization_id); farms
inherit access from their organization — no per-farm subscriptions.
``payment_transactions`` records every Paystack payment attempt, idempotent by a
UNIQUE ``reference`` (our own key, echoed by Paystack). Prices are NOT stored
here — they live on ``subscription_plans``.

Tables:
  subscriptions        — current entitlement per org: plan, status, period,
                         lifetime flag, activation source, Paystack customer code.
  payment_transactions — a payment attempt for a plan: reference, amount_kes,
                         currency, status, paid_at, optional link to the
                         subscription it activated.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "087"
down_revision = "086"
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
    # ── subscriptions — one current entitlement per organization ──────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active",
                  comment="active | expired | cancelled"),
        sa.Column("activation_source", sa.String(20), nullable=False, server_default="paystack",
                  comment="paystack | admin | lifetime"),
        sa.Column("current_period_start", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True,
                  comment="NULL = never expires (lifetime/admin grant)"),
        sa.Column("is_lifetime", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("paystack_customer_code", sa.String(100), nullable=True),
        *_base(),
        sa.UniqueConstraint("organization_id", name="uq_subscriptions_organization"),
    )
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    # ── payment_transactions — one row per Paystack payment attempt ───────────
    op.create_table(
        "payment_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("plan_id", UUID(as_uuid=True),
                  sa.ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False, index=True,
                  comment="Our idempotency key; Paystack echoes it back"),
        sa.Column("amount_kes", sa.Integer, nullable=False,
                  comment="KES amount from the plan at init time (never client-supplied)"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending",
                  comment="pending | success | failed | abandoned"),
        sa.Column("paystack_reference", sa.String(100), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("subscription_id", UUID(as_uuid=True),
                  sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        *_base(),
        sa.UniqueConstraint("reference", name="uq_payment_transactions_reference"),
    )
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_table("subscriptions")
