"""
Greena — Swine Health Service (Module 20, Milestone 6)

Owns the independent clinical event records — disease cases (group-capable),
vaccinations, treatments (therapeutic/preventive), procedures, observations, lab
tests — plus mortality and historical isolation. Each is its own historical record
linked to a pig and/or group; nothing is stored as a flag on the pig. A pig's death
creates a mortality event AND transitions the pig to ``deceased`` (never destroyed,
stays traceable). All health analytics are delegated to the PURE
:mod:`swine_health_engine`, which never diagnoses (frozen §4.4).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.exceptions import ConflictException, NotFoundException
from app.models.auth import User
from app.models.farm import Farm
from app.models.swine import (
    SwineDiseaseCase,
    SwineIsolation,
    SwineLabTest,
    SwineMortality,
    SwineObservation,
    SwinePig,
    SwineProcedure,
    SwineTreatment,
    SwineVaccination,
)
from app.schemas.swine import (
    DiseaseCaseCreate,
    DiseaseCaseUpdate,
    IsolationEndInput,
    IsolationStartInput,
    LabTestCreate,
    LabTestUpdate,
    MortalityCreate,
    ObservationCreate,
    ProcedureCreate,
    TreatmentCreate,
    VaccinationCreate,
)
from app.services import audit_service
from app.services import swine_health_engine as eng
from app.services.swine_service import _append_event, _get_pig_or_404, record_movement


async def _validate_pig(db, farm_id, pig_id):
    if pig_id is not None:
        await _get_pig_or_404(db, farm_id, pig_id)


async def _pig_note(db, pig_id, event_type, summary, on: date, user, details):
    if pig_id is not None:
        await _append_event(
            db, pig_id, event_type, summary,
            occurred_at=datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details=details)


# ── Disease cases (group-capable) ──────────────────────────────────────────────

async def create_disease_case(db, farm: Farm, data: DiseaseCaseCreate, user: User) -> SwineDiseaseCase:
    await _validate_pig(db, farm.id, data.pig_id)
    case = SwineDiseaseCase(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(case)
    await db.flush()
    await _pig_note(db, data.pig_id, "health_recorded", f"Disease case: {data.disease_name}",
                    data.onset_date or date.today(), user, {"disease_case_id": str(case.id)})
    await audit_service.log_action(
        db, action="swine.health.disease_case.create", resource_type="swine_disease_case",
        resource_id=case.id, farm_id=farm.id, user_id=user.id, new_value={"disease": data.disease_name})
    await db.commit()
    await db.refresh(case)
    return case


async def update_disease_case(db, farm_id, case_id, data: DiseaseCaseUpdate, user: User) -> SwineDiseaseCase:
    r = await db.execute(select(SwineDiseaseCase).where(
        SwineDiseaseCase.id == case_id, SwineDiseaseCase.farm_id == farm_id,
        SwineDiseaseCase.deleted_at.is_(None)))
    case = r.scalar_one_or_none()
    if case is None:
        raise NotFoundException(f"Disease case {case_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.health.disease_case.update", resource_type="swine_disease_case",
        resource_id=case.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(case)
    return case


async def list_disease_cases(db, farm_id, *, status=None, pig_id=None, limit=100, offset=0):
    conds = [SwineDiseaseCase.farm_id == farm_id, SwineDiseaseCase.deleted_at.is_(None)]
    if status:
        conds.append(SwineDiseaseCase.status == status)
    if pig_id:
        conds.append(SwineDiseaseCase.pig_id == pig_id)
    r = await db.execute(select(SwineDiseaseCase).where(*conds)
                         .order_by(SwineDiseaseCase.created_at.desc()).limit(limit).offset(offset))
    return list(r.scalars().all())


# ── Simple clinical events (vaccination / treatment / procedure / observation / lab) ─

async def create_vaccination(db, farm: Farm, data: VaccinationCreate, user: User) -> SwineVaccination:
    await _validate_pig(db, farm.id, data.pig_id)
    row = SwineVaccination(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await _pig_note(db, data.pig_id, "vaccination_recorded", f"Vaccinated: {data.vaccine_name}",
                    data.administered_on, user, {"vaccination_id": str(row.id)})
    await audit_service.log_action(
        db, action="swine.health.vaccination.create", resource_type="swine_vaccination",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"vaccine": data.vaccine_name})
    await db.commit()
    await db.refresh(row)
    return row


async def create_treatment(db, farm: Farm, data: TreatmentCreate, user: User) -> SwineTreatment:
    await _validate_pig(db, farm.id, data.pig_id)
    row = SwineTreatment(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await _pig_note(db, data.pig_id, "treatment_recorded", f"{data.intent.capitalize()}: {data.product_name}",
                    data.started_on, user, {"treatment_id": str(row.id), "intent": data.intent})
    await audit_service.log_action(
        db, action="swine.health.treatment.create", resource_type="swine_treatment",
        resource_id=row.id, farm_id=farm.id, user_id=user.id,
        new_value={"product": data.product_name, "intent": data.intent})
    await db.commit()
    await db.refresh(row)
    return row


async def create_procedure(db, farm: Farm, data: ProcedureCreate, user: User) -> SwineProcedure:
    await _validate_pig(db, farm.id, data.pig_id)
    row = SwineProcedure(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await _pig_note(db, data.pig_id, "health_recorded", f"Procedure: {data.procedure_type}",
                    data.performed_on, user, {"procedure_id": str(row.id)})
    await audit_service.log_action(
        db, action="swine.health.procedure.create", resource_type="swine_procedure",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"procedure": data.procedure_type})
    await db.commit()
    await db.refresh(row)
    return row


async def create_observation(db, farm: Farm, data: ObservationCreate, user: User) -> SwineObservation:
    await _validate_pig(db, farm.id, data.pig_id)
    row = SwineObservation(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await _pig_note(db, data.pig_id, "health_recorded", f"Observation: {data.observation_type}",
                    data.observed_on, user, {"observation_id": str(row.id)})
    await audit_service.log_action(
        db, action="swine.health.observation.create", resource_type="swine_observation",
        resource_id=row.id, farm_id=farm.id, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return row


async def create_lab_test(db, farm: Farm, data: LabTestCreate, user: User) -> SwineLabTest:
    await _validate_pig(db, farm.id, data.pig_id)
    row = SwineLabTest(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.health.lab_test.create", resource_type="swine_lab_test",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"test": data.test_name})
    await db.commit()
    await db.refresh(row)
    return row


async def update_lab_test(db, farm_id, test_id, data: LabTestUpdate, user: User) -> SwineLabTest:
    r = await db.execute(select(SwineLabTest).where(
        SwineLabTest.id == test_id, SwineLabTest.farm_id == farm_id, SwineLabTest.deleted_at.is_(None)))
    row = r.scalar_one_or_none()
    if row is None:
        raise NotFoundException(f"Lab test {test_id} not found on this farm.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.flush()
    await audit_service.log_action(
        db, action="swine.health.lab_test.update", resource_type="swine_lab_test",
        resource_id=row.id, farm_id=farm_id, user_id=user.id)
    await db.commit()
    await db.refresh(row)
    return row


async def _list(db, model, farm_id, *, pig_id=None, extra=None, order=None, limit=100, offset=0):
    conds = [model.farm_id == farm_id, model.deleted_at.is_(None)]
    if pig_id:
        conds.append(model.pig_id == pig_id)
    if extra is not None:
        conds.append(extra)
    order = order if order is not None else model.created_at.desc()
    r = await db.execute(select(model).where(*conds).order_by(order).limit(limit).offset(offset))
    return list(r.scalars().all())


# ── Mortality (preserves cause history + transitions the pig) ───────────────────

async def record_mortality(db, farm: Farm, data: MortalityCreate, user: User) -> SwineMortality:
    pig = None
    if data.pig_id is not None:
        pig = await _get_pig_or_404(db, farm.id, data.pig_id)
        if pig.status == "deceased":
            raise ConflictException(f"{pig.internal_ref} is already recorded as deceased.")
    row = SwineMortality(id=uuid.uuid4(), farm_id=farm.id, **data.model_dump(), created_by=user.id)
    db.add(row)
    await db.flush()
    if pig is not None:
        pig.status = "deceased"  # the pig row remains — historically traceable
        await _append_event(
            db, pig.id, "died", f"Died: {data.confirmed_cause or data.suspected_cause or data.cause_category}",
            occurred_at=datetime.combine(data.died_on, datetime.min.time(), tzinfo=timezone.utc),
            operator_id=user.id, details={"mortality_id": str(row.id), "cause_category": data.cause_category})
    await audit_service.log_action(
        db, action="swine.health.mortality.record", resource_type="swine_mortality",
        resource_id=row.id, farm_id=farm.id, user_id=user.id,
        new_value={"pig": str(data.pig_id) if data.pig_id else None, "cause": data.cause_category})
    await db.commit()
    await db.refresh(row)
    return row


async def list_mortality(db, farm_id, *, pig_id=None, limit=100, offset=0):
    return await _list(db, SwineMortality, farm_id, pig_id=pig_id,
                       order=SwineMortality.died_on.desc(), limit=limit, offset=offset)


# ── Isolation (historical) ─────────────────────────────────────────────────────

async def start_isolation(db, farm: Farm, data: IsolationStartInput, user: User) -> SwineIsolation:
    pig = None
    if data.pig_id is not None:
        pig = await _get_pig_or_404(db, farm.id, data.pig_id)
    row = SwineIsolation(
        id=uuid.uuid4(), farm_id=farm.id, pig_id=data.pig_id, group_id=data.group_id, pen_id=data.pen_id,
        disease_case_id=data.disease_case_id, reason=data.reason, status="active",
        started_on=data.started_on, notes=data.notes, created_by=user.id,
    )
    db.add(row)
    await db.flush()
    # Move the pig to the isolation pen (recorded in movement history).
    if pig is not None and data.pen_id is not None and pig.pen_id != data.pen_id:
        before_pen = pig.pen_id
        pig.pen_id = data.pen_id
        await record_movement(db, farm.id, pig.id, movement_type="isolation",
                              from_pen_id=before_pen, to_pen_id=data.pen_id,
                              moved_on=data.started_on, reason=f"isolation: {data.reason}", user=user)
        await _append_event(db, pig.id, "moved", "Moved to isolation",
                            occurred_at=datetime.combine(data.started_on, datetime.min.time(), tzinfo=timezone.utc),
                            operator_id=user.id, details={"isolation_id": str(row.id)})
    await audit_service.log_action(
        db, action="swine.health.isolation.start", resource_type="swine_isolation",
        resource_id=row.id, farm_id=farm.id, user_id=user.id, new_value={"reason": data.reason})
    await db.commit()
    await db.refresh(row)
    return row


async def end_isolation(db, farm_id, isolation_id, data: IsolationEndInput, user: User) -> SwineIsolation:
    r = await db.execute(select(SwineIsolation).where(
        SwineIsolation.id == isolation_id, SwineIsolation.farm_id == farm_id,
        SwineIsolation.deleted_at.is_(None)))
    row = r.scalar_one_or_none()
    if row is None:
        raise NotFoundException(f"Isolation {isolation_id} not found on this farm.")
    if row.status != "active":
        raise ConflictException(f"Isolation is already {row.status}.")
    row.status = "cleared" if data.cleared else "ended"
    row.ended_on = data.ended_on or date.today()
    row.cleared_by = data.cleared_by
    row.clearance_notes = data.clearance_notes
    await db.flush()
    await audit_service.log_action(
        db, action="swine.health.isolation.end", resource_type="swine_isolation",
        resource_id=row.id, farm_id=farm_id, user_id=user.id, new_value={"status": row.status})
    await db.commit()
    await db.refresh(row)
    return row


async def list_isolations(db, farm_id, *, status=None, pig_id=None, limit=100, offset=0):
    extra = (SwineIsolation.status == status) if status else None
    return await _list(db, SwineIsolation, farm_id, pig_id=pig_id, extra=extra,
                       order=SwineIsolation.started_on.desc(), limit=limit, offset=offset)


# ── Generic list wrappers for the simple clinical types ────────────────────────

async def list_vaccinations(db, farm_id, *, pig_id=None, limit=100, offset=0):
    return await _list(db, SwineVaccination, farm_id, pig_id=pig_id,
                       order=SwineVaccination.administered_on.desc(), limit=limit, offset=offset)


async def list_treatments(db, farm_id, *, pig_id=None, intent=None, limit=100, offset=0):
    extra = (SwineTreatment.intent == intent) if intent else None
    return await _list(db, SwineTreatment, farm_id, pig_id=pig_id, extra=extra,
                       order=SwineTreatment.started_on.desc(), limit=limit, offset=offset)


async def list_procedures(db, farm_id, *, pig_id=None, limit=100, offset=0):
    return await _list(db, SwineProcedure, farm_id, pig_id=pig_id,
                       order=SwineProcedure.performed_on.desc(), limit=limit, offset=offset)


async def list_observations(db, farm_id, *, pig_id=None, limit=100, offset=0):
    return await _list(db, SwineObservation, farm_id, pig_id=pig_id,
                       order=SwineObservation.observed_on.desc(), limit=limit, offset=offset)


async def list_lab_tests(db, farm_id, *, pig_id=None, limit=100, offset=0):
    return await _list(db, SwineLabTest, farm_id, pig_id=pig_id, limit=limit, offset=offset)


# ── Health summary (deterministic; never a diagnosis) ──────────────────────────

async def health_summary(db, farm_id) -> dict:
    async def _count(model, *extra) -> int:
        conds = [model.farm_id == farm_id, model.deleted_at.is_(None), *extra]
        return (await db.execute(select(func.count(model.id)).where(*conds))).scalar_one() or 0

    population = await _count(SwinePig, SwinePig.status == "active")
    deaths = await _count(SwineMortality)
    treatments_rows = await db.execute(select(SwineTreatment.withdrawal_until).where(
        SwineTreatment.farm_id == farm_id, SwineTreatment.deleted_at.is_(None)))
    treatments = [{"withdrawal_until": t[0]} for t in treatments_rows]
    counts = {
        "open_disease_cases": await _count(SwineDiseaseCase, SwineDiseaseCase.status.in_(("suspected", "confirmed", "chronic"))),
        "confirmed_cases": await _count(SwineDiseaseCase, SwineDiseaseCase.status == "confirmed"),
        "total_disease_cases": await _count(SwineDiseaseCase),
        "vaccinations": await _count(SwineVaccination),
        "treatments": await _count(SwineTreatment),
        "procedures": await _count(SwineProcedure),
        "observations": await _count(SwineObservation),
        "lab_tests": await _count(SwineLabTest),
        "active_isolations": await _count(SwineIsolation, SwineIsolation.status == "active"),
        "deaths": deaths,
        "population": population + deaths,
    }
    return eng.health_summary(counts, treatments=treatments)
