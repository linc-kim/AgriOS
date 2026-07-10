"""
Greena — Health Module Pydantic Schemas
Covers VaccinationRecord (M-017) and DiseaseAlert (M-018).

Input schemas (requests):
  VaccinationRecordCreate  — log a vaccination event
  VaccinationRecordUpdate  — edit a logged vaccination (correction)

Output schemas (responses):
  VaccinationRecordResponse  — single record
  VaccinationScheduleItem    — upcoming / overdue item (condensed)
  DiseaseAlertResponse       — single alert
  ActiveAlertSummary         — condensed card for farm dashboard banner

Admin-only schemas:
  DiseaseAlertCreate  — create a new alert (draft)
  DiseaseAlertPublish — publish a draft alert (admin action)
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import AGRIOSSchema

# ── Known vaccine protocol presets ────────────────────────────────────────────
# These are the common Kenyan poultry vaccine names. Free text is also allowed.
KNOWN_VACCINES = [
    "Newcastle Disease (ND)",
    "Infectious Bronchitis (IB)",
    "Gumboro (IBD)",
    "Marek's Disease",
    "Fowlpox",
    "Avian Encephalomyelitis (AE)",
    "Infectious Laryngotracheitis (ILT)",
    "Fowl Cholera",
    "Salmonella",
    "ND+IB Combined",
]

ADMINISTRATION_ROUTES = [
    "drinking_water",
    "spray",
    "eye_drop",
    "injection",
    "wing_stab",
    "oral",
]


# ── Input Schemas ─────────────────────────────────────────────────────────────

class VaccinationRecordCreate(AGRIOSSchema):
    """
    Log a vaccination event for a flock.

    Validation rules:
    - administered_date cannot be in the future
    - administered_date cannot be before the flock's placement_date (enforced
      in service layer when flock age is computed)
    - next_due_date, if provided, must be after administered_date
    - dose_number must be ≥ 1
    - vaccine_name max 200 chars
    - route, if provided, must be one of ADMINISTRATION_ROUTES or custom string
    """

    vaccine_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Vaccine name, e.g. 'Newcastle Disease (ND)'",
    )
    vaccine_brand: str | None = Field(
        default=None,
        max_length=200,
        description="Commercial brand, e.g. 'HIPRAVIAR B1+H120'",
    )
    dose_number: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Dose sequence number (1 = first dose, 2 = booster, etc.)",
    )
    administered_date: date = Field(
        ...,
        description="Date the vaccine was administered. Cannot be in the future.",
    )
    route: str | None = Field(
        default=None,
        max_length=50,
        description="Administration route: drinking_water, spray, eye_drop, injection, wing_stab, oral",
    )
    flock_age_days: int | None = Field(
        default=None,
        ge=0,
        description="Flock age in days at time of vaccination. Computed from placement date if omitted.",
    )
    batch_number: str | None = Field(
        default=None,
        max_length=100,
        description="Vaccine lot/batch number for traceability.",
    )
    next_due_date: date | None = Field(
        default=None,
        description="Date the next dose is due. Drives ARIA vaccination alerts.",
    )
    next_vaccine_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name of the next vaccine due (may differ from current vaccine).",
    )
    notes: str | None = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("administered_date")
    @classmethod
    def administered_date_not_future(cls, v: date) -> date:
        from datetime import date as dt_date
        if v > dt_date.today():
            raise ValueError("Administered date cannot be in the future.")
        return v

    @model_validator(mode="after")
    def next_due_after_administered(self) -> "VaccinationRecordCreate":
        if self.next_due_date is not None:
            if self.next_due_date <= self.administered_date:
                raise ValueError(
                    "next_due_date must be after administered_date."
                )
        return self


class VaccinationRecordUpdate(AGRIOSSchema):
    """
    Correct an existing vaccination record.
    At least one field must be provided.
    """

    vaccine_name: str | None = Field(default=None, min_length=2, max_length=200)
    vaccine_brand: str | None = Field(default=None, max_length=200)
    dose_number: int | None = Field(default=None, ge=1, le=10)
    administered_date: date | None = Field(default=None)
    route: str | None = Field(default=None, max_length=50)
    batch_number: str | None = Field(default=None, max_length=100)
    next_due_date: date | None = Field(default=None)
    next_vaccine_name: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    correction_reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for correction. Required for all updates.",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> "VaccinationRecordUpdate":
        updatable = [
            self.vaccine_name,
            self.vaccine_brand,
            self.dose_number,
            self.administered_date,
            self.route,
            self.batch_number,
            self.next_due_date,
            self.next_vaccine_name,
            self.notes,
        ]
        if all(v is None for v in updatable):
            raise ValueError("At least one field must be provided for update.")
        return self


# ── Admin Input Schemas ────────────────────────────────────────────────────────

class DiseaseAlertCreate(AGRIOSSchema):
    """
    Create a new disease alert (starts in draft status).
    super_admin only.
    """

    disease_name: str = Field(..., min_length=2, max_length=200)
    title: str = Field(..., min_length=5, max_length=300)
    description: str = Field(..., min_length=10)
    brief_guidance: str | None = Field(
        default=None,
        max_length=500,
        description="Short actionable text for SMS dispatch (~160 chars).",
    )
    severity: Literal["info", "warning", "critical"] = Field(default="warning")
    county: str | None = Field(
        default=None,
        max_length=100,
        description="Target county. NULL = national alert.",
    )
    species_key: str | None = Field(
        default=None,
        max_length=50,
        description="Target species. NULL = all species.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiry datetime. Alert remains active until explicitly deactivated if omitted.",
    )


class DiseaseAlertUpdate(AGRIOSSchema):
    """
    Update a draft disease alert before publishing.
    super_admin only.
    """

    disease_name: str | None = Field(default=None, min_length=2, max_length=200)
    title: str | None = Field(default=None, min_length=5, max_length=300)
    description: str | None = Field(default=None, min_length=10)
    brief_guidance: str | None = Field(default=None, max_length=500)
    severity: Literal["info", "warning", "critical"] | None = Field(default=None)
    county: str | None = Field(default=None, max_length=100)
    species_key: str | None = Field(default=None, max_length=50)
    expires_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "DiseaseAlertUpdate":
        updatable = [
            self.disease_name,
            self.title,
            self.description,
            self.brief_guidance,
            self.severity,
            self.county,
            self.species_key,
            self.expires_at,
        ]
        if all(v is None for v in updatable):
            raise ValueError("At least one field must be provided for update.")
        return self


# ── Output Schemas ────────────────────────────────────────────────────────────

class VaccinationRecordResponse(AGRIOSSchema):
    """Full vaccination record response."""

    id: UUID
    farm_id: UUID
    flock_id: UUID
    species_key: str
    vaccine_name: str
    vaccine_brand: str | None
    dose_number: int
    administered_date: date
    administered_by: UUID | None
    route: str | None
    flock_age_days: int | None
    batch_number: str | None
    next_due_date: date | None
    next_vaccine_name: str | None
    notes: str | None
    is_overdue: bool
    is_due_soon: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VaccinationScheduleItem(AGRIOSSchema):
    """
    Condensed representation of an upcoming or overdue vaccination.
    Used in H-01 Health Dashboard and H-02 Vaccination Schedule list.
    """

    id: UUID
    flock_id: UUID
    flock_name: str  # Joined from flock
    vaccine_name: str
    next_vaccine_name: str | None
    next_due_date: date
    dose_number: int
    is_overdue: bool
    days_until_due: int  # Negative = overdue, 0 = today, positive = future

    model_config = {"from_attributes": True}


class UpcomingVaccinationsResponse(AGRIOSSchema):
    """Response for the vaccination schedule / upcoming vaccinations endpoint."""

    overdue: list[VaccinationScheduleItem]
    due_today: list[VaccinationScheduleItem]
    due_this_week: list[VaccinationScheduleItem]
    upcoming: list[VaccinationScheduleItem]  # 8–30 days out

    model_config = {"from_attributes": True}


class DiseaseAlertResponse(AGRIOSSchema):
    """Full disease alert response."""

    id: UUID
    disease_name: str
    title: str
    description: str
    brief_guidance: str | None
    severity: str
    status: str
    county: str | None
    species_key: str | None
    published_at: datetime | None
    expires_at: datetime | None
    deactivated_at: datetime | None
    published_by: UUID | None
    sms_dispatched_at: datetime | None
    sms_recipient_count: int | None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_expired: bool

    model_config = {"from_attributes": True}


class ActiveAlertSummary(AGRIOSSchema):
    """
    Condensed alert card for the Home Dashboard banner (Zone 1).
    Only shown when there is at least one active alert for the farm's county.
    """

    id: UUID
    disease_name: str
    title: str
    brief_guidance: str | None
    severity: str
    county: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}
