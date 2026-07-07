"""
Greena — Organization Service.

Creating an organization is the first onboarding step after authentication:
it creates the workspace, makes the creator its owner (enterprise_owner role),
and attaches the free plan. Farms are created inside an organization.
"""

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.auth import Role
from app.models.farm import SubscriptionPlan
from app.models.organization import Organization, OrganizationMember
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

OWNER_ROLE = "enterprise_owner"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


class OrganizationService:
    async def _unique_slug(self, db: AsyncSession, base: str) -> str:
        slug, i = base, 1
        while True:
            existing = await db.execute(
                select(Organization.id).where(Organization.slug == slug)
            )
            if existing.scalar_one_or_none() is None:
                return slug
            i += 1
            slug = f"{base}-{i}"

    async def create_organization(
        self,
        db: AsyncSession,
        owner,
        name: str,
        *,
        country: str | None = None,
        timezone_: str | None = None,
        currency: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Organization, str]:
        slug = await self._unique_slug(db, _slugify(name))

        role_res = await db.execute(select(Role).where(Role.name == OWNER_ROLE))
        owner_role = role_res.scalar_one_or_none()
        if owner_role is None:
            raise NotFoundException("Owner role")

        plan_res = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
        )
        free_plan = plan_res.scalar_one_or_none()

        org = Organization(
            name=name,
            slug=slug,
            owner_id=owner.id,
            plan_id=free_plan.id if free_plan else None,
            country=country,
            timezone=timezone_ or "Africa/Nairobi",
            currency=currency or "KES",
        )
        db.add(org)
        await db.flush()

        db.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=owner.id,
                role_id=owner_role.id,
                status="active",
                accepted_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()

        await log_action(
            db,
            action="organization.create",
            resource_type="organization",
            resource_id=org.id,
            user_id=owner.id,
            ip_address=ip,
            user_agent=user_agent,
        )
        return org, owner_role.name

    async def list_for_user(self, db: AsyncSession, user_id: UUID) -> list[tuple[Organization, str]]:
        result = await db.execute(
            select(Organization, Role.name)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
                OrganizationMember.deleted_at.is_(None),
                Organization.deleted_at.is_(None),
            )
            .order_by(Organization.created_at)
        )
        return list(result.all())

    async def get_for_user(
        self, db: AsyncSession, org_id: UUID, user_id: UUID
    ) -> tuple[Organization, str]:
        result = await db.execute(
            select(Organization, Role.name)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .join(Role, Role.id == OrganizationMember.role_id)
            .where(
                Organization.id == org_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == "active",
                Organization.deleted_at.is_(None),
            )
        )
        row = result.first()
        if row is None:
            raise NotFoundException("Organization")
        return row[0], row[1]


organization_service = OrganizationService()
