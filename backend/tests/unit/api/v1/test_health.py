"""
AGRIOS — Health Module Unit Tests
Schema validation only — no database required.

Tests:
  TestVaccinationRecordCreate  (11 tests)
  TestVaccinationRecordUpdate  (5 tests)
  TestDiseaseAlertCreate       (7 tests)
  TestDiseaseAlertUpdate       (4 tests)
"""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.health import (
    DiseaseAlertCreate,
    DiseaseAlertUpdate,
    VaccinationRecordCreate,
    VaccinationRecordUpdate,
)


# ── VaccinationRecordCreate ───────────────────────────────────────────────────

class TestVaccinationRecordCreate:
    """Covers VaccinationRecordCreate schema validation."""

    def test_valid_minimal(self):
        """Minimum required fields pass validation."""
        record = VaccinationRecordCreate(
            vaccine_name="Newcastle Disease (ND)",
            administered_date=date.today(),
        )
        assert record.vaccine_name == "Newcastle Disease (ND)"
        assert record.dose_number == 1  # default

    def test_valid_full(self):
        """All fields populated."""
        record = VaccinationRecordCreate(
            vaccine_name="Gumboro (IBD)",
            vaccine_brand="HIPRAVIAR B1+H120",
            dose_number=2,
            administered_date=date.today() - timedelta(days=1),
            route="drinking_water",
            flock_age_days=21,
            batch_number="LOT-2025-001",
            next_due_date=date.today() + timedelta(days=21),
            next_vaccine_name="ND Booster",
            notes="Administered in morning water supply.",
        )
        assert record.dose_number == 2
        assert record.next_vaccine_name == "ND Booster"

    def test_future_administered_date_rejected(self):
        """Administered date in the future must fail."""
        with pytest.raises(ValidationError) as exc_info:
            VaccinationRecordCreate(
                vaccine_name="Newcastle Disease (ND)",
                administered_date=date.today() + timedelta(days=1),
            )
        assert "future" in str(exc_info.value).lower()

    def test_today_is_valid_administered_date(self):
        """Today is a valid administered date."""
        record = VaccinationRecordCreate(
            vaccine_name="Newcastle Disease (ND)",
            administered_date=date.today(),
        )
        assert record.administered_date == date.today()

    def test_vaccine_name_min_length(self):
        """Vaccine name must be at least 2 characters."""
        with pytest.raises(ValidationError):
            VaccinationRecordCreate(
                vaccine_name="A",
                administered_date=date.today(),
            )

    def test_vaccine_name_max_length(self):
        """Vaccine name cannot exceed 200 characters."""
        with pytest.raises(ValidationError):
            VaccinationRecordCreate(
                vaccine_name="V" * 201,
                administered_date=date.today(),
            )

    def test_dose_number_min_one(self):
        """Dose number cannot be 0 or negative."""
        with pytest.raises(ValidationError):
            VaccinationRecordCreate(
                vaccine_name="Newcastle Disease (ND)",
                administered_date=date.today(),
                dose_number=0,
            )

    def test_dose_number_max_ten(self):
        """Dose number cannot exceed 10."""
        with pytest.raises(ValidationError):
            VaccinationRecordCreate(
                vaccine_name="Newcastle Disease (ND)",
                administered_date=date.today(),
                dose_number=11,
            )

    def test_next_due_date_must_be_after_administered(self):
        """next_due_date must be strictly after administered_date."""
        today = date.today()
        with pytest.raises(ValidationError) as exc_info:
            VaccinationRecordCreate(
                vaccine_name="Newcastle Disease (ND)",
                administered_date=today,
                next_due_date=today,  # Same day — invalid
            )
        assert "after" in str(exc_info.value).lower()

    def test_next_due_date_before_administered_rejected(self):
        """next_due_date before administered_date must fail."""
        today = date.today()
        with pytest.raises(ValidationError):
            VaccinationRecordCreate(
                vaccine_name="Newcastle Disease (ND)",
                administered_date=today,
                next_due_date=today - timedelta(days=1),
            )

    def test_next_due_date_future_is_valid(self):
        """next_due_date after administered_date is valid."""
        record = VaccinationRecordCreate(
            vaccine_name="Newcastle Disease (ND)",
            administered_date=date.today() - timedelta(days=5),
            next_due_date=date.today() + timedelta(days=14),
        )
        assert record.next_due_date is not None


# ── VaccinationRecordUpdate ───────────────────────────────────────────────────

