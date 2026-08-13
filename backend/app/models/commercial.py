"""
Greena — Commercial Policy models (referrals + credit ledger).

Separate from the billing *infrastructure* models. A ``Referral`` records who
referred whom (one per referred organization, immutable once accepted). The
``CreditLedgerEntry`` is append-only — rewards and adjustments are new rows,
never updates or deletes; each row carries the running ``balance_after``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AGRIOSBase

REFERRAL_REWARD_STATUSES = ("pending", "granted")
CREDIT_SOURCES = ("referral_reward", "admin_adjustment")


class Referral(AGRIOSBase):
    """One referral per referred organization; immutable once accepted."""

    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_org_id", name="uq_referrals_referred_org"),
    )

    referred_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    referrer_org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code_used: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reward_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="pending | granted"
    )
    reward_payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def __repr__(self) -> str:
        return f"<Referral referred={self.referred_org_id} reward={self.reward_status}>"


class CreditLedgerEntry(AGRIOSBase):
    """An immutable credit-ledger row. Never updated or deleted."""

    __tablename__ = "credit_ledger"
    __table_args__ = (
        # Idempotency backstop: a given payment can credit a given source at most
        # once, so a concurrently-delivered duplicate webhook cannot double-credit
        # a referral reward even if two coroutines pass the app-level
        # reward_status guard before either commits. Partial (NULLable
        # payment_reference) so manual admin adjustments are unconstrained.
        Index(
            "uq_credit_ledger_payment_reference_source",
            "payment_reference", "source",
            unique=True,
            postgresql_where=text("payment_reference IS NOT NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    amount_kes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Signed: positive = credit granted, negative = adjustment/spend",
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="referral_reward | admin_adjustment"
    )
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<CreditLedgerEntry org={self.organization_id} amount={self.amount_kes}>"
