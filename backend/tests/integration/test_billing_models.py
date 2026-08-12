"""Integration tests for the billing models (Increment 8).

Verifies the org-scoped subscription shape, the uniqueness guarantees the later
increments rely on (one subscription per org; idempotent payment reference),
and the normalized plan prices. Model/schema only — no Paystack calls.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.billing import PaymentTransaction, Subscription
from app.models.farm import SubscriptionPlan
from app.models.organization import Organization


async def _plan(session, name: str) -> SubscriptionPlan:
    return (
        await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == name))
    ).scalar_one()


async def _make_org(session, workspace) -> Organization:
    org = Organization(
        name="Billing Test Co",
        slug=f"billing-{uuid.uuid4().hex[:8]}",
        owner_id=workspace.users["owner"].id,
    )
    session.add(org)
    await session.flush()
    return org


@pytest.mark.asyncio
async def test_plan_catalog_is_finalized(integration_session):
    """C1: the production catalog — prices, referral price, unlimited sentinels."""
    expected = {  # name: (price_kes, referral_first_payment_kes)
        "free": (0, None),
        "starter": (999, 599),
        "pro": (1499, None),        # display "Professional"
        "farm_pro": (2499, None),
        "enterprise": (-1, None),   # -1 = custom / not self-serve
    }
    for name, (price, referral) in expected.items():
        plan = await _plan(integration_session, name)
        assert plan.price_kes == price, f"{name} price"
        assert plan.referral_first_payment_kes == referral, f"{name} referral price"

    # Customer-facing paid prices end in 99.
    for name in ("starter", "pro", "farm_pro"):
        assert (await _plan(integration_session, name)).price_kes % 100 == 99

    # Self-serve = a real positive price (free and enterprise are not chargeable).
    assert (await _plan(integration_session, "starter")).is_self_serve is True
    assert (await _plan(integration_session, "free")).is_self_serve is False
    assert (await _plan(integration_session, "enterprise")).is_self_serve is False

    # Starter's finalized limits (spot check the row was fully updated).
    starter = await _plan(integration_session, "starter")
    assert (starter.max_farms, starter.max_houses_per_farm, starter.max_team_members) == (3, 20, 10)
    assert starter.max_active_flocks == 10000
    assert starter.history_days == -1  # unlimited


@pytest.mark.asyncio
async def test_subscription_is_org_scoped_and_unique(integration_session, workspace):
    """An organization owns exactly one subscription (unique organization_id)."""
    org = await _make_org(integration_session, workspace)
    pro = await _plan(integration_session, "pro")

    sub = Subscription(
        organization_id=org.id,
        plan_id=pro.id,
        status="active",
        activation_source="admin",
        is_lifetime=True,
    )
    integration_session.add(sub)
    await integration_session.flush()
    assert sub.id is not None
    assert sub.plan.name == "pro"  # relationship loads
    assert sub.organization_id == org.id

    # A second subscription for the same org violates the unique constraint.
    integration_session.add(Subscription(organization_id=org.id, plan_id=pro.id))
    with pytest.raises(IntegrityError):
        await integration_session.flush()


@pytest.mark.asyncio
async def test_payment_reference_is_idempotent(integration_session, workspace):
    """The payment reference is unique so a webhook/verify can't double-apply."""
    org = await _make_org(integration_session, workspace)
    starter = await _plan(integration_session, "starter")
    ref = f"greena_{uuid.uuid4().hex}"

    txn = PaymentTransaction(
        organization_id=org.id,
        plan_id=starter.id,
        reference=ref,
        amount_kes=starter.price_kes,
    )
    integration_session.add(txn)
    await integration_session.flush()
    assert txn.status == "pending"  # server default
    assert txn.currency == "KES"
    assert txn.amount_kes == starter.price_kes  # amount taken from the plan, not hardcoded

    # Same reference again is rejected.
    integration_session.add(
        PaymentTransaction(
            organization_id=org.id, plan_id=starter.id, reference=ref, amount_kes=starter.price_kes
        )
    )
    with pytest.raises(IntegrityError):
        await integration_session.flush()
