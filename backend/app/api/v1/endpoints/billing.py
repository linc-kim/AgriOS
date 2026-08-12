"""
Greena — Billing endpoints (API v1).

Paystack subscription payments. The client names which plan it wants; the amount
is always derived server-side from ``subscription_plans``.
"""

from fastapi import APIRouter, status

from app.dependencies import CurrentUser, DBSession
from app.schemas.base import SuccessResponse
from app.schemas.billing import InitializePaymentIn, InitializePaymentOut
from app.services.billing_service import billing_service

router = APIRouter(prefix="/billing", tags=["Billing"])


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
    result = await billing_service.initialize_subscription_payment(
        db,
        organization_id=body.organization_id,
        plan_id=body.plan_id,
        user=current_user,
        callback_url=body.callback_url,
    )
    return SuccessResponse(data=InitializePaymentOut(**result))
