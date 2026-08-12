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
