"""
Greena — Health Service
Business logic for:
  - Vaccination record CRUD with next_due_date computation
  - Upcoming/overdue vaccination schedule queries
  - Disease alert consumption (read-only for farmers)
  - Disease alert CRUD for admin (create, publish, deactivate)
  - Active alert banner query (farm county matching)

Permission enforcement is done at the endpoint layer via require_permission().
This service trusts that the caller has already been authorised.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.models.auth import User
from app.models.farm import Farm
from app.models.flock import Flock
from app.models.health import DiseaseAlert, HealthEvent, VaccinationRecord
from app.schemas.health import (
    ActiveAlertSummary,
    DiseaseAlertCreate,
    DiseaseAlertUpdate,
    UpcomingVaccinationsResponse,
    VaccinationRecordCreate,
    VaccinationRecordUpdate,
    VaccinationScheduleItem,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_vaccination_or_404(
    db: AsyncSession,
    farm_id: uuid.UUID,
    record_id: uuid.UUID,
) -> VaccinationRecord:
    result = await db.execute(
        select(VaccinationRecord).where(
            VaccinationRecord.id == record_id,
            VaccinationRecord.farm_id == farm_id,
            VaccinationRecord.deleted_at.is_(None),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundException("Vaccination record not found.")
    return record


async def _get_flock_or_404(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
) -> Flock:
    result = await db.execute(
        select(Flock).where(
            Flock.id == flock_id,
            Flock.farm_id == farm_id,
            Flock.deleted_at.is_(None),
        )
    )
    flock = result.scalar_one_or_none()
    if flock is None:
        raise NotFoundException("Flock not found.")
    return flock


async def _get_alert_or_404(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> DiseaseAlert:
    result = await db.execute(
        select(DiseaseAlert).where(
            DiseaseAlert.id == alert_id,
            DiseaseAlert.deleted_at.is_(None),
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise NotFoundException("Disease alert not found.")
    return alert


# ── Vaccination Record Operations ─────────────────────────────────────────────

async def log_vaccination(
    db: AsyncSession,
    farm: Farm,
    flock_id: uuid.UUID,
    data: VaccinationRecordCreate,
    current_user: User,
) -> VaccinationRecord:
    """
    Log a vaccination event for a flock.

    Validates:
    - Flock exists and belongs to this farm
    - Administered date is not before flock placement date
    - next_due_date, if set, is after administered_date (schema-level)
    - Computes flock_age_days if not provided by caller
    """
    flock = await _get_flock_or_404(db, farm.id, flock_id)

    # A vaccination can only be logged against an active flock — a closed/sold
    # flock is a historical record and must not accept new health events.
    if flock.status != "active":
        raise ValidationException(
            "Cannot log a vaccination for a flock that is not active."
        )

    # Validate administered_date is not before flock placement
    if data.administered_date < flock.placement_date:
        raise ValidationException(
            f"Administered date ({data.administered_date}) cannot be before "
            f"flock placement date ({flock.placement_date})."
        )

    # Compute flock age if not provided
    flock_age_days = data.flock_age_days
    if flock_age_days is None:
        flock_age_days = (data.administered_date - flock.placement_date).days

    now = datetime.now(tz=timezone.utc)
    record = VaccinationRecord(
        id=uuid.uuid4(),
        farm_id=farm.id,
        flock_id=flock_id,
        species_key="poultry",
        vaccine_name=data.vaccine_name,
        vaccine_brand=data.vaccine_brand,
        dose_number=data.dose_number,
        administered_date=data.administered_date,
        administered_by=current_user.id,
        route=data.route,
        flock_age_days=flock_age_days,
        batch_number=data.batch_number,
        next_due_date=data.next_due_date,
        next_vaccine_name=data.next_vaccine_name,
        notes=data.notes,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def list_vaccination_records(
    db: AsyncSession,
    farm_id: uuid.UUID,
    flock_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[VaccinationRecord]:
    """List all vaccination records for a flock, most recent first."""
    result = await db.execute(
        select(VaccinationRecord)
        .where(
            VaccinationRecord.farm_id == farm_id,
            VaccinationRecord.flock_id == flock_id,
            VaccinationRecord.deleted_at.is_(None),
        )
        .order_by(VaccinationRecord.administered_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_vaccination_record(
    db: AsyncSession,
    farm_id: uuid.UUID,
    record_id: uuid.UUID,
) -> VaccinationRecord:
    """Get a single vaccination record by ID."""
    return await _get_vaccination_or_404(db, farm_id, record_id)


async def update_vaccination_record(
    db: AsyncSession,
    farm_id: uuid.UUID,
    record_id: uuid.UUID,
    data: VaccinationRecordUpdate,
    current_user: User,
) -> VaccinationRecord:
    """
    Correct a vaccination record.
    Appends correction_reason to notes for audit trail.
    """
    record = await _get_vaccination_or_404(db, farm_id, record_id)

    if data.vaccine_name is not None:
        record.vaccine_name = data.vaccine_name
    if data.vaccine_brand is not None:
        record.vaccine_brand = data.vaccine_brand
    if data.dose_number is not None:
        record.dose_number = data.dose_number
    if data.administered_date is not None:
        record.administered_date = data.administered_date
    if data.route is not None:
        record.route = data.route
    if data.batch_number is not None:
        record.batch_number = data.batch_number
    if data.next_due_date is not None:
        record.next_due_date = data.next_due_date
    if data.next_vaccine_name is not None:
        record.next_vaccine_name = data.next_vaccine_name
    if data.notes is not None:
        record.notes = data.notes

    # Append correction note for audit trail
    correction_note = (
        f"\n[Corrected by {current_user.id} at "
        f"{datetime.now(tz=timezone.utc).isoformat()}: {data.correction_reason}]"
    )
    record.notes = (record.notes or "") + correction_note
    record.updated_at = datetime.now(tz=timezone.utc)

    await db.flush()
    await db.refresh(record)
    return record


async def delete_vaccination_record(
    db: AsyncSession,
    farm_id: uuid.UUID,
    record_id: uuid.UUID,
) -> None:
    """Soft-delete a vaccination record (DB-02 Frozen)."""
    record = await _get_vaccination_or_404(db, farm_id, record_id)
    record.deleted_at = datetime.now(tz=timezone.utc)
    record.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()


# ── Vaccination Schedule Query ─────────────────────────────────────────────────

async def get_upcoming_vaccinations(
    db: AsyncSession,
    farm_id: uuid.UUID,
) -> UpcomingVaccinationsResponse:
    """
    Query all upcoming and overdue vaccinations for the farm.

    Buckets:
      - overdue: next_due_date < today
      - due_today: next_due_date == today
      - due_this_week: next_due_date in [tomorrow, today+7]
      - upcoming: next_due_date in [today+8, today+30]

    Joins flock to get flock_name.
    Only includes records from active flocks.
    """
    today = date.today()
    week_out = today + timedelta(days=7)
    month_out = today + timedelta(days=30)

    # Query all records with a future or past next_due_date from active flocks
    result = await db.execute(
        select(VaccinationRecord, Flock.name.label("flock_name"))
        .join(Flock, VaccinationRecord.flock_id == Flock.id)
        .where(
            VaccinationRecord.farm_id == farm_id,
            VaccinationRecord.next_due_date.is_not(None),
            VaccinationRecord.next_due_date <= month_out,
            VaccinationRecord.deleted_at.is_(None),
            Flock.status == "active",
            Flock.deleted_at.is_(None),
        )
        .order_by(VaccinationRecord.next_due_date.asc())
    )
    rows = result.all()

    overdue: list[VaccinationScheduleItem] = []
    due_today: list[VaccinationScheduleItem] = []
    due_this_week: list[VaccinationScheduleItem] = []
    upcoming: list[VaccinationScheduleItem] = []

    for row in rows:
        record: VaccinationRecord = row[0]
        flock_name: str = row[1]
        due_date = record.next_due_date
        days_until = (due_date - today).days

        item = VaccinationScheduleItem(
            id=record.id,
            flock_id=record.flock_id,
            flock_name=flock_name,
            vaccine_name=record.next_vaccine_name or record.vaccine_name,
            next_vaccine_name=record.next_vaccine_name,
            next_due_date=due_date,
            dose_number=record.dose_number + 1 if record.next_vaccine_name else record.dose_number,
            is_overdue=days_until < 0,
            days_until_due=days_until,
        )

        if days_until < 0:
            overdue.append(item)
        elif days_until == 0:
            due_today.append(item)
        elif days_until <= 7:
            due_this_week.append(item)
        else:
            upcoming.append(item)

    return UpcomingVaccinationsResponse(
        overdue=overdue,
        due_today=due_today,
        due_this_week=due_this_week,
        upcoming=upcoming,
    )


# ── Disease Alert Operations (Farmer-facing) ──────────────────────────────────

async def get_active_alerts_for_farm(
    db: AsyncSession,
    farm: Farm,
) -> list[DiseaseAlert]:
    """
    Get all active disease alerts relevant to this farm.

    Matching logic:
    - Alert county is NULL (national) OR matches farm.county
    - Alert species_key is NULL (all species) OR matches 'poultry'
    - Alert status == 'active'
    - Alert not expired (expires_at is NULL or in the future)
    """
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(DiseaseAlert)
        .where(
            DiseaseAlert.status == "active",
            DiseaseAlert.deleted_at.is_(None),
            or_(
                DiseaseAlert.expires_at.is_(None),
                DiseaseAlert.expires_at > now,
            ),
            or_(
                DiseaseAlert.county.is_(None),
                DiseaseAlert.county == farm.county,
            ),
            or_(
                DiseaseAlert.species_key.is_(None),
                DiseaseAlert.species_key == "poultry",
            ),
        )
        .order_by(DiseaseAlert.published_at.desc())
    )
    return list(result.scalars().all())


async def list_disease_alerts(
    db: AsyncSession,
    farm: Farm,
    limit: int = 20,
    offset: int = 0,
) -> list[DiseaseAlert]:
    """
    List disease alerts relevant to this farm (active + recent deactivated).
    Used in H-05 Disease Alerts screen.
    """
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(DiseaseAlert)
        .where(
            DiseaseAlert.status.in_(["active", "deactivated"]),
            DiseaseAlert.deleted_at.is_(None),
            or_(
                DiseaseAlert.county.is_(None),
                DiseaseAlert.county == farm.county,
            ),
            or_(
                DiseaseAlert.species_key.is_(None),
                DiseaseAlert.species_key == "poultry",
            ),
        )
        .order_by(DiseaseAlert.published_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_disease_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> DiseaseAlert:
    """Get a single disease alert by ID (any status)."""
    return await _get_alert_or_404(db, alert_id)


# ── Disease Alert Admin Operations ────────────────────────────────────────────

async def admin_create_alert(
    db: AsyncSession,
    data: DiseaseAlertCreate,
    current_user: User,
) -> DiseaseAlert:
    """Create a new disease alert (draft). super_admin only."""
    now = datetime.now(tz=timezone.utc)
    alert = DiseaseAlert(
        id=uuid.uuid4(),
        disease_name=data.disease_name,
        title=data.title,
        description=data.description,
        brief_guidance=data.brief_guidance,
        severity=data.severity,
        status="draft",
        county=data.county,
        species_key=data.species_key,
        expires_at=data.expires_at,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(alert)
    await db.flush()
    await db.refresh(alert)
    return alert


async def admin_update_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
    data: DiseaseAlertUpdate,
) -> DiseaseAlert:
    """Update a draft disease alert. Published alerts cannot be edited. super_admin only."""
    alert = await _get_alert_or_404(db, alert_id)

    if alert.status != "draft":
        raise ConflictException(
            "Only draft alerts can be edited. Deactivate this alert and create a new one."
        )

    if data.disease_name is not None:
        alert.disease_name = data.disease_name
    if data.title is not None:
        alert.title = data.title
    if data.description is not None:
        alert.description = data.description
    if data.brief_guidance is not None:
        alert.brief_guidance = data.brief_guidance
    if data.severity is not None:
        alert.severity = data.severity
    if data.county is not None:
        alert.county = data.county
    if data.species_key is not None:
        alert.species_key = data.species_key
    if data.expires_at is not None:
        alert.expires_at = data.expires_at

    alert.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()
    await db.refresh(alert)
    return alert


async def admin_publish_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
    current_user: User,
) -> DiseaseAlert:
    """
    Publish a draft alert (draft → active). super_admin only.
    Sets published_at and published_by.
    """
    alert = await _get_alert_or_404(db, alert_id)

    if alert.status != "draft":
        raise ConflictException(
            f"Cannot publish alert with status '{alert.status}'. Only drafts can be published."
        )

    now = datetime.now(tz=timezone.utc)
    alert.status = "active"
    alert.published_at = now
    alert.published_by = current_user.id
    alert.updated_at = now
    await db.flush()
    await db.refresh(alert)
    return alert


async def admin_deactivate_alert(
    db: AsyncSession,
    alert_id: uuid.UUID,
) -> DiseaseAlert:
    """
    Deactivate an active alert (active → deactivated). super_admin only.
    Alert is preserved for historical record — never hard-deleted.
    """
    alert = await _get_alert_or_404(db, alert_id)

    if alert.status == "deactivated":
        raise ConflictException("Alert is already deactivated.")
    if alert.status == "draft":
        raise ConflictException("Cannot deactivate a draft alert. Delete it instead.")

    now = datetime.now(tz=timezone.utc)
    alert.status = "deactivated"
    alert.deactivated_at = now
    alert.updated_at = now
    await db.flush()
    await db.refresh(alert)
    return alert


async def admin_list_all_alerts(
    db: AsyncSession,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DiseaseAlert]:
    """
    List all disease alerts (all statuses). Admin-only view.
    """
    query = select(DiseaseAlert).where(DiseaseAlert.deleted_at.is_(None))

    if status_filter:
        query = query.where(DiseaseAlert.status == status_filter)

    query = query.order_by(DiseaseAlert.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


# ── Health Events (Phase 3) ───────────────────────────────────────────────────

# Map a health event type to the finance category its cost belongs to.
_HEALTH_COST_CATEGORY = {
    "medication": "medication",
    "treatment": "medication",
    "vet_visit": "vet_fees",
}


async def _get_health_event_or_404(db, farm_id, event_id) -> HealthEvent:
    result = await db.execute(
        select(HealthEvent).where(
            HealthEvent.id == event_id,
            HealthEvent.farm_id == farm_id,
            HealthEvent.deleted_at.is_(None),
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundException("Health event not found.")
    return event


async def create_health_event(db, farm, flock_id, data, current_user) -> HealthEvent:
    """Log a health event. If a cost is given it also books a finance expense."""
    flock = await _get_flock_or_404(db, farm.id, flock_id)

    event = HealthEvent(
        farm_id=farm.id,
        flock_id=flock.id,
        event_type=data.event_type,
        event_date=data.event_date,
        title=data.title,
        symptoms=data.symptoms,
        observations=data.observations,
        attachments=data.attachments,
        diagnosis=data.diagnosis,
        treatment=data.treatment,
        medication_name=data.medication_name,
        dosage=data.dosage,
        severity=data.severity,
        affected_count=data.affected_count,
        status=data.status,
        vet_name=data.vet_name,
        follow_up_date=data.follow_up_date,
        cost_kes=data.cost_kes,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(event)
    await db.flush()

    # Financial integration — medication / vet / treatment costs become expenses.
    if data.cost_kes and data.cost_kes > 0:
        from app.services import finance_service

        slug = _HEALTH_COST_CATEGORY.get(data.event_type, "medication")
        label = data.medication_name or data.title
        expense = await finance_service.record_category_expense(
            db, farm.id, flock.id, slug, data.cost_kes,
            f"Health: {label}", current_user, data.event_date,
        )
        if expense is not None:
            event.expense_id = expense.id

    await db.commit()

    if event.cost_kes and event.expense_id:
        from app.services import finance_service

        await finance_service.recompute_snapshot(db, farm.id, flock.id)

    await db.refresh(event)
    return event


async def list_health_events(db, farm_id, flock_id, status=None, limit=50, offset=0):
    query = select(HealthEvent).where(
        HealthEvent.farm_id == farm_id,
        HealthEvent.flock_id == flock_id,
        HealthEvent.deleted_at.is_(None),
    )
    if status:
        query = query.where(HealthEvent.status == status)
    query = query.order_by(HealthEvent.event_date.desc(), HealthEvent.created_at.desc())
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_health_event(db, farm_id, event_id) -> HealthEvent:
    return await _get_health_event_or_404(db, farm_id, event_id)


async def update_health_event(db, farm_id, event_id, data) -> HealthEvent:
    event = await _get_health_event_or_404(db, farm_id, event_id)
    fields = [
        "title", "symptoms", "observations", "attachments", "diagnosis",
        "treatment", "medication_name", "dosage", "severity", "affected_count",
        "status", "resolved_date", "vet_name", "follow_up_date", "notes",
    ]
    for f in fields:
        val = getattr(data, f, None)
        if val is not None:
            setattr(event, f, val)
    # Auto-stamp resolution date when marked resolved without an explicit date.
    if data.status == "resolved" and event.resolved_date is None:
        event.resolved_date = date.today()
    await db.commit()
    await db.refresh(event)
    return event


async def delete_health_event(db, farm_id, event_id) -> None:
    event = await _get_health_event_or_404(db, farm_id, event_id)
    event.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def get_farm_health_summary(db, farm):
    """Aggregate farm-wide health status for the health dashboard."""
    from app.schemas.health import FlockHealthSummary, HealthFollowUp

    farm_id = farm.id

    # Event status counts + affected/critical across active (non-resolved) events.
    counts_result = await db.execute(
        select(HealthEvent.status, func.count(HealthEvent.id)).where(
            HealthEvent.farm_id == farm_id,
            HealthEvent.deleted_at.is_(None),
        ).group_by(HealthEvent.status)
    )
    by_status = {s: int(c) for s, c in counts_result.all()}

    critical_result = await db.execute(
        select(func.count(HealthEvent.id)).where(
            HealthEvent.farm_id == farm_id,
            HealthEvent.deleted_at.is_(None),
            HealthEvent.status != "resolved",
            HealthEvent.severity == "critical",
        )
    )
    critical_open = int(critical_result.scalar_one())

    affected_result = await db.execute(
        select(func.coalesce(func.sum(HealthEvent.affected_count), 0)).where(
            HealthEvent.farm_id == farm_id,
            HealthEvent.deleted_at.is_(None),
            HealthEvent.status != "resolved",
        )
    )
    total_affected = int(affected_result.scalar_one())

    # Upcoming follow-ups (not resolved, due today or later).
    follow_result = await db.execute(
        select(HealthEvent).where(
            HealthEvent.farm_id == farm_id,
            HealthEvent.deleted_at.is_(None),
            HealthEvent.status != "resolved",
            HealthEvent.follow_up_date.isnot(None),
            HealthEvent.follow_up_date >= date.today(),
        ).order_by(HealthEvent.follow_up_date.asc()).limit(10)
    )
    follow_ups = [
        HealthFollowUp(
            id=e.id, flock_id=e.flock_id, title=e.title,
            follow_up_date=e.follow_up_date, severity=e.severity, status=e.status,
        )
        for e in follow_result.scalars().all()
    ]

    # Overdue vaccinations across the farm's flocks.
    overdue_result = await db.execute(
        select(func.count(VaccinationRecord.id)).where(
            VaccinationRecord.farm_id == farm_id,
            VaccinationRecord.deleted_at.is_(None),
            VaccinationRecord.next_due_date.isnot(None),
            VaccinationRecord.next_due_date < date.today(),
        )
    )
    overdue_vax = int(overdue_result.scalar_one())

    # Active disease alerts relevant to this farm.
    active_alerts = await get_active_alerts_for_farm(db, farm)

    return FlockHealthSummary(
        open_events=by_status.get("open", 0),
        monitoring_events=by_status.get("monitoring", 0),
        resolved_events=by_status.get("resolved", 0),
        critical_open=critical_open,
        total_affected_open=total_affected,
        upcoming_follow_ups=follow_ups,
        active_alert_count=len(active_alerts),
        overdue_vaccinations=overdue_vax,
    )
