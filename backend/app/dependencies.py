"""
Greena — FastAPI Dependencies
Reusable dependencies injected into route handlers.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import extract_user_id
from app.database import get_db
from app.exceptions import FarmAccessException, NotFoundException, UnauthenticatedException
from app.models.auth import User, UserRole
from app.models.farm import Farm, FarmMember

# ── Bearer Token Extractor ────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """
    Extract and validate the JWT from the Authorization header.
    Loads the full user with their roles (eager loading to avoid N+1).
    Raises 401 if token is missing, expired, or invalid.
    """
    if not credentials:
        raise UnauthenticatedException("No authentication token provided.")

    try:
        user_id_str = extract_user_id(credentials.credentials)
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise UnauthenticatedException("Invalid authentication token.")

    result = await db.execute(
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .options(
            selectinload(User.user_roles).selectinload(UserRole.role)
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthenticatedException("User not found or has been deactivated.")

    if not user.is_active:
        raise UnauthenticatedException("This account has been deactivated.")

    return user


# ── Optional Auth (for public endpoints that optionally use user context) ─────

async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    """Returns the current user if authenticated, or None for unauthenticated requests."""
    if not credentials:
        return None
    try:
        return await get_current_user(db=db, credentials=credentials)
    except UnauthenticatedException:
        return None


# ── Farm Access Dependency ────────────────────────────────────────────────────

def require_farm_access(
    allowed_roles: set[str] | None = None,
) -> Callable:
    """
    Dependency factory: verify that the current user is an active member of the
    requested farm (path param ``farm_id``). Optionally restrict to specific roles.

    Usage::

        @router.get("/farms/{farm_id}/members")
        async def list_members(
            farm_id: uuid.UUID,
            db: DBSession,
            user: CurrentUser,
            _: FarmAccess = Depends(require_farm_access({"farm_owner", "farm_manager"})),
        ):
            ...
    """

    async def dependency(
        farm_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> tuple[Farm, FarmMember]:
        # Fetch the farm
        farm_result = await db.execute(
            select(Farm).where(
                Farm.id == farm_id,
                Farm.deleted_at.is_(None),
            ).options(selectinload(Farm.plan))  # type: ignore[arg-type]
        )
        farm = farm_result.scalar_one_or_none()
        if not farm:
            raise NotFoundException("Farm")

        # Fetch the membership
        member_result = await db.execute(
            select(FarmMember)
            .where(
                FarmMember.farm_id == farm_id,
                FarmMember.user_id == current_user.id,
                FarmMember.status == "active",
                FarmMember.deleted_at.is_(None),
            )
            .options(selectinload(FarmMember.role))  # type: ignore[arg-type]
        )
        member = member_result.scalar_one_or_none()

        if not member:
            raise FarmAccessException("You are not an active member of this farm.")

        if allowed_roles:
            user_platform_roles = {ur.role.name for ur in current_user.user_roles}
            # super_admin bypasses all farm-level role restrictions
            if "super_admin" not in user_platform_roles:
                if member.role.name not in allowed_roles:
                    raise FarmAccessException(
                        f"Your role '{member.role.name}' does not permit this action."
                    )

        return farm, member

    return dependency


# ── Type Aliases for cleaner route signatures ─────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
FarmAccess = Annotated[tuple[Farm, FarmMember], Depends(require_farm_access())]
