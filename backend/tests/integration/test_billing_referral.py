"""Integration tests for referrals, discount, rewards, and the credit ledger
(Increments C3-C6). Paystack mocked; service-level with a committing session.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.billing import PaymentTransaction
from app.models.commercial import CreditLedgerEntry, Referral
from app.models.farm import SubscriptionPlan
from app.models.organization import Organization
from app.services import paystack_service
from app.services.billing_service import billing_service
from app.services.credit_service import credit_service
from app.services.referral_service import REFERRAL_REWARD_KES, referral_service

SECRET = "sk_test_referral"


@pytest.fixture
def paystack_secret(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", SECRET)


async def _plan(session, name):
    return (await session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == name))).scalar_one()


async def _org(session, owner_user, name):
    org = Organization(name=name, slug=f"r-{uuid.uuid4().hex[:8]}", owner_id=owner_user.id)
    session.add(org)
    await session.flush()
    code = await referral_service.assign_referral_code(session, org.id)
    return org, code


async def _pay(session, monkeypatch, org_id, plan, amount):
    ref = f"greena_r_{uuid.uuid4().hex}"
    session.add(PaymentTransaction(
        organization_id=org_id, plan_id=plan.id, reference=ref,
        amount_kes=amount, currency="KES", status="pending"))
    await session.flush()

    async def fake_verify(reference):
        return {"status": "success", "amount": paystack_service.kes_to_subunit(amount),
                "currency": "KES", "reference": reference,
                "metadata": {"organization_id": str(org_id), "plan_id": str(plan.id)}}
    monkeypatch.setattr(paystack_service, "verify_transaction", fake_verify)

    body = json.dumps({"event": "charge.success", "data": {"reference": ref}}).encode()
    sig = hmac.new(SECRET.encode(), body, hashlib.sha512).hexdigest()
    result = await billing_service.process_webhook(session, raw_body=body, signature=sig)
    return ref, result


# ── C3: referral acceptance rules ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_referral_accepted(integration_session, workspace):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    ref = await referral_service.submit(integration_session, referred.id, code)
    assert ref.referrer_org_id == referrer.id
    assert ref.reward_status == "pending"


@pytest.mark.asyncio
async def test_unknown_code_rejected(integration_session, workspace):
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    with pytest.raises(NotFoundException):
        await referral_service.submit(integration_session, referred.id, "GREENA-000000")


@pytest.mark.asyncio
async def test_self_referral_rejected(integration_session, workspace):
    org, code = await _org(integration_session, workspace.users["owner"], "SelfOrg")
    with pytest.raises(ValidationException):
        await referral_service.submit(integration_session, org.id, code)


@pytest.mark.asyncio
async def test_duplicate_referral_rejected(integration_session, workspace):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    await referral_service.submit(integration_session, referred.id, code)
    with pytest.raises(ConflictException):
        await referral_service.submit(integration_session, referred.id, code)


@pytest.mark.asyncio
async def test_referral_after_48h_rejected(integration_session, workspace):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    referred.created_at = datetime.now(timezone.utc) - timedelta(hours=49)  # window closed
    await integration_session.flush()
    with pytest.raises(ValidationException):
        await referral_service.submit(integration_session, referred.id, code)
    # validate() reports the same, non-committing
    res = await referral_service.validate(integration_session, referred.id, code)
    assert res["valid"] is False


# ── C4: first-payment discount ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_referral_discounts_starter_first_payment(integration_session, workspace):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    await referral_service.submit(integration_session, referred.id, code)
    starter = await _plan(integration_session, "starter")

    amount = await referral_service.resolve_first_payment_amount(
        integration_session, referred.id, starter.id)
    assert amount == 599  # 999 -> 599


@pytest.mark.asyncio
async def test_no_referral_pays_full_price(integration_session, workspace):
    org, _ = await _org(integration_session, workspace.users["owner"], "NoRef")
    starter = await _plan(integration_session, "starter")
    amount = await referral_service.resolve_first_payment_amount(
        integration_session, org.id, starter.id)
    assert amount == 999


@pytest.mark.asyncio
async def test_renewal_not_discounted(integration_session, workspace, paystack_secret, monkeypatch):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    await referral_service.submit(integration_session, referred.id, code)
    starter = await _plan(integration_session, "starter")

    # First payment succeeds (discounted).
    _ref, result = await _pay(integration_session, monkeypatch, referred.id, starter, 599)
    assert result["status"] == "activated"

    # A subsequent charge for the same org is full price (no discount on renewals).
    amount = await referral_service.resolve_first_payment_amount(
        integration_session, referred.id, starter.id)
    assert amount == 999


# ── C5/C6: referrer reward + immutable ledger ─────────────────────────────────

@pytest.mark.asyncio
async def test_referrer_rewarded_after_verified_payment(
    integration_session, workspace, paystack_secret, monkeypatch
):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    await referral_service.submit(integration_session, referred.id, code)
    starter = await _plan(integration_session, "starter")

    assert await credit_service.get_balance(integration_session, referrer.id) == 0
    ref, result = await _pay(integration_session, monkeypatch, referred.id, starter, 599)
    assert result["status"] == "activated"
    await referral_service.on_payment_activated(integration_session, ref)

    assert await credit_service.get_balance(integration_session, referrer.id) == REFERRAL_REWARD_KES
    referral = (await integration_session.execute(
        select(Referral).where(Referral.referred_org_id == referred.id))).scalar_one()
    assert referral.reward_status == "granted"


@pytest.mark.asyncio
async def test_reward_not_duplicated_on_repeat_hook(
    integration_session, workspace, paystack_secret, monkeypatch
):
    referrer, code = await _org(integration_session, workspace.users["owner"], "Referrer")
    referred, _ = await _org(integration_session, workspace.users["owner"], "Referred")
    await referral_service.submit(integration_session, referred.id, code)
    starter = await _plan(integration_session, "starter")

    ref, _ = await _pay(integration_session, monkeypatch, referred.id, starter, 599)
    await referral_service.on_payment_activated(integration_session, ref)
    await referral_service.on_payment_activated(integration_session, ref)  # repeat = no-op

    assert await credit_service.get_balance(integration_session, referrer.id) == REFERRAL_REWARD_KES
    n = (await integration_session.execute(
        select(func.count()).select_from(CreditLedgerEntry).where(
            CreditLedgerEntry.organization_id == referrer.id))).scalar()
    assert n == 1  # exactly one ledger entry


@pytest.mark.asyncio
async def test_ledger_is_append_only_with_running_balance(integration_session, workspace):
    org, _ = await _org(integration_session, workspace.users["owner"], "LedgerOrg")
    e1 = await credit_service.add_entry(integration_session, org.id, 100, "referral_reward")
    e2 = await credit_service.add_entry(integration_session, org.id, 100, "referral_reward")
    e3 = await credit_service.add_entry(integration_session, org.id, -50, "admin_adjustment")
    assert (e1.balance_after, e2.balance_after, e3.balance_after) == (100, 200, 150)
    assert await credit_service.get_balance(integration_session, org.id) == 150
    history = await credit_service.get_history(integration_session, org.id)
    assert len(history) == 3
