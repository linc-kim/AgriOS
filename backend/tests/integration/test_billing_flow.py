"""Integration tests for the billing payment flow (Increment 9b — initialize).

Paystack HTTP is mocked (no live calls). Covers: a successful initialize, that
the charged amount is read dynamically from the plan (never hardcoded/client-
supplied), rejection of non-self-serve plans, and org-owner access control.

Test-harness note: ``integration_session`` and ``async_client`` share one
connection with SAVEPOINT join mode, so all seed writes/reads are committed
*before* any request — an open savepoint would be orphaned by the endpoint's
commit and break teardown. Seed helpers therefore return plain values.
"""

import pytest
from sqlalchemy import select

from app.models.auth import User
from app.models.billing import PaymentTransaction
from app.models.farm import SubscriptionPlan
from app.services import paystack_service
from app.services.organization_service import organization_service

INIT_URL = "/api/v1/billing/initialize"


async def _setup(session, owner_user, plan_name, *, price_override=None, email="owner@greenafarms.co"):
    """Seed an org owned by ``owner_user`` and return plain (org_id, plan_id, price).

    Commits before returning so no savepoint is held across an async_client call.
    """
    owner = await session.get(User, owner_user.id)
    owner.email = email  # payments require an email
    org, _role = await organization_service.create_organization(session, owner, "Billing Test Org")
    plan = (
        await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name))
    ).scalar_one()
    if price_override is not None:
        plan.price_kes = price_override
    result = (org.id, plan.id, plan.price_kes)
    await session.commit()
    return result


@pytest.fixture
def mock_paystack_init(monkeypatch):
    """Replace the real Paystack call; capture what the service sent."""
    calls: dict = {}

    async def fake_init(*, email, amount_kes, reference, callback_url=None, metadata=None):
        calls.update(
            email=email, amount_kes=amount_kes, reference=reference,
            callback_url=callback_url, metadata=metadata,
        )
        return {
            "authorization_url": f"https://checkout.paystack.com/{reference}",
            "access_code": "acc_test",
            "reference": reference,
        }

    monkeypatch.setattr(paystack_service, "initialize_transaction", fake_init)
    return calls


@pytest.mark.asyncio
async def test_initialize_payment_success(
    async_client, integration_session, workspace, auth_headers_owner, mock_paystack_init
):
    org_id, plan_id, price = await _setup(integration_session, workspace.users["owner"], "starter")

    resp = await async_client.post(
        INIT_URL,
        json={"organization_id": str(org_id), "plan_id": str(plan_id)},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["authorization_url"].startswith("https://checkout.paystack.com/")
    assert data["amount_kes"] == price
    assert data["plan_name"] == "starter"

    # The amount handed to Paystack is the plan price, not anything client-supplied.
    assert mock_paystack_init["amount_kes"] == price
    assert mock_paystack_init["metadata"]["organization_id"] == str(org_id)

    # A pending transaction was recorded with the plan's price (read after the request).
    txn = (
        await integration_session.execute(
            select(PaymentTransaction).where(PaymentTransaction.reference == data["reference"])
        )
    ).scalar_one()
    assert txn.status == "pending"
    assert txn.amount_kes == price
    assert txn.organization_id == org_id


@pytest.mark.asyncio
async def test_amount_follows_db_price_no_hardcoding(
    async_client, integration_session, workspace, auth_headers_owner, mock_paystack_init
):
    """Move the plan's price to an arbitrary value; the charge must follow it."""
    org_id, plan_id, _ = await _setup(
        integration_session, workspace.users["owner"], "starter", price_override=12345
    )

    resp = await async_client.post(
        INIT_URL,
        json={"organization_id": str(org_id), "plan_id": str(plan_id)},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["amount_kes"] == 12345
    assert mock_paystack_init["amount_kes"] == 12345


@pytest.mark.asyncio
async def test_free_plan_cannot_be_purchased(
    async_client, integration_session, workspace, auth_headers_owner, mock_paystack_init
):
    org_id, free_id, _ = await _setup(integration_session, workspace.users["owner"], "free")

    resp = await async_client.post(
        INIT_URL,
        json={"organization_id": str(org_id), "plan_id": str(free_id)},
        headers=auth_headers_owner,
    )
    # ValidationException → 422 in this app; free (price 0) is not purchasable.
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_list_plans(async_client, workspace, auth_headers_owner):
    resp = await async_client.get("/api/v1/billing/plans", headers=auth_headers_owner)
    assert resp.status_code == 200, resp.text
    plans = resp.json()["data"]
    by_name = {p["name"]: p for p in plans}
    assert {"free", "starter", "pro"} <= set(by_name)
    assert by_name["starter"]["is_self_serve"] is True
    assert by_name["free"]["is_self_serve"] is False
    # cheapest first
    assert plans == sorted(plans, key=lambda p: p["price_kes"])


@pytest.mark.asyncio
async def test_non_member_cannot_initialize(
    async_client, integration_session, workspace, auth_headers_manager, mock_paystack_init
):
    """A user who is not the org owner/member is refused (no cross-tenant billing)."""
    org_id, plan_id, _ = await _setup(integration_session, workspace.users["owner"], "starter")

    resp = await async_client.post(
        INIT_URL,
        json={"organization_id": str(org_id), "plan_id": str(plan_id)},
        headers=auth_headers_manager,  # manager is not a member of this org
    )
    assert resp.status_code in (403, 404), resp.text
