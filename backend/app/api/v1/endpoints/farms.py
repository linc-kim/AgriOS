"""
AGRIOS — Farm API Endpoints
Sprint 2: All farm management routes.

Route map:
  GET    /plans                                               → list subscription plans
  GET    /species                                             → list species profiles

  POST   /farms                                              → create farm
  GET    /farms                                              → list user's farms
  GET    /farms/{farm_id}                                    → get farm detail
  PATCH  /farms/{farm_id}                                    → update farm

  GET    /farms/{farm_id}/members                            → list members
  POST   /farms/{farm_id}/members/invite                     → invite member
  PATCH  /farms/{farm_id}/members/{member_id}                → update member
  DELETE /farms/{farm_id}/members/{member_id}                → remove member

  GET    /farms/{farm_id}/units                              → list units
  POST   /farms/{farm_id}/units                              → create unit
  PATCH  /farms/{farm_id}/units/{unit_id}                    → update unit
  DELETE /farms/{farm_id}/units/{unit_id}                    → delete unit

  GET    /farms/{farm_id}/houses                             → list all farm houses
  POST   /farms/{farm_id}/units/{unit_id}/houses             → create house
  PATCH  /farms/{farm_id}/units/{unit_id}/houses/{house_id}  → update house
  DELETE /farms/{farm_id}/units/{unit_id}/houses/{house_id}  → delete house
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession, require_farm_access
from app.models.farm import SpeciesProfile, SubscriptionPlan
from app.schemas.base import SuccessResponse
from app.schemas.farm import (
    FarmCreate,
    FarmMemberInvite,
    FarmMemberResponse,
    FarmMemberUpdate,
    FarmResponse,
    FarmSummaryResponse,
    FarmUnitCreate,
    FarmUnitResponse,
    FarmUnitUpdate,
    FarmUpdate,
    ProductionHouseCreate,
    ProductionHouseResponse,
    ProductionHouseUpdate,
    SpeciesProfileResponse,
    SubscriptionPlanResponse,
)
from app.services import farm_service

router = APIRouter()


# ── Subscription Plans ────────────────────────────────────────────────────────

@router.get(
    "/plans",
    response_model=SuccessResponse[list[SubscriptionPlanResponse]],
    summary="List subscription plans",
    tags=["Plans"],
)
async def list_plans(
    db: DBSession,
) -> SuccessResponse[list[SubscriptionPlanResponse]]:
    """Returns all active subscription plans. Public endpoint — no auth required."""
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.deleted_at.is_(None),
        )
    )
    plans = list(result.scalars().all())
    items = [SubscriptionPlanResponse.model_validate(p) for p in plans]
    return SuccessResponse(data=items)


# ── Species Profiles ──────────────────────────────────────────────────────────

@router.get(
    "/species",
    response_model=SuccessResponse[list[SpeciesProfileResponse]],
    summary="List species profiles",
    tags=["Species"],
)
async def list_species(
    db: DBSession,
) -> SuccessResponse[list[SpeciesProfileResponse]]:
    """Returns all species profiles (active and inactive). Public endpoint."""
    result = await db.execute(
        select(SpeciesProfile)
        .where(SpeciesProfile.deleted_at.is_(None))
        .order_by(SpeciesProfile.sort_order.asc())
    )
    profiles = list(result.scalars().all())
    items = [SpeciesProfileResponse.model_validate(p) for p in profiles]
    return SuccessResponse(data=items)


# ── Farms ─────────────────────────────────────────────────────────────────────

@router.post(
    "/farms",
    response_model=SuccessResponse[FarmResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new farm",
    tags=["Farms"],
)
async def create_farm(
    body: FarmCreate,
    db: DBSession,
    user: CurrentUser,
) -> SuccessResponse[FarmResponse]:
    farm = await farm_service.create_farm(db, user, body)
    counts = await farm_service.get_farm_counts(db, farm.id)
    response = FarmResponse.model_validate({**farm.__dict__, **counts})
    return SuccessResponse(data=response)


@router.get(
    "/farms",
    response_model=SuccessResponse[list[FarmSummaryResponse]],
    summary="List farms for the current user",
    tags=["Farms"],
)
async def list_farms(
    db: DBSession,
    user: CurrentUser,
) -> SuccessResponse[list[FarmSummaryResponse]]:
    farms = await farm_service.list_farms_for_user(db, user)
    items = []
    for farm in farms:
        counts = await farm_service.get_farm_counts(db, farm.id)
        items.append(
            FarmSummaryResponse(
                id=farm.id,
                name=farm.name,
                county=farm.county,
                is_active=farm.is_active,
                member_count=counts["member_count"],
                plan_name=farm.plan.display_name if farm.plan else "Free",
                created_at=farm.created_at,
            )
        )
    return SuccessResponse(data=items)


@router.get(
    "/farms/{farm_id}",
    response_model=SuccessResponse[FarmResponse],
    summary="Get farm detail",
    tags=["Farms"],
)
async def get_farm(
    farm_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access()),
) -> SuccessResponse[FarmResponse]:
    farm = await farm_service.get_farm(db, farm_id)
    counts = await farm_service.get_farm_counts(db, farm.id)
    response = FarmResponse.model_validate(
        {**farm.__dict__, **counts, "plan": farm.plan}
    )
    return SuccessResponse(data=response)


@router.patch(
    "/farms/{farm_id}",
    response_model=SuccessResponse[FarmResponse],
    summary="Update farm details",
    tags=["Farms"],
)
async def update_farm(
    farm_id: uuid.UUID,
    body: FarmUpdate,
    db: DBSession,
    user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[FarmResponse]:
    farm, _ = access
    updated = await farm_service.update_farm(db, farm, body)
    counts = await farm_service.get_farm_counts(db, updated.id)
    response = FarmResponse.model_validate(
        {**updated.__dict__, **counts, "plan": updated.plan}
    )
    return SuccessResponse(data=response)


# ── Farm Members ──────────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/members",
    response_model=SuccessResponse[list[FarmMemberResponse]],
    summary="List farm members",
    tags=["Farm Members"],
)
async def list_farm_members(
    farm_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access()),
) -> SuccessResponse[list[FarmMemberResponse]]:
    members = await farm_service.list_farm_members(db, farm_id)
    items = [
        FarmMemberResponse(
            id=m.id,
            farm_id=m.farm_id,
            user_id=m.user_id,
            phone=m.phone,
            status=m.status,
            accepted_at=m.accepted_at,
            role_name=m.role.name,
            role_display_name=m.role.display_name,
            full_name=m.user.full_name if m.user else None,
            user_phone=m.user.phone if m.user else None,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in members
    ]
    return SuccessResponse(data=items)


@router.post(
    "/farms/{farm_id}/members/invite",
    response_model=SuccessResponse[FarmMemberResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new farm member",
    tags=["Farm Members"],
)
async def invite_farm_member(
    farm_id: uuid.UUID,
    body: FarmMemberInvite,
    db: DBSession,
    user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[FarmMemberResponse]:
    farm, _ = access
    member = await farm_service.invite_farm_member(db, farm, user, body)
    response = FarmMemberResponse(
        id=member.id,
        farm_id=member.farm_id,
        user_id=member.user_id,
        phone=member.phone,
        status=member.status,
        accepted_at=member.accepted_at,
        role_name=member.role.name,
        role_display_name=member.role.display_name,
        full_name=member.user.full_name if member.user else None,
        user_phone=member.user.phone if member.user else None,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )
    return SuccessResponse(data=response)


@router.patch(
    "/farms/{farm_id}/members/{member_id}",
    response_model=SuccessResponse[FarmMemberResponse],
    summary="Update a farm member's role or status",
    tags=["Farm Members"],
)
async def update_farm_member(
    farm_id: uuid.UUID,
    member_id: uuid.UUID,
    body: FarmMemberUpdate,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[FarmMemberResponse]:
    member = await farm_service.update_farm_member(db, farm_id, member_id, body)
    response = FarmMemberResponse(
        id=member.id,
        farm_id=member.farm_id,
        user_id=member.user_id,
        phone=member.phone,
        status=member.status,
        accepted_at=member.accepted_at,
        role_name=member.role.name,
        role_display_name=member.role.display_name,
        full_name=member.user.full_name if member.user else None,
        user_phone=member.user.phone if member.user else None,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )
    return SuccessResponse(data=response)


@router.delete(
    "/farms/{farm_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a farm member",
    tags=["Farm Members"],
)
async def remove_farm_member(
    farm_id: uuid.UUID,
    member_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> None:
    await farm_service.remove_farm_member(db, farm_id, member_id, user.id)


# ── Farm Units ────────────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/units",
    response_model=SuccessResponse[list[FarmUnitResponse]],
    summary="List farm units",
    tags=["Farm Units"],
)
async def list_farm_units(
    farm_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access()),
) -> SuccessResponse[list[FarmUnitResponse]]:
    units = await farm_service.list_farm_units(db, farm_id)
    items = [
        FarmUnitResponse(
            id=u.id,
            farm_id=u.farm_id,
            name=u.name,
            description=u.description,
            sort_order=u.sort_order,
            house_count=len([h for h in u.houses if not h.is_deleted]),
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in units
    ]
    return SuccessResponse(data=items)


@router.post(
    "/farms/{farm_id}/units",
    response_model=SuccessResponse[FarmUnitResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a farm unit",
    tags=["Farm Units"],
)
async def create_farm_unit(
    farm_id: uuid.UUID,
    body: FarmUnitCreate,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[FarmUnitResponse]:
    unit = await farm_service.create_farm_unit(db, farm_id, body)
    response = FarmUnitResponse(
        id=unit.id,
        farm_id=unit.farm_id,
        name=unit.name,
        description=unit.description,
        sort_order=unit.sort_order,
        house_count=0,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )
    return SuccessResponse(data=response)


@router.patch(
    "/farms/{farm_id}/units/{unit_id}",
    response_model=SuccessResponse[FarmUnitResponse],
    summary="Update a farm unit",
    tags=["Farm Units"],
)
async def update_farm_unit(
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    body: FarmUnitUpdate,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[FarmUnitResponse]:
    unit = await farm_service.update_farm_unit(db, farm_id, unit_id, body)
    house_count = len([h for h in unit.houses if not h.is_deleted]) if unit.houses else 0
    response = FarmUnitResponse(
        id=unit.id,
        farm_id=unit.farm_id,
        name=unit.name,
        description=unit.description,
        sort_order=unit.sort_order,
        house_count=house_count,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )
    return SuccessResponse(data=response)


@router.delete(
    "/farms/{farm_id}/units/{unit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a farm unit",
    tags=["Farm Units"],
)
async def delete_farm_unit(
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> None:
    await farm_service.delete_farm_unit(db, farm_id, unit_id)


# ── Production Houses ─────────────────────────────────────────────────────────

@router.get(
    "/farms/{farm_id}/houses",
    response_model=SuccessResponse[list[ProductionHouseResponse]],
    summary="List all production houses in a farm",
    tags=["Production Houses"],
)
async def list_farm_houses(
    farm_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access()),
) -> SuccessResponse[list[ProductionHouseResponse]]:
    houses = await farm_service.list_all_farm_houses(db, farm_id)
    items = [
        ProductionHouseResponse(
            id=h.id,
            farm_id=h.farm_id,
            unit_id=h.unit_id,
            name=h.name,
            capacity=h.capacity,
            house_type=h.house_type,
            sort_order=h.sort_order,
            current_flock_id=h.current_flock_id,
            is_occupied=h.is_occupied,
            created_at=h.created_at,
            updated_at=h.updated_at,
        )
        for h in houses
    ]
    return SuccessResponse(data=items)


@router.post(
    "/farms/{farm_id}/units/{unit_id}/houses",
    response_model=SuccessResponse[ProductionHouseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a production house in a unit",
    tags=["Production Houses"],
)
async def create_production_house(
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    body: ProductionHouseCreate,
    db: DBSession,
    user: CurrentUser,
    access: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[ProductionHouseResponse]:
    farm, _ = access
    house = await farm_service.create_production_house(db, farm, unit_id, body)
    response = ProductionHouseResponse(
        id=house.id,
        farm_id=house.farm_id,
        unit_id=house.unit_id,
        name=house.name,
        capacity=house.capacity,
        house_type=house.house_type,
        sort_order=house.sort_order,
        current_flock_id=house.current_flock_id,
        is_occupied=house.is_occupied,
        created_at=house.created_at,
        updated_at=house.updated_at,
    )
    return SuccessResponse(data=response)


@router.patch(
    "/farms/{farm_id}/units/{unit_id}/houses/{house_id}",
    response_model=SuccessResponse[ProductionHouseResponse],
    summary="Update a production house",
    tags=["Production Houses"],
)
async def update_production_house(
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    house_id: uuid.UUID,
    body: ProductionHouseUpdate,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> SuccessResponse[ProductionHouseResponse]:
    house = await farm_service.update_production_house(
        db, farm_id, unit_id, house_id, body
    )
    response = ProductionHouseResponse(
        id=house.id,
        farm_id=house.farm_id,
        unit_id=house.unit_id,
        name=house.name,
        capacity=house.capacity,
        house_type=house.house_type,
        sort_order=house.sort_order,
        current_flock_id=house.current_flock_id,
        is_occupied=house.is_occupied,
        created_at=house.created_at,
        updated_at=house.updated_at,
    )
    return SuccessResponse(data=response)


@router.delete(
    "/farms/{farm_id}/units/{unit_id}/houses/{house_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a production house",
    tags=["Production Houses"],
)
async def delete_production_house(
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    house_id: uuid.UUID,
    db: DBSession,
    user: CurrentUser,
    _: tuple = Depends(require_farm_access({"farm_owner", "farm_manager"})),
) -> None:
    await farm_service.delete_production_house(db, farm_id, unit_id, house_id)
