"""Integration tests for paywall activation (Increment 9d).

A subscription grants entitlement by keeping each of the org's farms on the
subscribed plan (the existing farm.plan paywall is unchanged). Activation
propagates the plan to the org's farms; expiry reverts them (and the org) to
Free. Driven at the service level with a committing session; Paystack mocked.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.auth import User
from app.models.billing import PaymentTransaction, Subscription
from app.models.farm import Farm, SubscriptionPlan
from app.services import paystack_service
from app.services.billing_service import billing_service
from app.services.organization_service import organization_service

SECRET = "sk_test_paywall"


@pytest.fixture
def paystack_secret(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", SECRET)


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()


def _body(ref: str) -> bytes:
    return json.dumps({"event": "charge.success", "data": {"reference": ref}}).encode()


async def _plan(session, name: str) -> SubscriptionPlan:
    return (
        await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == name))
    ).scalar_one()


async def _org_with_farm(session, owner_user):
    owner = await session.get(User, owner_user.id)
    owner.email = "owner@greenafarms.co"
    org, _ = await organization_service.create_organization(session, owner, "PW Org")
    free = await _plan(session, "free")
    farm = Farm(
        name="PW Farm", county="Nairobi", location="Test", owner_id=owner.id,
        plan_id=free.id, organization_id=org.id, is_active=True, timezone="Africa/Nairobi",
    )
    session.add(farm)
    await session.flush()
    return org, farm


@pytest.mark.asyncio
async def test_activation_propagates_plan_to_org_farms(
    integration_session, workspace, paystack_secret, monkeypatch
):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    starter = await _plan(integration_session, "starter")
    ref = f"greena_pw_{uuid.uuid4().hex}"
    txn = PaymentTransaction(
        organization_id=org.id, plan_id=starter.id, reference=ref,
        amount_kes=starter.price_kes, currency="KES", status="pending",
    )
    integration_session.add(txn)
    await integration_session.flush()

    async def fake_verify(reference):
        return {
            "status": "success",
            "amount": paystack_service.kes_to_subunit(starter.price_kes),
            "currency": "KES",
            "reference": reference,
            "metadata": {"organization_id": str(org.id), "plan_id": str(starter.id)},
        }

    monkeypatch.setattr(paystack_service, "verify_transaction", fake_verify)

    body = _body(ref)
    result = await billing_service.process_webhook(
        integration_session, raw_body=body, signature=_sign(body)
    )
    assert result["status"] == "activated"

    await integration_session.refresh(org)
    await integration_session.refresh(farm)  # bulk UPDATE — reload from DB
    assert org.plan_id == starter.id
    assert farm.plan_id == starter.id  # farm inherited the org's entitlement
    sub = (
        await integration_session.execute(
            select(Subscription).where(Subscription.organization_id == org.id))
    ).scalar_one()
    assert sub.status == "active"
    assert sub.plan_id == starter.id


async def _put_on_starter(session, org, farm, *, period_end, is_lifetime=False):
    starter = await _plan(session, "starter")
    org.plan_id = starter.id
    farm.plan_id = starter.id
    sub = Subscription(
        organization_id=org.id, plan_id=starter.id, status="active",
        activation_source="paystack", is_lifetime=is_lifetime,
        current_period_start=datetime.now(timezone.utc) - timedelta(days=40),
        current_period_end=period_end,
    )
    session.add(sub)
    await session.flush()
    return sub


@pytest.mark.asyncio
async def test_expiry_downgrades_org_and_farms(integration_session, workspace):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    free = await _plan(integration_session, "free")
    sub = await _put_on_starter(
        integration_session, org, farm,
        period_end=datetime.now(timezone.utc) - timedelta(days=10),  # lapsed
    )

    changed = await billing_service.downgrade_if_expired(integration_session, org.id)
    assert changed is True

    await integration_session.refresh(org)
    await integration_session.refresh(farm)
    await integration_session.refresh(sub)
    assert sub.status == "expired"
    assert org.plan_id == free.id
    assert farm.plan_id == free.id


@pytest.mark.asyncio
async def test_active_subscription_not_downgraded(integration_session, workspace):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    starter = await _plan(integration_session, "starter")
    await _put_on_starter(
        integration_session, org, farm,
        period_end=datetime.now(timezone.utc) + timedelta(days=10),  # still active
    )

    changed = await billing_service.downgrade_if_expired(integration_session, org.id)
    assert changed is False
    await integration_session.refresh(org)
    assert org.plan_id == starter.id  # unchanged


@pytest.mark.asyncio
async def test_lifetime_subscription_never_expires(integration_session, workspace):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    starter = await _plan(integration_session, "starter")
    await _put_on_starter(
        integration_session, org, farm,
        period_end=datetime.now(timezone.utc) - timedelta(days=10),  # past, but lifetime
        is_lifetime=True,
    )

    changed = await billing_service.downgrade_if_expired(integration_session, org.id)
    assert changed is False
    await integration_session.refresh(org)
    assert org.plan_id == starter.id
