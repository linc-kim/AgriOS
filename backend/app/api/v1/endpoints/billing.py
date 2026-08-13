"""
Greena — Billing endpoints (API v1).

Paystack subscription payments. The client names which plan it wants; the amount
is always derived server-side from ``subscription_plans``.
"""

from fastapi import APIRouter, Request, status

from app.dependencies import CurrentUser, DBSession
from app.schemas.base import SuccessResponse
from app.schemas.billing import (
    InitializePaymentIn,
    InitializePaymentOut,
    PaymentStatusOut,
    PlanOut,
)
from app.services.billing_service import billing_service
from app.services.referral_service import referral_service
from app.services.trial_service import trial_service

router = APIRouter(prefix="/billing", tags=["Billing"])


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
