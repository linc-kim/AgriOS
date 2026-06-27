"""
AGRIOS — Farm Infrastructure Pydantic Schemas
Request validation and response serialisation for:
  - Subscription Plans
  - Species Profiles
  - Farms
  - Farm Members
  - Farm Units
  - Production Houses
"""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema

# ── Kenya Counties (47) ───────────────────────────────────────────────────────
# Used for farm.county validation (disease alert targeting).

KENYA_COUNTIES = {
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu",
    "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho",
    "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale",
    "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
    "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru",
    "Nandi", "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu",
    "Siaya", "Taita-Taveta", "Tana River", "Tharaka-Nithi",
    "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir",
    "West Pokot",
}

PHONE_REGEX = re.compile(r"^\+254[17]\d{8}$")

# ── Subscription Plan Schemas ─────────────────────────────────────────────────

class SubscriptionPlanResponse(TimestampedSchema):
    """Subscription plan as returned by the API."""
    name: str
    display_name: str
    price_kes: int
    max_farms: int
    max_houses_per_farm: int
    max_active_flocks: int
    max_aria_queries_per_month: int
    history_days: int
    max_team_members: int
    is_active: bool


# ── Species Profile Schemas ───────────────────────────────────────────────────

class SpeciesProfileResponse(TimestampedSchema):
    """Species profile as returned by the API."""
    species_key: str
    display_name: str
    display_name_sw: str | None
    icon: str
    module_accent_hex: str
    is_active: bool
    sort_order: int
    description: str | None


# ── Farm Schemas ──────────────────────────────────────────────────────────────

class FarmCreate(AGRIOSSchema):
    """Request body for creating a new farm."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Farm display name.",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    location: str | None = Field(
        default=None,
        max_length=255,
        description="Optional detailed location within the county.",
    )
    county: str | None = Field(
        default=None,
        description="Kenya county. Must be one of the 47 official counties.",
    )

    @field_validator("county")
    @classmethod
    def validate_county(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.strip().title()
        if normalized not in KENYA_COUNTIES:
            raise ValueError(
                f"'{v}' is not a recognised Kenya county. "
                "Provide one of the 47 official county names."
            )
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Farm name cannot be empty or whitespace only.")
        return cleaned


class FarmUpdate(AGRIOSSchema):
    """Request body for updating an existing farm. All fields optional."""
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    location: str | None = Field(default=None, max_length=255)
    county: str | None = Field(default=None)

    @field_validator("county")
    @classmethod
    def validate_county(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.strip().title()
        if normalized not in KENYA_COUNTIES:
            raise ValueError(
                f"'{v}' is not a recognised Kenya county."
            )
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Farm name cannot be empty or whitespace only.")
        return cleaned


class FarmResponse(TimestampedSchema):
    """Farm data as returned by the API."""
    name: str
    description: str | None
    location: str | None
    county: str | None
    owner_id: UUID
    plan_id: UUID
    is_active: bool
    timezone: str
    # Computed fields populated by service
    member_count: int = 0
    unit_count: int = 0
    house_count: int = 0
    plan: SubscriptionPlanResponse | None = None


class FarmSummaryResponse(AGRIOSSchema):
    """Lightweight farm summary for list views."""
    id: UUID
    name: str
    county: str | None
    is_active: bool
    member_count: int
    plan_name: str
    created_at: datetime


# ── Farm Member Schemas ───────────────────────────────────────────────────────

class FarmMemberInvite(AGRIOSSchema):
    """Request body for inviting a new farm member."""
    phone: str = Field(
        ...,
        description="Kenyan phone number in E.164 format: +254XXXXXXXXX",
    )
    role_name: str = Field(
        ...,
        description=(
            "Role to assign: farm_manager | vet_consultant | farm_worker | viewer"
        ),
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = v.strip().replace(" ", "")
        if not PHONE_REGEX.match(cleaned):
            raise ValueError(
                "Phone must be a valid Kenyan number in E.164 format: +254XXXXXXXXX"
            )
        return cleaned

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, v: str) -> str:
        allowed = {"farm_manager", "vet_consultant", "farm_worker", "viewer"}
        if v not in allowed:
            raise ValueError(
                f"Role '{v}' cannot be assigned by invite. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )
        return v


class FarmMemberUpdate(AGRIOSSchema):
    """Update a farm member's status or role."""
    status: Literal["active", "suspended"] | None = None
    role_name: str | None = Field(
        default=None,
        description="New role: farm_manager | vet_consultant | farm_worker | viewer",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "FarmMemberUpdate":
        if self.status is None and self.role_name is None:
            raise ValueError("Provide at least one of: status, role_name")
        return self

    @field_validator("role_name")
    @classmethod
    def validate_role_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"farm_manager", "vet_consultant", "farm_worker", "viewer"}
        if v not in allowed:
            raise ValueError(
                f"Role '{v}' cannot be assigned by invite. "
                f"Allowed: {', '.join(sorted(allowed))}"
            )
        return v


class FarmMemberResponse(TimestampedSchema):
    """Farm member as returned by the API."""
    farm_id: UUID
    user_id: UUID | None
    phone: str | None
    status: str
    accepted_at: datetime | None
    # Denormalised from joined role
    role_name: str
    role_display_name: str
    # Denormalised from joined user (None for pending invites)
    full_name: str | None = None
    user_phone: str | None = None


# ── Farm Unit Schemas ─────────────────────────────────────────────────────────

class FarmUnitCreate(AGRIOSSchema):
    """Request body for creating a farm unit."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Unit name cannot be empty.")
        return cleaned


class FarmUnitUpdate(AGRIOSSchema):
    """Update an existing farm unit."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Unit name cannot be empty.")
        return cleaned


class FarmUnitResponse(TimestampedSchema):
    """Farm unit as returned by the API."""
    farm_id: UUID
    name: str
    description: str | None
    sort_order: int
    house_count: int = 0


# ── Production House Schemas ──────────────────────────────────────────────────

HouseTypeLiteral = Literal["broiler", "layer", "breeder", "pullet", "multi"]


class ProductionHouseCreate(AGRIOSSchema):
    """Request body for creating a production house."""
    name: str = Field(..., min_length=1, max_length=255)
    capacity: int = Field(..., gt=0, le=100_000, description="Bird capacity. Must be > 0.")
    house_type: HouseTypeLiteral = "broiler"
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("House name cannot be empty.")
        return cleaned


class ProductionHouseUpdate(AGRIOSSchema):
    """Update an existing production house."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0, le=100_000)
    house_type: HouseTypeLiteral | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("House name cannot be empty.")
        return cleaned


class ProductionHouseResponse(TimestampedSchema):
    """Production house as returned by the API."""
    farm_id: UUID
    unit_id: UUID
    name: str
    capacity: int
    house_type: str
    sort_order: int
    current_flock_id: UUID | None
    is_occupied: bool
