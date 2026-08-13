"""
Greena — Admin billing endpoints (Commercial Policy C7).

Super-admin support tooling: view referral history, per-org billing summary
(trial + referral + credit balance), grant lifetime subscriptions, and adjust
credits via new ledger entries. Every mutating action is audited.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.core.permissions import Permission, require_permission
from app.dependencies import CurrentUser, DBSession
from app.schemas.base import SuccessResponse
from app.schemas.commercial import (
    AdminCreditAdjustIn,
    AdminLifetimeGrantIn,
    AdminOrgBillingSummaryOut,
    ReferralHistoryItemOut,
    ReferralStatusOut,
    TrialStatusOut,
)
from app.services import audit_service
from app.services.billing_service import billing_service
from app.services.credit_service import credit_service
from app.services.referral_service import referral_service
from app.services.trial_service import trial_service

router = APIRouter(prefix="/admin/billing", tags=["Admin Billing"])


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get(
    "/referrals",
    response_model=SuccessResponse[list[ReferralHistoryItemOut]],
    summary="Referral history (super-admin)",
)
async def list_referrals(
    db: DBSession,
    current_user: CurrentUser,
    _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
    limit: int = Query(200, ge=1, le=1000),
) -> SuccessResponse[list[ReferralHistoryItemOut]]:
    rows = await referral_service.list_referrals(db, limit=limit)
    return SuccessResponse(data=[ReferralHistoryItemOut.model_validate(r) for r in rows])


@router.get(
    "/organizations/{organization_id}",
    response_model=SuccessResponse[AdminOrgBillingSummaryOut],
    summary="Per-org billing summary: trial + referral + credit balance (super-admin)",
)
async def org_billing_summary(
    organization_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
    _p=Depends(require_permission(Permission.ADMIN_DASHBOARD)),
) -> SuccessResponse[AdminOrgBillingSummaryOut]:
    trial = await trial_service.get_trial_status(db, organization_id)
    referral = await referral_service.get_referral_status(db, organization_id)
    balance = await credit_service.get_balance(db, organization_id)
    return SuccessResponse(
        data=AdminOrgBillingSummaryOut(
            organization_id=organization_id,
            trial=TrialStatusOut(**trial),
            referral=ReferralStatusOut(**referral),
            credit_balance_kes=balance,
        )
    )


@router.post(
    "/organizations/{organization_id}/lifetime",
    response_model=SuccessResponse[dict],
    summary="Grant a lifetime subscription (super-admin, audited)",
)
async def grant_lifetime(
    organization_id: UUID,
    body: AdminLifetimeGrantIn,
    db: DBSession,
    current_user: CurrentUser,
    request: Request,
    _p=Depends(require_permission(Permission.ADMIN_ORG_MANAGE)),
) -> SuccessResponse[dict]:
    sub = await billing_service.grant_lifetime_subscription(db, organization_id, body.plan_id)
    await audit_service.log_action(
        db,
        action="billing.lifetime_grant",
        resource_type="subscription",
        resource_id=sub.id,
        user_id=current_user.id,
        new_value={"organization_id": str(organization_id), "plan_id": str(body.plan_id)},
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return SuccessResponse(data={"organization_id": str(organization_id), "is_lifetime": True})


@router.post(
    "/organizations/{organization_id}/credits",
    response_model=SuccessResponse[dict],
    summary="Adjust an org's credits via a new ledger entry (super-admin, audited)",
)
async def adjust_credits(
    organization_id: UUID,
    body: AdminCreditAdjustIn,
    db: DBSession,
    current_user: CurrentUser,
    request: Request,
    _p=Depends(require_permission(Permission.ADMIN_ORG_MANAGE)),
) -> SuccessResponse[dict]:
    entry = await credit_service.add_entry(
        db, organization_id, body.amount_kes, "admin_adjustment"
    )
    await audit_service.log_action(
        db,
        action="billing.credit_adjust",
        resource_type="credit_ledger",
        resource_id=entry.id,
        user_id=current_user.id,
        new_value={
            "organization_id": str(organization_id),
            "amount_kes": body.amount_kes,
            "reason": body.reason,
            "balance_after": entry.balance_after,
        },
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return SuccessResponse(
        data={"balance_kes": entry.balance_after, "amount_kes": body.amount_kes}
    )
