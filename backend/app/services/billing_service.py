"""
Greena — Billing service (subscription payments).

The amount charged is **always read from ``subscription_plans``** — never
hardcoded, never taken from the client. The client only names which plan it
wants; the server derives the price. The seeded catalog is a placeholder until
the Commercial Policy Update, so this service must keep working unchanged when
prices or plans change in the database — payment behaviour follows the DB.

Increment 9b: initialize only. Webhook verification, activation, and referral/
trial logic land in later increments.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    AGRIOSException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.auth import User
from app.models.billing import PaymentTransaction, Subscription
from app.models.farm import Farm, SubscriptionPlan
from app.models.organization import Organization
from app.services import paystack_service
from app.services.farm_service import get_plan_by_name
from app.services.organization_service import OWNER_ROLE, organization_service

# A billing period is one month; calendar-month/annual billing is commercial
# policy (deferred). Kept here, not hardcoded per-plan, so it is easy to revisit.
BILLING_PERIOD_DAYS = 30


def _new_reference(org_id: uuid.UUID) -> str:
    """A unique, idempotent payment reference we generate and Paystack echoes."""
    return f"greena_{org_id.hex[:8]}_{uuid.uuid4().hex}"


class BillingService:
    async def initialize_subscription_payment(
        self,
        db: AsyncSession,
        *,
        organization_id: uuid.UUID,
        plan_id: uuid.UUID,
        user: User,
        callback_url: str | None = None,
    ) -> dict:
        """Start a Paystack payment for ``plan_id`` on ``organization_id``.

        Only the organization owner may pay. The amount is the plan's current
        DB price. A pending ``PaymentTransaction`` is recorded before Paystack is
        called so the webhook/verify step has an authoritative record to check.
        """
        # Org chokepoint: an active membership is required; only the owner pays.
        org, role = await organization_service.get_for_user(db, organization_id, user.id)
        if role != OWNER_ROLE:
            raise ForbiddenException("Only the organization owner can manage billing.")

        plan = (
            await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        ).scalar_one_or_none()
        if plan is None or not plan.is_active:
            raise NotFoundException("Subscription plan")

        # The amount is the plan's current price — from the DB, not the client.
        amount_kes = plan.price_kes
        if amount_kes <= 0:
            # Free (0) needs no payment; a custom/Enterprise plan (-1) is contact-sales.
            raise ValidationException("This plan cannot be purchased online.")

        if not user.email:
            raise ValidationException("An email address is required to make a payment.")

        reference = _new_reference(org.id)
        txn = PaymentTransaction(
            organization_id=org.id,
            plan_id=plan.id,
            reference=reference,
            amount_kes=amount_kes,
            currency="KES",
            status="pending",
        )
        db.add(txn)
        await db.flush()

        # Sent for our own cross-check on the webhook; never trusted on its own.
        metadata = {
            "organization_id": str(org.id),
            "plan_id": str(plan.id),
            "plan_name": plan.name,
            "reference": reference,
        }
        try:
            data = await paystack_service.initialize_transaction(
                email=user.email,
                amount_kes=amount_kes,
                reference=reference,
                callback_url=callback_url,
                metadata=metadata,
            )
        except paystack_service.PaystackError as exc:
            txn.status = "failed"
            await db.flush()
            raise AGRIOSException(
                "PAYMENT_PROVIDER_ERROR",
                "Could not initialize payment with the provider.",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        txn.paystack_reference = data.get("reference") or reference
        await db.flush()

        return {
            "authorization_url": data.get("authorization_url", ""),
            "reference": reference,
            "amount_kes": amount_kes,
            "plan_id": plan.id,
            "plan_name": plan.name,
        }

    # ── Webhook + verify (activation) ─────────────────────────────────────────

    async def process_webhook(
        self, db: AsyncSession, *, raw_body: bytes, signature: str | None
    ) -> dict:
        """Handle a Paystack webhook. HMAC-verified; only ``charge.success`` acts.

        The webhook body is NOT trusted for the amount — the reference is looked
        up locally and re-verified against Paystack in ``_verify_and_activate``.
        """
        if not paystack_service.verify_webhook_signature(raw_body, signature):
            raise AGRIOSException(
                "INVALID_SIGNATURE",
                "Invalid webhook signature.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValidationException("Malformed webhook payload.") from exc

        data = payload.get("data") or {}
        reference = data.get("reference")
        if payload.get("event") != "charge.success" or not reference:
            return {"status": "ignored", "reference": reference, "plan_id": None,
                    "subscription_active": False}

        txn = await self._get_txn(db, reference)
        if txn is None:  # unknown reference — nothing of ours to activate
            return {"status": "ignored", "reference": reference, "plan_id": None,
                    "subscription_active": False}
        return await self._verify_and_activate(db, txn)

    async def verify_payment(
        self, db: AsyncSession, *, reference: str, user: User
    ) -> dict:
        """Manual verification (frontend callback). Owner-only; same activation path."""
        txn = await self._get_txn(db, reference)
        if txn is None:
            raise NotFoundException("Payment")
        _org, role = await organization_service.get_for_user(db, txn.organization_id, user.id)
        if role != OWNER_ROLE:
            raise ForbiddenException("Only the organization owner can verify billing.")
        return await self._verify_and_activate(db, txn)

    async def _verify_and_activate(self, db: AsyncSession, txn: PaymentTransaction) -> dict:
        """Verify a transaction against Paystack, then activate the subscription.

        Idempotent: an already-successful transaction is a no-op. Activation only
        happens when Paystack independently reports success AND the verified
        amount, currency, and metadata match our stored record (which took its
        amount from the plan, never the client).
        """
        if txn.status == "success":
            sub = await self._get_org_subscription(db, txn.organization_id)
            return {
                "status": "already_processed",
                "reference": txn.reference,
                "plan_id": txn.plan_id,
                "subscription_active": bool(sub and sub.status == "active"),
            }

        verified = await paystack_service.verify_transaction(txn.reference)

        if verified.get("status") != "success":
            raise ValidationException("Payment was not successful.")
        if int(verified.get("amount", -1)) != paystack_service.kes_to_subunit(txn.amount_kes):
            raise ValidationException("Payment amount does not match the plan price.")
        if str(verified.get("currency", "")).upper() != txn.currency.upper():
            raise ValidationException("Payment currency does not match.")
        meta = verified.get("metadata") or {}
        if str(meta.get("organization_id")) != str(txn.organization_id) or str(
            meta.get("plan_id")
        ) != str(txn.plan_id):
            raise ValidationException("Payment metadata does not match.")

        now = datetime.now(timezone.utc)
        txn.status = "success"
        txn.paid_at = now
        txn.paystack_reference = verified.get("reference") or txn.reference

        sub = await self._get_org_subscription(db, txn.organization_id)
        if sub is None:
            sub = Subscription(organization_id=txn.organization_id)
            db.add(sub)
        sub.plan_id = txn.plan_id
        sub.status = "active"
        sub.activation_source = "paystack"
        sub.is_lifetime = False
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
        await db.flush()

        # Organization entitlement follows the subscription; farms inherit it.
        org = await db.get(Organization, txn.organization_id)
        if org is not None:
            org.plan_id = txn.plan_id
        await self._apply_plan_to_org_farms(db, txn.organization_id, txn.plan_id)
        txn.subscription_id = sub.id
        await db.flush()

        return {
            "status": "activated",
            "reference": txn.reference,
            "plan_id": txn.plan_id,
            "subscription_active": True,
        }

    async def downgrade_if_expired(self, db: AsyncSession, organization_id: uuid.UUID) -> bool:
        """If the org's subscription has lapsed, downgrade it (and its farms) to Free.

        The paywall is the plan on each farm; keeping that in sync with the
        subscription is the whole enforcement mechanism. Returns True if a
        downgrade happened. Lifetime/admin grants (no period end) never expire.
        """
        sub = await self._get_org_subscription(db, organization_id)
        if (
            sub is None
            or sub.status != "active"
            or sub.is_lifetime
            or sub.current_period_end is None
            or sub.current_period_end > datetime.now(timezone.utc)
        ):
            return False

        free = await get_plan_by_name(db, "free")
        sub.status = "expired"
        org = await db.get(Organization, organization_id)
        if org is not None:
            org.plan_id = free.id
        await self._apply_plan_to_org_farms(db, organization_id, free.id)
        await db.flush()
        return True

    async def _apply_plan_to_org_farms(
        self, db: AsyncSession, org_id: uuid.UUID, plan_id: uuid.UUID
    ) -> None:
        """Set every farm in the org to ``plan_id`` — farms inherit the org's entitlement."""
        await db.execute(
            update(Farm).where(Farm.organization_id == org_id).values(plan_id=plan_id)
        )

    async def _get_txn(self, db: AsyncSession, reference: str) -> PaymentTransaction | None:
        return (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == reference)
            )
        ).scalar_one_or_none()

    async def _get_org_subscription(
        self, db: AsyncSession, org_id: uuid.UUID
    ) -> Subscription | None:
        return (
            await db.execute(select(Subscription).where(Subscription.organization_id == org_id))
        ).scalar_one_or_none()


billing_service = BillingService()
