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

import uuid

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    AGRIOSException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.auth import User
from app.models.billing import PaymentTransaction
from app.models.farm import SubscriptionPlan
from app.services import paystack_service
from app.services.organization_service import OWNER_ROLE, organization_service


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


billing_service = BillingService()