class TestVaccinationRecordUpdate:
    """Covers VaccinationRecordUpdate correction schema."""

    def test_valid_with_one_field(self):
        """Providing one updatable field + correction_reason is valid."""
        update = VaccinationRecordUpdate(
            vaccine_name="Marek's Disease",
            correction_reason="Wrong vaccine name was recorded initially.",
        )
        assert update.vaccine_name == "Marek's Disease"

    def test_requires_correction_reason(self):
        """correction_reason is mandatory."""
        with pytest.raises(ValidationError):
            VaccinationRecordUpdate(
                vaccine_name="Marek's Disease",
            )

    def test_correction_reason_min_length(self):
        """correction_reason must be at least 5 characters."""
        with pytest.raises(ValidationError):
            VaccinationRecordUpdate(
                vaccine_name="Marek's Disease",
                correction_reason="Bad",  # < 5 chars
            )

    def test_no_updatable_fields_rejected(self):
        """At least one updatable field must be provided."""
        with pytest.raises(ValidationError) as exc_info:
            VaccinationRecordUpdate(
                correction_reason="Correcting because I misclicked.",
            )
        assert "at least one" in str(exc_info.value).lower()

    def test_update_notes_only_valid(self):
        """Updating only notes is valid."""
        update = VaccinationRecordUpdate(
            notes="Additional observation: birds showed slight lethargy post-vaccination.",
            correction_reason="Adding missing observation note.",
        )
        assert update.notes is not None


# ── DiseaseAlertCreate ────────────────────────────────────────────────────────

class TestDiseaseAlertCreate:
    """Covers DiseaseAlertCreate admin schema."""

    def test_valid_minimal(self):
        """Minimum required fields pass."""
        alert = DiseaseAlertCreate(
            disease_name="Newcastle Disease",
            title="ND Outbreak in Kiambu County",
            description="A confirmed outbreak of Newcastle Disease has been reported in Kiambu County.",
        )
        assert alert.severity == "warning"  # default
        assert alert.county is None  # defaults to None (not provided)

    def test_valid_full(self):
        """All optional fields populate correctly."""
        from datetime import datetime, timezone, timedelta
        alert = DiseaseAlertCreate(
            disease_name="Avian Influenza H5N1",
            title="Critical AI Alert — Nakuru County",
            description="Highly pathogenic avian influenza confirmed in commercial layer operations.",
            brief_guidance="Restrict bird movement. Report unusual mortality immediately to county vet.",
            severity="critical",
            county="Nakuru",
            species_key="poultry",
            expires_at=datetime.now(tz=timezone.utc) + timedelta(days=30),
        )
        assert alert.severity == "critical"
        assert alert.county == "Nakuru"

    def test_disease_name_min_length(self):
        """disease_name must be at least 2 chars."""
        with pytest.raises(ValidationError):
            DiseaseAlertCreate(
                disease_name="A",
                title="Alert Title Here",
                description="Alert description text that is long enough.",
            )

    def test_title_min_length(self):
        """title must be at least 5 chars."""
        with pytest.raises(ValidationError):
            DiseaseAlertCreate(
                disease_name="Newcastle Disease",
                title="Hi",
                description="Alert description text that is long enough.",
            )

    def test_description_min_length(self):
        """description must be at least 10 chars."""
        with pytest.raises(ValidationError):
            DiseaseAlertCreate(
                disease_name="Newcastle Disease",
                title="Alert Title Here",
                description="Short",
            )

    def test_invalid_severity(self):
        """Severity must be info, warning, or critical."""
        with pytest.raises(ValidationError):
            DiseaseAlertCreate(
                disease_name="Newcastle Disease",
                title="Alert Title Here",
                description="Alert description text that is long enough.",
                severity="high",  # type: ignore
            )

    def test_national_alert_no_county(self):
        """A national alert with county=None is valid."""
        alert = DiseaseAlertCreate(
            disease_name="Avian Influenza",
            title="National AI Alert",
            description="Avian influenza confirmed in multiple counties. Biosecurity precautions apply.",
            county=None,
        )
        assert alert.county is None


# ── DiseaseAlertUpdate ────────────────────────────────────────────────────────

class TestDiseaseAlertUpdate:
    """Covers DiseaseAlertUpdate schema validation."""

    def test_valid_single_field(self):
        """Providing one field is valid."""
        update = DiseaseAlertUpdate(severity="critical")
        assert update.severity == "critical"

    def test_empty_update_rejected(self):
        """No fields provided must fail."""
        with pytest.raises(ValidationError) as exc_info:
            DiseaseAlertUpdate()
        assert "at least one" in str(exc_info.value).lower()

    def test_invalid_severity(self):
        """Invalid severity must fail."""
        with pytest.raises(ValidationError):
            DiseaseAlertUpdate(severity="extreme")  # type: ignore

    def test_update_multiple_fields(self):
        """Multiple fields can be updated at once."""
        update = DiseaseAlertUpdate(
            title="Updated Alert Title",
            severity="critical",
            county="Nairobi",
        )
        assert update.title == "Updated Alert Title"
        assert update.county == "Nairobi"
