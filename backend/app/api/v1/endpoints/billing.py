"""
Greena — Billing endpoints (API v1).

Paystack subscription payments. The client names which plan it wants; the amount
is always derived server-side from ``subscription_plans``.
"""

from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.dependencies import CurrentUser, DBSession
from app.exceptions import ForbiddenException
from app.schemas.base import SuccessResponse
from app.schemas.billing import (
    InitializePaymentIn,
    InitializePaymentOut,
    PaymentStatusOut,
    PlanOut,
)
from app.schemas.commercial import (
    CreditBalanceOut,
    CreditEntryOut,
    ReferralStatusOut,
    ReferralSubmitIn,
    ReferralValidateOut,
    TrialStatusOut,
)
from app.services.billing_service import billing_service
from app.services.credit_service import credit_service
from app.services.organization_service import OWNER_ROLE, organization_service
from app.services.referral_service import referral_service
from app.services.trial_service import trial_service

router = APIRouter(prefix="/billing", tags=["Billing"])


async def _require_member(db, organization_id: UUID, user):
    """Active membership of the org (raises 404 if not a member)."""
    return await organization_service.get_for_user(db, organization_id, user.id)


async def _require_owner(db, organization_id: UUID, user):
    _org, role = await organization_service.get_for_user(db, organization_id, user.id)
    if role != OWNER_ROLE:
        raise ForbiddenException("Only the organization owner can manage billing.")


@router.get(
    "/plans",
    response_model=SuccessResponse[list[PlanOut]],
    status_code=status.HTTP_200_OK,
    summary="List active subscription plans for the checkout UI",
)
async def list_plans(db: DBSession, current_user: CurrentUser) -> SuccessResponse[list[PlanOut]]:
    plans = await billing_service.list_active_plans(db)
    data = [
        PlanOut(
            id=p.id,
            name=p.name,
            display_name=p.display_name,
            price_kes=p.price_kes,
            is_self_serve=p.price_kes > 0,
        )
        for p in plans
    ]
    return SuccessResponse(data=data)


@router.post(
    "/initialize",
    response_model=SuccessResponse[InitializePaymentOut],
    status_code=status.HTTP_201_CREATED,
    summary="Start a subscription payment (returns a Paystack authorization URL)",
)
async def initialize_payment(
    body: InitializePaymentIn,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[InitializePaymentOut]:
    # Commercial policy (server-computed): a referral may discount the first
    # payment. The amount is derived from the DB plan, never the client.
    amount_override = await referral_service.resolve_first_payment_amount(
        db, body.organization_id, body.plan_id
    )
    result = await billing_service.initialize_subscription_payment(
        db,
        organization_id=body.organization_id,
        plan_id=body.plan_id,
        user=current_user,
        callback_url=body.callback_url,
        amount_kes_override=amount_override,
    )
    return SuccessResponse(data=InitializePaymentOut(**result))


@router.post(
    "/webhook",
    response_model=SuccessResponse[PaymentStatusOut],
    status_code=status.HTTP_200_OK,
    summary="Paystack webhook (HMAC-verified; server-to-server, no auth)",
)
async def paystack_webhook(request: Request, db: DBSession) -> SuccessResponse[PaymentStatusOut]:
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature")
    result = await billing_service.process_webhook(db, raw_body=raw_body, signature=signature)
    if result["status"] == "activated":
        await trial_service.convert_trial_on_payment(db, result["reference"])
        await referral_service.on_payment_activated(db, result["reference"])
    return SuccessResponse(data=PaymentStatusOut(**result))


@router.get(
    "/verify/{reference}",
    response_model=SuccessResponse[PaymentStatusOut],
    status_code=status.HTTP_200_OK,
    summary="Manually verify a payment and activate the subscription (owner-only)",
)
async def verify_payment(
    reference: str,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[PaymentStatusOut]:
    result = await billing_service.verify_payment(db, reference=reference, user=current_user)
    if result["status"] == "activated":
        await trial_service.convert_trial_on_payment(db, result["reference"])
        await referral_service.on_payment_activated(db, result["reference"])
    return SuccessResponse(data=PaymentStatusOut(**result))


# ── Commercial policy: trial / referral / credits (org-scoped, C8) ─────────────

@router.get(
    "/trial/{organization_id}",
    response_model=SuccessResponse[TrialStatusOut],
    summary="Trial status for an organization (member)",
)
async def trial_status(
    organization_id: UUID, db: DBSession, current_user: CurrentUser
) -> SuccessResponse[TrialStatusOut]:
    await _require_member(db, organization_id, current_user)
    data = await trial_service.get_trial_status(db, organization_id)
    return SuccessResponse(data=TrialStatusOut(**data))


@router.get(
    "/referral/{organization_id}",
    response_model=SuccessResponse[ReferralStatusOut],
    summary="Referral status + this org's shareable code (member)",
)
async def referral_status(
    organization_id: UUID, db: DBSession, current_user: CurrentUser
) -> SuccessResponse[ReferralStatusOut]:
    await _require_member(db, organization_id, current_user)
    data = await referral_service.get_referral_status(db, organization_id)
    return SuccessResponse(data=ReferralStatusOut(**data))


@router.get(
    "/referral/{organization_id}/validate",
    response_model=SuccessResponse[ReferralValidateOut],
    summary="Validate a referral code without committing (member)",
)
async def referral_validate(
    organization_id: UUID, db: DBSession, current_user: CurrentUser, code: str = Query(...)
) -> SuccessResponse[ReferralValidateOut]:
    await _require_member(db, organization_id, current_user)
    data = await referral_service.validate(db, organization_id, code)
    return SuccessResponse(data=ReferralValidateOut(valid=data["valid"], reason=data["reason"]))


@router.post(
    "/referral/{organization_id}",
    response_model=SuccessResponse[ReferralStatusOut],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a referral code (owner; onboarding or within 48h)",
)
async def referral_submit(
    organization_id: UUID, body: ReferralSubmitIn, db: DBSession, current_user: CurrentUser
) -> SuccessResponse[ReferralStatusOut]:
    await _require_owner(db, organization_id, current_user)
    await referral_service.submit(db, organization_id, body.code)
    data = await referral_service.get_referral_status(db, organization_id)
    return SuccessResponse(data=ReferralStatusOut(**data))


@router.get(
    "/credits/{organization_id}",
    response_model=SuccessResponse[CreditBalanceOut],
    summary="Credit balance + ledger history (member)",
)
async def credit_balance(
    organization_id: UUID, db: DBSession, current_user: CurrentUser
) -> SuccessResponse[CreditBalanceOut]:
    await _require_member(db, organization_id, current_user)
    balance = await credit_service.get_balance(db, organization_id)
    entries = await credit_service.get_history(db, organization_id)
    return SuccessResponse(
        data=CreditBalanceOut(
            balance_kes=balance,
            entries=[CreditEntryOut.model_validate(e) for e in entries],
        )
    )
