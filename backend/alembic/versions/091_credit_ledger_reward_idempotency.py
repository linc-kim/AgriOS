"""Migration 091 — credit ledger reward idempotency guard

Hardening: add a partial UNIQUE index on credit_ledger(payment_reference,
source). A referral reward is credited from the webhook path, guarded in the
app by referrals.reward_status. That guard is read-then-write, so a
concurrently-delivered duplicate webhook could pass it twice before either
commits and double-credit the referrer. This DB-level uniqueness makes that
impossible: a given payment_reference can credit a given source at most once.
Partial (payment_reference IS NOT NULL) so admin adjustments, which carry no
payment reference, remain unconstrained. Additive and non-destructive.
"""

from alembic import op

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_credit_ledger_payment_reference_source",
        "credit_ledger",
        ["payment_reference", "source"],
        unique=True,
        postgresql_where="payment_reference IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_credit_ledger_payment_reference_source", table_name="credit_ledger")
