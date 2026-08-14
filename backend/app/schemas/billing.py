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


class PlanOut(AGRIOSSchema):
    """A subscription plan for the checkout UI. Prices come from the DB.

    ``is_self_serve`` = a real positive price the checkout can charge (free is 0,
    a custom/Enterprise plan is -1).
    """

    id: UUID
    name: str
    display_name: str
    price_kes: int
    is_self_serve: bool


class CommercialPolicyOut(AGRIOSSchema):
    """The authoritative commercial policy for every public/app surface.

    One endpoint so the website, signup, dashboard, billing and ARIA all read
    the same trial length and Premium price instead of hardcoding their own.
    """

    trial_days: int
    plan_name: str          # customer-facing name of the trial/premium plan
    monthly_price: int      # premium monthly price
    currency: str           # ISO currency code, e.g. "KES"
    billing_period: str     # "month"


class PublicPlanOut(AGRIOSSchema):
    """A subscription plan for the PUBLIC pricing page (no auth required).

    Contains only non-sensitive, already-public catalogue information — price and
    plan limits — so the marketing site reads the same source of truth the
    checkout charges from and cannot silently drift. ``-1`` means unlimited.
    """

    name: str
    display_name: str
    price_kes: int
    is_self_serve: bool
    max_farms: int
    max_houses_per_farm: int
    max_active_flocks: int
    max_aria_queries_per_month: int
    history_days: int
    max_team_members: int


class PaymentStatusOut(AGRIOSSchema):
    """Result of a webhook/verify: what happened and whether the sub is active."""

    reference: str | None = None
    status: str  # activated | already_processed | ignored
    plan_id: UUID | None = None
    subscription_active: bool = False
