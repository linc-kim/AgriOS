"""Integration tests for the billing webhook + verify flow (Increment 9c).

Paystack HTTP is mocked. Covers HMAC signature enforcement, verify-against-
stored-plan (amount/currency/metadata), idempotent activation (duplicate
webhook), and the owner-only manual verify endpoint. No live Paystack calls.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.auth import User
from app.models.billing import PaymentTransaction, Subscription
from app.models.farm import SubscriptionPlan
from app.models.organization import Organization
from app.services import paystack_service
from app.services.organization_service import organization_service

WEBHOOK_URL = "/api/v1/billing/webhook"
SECRET = "sk_test_webhook_secret"


@pytest.fixture
def paystack_secret(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", SECRET)


async def _starter(session) -> SubscriptionPlan:
    return (
        await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "starter"))
    ).scalar_one()


async def _seed_pending(session, owner_user, *, with_membership=False, amount_override=None):
    """Create an org + a pending starter transaction. Returns plain values."""
    starter = await _starter(session)
    if with_membership:
        owner = await session.get(User, owner_user.id)
        owner.email = "owner@greenafarms.co"
        org, _ = await organization_service.create_organization(session, owner, "WH Org")
    else:
        org = Organization(
            name="WH Org", slug=f"wh-{uuid.uuid4().hex[:8]}", owner_id=owner_user.id
        )
        session.add(org)
        await session.flush()
    amount = amount_override if amount_override is not None else starter.price_kes
    ref = f"greena_wh_{uuid.uuid4().hex}"
    txn = PaymentTransaction(
        organization_id=org.id, plan_id=starter.id, reference=ref,
        amount_kes=amount, currency="KES", status="pending",
    )
    session.add(txn)
    await session.flush()
    out = (org.id, starter.id, ref, amount)
    await session.commit()
    return out


def _body(ref: str) -> bytes:
    return json.dumps({"event": "charge.success", "data": {"reference": ref}}).encode()


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()


def _mock_verify(monkeypatch, *, amount, currency, org_id, plan_id, status_="success"):
    async def fake_verify(reference):
        return {
            "status": status_,
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "metadata": {"organization_id": str(org_id), "plan_id": str(plan_id)},
        }

    monkeypatch.setattr(paystack_service, "verify_transaction", fake_verify)


@pytest.mark.asyncio
async def test_webhook_activates_subscription(
    async_client, integration_session, workspace, paystack_secret, monkeypatch
):
    org_id, plan_id, ref, amount = await _seed_pending(integration_session, workspace.users["owner"])
    _mock_verify(
        monkeypatch, amount=paystack_service.kes_to_subunit(amount), currency="KES",
        org_id=org_id, plan_id=plan_id,
    )

    body = _body(ref)
    resp = await async_client.post(WEBHOOK_URL, content=body, headers={"x-paystack-signature": _sign(body)})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "activated"
    assert data["subscription_active"] is True

    integration_session.expire_all()
    txn = (await integration_session.execute(
        select(PaymentTransaction).where(PaymentTransaction.reference == ref))).scalar_one()
    assert txn.status == "success"
    assert txn.paid_at is not None
    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == org_id))).scalar_one()
    assert sub.status == "active"
    assert sub.plan_id == plan_id
    assert sub.current_period_end is not None
    org = await integration_session.get(Organization, org_id)
    assert org.plan_id == plan_id  # entitlement follows the subscription


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent(
    async_client, integration_session, workspace, paystack_secret, monkeypatch
):
    org_id, plan_id, ref, amount = await _seed_pending(integration_session, workspace.users["owner"])
    _mock_verify(
        monkeypatch, amount=paystack_service.kes_to_subunit(amount), currency="KES",
        org_id=org_id, plan_id=plan_id,
    )
    body = _body(ref)
    headers = {"x-paystack-signature": _sign(body)}

    first = await async_client.post(WEBHOOK_URL, content=body, headers=headers)
    assert first.json()["data"]["status"] == "activated"
    second = await async_client.post(WEBHOOK_URL, content=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "already_processed"
    assert second.json()["data"]["subscription_active"] is True

    integration_session.expire_all()
    count = (await integration_session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.organization_id == org_id)
    )).scalar()
    assert count == 1  # no duplicate subscription


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(
    async_client, integration_session, workspace, paystack_secret, monkeypatch
):
    org_id, plan_id, ref, amount = await _seed_pending(integration_session, workspace.users["owner"])
    _mock_verify(
        monkeypatch, amount=paystack_service.kes_to_subunit(amount), currency="KES",
        org_id=org_id, plan_id=plan_id,
    )
    body = _body(ref)
    resp = await async_client.post(WEBHOOK_URL, content=body, headers={"x-paystack-signature": "deadbeef"})
    assert resp.status_code == 401

    integration_session.expire_all()
    txn = (await integration_session.execute(
        select(PaymentTransaction).where(PaymentTransaction.reference == ref))).scalar_one()
    assert txn.status == "pending"  # nothing activated


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    ["amount", "currency", "metadata"],
)
async def test_verification_mismatches_do_not_activate(
    async_client, integration_session, workspace, paystack_secret, monkeypatch, bad
):
    org_id, plan_id, ref, amount = await _seed_pending(integration_session, workspace.users["owner"])
    good_amount = paystack_service.kes_to_subunit(amount)
    kwargs = dict(amount=good_amount, currency="KES", org_id=org_id, plan_id=plan_id)
    if bad == "amount":
        kwargs["amount"] = good_amount + 100
    elif bad == "currency":
        kwargs["currency"] = "USD"
    elif bad == "metadata":
        kwargs["org_id"] = uuid.uuid4()  # wrong org in metadata
    _mock_verify(monkeypatch, **kwargs)

    body = _body(ref)
    resp = await async_client.post(WEBHOOK_URL, content=body, headers={"x-paystack-signature": _sign(body)})
    assert resp.status_code == 422, resp.text

    integration_session.expire_all()
    txn = (await integration_session.execute(
        select(PaymentTransaction).where(PaymentTransaction.reference == ref))).scalar_one()
    assert txn.status == "pending"
    count = (await integration_session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.organization_id == org_id)
    )).scalar()
    assert count == 0  # no subscription created on a mismatch


@pytest.mark.asyncio
async def test_verify_endpoint_owner_activates(
    async_client, integration_session, workspace, auth_headers_owner, paystack_secret, monkeypatch
):
    org_id, plan_id, ref, amount = await _seed_pending(
        integration_session, workspace.users["owner"], with_membership=True
    )
    _mock_verify(
        monkeypatch, amount=paystack_service.kes_to_subunit(amount), currency="KES",
        org_id=org_id, plan_id=plan_id,
    )
    resp = await async_client.get(f"/api/v1/billing/verify/{ref}", headers=auth_headers_owner)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "activated"

    integration_session.expire_all()
    sub = (await integration_session.execute(
        select(Subscription).where(Subscription.organization_id == org_id))).scalar_one()
    assert sub.status == "active"
