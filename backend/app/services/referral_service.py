"""
Greena — Referral service (Commercial Policy layer, C3-C5).

Referral acceptance (during onboarding or within 48h), the Starter first-payment
discount, and the referrer reward. Orchestrated at endpoints; it reuses the
credit ledger and reads the billing tables, but never touches payment
verification. Rules: one referral per org, immutable once accepted, no
self-referral, no duplicate, no retroactive entry after 48h.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.billing import PaymentTransaction
from app.models.commercial import Referral
from app.models.farm import SubscriptionPlan
from app.models.organization import Organization
from app.services.credit_service import credit_service

REFERRAL_ENTRY_WINDOW_HOURS = 48
REFERRAL_REWARD_KES = 100


def _generate_code() -> str:
    return "GREENA-" + secrets.token_hex(3).upper()  # e.g. GREENA-A1B2C3


class ReferralService:
    async def assign_referral_code(self, db: AsyncSession, organization_id: uuid.UUID) -> str:
        """Give the org a unique shareable code (idempotent — kept once set)."""
        org = await db.get(Organization, organization_id)
        if org is None:
            raise NotFoundException("Organization")
        if org.referral_code:
            return org.referral_code
        for _ in range(6):
            code = _generate_code()
            clash = (
                await db.execute(select(Organization.id).where(Organization.referral_code == code))
            ).scalar_one_or_none()
            if clash is None:
                org.referral_code = code
                await db.flush()
                return code
        raise ConflictException("Could not generate a unique referral code.")

    async def get_existing(self, db: AsyncSession, organization_id: uuid.UUID) -> Referral | None:
        return (
            await db.execute(select(Referral).where(Referral.referred_org_id == organization_id))
        ).scalar_one_or_none()

    def _entry_open(self, org: Organization) -> bool:
        deadline = org.created_at + timedelta(hours=REFERRAL_ENTRY_WINDOW_HOURS)
        return datetime.now(timezone.utc) <= deadline

    async def validate(self, db: AsyncSession, organization_id: uuid.UUID, code: str) -> dict:
        """Non-committing eligibility check for the referral-entry UI."""
        org = await db.get(Organization, organization_id)
        if org is None:
            raise NotFoundException("Organization")
        if await self.get_existing(db, organization_id) is not None:
            return {"valid": False, "reason": "A referral is already set for this organization."}
        if not self._entry_open(org):
            return {"valid": False, "reason": "The 48-hour referral entry window has closed."}
        referrer = (
            await db.execute(select(Organization).where(Organization.referral_code == code))
        ).scalar_one_or_none()
        if referrer is None:
            return {"valid": False, "reason": "Referral code not found."}
        if referrer.id == organization_id:
            return {"valid": False, "reason": "You cannot refer your own organization."}
        return {"valid": True, "reason": None, "referrer_org_id": str(referrer.id)}

    async def submit(self, db: AsyncSession, organization_id: uuid.UUID, code: str) -> Referral:
        """Accept a referral. Immutable once set; enforces all referral rules."""
        org = await db.get(Organization, organization_id)
        if org is None:
            raise NotFoundException("Organization")
        if await self.get_existing(db, organization_id) is not None:
            raise ConflictException("A referral is already set for this organization.")
        if not self._entry_open(org):
            raise ValidationException("The 48-hour referral entry window has closed.")
        referrer = (
            await db.execute(select(Organization).where(Organization.referral_code == code))
        ).scalar_one_or_none()
        if referrer is None:
            raise NotFoundException("Referral code")
        if referrer.id == organization_id:
            raise ValidationException("You cannot refer your own organization.")
        referral = Referral(
            referred_org_id=organization_id,
            referrer_org_id=referrer.id,
            code_used=code,
            accepted_at=datetime.now(timezone.utc),
            reward_status="pending",
        )
        db.add(referral)
        await db.flush()
        return referral

    async def list_referrals(self, db: AsyncSession, limit: int = 200) -> list[Referral]:
        """All referrals, newest first (admin history)."""
        return list(
            (
                await db.execute(
                    select(Referral).order_by(Referral.accepted_at.desc()).limit(limit)
                )
            ).scalars().all()
        )

    async def get_referral_status(self, db: AsyncSession, organization_id: uuid.UUID) -> dict:
        """The org's own shareable code + whether it has used a referral."""
        org = await db.get(Organization, organization_id)
        if org is None:
            raise NotFoundException("Organization")
        ref = await self.get_existing(db, organization_id)
        return {
            "referral_code": org.referral_code,
            "has_referral": ref is not None,
            "referrer_org_id": ref.referrer_org_id if ref else None,
            "reward_status": ref.reward_status if ref else None,
            "entry_open": self._entry_open(org),
            "entry_deadline": org.created_at + timedelta(hours=REFERRAL_ENTRY_WINDOW_HOURS),
        }

    async def resolve_first_payment_amount(
        self, db: AsyncSession, organization_id: uuid.UUID, plan_id: uuid.UUID
    ) -> int | None:
        """The amount to charge for this plan's *first* payment.

        Returns the discounted referral price only when: the plan has a referral
        price set (Starter), the org has an accepted referral, and there is no
        prior successful payment. Otherwise the normal price. ``None`` if the
        plan does not exist (the caller/infra then 404s).
        """
        plan = await db.get(SubscriptionPlan, plan_id)
        if plan is None:
            return None
        if plan.referral_first_payment_kes is None:
            return plan.price_kes
        if await self.get_existing(db, organization_id) is None:
            return plan.price_kes
        prior_success = (
            await db.execute(
                select(PaymentTransaction.id).where(
                    PaymentTransaction.organization_id == organization_id,
                    PaymentTransaction.status == "success",
                ).limit(1)
            )
        ).scalar_one_or_none()
        if prior_success is not None:
            return plan.price_kes
        return plan.referral_first_payment_kes

    async def on_payment_activated(self, db: AsyncSession, reference: str) -> None:
        """Award the referrer a one-time credit after the referred org's FIRST
        successful payment. Idempotent (reward_status guard + first-payment check)."""
        txn = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == reference)
            )
        ).scalar_one_or_none()
        if txn is None:
            return
        referral = await self.get_existing(db, txn.organization_id)
        if referral is None or referral.reward_status != "pending":
            return
        successes = (
            await db.execute(
                select(func.count()).select_from(PaymentTransaction).where(
                    PaymentTransaction.organization_id == txn.organization_id,
                    PaymentTransaction.status == "success",
                )
            )
        ).scalar_one()
        if successes != 1:  # reward only on the first successful payment
            return
        await credit_service.add_entry(
            db, referral.referrer_org_id, REFERRAL_REWARD_KES, "referral_reward",
            payment_reference=reference,
        )
        referral.reward_status = "granted"
        referral.reward_payment_reference = reference
        await db.flush()


referral_service = ReferralService()
