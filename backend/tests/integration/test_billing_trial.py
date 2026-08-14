"""Integration tests for the trial system (Increment C2).

One 14-day Premium trial per organization, granted at creation; a paid
payment converts it immediately (remaining days discarded); expiry downgrades to
Free. Service-level tests plus one endpoint-wiring test. Paystack mocked.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.auth import User
from app.models.billing import PaymentTransaction, Subscription
from app.models.farm import Farm, SubscriptionPlan
from app.models.organization import Organization
from app.services import paystack_service
from app.services.billing_service import billing_service
from app.services.trial_service import TRIAL_DAYS, trial_service

SECRET = "sk_test_trial"


async def _plan(session, name):
    return (await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == name))).scalar_one()


async def _org_with_farm(session, owner_user, name="Trial Org"):
    free = await _plan(session, "free")
    org = Organization(name=name, slug=f"t-{uuid.uuid4().hex[:8]}", owner_id=owner_user.id)
    session.add(org)
    await session.flush()
    farm = Farm(
        name="Trial Farm", county="Nairobi", location="Test", owner_id=owner_user.id,
        plan_id=free.id, organization_id=org.id, is_active=True, timezone="Africa/Nairobi",
    )
    session.add(farm)
    await session.flush()
    return org, farm


@pytest.mark.asyncio
async def test_grant_initial_trial(integration_session, workspace):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    pro = await _plan(integration_session, "pro")

    granted = await trial_service.grant_initial_trial(integration_session, org.id)
    assert granted is True

    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == org.id))).scalar_one()
    assert sub.is_trial is True
    assert sub.status == "active"
    assert sub.activation_source == "trial"
    assert sub.plan_id == pro.id
    # ~TRIAL_DAYS out (policy: 14 days)
    delta = sub.current_period_end - datetime.now(timezone.utc)
    assert timedelta(days=TRIAL_DAYS - 1) < delta <= timedelta(days=TRIAL_DAYS)
    assert sub.trial_ends_at == sub.current_period_end

    await integration_session.refresh(org)
    await integration_session.refresh(farm)
    assert org.plan_id == pro.id
    assert farm.plan_id == pro.id  # farm inherits the trial entitlement


@pytest.mark.asyncio
async def test_only_one_trial_per_org(integration_session, workspace):
    org, _ = await _org_with_farm(integration_session, workspace.users["owner"])
    assert await trial_service.grant_initial_trial(integration_session, org.id) is True
    assert await trial_service.grant_initial_trial(integration_session, org.id) is False  # no second
    count = (await integration_session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.organization_id == org.id))).scalar()
    assert count == 1


@pytest.mark.asyncio
async def test_each_org_gets_its_own_trial(integration_session, workspace):
    org1, _ = await _org_with_farm(integration_session, workspace.users["owner"], "Org One")
    org2, _ = await _org_with_farm(integration_session, workspace.users["owner"], "Org Two")
    assert await trial_service.grant_initial_trial(integration_session, org1.id) is True
    assert await trial_service.grant_initial_trial(integration_session, org2.id) is True


@pytest.mark.asyncio
async def test_payment_during_trial_converts_immediately(
    integration_session, workspace, monkeypatch
):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", SECRET)
    org, _ = await _org_with_farm(integration_session, workspace.users["owner"])
    await trial_service.grant_initial_trial(integration_session, org.id)
    starter = await _plan(integration_session, "starter")

    ref = f"greena_trial_{uuid.uuid4().hex}"
    integration_session.add(PaymentTransaction(
        organization_id=org.id, plan_id=starter.id, reference=ref,
        amount_kes=starter.price_kes, currency="KES", status="pending"))
    await integration_session.flush()

    async def fake_verify(reference):
        return {"status": "success", "amount": paystack_service.kes_to_subunit(starter.price_kes),
                "currency": "KES", "reference": reference,
                "metadata": {"organization_id": str(org.id), "plan_id": str(starter.id)}}
    monkeypatch.setattr(paystack_service, "verify_transaction", fake_verify)

    body = json.dumps({"event": "charge.success", "data": {"reference": ref}}).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    result = await billing_service.process_webhook(integration_session, raw_body=body, signature=sig)
    assert result["status"] == "activated"
    await trial_service.convert_trial_on_payment(integration_session, ref)

    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == org.id))).scalar_one()
    assert sub.is_trial is False           # converted
    assert sub.trial_ends_at is None       # remaining trial days discarded
    assert sub.plan_id == starter.id       # now the paid plan
    assert sub.activation_source == "paystack"
    # fresh 30-day paid period, not the trial's remaining ~14 days
    delta = sub.current_period_end - datetime.now(timezone.utc)
    assert delta > timedelta(days=25)


@pytest.mark.asyncio
async def test_expired_trial_downgrades_to_free(integration_session, workspace):
    org, farm = await _org_with_farm(integration_session, workspace.users["owner"])
    await trial_service.grant_initial_trial(integration_session, org.id)
    free = await _plan(integration_session, "free")

    # Force the trial into the past.
    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == org.id))).scalar_one()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    sub.current_period_end = past
    sub.trial_ends_at = past
    await integration_session.flush()

    downgraded = await billing_service.sweep_expired_subscriptions(integration_session)
    assert downgraded >= 1

    await integration_session.refresh(sub)
    await integration_session.refresh(org)
    await integration_session.refresh(farm)
    assert sub.status == "expired"
    assert org.plan_id == free.id
    assert farm.plan_id == free.id


@pytest.mark.asyncio
async def test_org_creation_endpoint_grants_trial(
    async_client, integration_session, workspace, auth_headers_owner
):
    # Ensure the owner has an email (not required for org creation, but realistic).
    owner = await integration_session.get(User, workspace.users["owner"].id)
    owner.email = "owner@greenafarms.co"
    await integration_session.commit()

    resp = await async_client.post(
        "/api/v1/organizations", json={"name": "Endpoint Trial Org"}, headers=auth_headers_owner)
    assert resp.status_code == 201, resp.text
    org_id = resp.json()["data"]["id"]

    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == uuid.UUID(org_id)))).scalar_one()
    assert sub.is_trial is True
    assert sub.activation_source == "trial"
