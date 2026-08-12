"""Greena — Billing schemas (API v1).

The client names *which* plan (by id); it never supplies an amount. The price is
always derived server-side from ``subscription_plans``.
"""

from uuid import UUID

from app.schemas.base import AGRIOSSchema


class InitializePaymentIn(AGRIOSSchema):
    """Request body for POST /billing/initialize."""

    organization_id: UUID
    plan_id: UUID
    callback_url: str | None = None


class InitializePaymentOut(AGRIOSSchema):
    """Where to send the customer to pay, plus the server-derived amount."""

    authorization_url: str
    reference: str
    amount_kes: int
    plan_id: UUID
    plan_name: str


class PaymentStatusOut(AGRIOSSchema):
    """Result of a webhook/verify: what happened and whether the sub is active."""

    reference: str | None = None
    status: str  # activated | already_processed | ignored
    plan_id: UUID | None = None
    subscription_active: bool = False
