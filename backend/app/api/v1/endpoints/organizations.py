"""
Greena — Organization endpoints (API v1).

An organization is the tenant workspace that owns farms. Creating one is the
first onboarding step; the creator becomes its owner.
"""

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.dependencies import CurrentUser, DBSession
from app.schemas.base import SuccessResponse
from app.schemas.organization import OrganizationCreateIn, OrganizationOut
from app.services.organization_service import organization_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _out(org, role: str | None) -> OrganizationOut:
    data = OrganizationOut.model_validate(org)
    data.role = role
    return data


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "",
    response_model=SuccessResponse[OrganizationOut],
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization (onboarding)",
)
async def create_organization(
    body: OrganizationCreateIn,
    db: DBSession,
    current_user: CurrentUser,
    request: Request,
) -> SuccessResponse[OrganizationOut]:
    org, role = await organization_service.create_organization(
        db,
        current_user,
        body.name,
        country=body.country,
        timezone_=body.timezone,
        currency=body.currency,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return SuccessResponse(data=_out(org, role))


@router.get(
    "",
    response_model=SuccessResponse[list[OrganizationOut]],
    status_code=status.HTTP_200_OK,
    summary="List organizations the current user belongs to",
)
async def list_organizations(
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[list[OrganizationOut]]:
    rows = await organization_service.list_for_user(db, current_user.id)
    return SuccessResponse(data=[_out(org, role) for org, role in rows])


@router.get(
    "/{organization_id}",
    response_model=SuccessResponse[OrganizationOut],
    status_code=status.HTTP_200_OK,
    summary="Get an organization the current user belongs to",
)
async def get_organization(
    organization_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse[OrganizationOut]:
    org, role = await organization_service.get_for_user(db, organization_id, current_user.id)
    return SuccessResponse(data=_out(org, role))
