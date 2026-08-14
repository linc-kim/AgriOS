"""
Greena — Trial service (Commercial Policy layer, C2).

One 14-day **Premium** trial per organization, granted at creation. This is
commercial policy: it sits *on top of* the billing infrastructure and reuses its
entitlement propagation (`billing_service.apply_org_entitlement`) — it never
reaches into payment/verification logic. Endpoints orchestrate (infra first,
then this); infra never imports this module.

Lifecycle:
  * grant at org creation (once per org — skipped if any subscription exists);
  * a successful paid payment converts the trial immediately (remaining days are
    discarded — the paid activation already set a fresh 30-day period);
  * expiry is handled by the shared subscription sweep (trial_ends_at mirrors
    current_period_end, so a lapsed trial downgrades to Free like any lapse).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import PaymentTransaction, Subscription
from app.services.billing_service import billing_service
from app.services.farm_service import get_plan_by_name

# ── Trial policy — the single source of truth for trial duration ──────────────
# Every surface (API, frontend, website, ARIA, admin) derives the trial length
# from here; nothing else should hardcode a number of days.
TRIAL_DAYS = 14
TRIAL_PLAN = "pro"  # the Premium entitlement (plan key "pro", display "Premium")


class TrialService:
    async def grant_initial_trial(self, db: AsyncSession, organization_id: uuid.UUID) -> bool:
        """Grant a one-time 14-day Premium trial. No-op if the org already
        has a subscription (one trial per organization; never a second)."""
        existing = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return False

        plan = await get_plan_by_name(db, TRIAL_PLAN)
        now = datetime.now(timezone.utc)
        ends = now + timedelta(days=TRIAL_DAYS)
        db.add(
            Subscription(
                organization_id=organization_id,
                plan_id=plan.id,
                status="active",
                activation_source="trial",
                is_trial=True,
                current_period_start=now,
                current_period_end=ends,
                trial_ends_at=ends,
            )
        )
        await db.flush()
        await billing_service.apply_org_entitlement(db, organization_id, plan.id)
        await db.flush()
        return True

    async def get_trial_status(self, db: AsyncSession, organization_id: uuid.UUID) -> dict:
        """Current trial state for an org (for the countdown UI)."""
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if sub is None:
            return {
                "is_trial": False,
                "active": False,
                "trial_ends_at": None,
                "days_remaining": 0,
                "trial_days": TRIAL_DAYS,
            }
        days = 0
        if sub.is_trial and sub.trial_ends_at is not None:
            days = max(0, (sub.trial_ends_at - datetime.now(timezone.utc)).days)
        return {
            "is_trial": sub.is_trial,
            "active": sub.status == "active",
            "trial_ends_at": sub.trial_ends_at,
            "days_remaining": days,
            # The trial-length policy, so the UI/ARIA never hardcode a number.
            "trial_days": TRIAL_DAYS,
        }

    async def convert_trial_on_payment(self, db: AsyncSession, reference: str) -> None:
        """After a successful paid activation, clear the trial markers.

        The paid activation (infra) already moved the subscription onto the paid
        plan with a fresh 30-day period; here we just drop the trial flag so the
        remaining trial days are discarded. Idempotent and reference-driven.
        """
        txn = (
            await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.reference == reference)
            )
        ).scalar_one_or_none()
        if txn is None:
            return
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.organization_id == txn.organization_id)
            )
        ).scalar_one_or_none()
        if sub is not None and sub.is_trial:
            sub.is_trial = False
            sub.trial_ends_at = None
            await db.flush()


trial_service = TrialService()
