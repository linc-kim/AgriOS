"""
Greena — Organization models (Migration 036)

Workspace-first architecture: an Organization owns Farms and holds the team.
One identity may belong to many organizations. Membership roles reuse the
existing `roles` table (enterprise_owner for the org owner, etc.).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import Role, User
    from app.models.farm import Farm, SubscriptionPlan

# Reuse the existing member_status PG enum (created in migration 009).
OrgMemberStatusEnum = Enum(
    "pending", "active", "suspended",
    name="member_status", create_type=False, create_constraint=False,
)


class Organization(AGRIOSBase):
    """A tenant workspace that owns farms and a team."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Org-level subscription. NULL falls back to the free tier.",
    )
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Nairobi", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="KES", nullable=False)
    # Platform admin can suspend an organization (Module 10).
    is_suspended: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id], lazy="noload")
    plan: Mapped["SubscriptionPlan | None"] = relationship(lazy="noload")
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan",
    )
    farms: Mapped[list["Farm"]] = relationship(
        back_populates="organization", lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class OrganizationMember(AGRIOSBase):
    """A user's membership in an organization at a given role."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="NULL for a pending email invite with no account yet.",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(OrgMemberStatusEnum, nullable=False, default="active")
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id], lazy="noload")
    role: Mapped["Role"] = relationship(lazy="joined")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<OrganizationMember org={self.organization_id} user={self.user_id}>"
