"""Integration tests for the commercial API (C8) + admin support (C7).

Customer endpoints are org-scoped (member reads, owner writes); admin endpoints
require super-admin and are audited. Paystack not involved here.
"""

import pytest
from sqlalchemy import func, select

from app.models.auth import User
from app.models.commercial import CreditLedgerEntry
from app.models.farm import SubscriptionPlan
from app.services.billing_service import billing_service
from app.services.organization_service import organization_service
from app.services.referral_service import referral_service
from app.services.trial_service import trial_service


async def _make_org(session, owner_user, name="API Org"):
    owner = await session.get(User, owner_user.id)
    owner.email = "owner@greenafarms.co"
    org, _ = await organization_service.create_organization(session, owner, name)
    org_id = org.id
    code = await referral_service.assign_referral_code(session, org_id)
    await trial_service.grant_initial_trial(session, org_id)
    await session.commit()
    return org_id, code


async def _plan_id(session, name):
    return (await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == name))).scalar_one().id


# ── C8 customer endpoints ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trial_status_endpoint(async_client, integration_session, workspace, auth_headers_owner):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.get(f"/api/v1/billing/trial/{org_id}", headers=auth_headers_owner)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["is_trial"] is True
    assert data["days_remaining"] >= 19  # ~21


@pytest.mark.asyncio
async def test_referral_validate_and_submit(async_client, integration_session, workspace, auth_headers_owner):
    _referrer_id, referrer_code = await _make_org(integration_session, workspace.users["owner"], "Referrer")
    referred_id, _ = await _make_org(integration_session, workspace.users["owner"], "Referred")

    v = await async_client.get(
        f"/api/v1/billing/referral/{referred_id}/validate",
        params={"code": referrer_code}, headers=auth_headers_owner)
    assert v.status_code == 200
    assert v.json()["data"]["valid"] is True

    s = await async_client.post(
        f"/api/v1/billing/referral/{referred_id}",
        json={"code": referrer_code}, headers=auth_headers_owner)
    assert s.status_code == 201, s.text
    assert s.json()["data"]["has_referral"] is True


@pytest.mark.asyncio
async def test_referral_status_exposes_own_code(async_client, integration_session, workspace, auth_headers_owner):
    org_id, code = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.get(f"/api/v1/billing/referral/{org_id}", headers=auth_headers_owner)
    assert r.status_code == 200
    assert r.json()["data"]["referral_code"] == code


@pytest.mark.asyncio
async def test_credits_endpoint(async_client, integration_session, workspace, auth_headers_owner):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.get(f"/api/v1/billing/credits/{org_id}", headers=auth_headers_owner)
    assert r.status_code == 200
    assert r.json()["data"]["balance_kes"] == 0


@pytest.mark.asyncio
async def test_non_member_denied(async_client, integration_session, workspace, auth_headers_manager):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.get(f"/api/v1/billing/trial/{org_id}", headers=auth_headers_manager)
    assert r.status_code in (403, 404)


# ── C7 admin endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_org_summary(
    async_client, integration_session, workspace, auth_headers_super_admin
):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    summary = await async_client.get(
        f"/api/v1/admin/billing/organizations/{org_id}", headers=auth_headers_super_admin)
    assert summary.status_code == 200, summary.text
    assert summary.json()["data"]["trial"]["is_trial"] is True


@pytest.mark.asyncio
async def test_lifetime_grant_makes_never_expiring_subscription(integration_session, workspace):
    """Lifetime-grant logic (service level): active, is_lifetime, no period end."""
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    farm_pro = await _plan_id(integration_session, "farm_pro")
    sub = await billing_service.grant_lifetime_subscription(integration_session, org_id, farm_pro)
    assert sub.is_lifetime is True
    assert sub.status == "active"
    assert sub.is_trial is False
    assert sub.current_period_end is None  # never expires
    assert sub.plan_id == farm_pro
    # the sweep never downgrades a lifetime grant
    assert await billing_service.downgrade_if_expired(integration_session, org_id) is False


@pytest.mark.asyncio
async def test_admin_credit_adjustment_is_audited(
    async_client, integration_session, workspace, auth_headers_super_admin
):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.post(
        f"/api/v1/admin/billing/organizations/{org_id}/credits",
        json={"amount_kes": 250, "reason": "goodwill"}, headers=auth_headers_super_admin)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["balance_kes"] == 250

    integration_session.expire_all()
    n = (await integration_session.execute(
        select(func.count()).select_from(CreditLedgerEntry).where(
            CreditLedgerEntry.organization_id == org_id))).scalar()
    assert n == 1


@pytest.mark.asyncio
async def test_admin_endpoints_require_super_admin(
    async_client, integration_session, workspace, auth_headers_owner
):
    org_id, _ = await _make_org(integration_session, workspace.users["owner"])
    r = await async_client.get(
        f"/api/v1/admin/billing/organizations/{org_id}", headers=auth_headers_owner)
    assert r.status_code == 403
