"""
Greena — Farm Service
Business logic for:
  - Farm CRUD with plan limit enforcement
  - Farm membership (invite, accept, suspend, remove)
  - Farm units (create, update, delete)
  - Production houses (create, update, delete)

All queries are farm-scoped (DB-04: farm_id present on every operational table).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.exceptions import (
    ConflictException,
    FarmAccessException,
    NotFoundException,
    PlanLimitException,
)
from app.models.auth import Role, User, UserRole
from app.models.farm import (
    Farm,
    FarmMember,
    FarmUnit,
    ProductionHouse,
    SubscriptionPlan,
)
from app.schemas.farm import (
    FarmCreate,
    FarmMemberInvite,
    FarmMemberUpdate,
    FarmUpdate,
    FarmUnitCreate,
    FarmUnitUpdate,
    ProductionHouseCreate,
    ProductionHouseUpdate,
)
from app.services import sms_service

# ── Plan Limit Helpers ────────────────────────────────────────────────────────

def _check_limit(current: int, limit: int, resource: str) -> None:
    """Raise PlanLimitException if limit is exceeded. -1 = unlimited."""
    if limit == -1:
        return
    if current >= limit:
        raise PlanLimitException(
            f"Your plan allows a maximum of {limit} {resource}. "
            "Upgrade your subscription to add more."
        )


# ── Farm CRUD ─────────────────────────────────────────────────────────────────

async def get_plan_by_name(db: AsyncSession, name: str) -> SubscriptionPlan:
    """Retrieve a subscription plan by name key. Raises NotFoundException if missing."""
    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == name,
            SubscriptionPlan.deleted_at.is_(None),
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise NotFoundException(f"Subscription plan '{name}'")
    return plan


async def create_farm(
    db: AsyncSession,
    user: User,
    data: FarmCreate,
) -> Farm:
    """
    Create a new farm owned by the current user.
    Assigns free plan, creates owner FarmMember record.
    Enforces plan.max_farms limit.
    """
    # Check how many farms this user already owns
    farm_count_result = await db.execute(
        select(func.count(Farm.id)).where(
            Farm.owner_id == user.id,
            Farm.deleted_at.is_(None),
        )
    )
    existing_farms = farm_count_result.scalar_one()

    # Get user's plan from any of their existing farms, default to free
    free_plan = await get_plan_by_name(db, "free")
    _check_limit(existing_farms, free_plan.max_farms, "farms")

    # Workspace-first: if an organization is given, the creator must belong to it.
    if data.organization_id is not None:
        from app.models.organization import OrganizationMember

        member_check = await db.execute(
            select(OrganizationMember.id).where(
                OrganizationMember.organization_id == data.organization_id,
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == "active",
                OrganizationMember.deleted_at.is_(None),
            )
        )
        if member_check.scalar_one_or_none() is None:
            raise FarmAccessException("You are not a member of that organization.")

    farm = Farm(
        name=data.name,
        description=data.description,
        location=data.location,
        county=data.county,
        owner_id=user.id,
        plan_id=free_plan.id,
        organization_id=data.organization_id,
        is_active=True,
        timezone="Africa/Nairobi",
    )
    db.add(farm)
    await db.flush()  # Get the farm.id before creating member

    # Look up farm_owner role
    role_result = await db.execute(
        select(Role).where(Role.name == "farm_owner")
    )
    farm_owner_role = role_result.scalar_one()

    # Add owner as an active member
    member = FarmMember(
        farm_id=farm.id,
        user_id=user.id,
        role_id=farm_owner_role.id,
        phone=user.phone,
        status="active",
        invited_by=user.id,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(member)

    # Ensure the creator holds the platform-level farm_owner role. The permission
    # system (require_permission) reads UserRole, not farm membership; without
    # this, an email-signup user who onboards a farm would be blocked (403) from
    # every write endpoint (flocks, health, finance, ...).
    existing_role = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == farm_owner_role.id,
        )
    )
    if existing_role.scalar_one_or_none() is None:
        db.add(UserRole(user_id=user.id, role_id=farm_owner_role.id, farm_id=None))

    await db.commit()
    await db.refresh(farm)
    return farm


async def get_farm(db: AsyncSession, farm_id: uuid.UUID) -> Farm:
    """Retrieve a farm by ID. Raises NotFoundException if not found or soft-deleted."""
    result = await db.execute(
        select(Farm)
        .where(Farm.id == farm_id, Farm.deleted_at.is_(None))
        .options(joinedload(Farm.plan))
    )
    farm = result.scalar_one_or_none()
    if not farm:
        raise NotFoundException("Farm")
    return farm


async def list_farms_for_user(db: AsyncSession, user: User) -> list[Farm]:
    """
    Return all farms where the user is an active member.
    Includes plan details via join.
    """
    result = await db.execute(
        select(Farm)
        .join(
            FarmMember,
            (FarmMember.farm_id == Farm.id)
            & (FarmMember.user_id == user.id)
            & (FarmMember.status == "active")
            & (FarmMember.deleted_at.is_(None)),
        )
        .where(Farm.deleted_at.is_(None), Farm.is_active.is_(True))
        .options(joinedload(Farm.plan))
        .order_by(Farm.created_at.asc())
    )
    return list(result.scalars().all())


async def update_farm(
    db: AsyncSession,
    farm: Farm,
    data: FarmUpdate,
) -> Farm:
    """Apply partial updates to a farm. Only non-None fields are updated."""
    if data.name is not None:
        farm.name = data.name
    if data.description is not None:
        farm.description = data.description
    if data.location is not None:
        farm.location = data.location
    if data.county is not None:
        farm.county = data.county
    await db.commit()
    await db.refresh(farm)
    return farm


async def get_farm_counts(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> dict[str, int]:
    """Return member_count, unit_count, house_count for a farm."""
    member_count = (
        await db.execute(
            select(func.count(FarmMember.id)).where(
                FarmMember.farm_id == farm_id,
                FarmMember.status == "active",
                FarmMember.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    unit_count = (
        await db.execute(
            select(func.count(FarmUnit.id)).where(
                FarmUnit.farm_id == farm_id,
                FarmUnit.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    house_count = (
        await db.execute(
            select(func.count(ProductionHouse.id)).where(
                ProductionHouse.farm_id == farm_id,
                ProductionHouse.deleted_at.is_(None),
            )
        )
    ).scalar_one()

    return {
        "member_count": member_count,
        "unit_count": unit_count,
        "house_count": house_count,
    }


# ── Farm Access Verification ──────────────────────────────────────────────────

async def get_farm_member(
    db: AsyncSession,
    farm_id: uuid.UUID,
    user: User,
) -> FarmMember:
    """
    Return the active FarmMember record for a user in a farm.
    Raises FarmAccessException if the user is not an active member.
    """
    result = await db.execute(
        select(FarmMember)
        .where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == user.id,
            FarmMember.status == "active",
            FarmMember.deleted_at.is_(None),
        )
        .options(joinedload(FarmMember.role))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise FarmAccessException(
            "You are not an active member of this farm."
        )
    return member


async def verify_farm_access(
    db: AsyncSession,
    farm_id: uuid.UUID,
    user: User,
    allowed_roles: set[str] | None = None,
) -> tuple[Farm, FarmMember]:
    """
    Verify the user has access to the farm.
    Optionally enforce that the user's role is in allowed_roles.
    Returns (farm, member) tuple.
    """
    farm = await get_farm(db, farm_id)
    member = await get_farm_member(db, farm_id, user)

    if allowed_roles and member.role.name not in allowed_roles:
        # super_admin bypasses farm-level role restrictions
        user_role_names = {ur.role.name for ur in user.user_roles}
        if "super_admin" not in user_role_names:
            raise FarmAccessException(
                f"Your role '{member.role.name}' does not permit this action on this farm."
            )

    return farm, member


# ── Farm Members ──────────────────────────────────────────────────────────────

async def list_farm_members(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> list[FarmMember]:
    """List all non-deleted members of a farm."""
    result = await db.execute(
        select(FarmMember)
        .where(
            FarmMember.farm_id == farm_id,
            FarmMember.deleted_at.is_(None),
        )
        .options(
            joinedload(FarmMember.role),
            joinedload(FarmMember.user),
        )
        .order_by(FarmMember.created_at.asc())
    )
    return list(result.scalars().all())


async def invite_farm_member(
    db: AsyncSession,
    farm: Farm,
    inviter: User,
    data: FarmMemberInvite,
) -> FarmMember:
    """
    Invite a user to join the farm by phone number.
    Checks plan.max_team_members before creating the invite.
    Sends an SMS invite notification.
    Raises ConflictException if phone already has an active membership.
    """
    # Count active members
    active_count_result = await db.execute(
        select(func.count(FarmMember.id)).where(
            FarmMember.farm_id == farm.id,
            FarmMember.status.in_(["active", "pending"]),
            FarmMember.deleted_at.is_(None),
        )
    )
    active_count = active_count_result.scalar_one()
    _check_limit(active_count, farm.plan.max_team_members, "team members")

    # Check for existing membership by phone
    existing_result = await db.execute(
        select(FarmMember).where(
            FarmMember.farm_id == farm.id,
            FarmMember.phone == data.phone,
            FarmMember.deleted_at.is_(None),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        raise ConflictException(
            f"{data.phone} is already a member or has a pending invite for this farm."
        )

    # Look up the role
    role_result = await db.execute(
        select(Role).where(Role.name == data.role_name)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise NotFoundException(f"Role '{data.role_name}'")

    # Check if an Greena user exists with this phone
    user_result = await db.execute(
        select(User).where(
            User.phone == data.phone,
            User.deleted_at.is_(None),
        )
    )
    invitee_user = user_result.scalar_one_or_none()

    member = FarmMember(
        farm_id=farm.id,
        user_id=invitee_user.id if invitee_user else None,
        role_id=role.id,
        phone=data.phone,
        status="active" if invitee_user else "pending",
        invited_by=inviter.id,
        accepted_at=datetime.now(timezone.utc) if invitee_user else None,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    # Send SMS invite (non-blocking failure).
    # V1 has no deep-link yet; instruct invitee to download Greena and log in.
    await sms_service.sms_farm_invite(
        phone=data.phone,
        farm_name=farm.name,
    )

    return member


async def update_farm_member(
    db: AsyncSession,
    farm_id: uuid.UUID,
    member_id: uuid.UUID,
    data: FarmMemberUpdate,
) -> FarmMember:
    """Update a farm member's status or role."""
    result = await db.execute(
        select(FarmMember)
        .where(
            FarmMember.id == member_id,
            FarmMember.farm_id == farm_id,
            FarmMember.deleted_at.is_(None),
        )
        .options(joinedload(FarmMember.role))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundException("Farm member")

    if data.status is not None:
        member.status = data.status

    if data.role_name is not None:
        role_result = await db.execute(
            select(Role).where(Role.name == data.role_name)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise NotFoundException(f"Role '{data.role_name}'")
        member.role_id = role.id

    await db.commit()
    await db.refresh(member)
    return member


async def remove_farm_member(
    db: AsyncSession,
    farm_id: uuid.UUID,
    member_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
) -> None:
    """
    Soft-delete a farm member.
    Cannot remove the farm owner (role = farm_owner).
    Cannot remove yourself.
    """
    result = await db.execute(
        select(FarmMember)
        .where(
            FarmMember.id == member_id,
            FarmMember.farm_id == farm_id,
            FarmMember.deleted_at.is_(None),
        )
        .options(joinedload(FarmMember.role))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundException("Farm member")

    if member.role.name == "farm_owner":
        raise FarmAccessException(
            "The farm owner cannot be removed. Transfer ownership first."
        )

    if member.user_id == requesting_user_id:
        raise FarmAccessException(
            "You cannot remove yourself from a farm. Use 'Leave Farm' instead."
        )

    member.soft_delete()
    await db.commit()


# ── Farm Units ────────────────────────────────────────────────────────────────

async def list_farm_units(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> list[FarmUnit]:
    """List all non-deleted units for a farm, ordered by sort_order."""
    result = await db.execute(
        select(FarmUnit)
        .where(
            FarmUnit.farm_id == farm_id,
            FarmUnit.deleted_at.is_(None),
        )
        .options(selectinload(FarmUnit.houses))
        .order_by(FarmUnit.sort_order.asc(), FarmUnit.created_at.asc())
    )
    return list(result.scalars().all())


async def create_farm_unit(
    db: AsyncSession,
    farm_id: uuid.UUID,
    data: FarmUnitCreate,
) -> FarmUnit:
    """Create a new farm unit."""
    unit = FarmUnit(
        farm_id=farm_id,
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
    )
    db.add(unit)
    await db.commit()
    await db.refresh(unit)
    return unit


async def update_farm_unit(
    db: AsyncSession,
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    data: FarmUnitUpdate,
) -> FarmUnit:
    """Update a farm unit."""
    result = await db.execute(
        select(FarmUnit).where(
            FarmUnit.id == unit_id,
            FarmUnit.farm_id == farm_id,
            FarmUnit.deleted_at.is_(None),
        )
    )
    unit = result.scalar_one_or_none()
    if not unit:
        raise NotFoundException("Farm unit")

    if data.name is not None:
        unit.name = data.name
    if data.description is not None:
        unit.description = data.description
    if data.sort_order is not None:
        unit.sort_order = data.sort_order

    await db.commit()
    await db.refresh(unit)
    return unit


async def delete_farm_unit(
    db: AsyncSession,
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
) -> None:
    """
    Soft-delete a farm unit and cascade to its houses.
    Cannot delete a unit that has occupied houses (active flock).
    """
    result = await db.execute(
        select(FarmUnit)
        .where(
            FarmUnit.id == unit_id,
            FarmUnit.farm_id == farm_id,
            FarmUnit.deleted_at.is_(None),
        )
        .options(selectinload(FarmUnit.houses))
    )
    unit = result.scalar_one_or_none()
    if not unit:
        raise NotFoundException("Farm unit")

    occupied = [h for h in unit.houses if h.is_occupied and not h.is_deleted]
    if occupied:
        raise ConflictException(
            f"Cannot delete unit '{unit.name}': {len(occupied)} house(s) have active flocks. "
            "Close all flocks before deleting the unit."
        )

    # Soft-delete all houses first
    for house in unit.houses:
        if not house.is_deleted:
            house.soft_delete()

    unit.soft_delete()
    await db.commit()


# ── Production Houses ─────────────────────────────────────────────────────────

async def list_houses_in_unit(
    db: AsyncSession,
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
) -> list[ProductionHouse]:
    """List all non-deleted production houses within a unit."""
    result = await db.execute(
        select(ProductionHouse)
        .where(
            ProductionHouse.unit_id == unit_id,
            ProductionHouse.farm_id == farm_id,
            ProductionHouse.deleted_at.is_(None),
        )
        .order_by(
            ProductionHouse.sort_order.asc(),
            ProductionHouse.created_at.asc(),
        )
    )
    return list(result.scalars().all())


async def list_all_farm_houses(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> list[ProductionHouse]:
    """List all non-deleted production houses across all units of a farm."""
    result = await db.execute(
        select(ProductionHouse)
        .where(
            ProductionHouse.farm_id == farm_id,
            ProductionHouse.deleted_at.is_(None),
        )
        .order_by(
            ProductionHouse.sort_order.asc(),
            ProductionHouse.created_at.asc(),
        )
    )
    return list(result.scalars().all())


async def create_production_house(
    db: AsyncSession,
    farm: Farm,
    unit_id: uuid.UUID,
    data: ProductionHouseCreate,
) -> ProductionHouse:
    """
    Create a production house inside a unit.
    Enforces plan.max_houses_per_farm limit.
    """
    # Verify the unit exists and belongs to this farm
    unit_result = await db.execute(
        select(FarmUnit).where(
            FarmUnit.id == unit_id,
            FarmUnit.farm_id == farm.id,
            FarmUnit.deleted_at.is_(None),
        )
    )
    unit = unit_result.scalar_one_or_none()
    if not unit:
        raise NotFoundException("Farm unit")

    # Check plan house limit
    house_count_result = await db.execute(
        select(func.count(ProductionHouse.id)).where(
            ProductionHouse.farm_id == farm.id,
            ProductionHouse.deleted_at.is_(None),
        )
    )
    house_count = house_count_result.scalar_one()
    _check_limit(
        house_count,
        farm.plan.max_houses_per_farm,
        "production houses",
    )

    house = ProductionHouse(
        farm_id=farm.id,
        unit_id=unit_id,
        name=data.name,
        capacity=data.capacity,
        house_type=data.house_type,
        sort_order=data.sort_order,
        current_flock_id=None,
    )
    db.add(house)
    await db.commit()
    await db.refresh(house)
    return house


async def update_production_house(
    db: AsyncSession,
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    house_id: uuid.UUID,
    data: ProductionHouseUpdate,
) -> ProductionHouse:
    """Update a production house."""
    result = await db.execute(
        select(ProductionHouse).where(
            ProductionHouse.id == house_id,
            ProductionHouse.unit_id == unit_id,
            ProductionHouse.farm_id == farm_id,
            ProductionHouse.deleted_at.is_(None),
        )
    )
    house = result.scalar_one_or_none()
    if not house:
        raise NotFoundException("Production house")

    if data.name is not None:
        house.name = data.name
    if data.capacity is not None:
        house.capacity = data.capacity
    if data.house_type is not None:
        house.house_type = data.house_type
    if data.sort_order is not None:
        house.sort_order = data.sort_order

    await db.commit()
    await db.refresh(house)
    return house


async def delete_production_house(
    db: AsyncSession,
    farm_id: uuid.UUID,
    unit_id: uuid.UUID,
    house_id: uuid.UUID,
) -> None:
    """
    Soft-delete a production house.
    Cannot delete a house with an active flock.
    """
    result = await db.execute(
        select(ProductionHouse).where(
            ProductionHouse.id == house_id,
            ProductionHouse.unit_id == unit_id,
            ProductionHouse.farm_id == farm_id,
            ProductionHouse.deleted_at.is_(None),
        )
    )
    house = result.scalar_one_or_none()
    if not house:
        raise NotFoundException("Production house")

    if house.is_occupied:
        raise ConflictException(
            f"Cannot delete house '{house.name}': it has an active flock. "
            "Close the flock before deleting the house."
        )

    house.soft_delete()
    await db.commit()
