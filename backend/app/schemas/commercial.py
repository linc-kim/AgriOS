"""Greena — Commercial Policy schemas (trial, referral, credits; customer + admin)."""

from datetime import datetime
from uuid import UUID

from app.schemas.base import AGRIOSSchema


class TrialStatusOut(AGRIOSSchema):
    is_trial: bool
    active: bool
    trial_ends_at: datetime | None = None
    days_remaining: int = 0
    # Trial-length policy (single source of truth: trial_service.TRIAL_DAYS).
    trial_days: int = 14


class ReferralStatusOut(AGRIOSSchema):
    referral_code: str | None = None
    has_referral: bool
    referrer_org_id: UUID | None = None
    reward_status: str | None = None
    entry_open: bool
    entry_deadline: datetime | None = None


class ReferralValidateOut(AGRIOSSchema):
    valid: bool
    reason: str | None = None


class ReferralSubmitIn(AGRIOSSchema):
    code: str


class CreditEntryOut(AGRIOSSchema):
    amount_kes: int
    source: str
    payment_reference: str | None = None
    balance_after: int
    created_at: datetime


class CreditBalanceOut(AGRIOSSchema):
    balance_kes: int
    entries: list[CreditEntryOut]


# ── Admin ─────────────────────────────────────────────────────────────────────

class AdminLifetimeGrantIn(AGRIOSSchema):
    plan_id: UUID


class AdminCreditAdjustIn(AGRIOSSchema):
    amount_kes: int  # signed: positive grants, negative deducts
    reason: str | None = None


class ReferralHistoryItemOut(AGRIOSSchema):
    referred_org_id: UUID
    referrer_org_id: UUID
    code_used: str
    reward_status: str
    accepted_at: datetime


class AdminOrgBillingSummaryOut(AGRIOSSchema):
    organization_id: UUID
    trial: TrialStatusOut
    referral: ReferralStatusOut
    credit_balance_kes: int
