"""
Greena — Farm Infrastructure Models
Covers Migrations 006-011:
  006: subscription_plans
  007: species_profiles
  008: farms
  009: farm_members
  010: farm_units
  011: production_houses
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AGRIOSBase

if TYPE_CHECKING:
    from app.models.auth import User, Role
    from app.models.organization import Organization


# ── Migration 006: Subscription Plans ────────────────────────────────────────

class SubscriptionPlan(AGRIOSBase):
    """
    Defines the limits and features of each Greena subscription tier.
    Values seeded at migration time. Not user-created.
    -1 in integer limit fields means UNLIMITED.
    """

    __tablename__ = "subscription_plans"

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Plan key: free | starter | pro",
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_kes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Monthly price in KES. 0 = free.",
    )
    max_farms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="-1 = unlimited",
    )
    max_houses_per_farm: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="-1 = unlimited",
    )
    max_active_flocks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="-1 = unlimited",
    )
    max_aria_queries_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="-1 = unlimited",
    )
    history_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="-1 = unlimited",
    )
    max_team_members: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    farms: Mapped[list["Farm"]] = relationship(back_populates="plan")

    def is_unlimited(self, field: str) -> bool:
        """Check if a specific limit is unlimited (-1)."""
        return getattr(self, field, 0) == -1

    def __repr__(self) -> str:
        return f"<SubscriptionPlan {self.name} KES{self.price_kes}/mo>"


# ── Migration 007: Species Profiles ──────────────────────────────────────────

class SpeciesProfile(AGRIOSBase):
    """
    The extensibility engine for Greena species modules.
    Activating a new species = UPDATE SET is_active=TRUE + add species-specific tables.
    NEVER modify existing tables to activate a species.
    """

    __tablename__ = "species_profiles"

    species_key: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Stable FK used in species-specific tables. Never rename in production.",
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name_sw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    icon: Mapped[str] = mapped_column(String(50), nullable=False)
    module_accent_hex: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        comment="Design System v1 accent color for this module.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Only super_admin can activate. Activating makes module available platform-wide.",
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SpeciesProfile {self.species_key} active={self.is_active}>"


# ── Migration 008: Farms ──────────────────────────────────────────────────────

class Farm(AGRIOSBase):
    """
    A farm is the primary tenancy unit in Greena.
    Every operational record carries farm_id.
    DB-04 (Frozen): farm_id is present on every operational table.
    """

    __tablename__ = "farms"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    county: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Kenya county (47 counties). Used for SMS disease alert targeting.",
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Owning organization (workspace-first). Nullable for legacy farms.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="Africa/Nairobi",
        nullable=False,
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        foreign_keys=[owner_id],
        lazy="noload",
    )
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="farms")
    organization: Mapped["Organization | None"] = relationship(
        back_populates="farms",
        lazy="noload",
    )
    members: Mapped[list["FarmMember"]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
    )
    units: Mapped[list["FarmUnit"]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
    )
    production_houses: Mapped[list["ProductionHouse"]] = relationship(
        back_populates="farm",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Farm '{self.name}' owner={self.owner_id}>"


# ── Migration 009: Farm Members ───────────────────────────────────────────────

MEMBER_STATUS_VALUES = ("pending", "active", "suspended")
MemberStatusEnum = Enum(
    *MEMBER_STATUS_VALUES,
    name="member_status",
    create_type=False,
    create_constraint=True,
)



class FarmMember(AGRIOSBase):
    """
    Represents a user's membership in a farm at a specific role.
    Supports invite-by-phone: user_id is NULL while status = 'pending'
    for invitees who do not yet have an Greena account.
    """

    __tablename__ = "farm_members"
    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "user_id",
            name="uq_farm_members_farm_user",
        ),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL for pending invites where invitee has no Greena account.",
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Phone number used to send the invite SMS.",
    )
    status: Mapped[str] = mapped_column(
        MemberStatusEnum,
        nullable=False,
        default="pending",
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    farm: Mapped["Farm"] = relationship(back_populates="members")
    user: Mapped["User | None"] = relationship(
        foreign_keys=[user_id],
        lazy="noload",
    )
    role: Mapped["Role"] = relationship(lazy="joined")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def __repr__(self) -> str:
        return (
            f"<FarmMember farm={self.farm_id} user={self.user_id} "
            f"status={self.status}>"
        )


# ── Migration 010: Farm Units ─────────────────────────────────────────────────

class FarmUnit(AGRIOSBase):
    """
    A named physical section of a farm, grouping production houses.
    e.g., 'Section A', 'Block 1', 'North Wing'.
    """

    __tablename__ = "farm_units"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    farm: Mapped["Farm"] = relationship(back_populates="units")
    houses: Mapped[list["ProductionHouse"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FarmUnit '{self.name}' farm={self.farm_id}>"


# ── Migration 011: Production Houses ─────────────────────────────────────────

HOUSE_TYPE_VALUES = ("broiler", "layer", "breeder", "pullet", "multi")
HouseTypeEnum = Enum(
    *HOUSE_TYPE_VALUES,
    name="house_type",
    create_constraint=True,
)


class ProductionHouse(AGRIOSBase):
    """
    An individual physical structure within a farm unit.
    e.g., 'House 1', 'Broiler Pen A', 'Layer House 3'.
    One active flock per house at a time (enforced at application layer).
    """

    __tablename__ = "production_houses"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum bird capacity. Used for stocking density warnings.",
    )
    house_type: Mapped[str] = mapped_column(
        HouseTypeEnum,
        nullable=False,
        default="broiler",
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # FK to flocks.id added in Migration 012 when flocks table exists.
    current_flock_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK to flocks.id added in Migration 012.",
    )

    # Relationships
    farm: Mapped["Farm"] = relationship(back_populates="production_houses")
    unit: Mapped["FarmUnit"] = relationship(back_populates="houses")

    @property
    def is_occupied(self) -> bool:
        return self.current_flock_id is not None

    def __repr__(self) -> str:
        return f"<ProductionHouse '{self.name}' unit={self.unit_id}>"
