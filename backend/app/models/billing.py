"""
Greena — Billing models (Increment 8).

**Organization-scoped.** An organization owns at most one subscription (its
current entitlement); farms inherit access from their organization — there are
no per-farm subscriptions. Subscription state is the **source of truth** for
what a customer is entitled to: a plan is activated only after a *verified*
successful Paystack payment or a manually granted admin/lifetime subscription
(enforced in the service layer — Inc 9–10 — never by trusting a client).

Prices are **not** stored here — they live on ``subscription_plans`` so they can
change without code. ``payment_transactions`` records every payment attempt,
keyed by our own idempotent ``reference`` (which Paystack echoes back), so the
verified gateway amount can be checked against the plan before activation.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

# Allowed string values (plain constants, matching the recent String-status
# convention across the swine modules — no native PG enum).
SUBSCRIPTION_STATUSES = ("active", "expired", "cancelled")
ACTIVATION_SOURCES = ("paystack", "admin", "lifetime")
PAYMENT_STATUSES = ("pending", "success", "failed", "abandoned")


class Subscription(AGRIOSBase):
    """An organization's current subscription entitlement (one row per org)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_subscriptions_organization"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active | expired | cancelled",
    )
    activation_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="paystack",
        comment="paystack | admin | lifetime — how the entitlement was granted",
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="NULL = never expires (lifetime/admin grant)",
    )
    is_lifetime: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paystack_customer_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    organization = relationship("Organization")
    plan = relationship("SubscriptionPlan")

    def __repr__(self) -> str:
        return f"<Subscription org={self.organization_id} status={self.status}>"


class PaymentTransaction(AGRIOSBase):
    """A single Paystack payment attempt for a plan, idempotent by ``reference``.

    ``amount_kes`` is recorded from the plan at initialization time; at
    verification the gateway's amount/currency are checked against it (and the
    plan) before any subscription is activated.
    """

    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("reference", name="uq_payment_transactions_reference"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reference: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="Our own idempotency key; Paystack echoes it back",
    )
    amount_kes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="Amount in KES taken from the plan at init time (never client-supplied)",
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending | success | failed | abandoned",
    )
    paystack_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when this payment activated/renewed a subscription",
    )

    organization = relationship("Organization")
    plan = relationship("SubscriptionPlan")
    subscription = relationship("Subscription")

    def __repr__(self) -> str:
        return f"<PaymentTransaction ref={self.reference} status={self.status}>"
