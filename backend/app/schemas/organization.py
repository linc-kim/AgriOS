"""Greena — Organization schemas."""

from pydantic import field_validator

from app.schemas.base import AGRIOSSchema, TimestampedSchema


class OrganizationCreateIn(AGRIOSSchema):
    """Request body for POST /organizations (onboarding step 1)."""

    name: str
    country: str | None = None
    timezone: str | None = None
    currency: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Organization name must be at least 2 characters")
        if len(v) > 120:
            raise ValueError("Organization name is too long")
        return v

    @field_validator("country")
    @classmethod
    def upper_country(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None


class OrganizationOut(TimestampedSchema):
    """Public organization view, with the requesting user's role."""

    name: str
    slug: str
    country: str | None = None
    timezone: str
    currency: str
    role: str | None = None  # requesting user's role in this org
