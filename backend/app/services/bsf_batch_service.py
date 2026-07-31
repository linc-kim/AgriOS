"""
Greena — BSF Batch Service (Module 16, Part 2)

The operational backbone of the BSF module. Owns every write to the production
batch (the aggregate root): creation, edits, lifecycle advancement, movement,
splitting and merging (Spec Part 4 §4). Business rules live here; the
deterministic maths is delegated to the pure engines
(:mod:`bsf_lifecycle_engine`, :mod:`bsf_production_engine`) so the same inputs
always yield the same result.

Invariants (Spec Part 3 §8-10, §21):
  * farm-scoped — organisation isolation via ``farms.organization_id``;
  * lifecycle transitions append an immutable :class:`BsfLifecycleEvent`;
  * every state change appends an append-only :class:`BsfBatchEvent` and an
    audit-log entry;
  * lineage (split/merge) is preserved permanently — sources are soft-status
    changed, never destroyed.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.bsf import (
    BsfBatch,
    BsfBatchEvent,
    BsfColony,
    BsfLifecycleEvent,
    BsfProductionUnit,
    BsfSpecies,
)
from app.schemas.bsf import (
    BatchAdvanceInput,
    BatchCreate,
    BatchMergeInput,
    BatchMoveInput,
    BatchSplitInput,
    BatchTerminateInput,
    BatchUpdate,
)
from app.services import audit_service
from app.services import bsf_lifecycle_engine as life
from app.services import bsf_production_engine as prod

_TERMINAL_STATUSES = ("harvested", "completed", "split", "merged", "terminated", "archived")


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_batch_or_404(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> BsfBatch:
    result = await db.execute(
        select(BsfBatch).where(
            BsfBatch.id == batch_id,
            BsfBatch.farm_id == farm_id,
            BsfBatch.deleted_at.is_(None),
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundException(f"Batch {batch_id} not found on this farm.")
    return batch


async def _generate_batch_number(db: AsyncSession, farm_id: uuid.UUID) -> str:
    """Sequential per-farm batch number (BSF-00001). Uniqueness is enforced by
    the DB constraint; the count only seeds a readable starting point."""
    result = await db.execute(
        select(func.count(BsfBatch.id)).where(BsfBatch.farm_id == farm_id)
    )
    seq = (result.scalar_one() or 0) + 1
    return f"BSF-{seq:05d}"


async def _validate_refs(
    db: AsyncSession, farm_id: uuid.UUID, org_id: uuid.UUID | None,
    *, species_id: uuid.UUID | None = None, colony_id: uuid.UUID | None = None,
    unit_id: uuid.UUID | None = None,
) -> None:
    """Ensure referenced species/colony/unit belong to this farm/org (no cross-tenant leak)."""
    if species_id is not None:
        row = (await db.execute(select(BsfSpecies.id).where(
            BsfSpecies.id == species_id, BsfSpecies.deleted_at.is_(None),
            (BsfSpecies.organization_id == org_id) | (BsfSpecies.organization_id.is_(None)),
        ))).scalar_one_or_none()
        if row is None:
            raise NotFoundException(f"BSF species {species_id} not found.")
    if colony_id is not None:
        row = (await db.execute(select(BsfColony.id).where(
            BsfColony.id == colony_id, BsfColony.farm_id == farm_id, BsfColony.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if row is None:
            raise NotFoundException(f"Colony {colony_id} not found on this farm.")
    if unit_id is not None:
        row = (await db.execute(select(BsfProductionUnit.id).where(
            BsfProductionUnit.id == unit_id, BsfProductionUnit.farm_id == farm_id,
            BsfProductionUnit.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if row is None:
            raise NotFoundException(f"Production unit {unit_id} not found on this farm.")


def _append_event(
    db: AsyncSession, batch_id: uuid.UUID, event_type: str, summary: str,
    *, details: dict | None = None, related_batch_id: uuid.UUID | None = None,
    operator_id: uuid.UUID | None = None, occurred_at: datetime | None = None,
) -> BsfBatchEvent:
    event = BsfBatchEvent(
        id=uuid.uuid4(),
        batch_id=batch_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        summary=summary,
        details=details or {},
        related_batch_id=related_batch_id,
        operator_id=operator_id,
    )
    db.add(event)
    return event


async def _species_profile(db: AsyncSession, species_id: uuid.UUID | None) -> dict:
    if species_id is None:
        return {}
    profile = (await db.execute(
        select(BsfSpecies.profile).where(BsfSpecies.id == species_id)
    )).scalar_one_or_none()
    return profile or {}


# ── Batch CRUD ────────────────────────────────────────────────────────────────

async def create_batch(
    db: AsyncSession, farm_id: uuid.UUID, org_id: uuid.UUID | None,
    data: BatchCreate, user: User,
) -> BsfBatch:
    await _validate_refs(
        db, farm_id, org_id,
        species_id=data.species_id, colony_id=data.source_colony_id,
        unit_id=data.production_unit_id,
    )
    batch_number = data.batch_number or await _generate_batch_number(db, farm_id)
    dup = (await db.execute(select(func.count(BsfBatch.id)).where(
        BsfBatch.farm_id == farm_id, BsfBatch.batch_number == batch_number,
        BsfBatch.deleted_at.is_(None),
    ))).scalar_one()
    if dup > 0:
        raise ConflictException(f"Batch number {batch_number!r} already exists on this farm.")

    started = data.started_on or date.today()
    batch = BsfBatch(
        id=uuid.uuid4(),
        farm_id=farm_id,
        species_id=data.species_id,
        source_colony_id=data.source_colony_id,
        production_unit_id=data.production_unit_id,
        batch_number=batch_number,
        name=data.name,
        batch_type=data.batch_type,
        lifecycle_stage=data.lifecycle_stage,
        stage_started_on=started,
        status="active",
        started_on=started,
        population_estimate=data.population_estimate,
        biomass_estimate_g=data.biomass_estimate_g,
        tags=data.tags,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(batch)
    await db.flush()
    # Immutable birth record for the lifecycle history.
    db.add(BsfLifecycleEvent(
        id=uuid.uuid4(), batch_id=batch.id, previous_stage=None,
        new_stage=batch.lifecycle_stage, occurred_on=started,
        population_estimate=batch.population_estimate,
        biomass_estimate_g=batch.biomass_estimate_g, source="manual",
        observations="Batch created.", operator_id=user.id,
    ))
    _append_event(db, batch.id, "created", f"Batch {batch_number} created at stage {batch.lifecycle_stage}.",
                  details={"batch_number": batch_number}, operator_id=user.id)
    await audit_service.log_action(
        db, action="bsf.batch.create", resource_type="bsf_batch",
        resource_id=batch.id, farm_id=farm_id, user_id=user.id,
        new_value={"batch_number": batch_number, "stage": batch.lifecycle_stage},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


async def list_batches(
    db: AsyncSession, farm_id: uuid.UUID, *,
    status: str | None = None, lifecycle_stage: str | None = None,
    production_unit_id: uuid.UUID | None = None,
    page: int = 1, limit: int = 50,
) -> tuple[list[BsfBatch], int]:
    filters = [BsfBatch.farm_id == farm_id, BsfBatch.deleted_at.is_(None)]
    if status:
        filters.append(BsfBatch.status == status)
    if lifecycle_stage:
        filters.append(BsfBatch.lifecycle_stage == lifecycle_stage)
    if production_unit_id:
        filters.append(BsfBatch.production_unit_id == production_unit_id)

    total = (await db.execute(select(func.count(BsfBatch.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(BsfBatch).where(*filters)
        .order_by(BsfBatch.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    )).scalars().all()
    return list(rows), total


async def get_batch(db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID) -> BsfBatch:
    return await _get_batch_or_404(db, farm_id, batch_id)


async def update_batch(
    db: AsyncSession, farm_id: uuid.UUID, org_id: uuid.UUID | None,
    batch_id: uuid.UUID, data: BatchUpdate, user: User,
) -> BsfBatch:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(
            f"Batch {batch.batch_number} is {batch.status}; terminal batches cannot be edited."
        )
    fields = data.model_dump(exclude_unset=True)
    await _validate_refs(
        db, farm_id, org_id,
        species_id=fields.get("species_id"), unit_id=fields.get("production_unit_id"),
    )
    for key, value in fields.items():
        setattr(batch, key, value)
    await db.flush()
    await audit_service.log_action(
        db, action="bsf.batch.update", resource_type="bsf_batch",
        resource_id=batch.id, farm_id=farm_id, user_id=user.id,
        new_value={k: str(v) for k, v in fields.items()},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


# ── Lifecycle advancement (Spec Part 4 §5) ────────────────────────────────────

async def advance_stage(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
    data: BatchAdvanceInput, user: User,
) -> BsfBatch:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(
            f"Batch {batch.batch_number} is {batch.status}; its lifecycle is closed."
        )

    check = life.validate_transition(batch.lifecycle_stage, data.to_stage)
    if not check["valid"]:
        raise ValidationException(check["reason"])

    profile = await _species_profile(db, batch.species_id)
    if not data.allow_premature and life.is_premature_advance(
        profile, batch.lifecycle_stage, batch.stage_started_on, as_of=data.occurred_on or date.today()
    ):
        expected = life.expected_stage_days(profile, batch.lifecycle_stage)
        raise ValidationException(
            f"Advancing now is premature: stage {batch.lifecycle_stage!r} typically lasts "
            f"~{expected} days for this species. Re-submit with allow_premature=true to proceed."
        )

    previous_stage = batch.lifecycle_stage
    occurred_on = data.occurred_on or date.today()
    batch.lifecycle_stage = data.to_stage
    batch.stage_started_on = occurred_on
    if data.population_estimate is not None:
        batch.population_estimate = data.population_estimate
    if data.biomass_estimate_g is not None:
        batch.biomass_estimate_g = data.biomass_estimate_g

    db.add(BsfLifecycleEvent(
        id=uuid.uuid4(), batch_id=batch.id, previous_stage=previous_stage,
        new_stage=data.to_stage, occurred_on=occurred_on,
        population_estimate=data.population_estimate if data.population_estimate is not None else batch.population_estimate,
        biomass_estimate_g=data.biomass_estimate_g if data.biomass_estimate_g is not None else batch.biomass_estimate_g,
        survival_rate_pct=data.survival_rate_pct, source="manual",
        observations=data.observations, operator_id=user.id,
    ))
    _append_event(
        db, batch.id, "stage_changed",
        f"Advanced {previous_stage} → {data.to_stage}.",
        details={"from": previous_stage, "to": data.to_stage, "skipped": check["skipped"]},
        operator_id=user.id,
    )
    await audit_service.log_action(
        db, action="bsf.batch.advance", resource_type="bsf_batch",
        resource_id=batch.id, farm_id=farm_id, user_id=user.id,
        old_value={"stage": previous_stage}, new_value={"stage": data.to_stage},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


# ── Movement (Spec Part 4 §4) ─────────────────────────────────────────────────

async def move_batch(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
    data: BatchMoveInput, user: User,
) -> BsfBatch:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {batch.batch_number} is {batch.status}; it cannot be moved.")
    if data.production_unit_id is not None:
        await _validate_refs(db, farm_id, None, unit_id=data.production_unit_id)

    previous = batch.production_unit_id
    batch.production_unit_id = data.production_unit_id
    if data.production_unit_id is not None:
        default_summary = f"Moved to unit {data.production_unit_id}."
    else:
        default_summary = "Unassigned from production unit."
    occurred_at = (
        datetime.combine(data.occurred_on, datetime.min.time(), tzinfo=timezone.utc)
        if data.occurred_on else None
    )
    _append_event(
        db, batch.id, "moved", data.note or default_summary,
        details={"from_unit": str(previous) if previous else None,
                 "to_unit": str(data.production_unit_id) if data.production_unit_id else None},
        operator_id=user.id, occurred_at=occurred_at,
    )
    await audit_service.log_action(
        db, action="bsf.batch.move", resource_type="bsf_batch",
        resource_id=batch.id, farm_id=farm_id, user_id=user.id,
        old_value={"unit": str(previous) if previous else None},
        new_value={"unit": str(data.production_unit_id) if data.production_unit_id else None},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


# ── Split (Spec Part 3 §9, Part 4 §4) ─────────────────────────────────────────

async def split_batch(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
    data: BatchSplitInput, user: User,
) -> list[BsfBatch]:
    parent = await _get_batch_or_404(db, farm_id, batch_id)
    if parent.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {parent.batch_number} is {parent.status}; it cannot be split.")

    child_pops = [p.population_estimate for p in data.parts]
    validation = prod.validate_split(parent.population_estimate, child_pops)
    if not validation["valid"]:
        raise ValidationException(validation["reason"])
    for part in data.parts:
        if part.production_unit_id is not None:
            await _validate_refs(db, farm_id, None, unit_id=part.production_unit_id)

    occurred_on = data.occurred_on or date.today()
    children: list[BsfBatch] = []
    for idx, part in enumerate(data.parts, start=1):
        child_number = f"{parent.batch_number}-{chr(ord('A') + idx - 1)}"
        bio = prod.split_child_biomass(parent.biomass_estimate_g, parent.population_estimate, part.population_estimate)
        child = BsfBatch(
            id=uuid.uuid4(),
            farm_id=farm_id,
            species_id=parent.species_id,
            source_colony_id=parent.source_colony_id,
            parent_batch_id=parent.id,
            production_unit_id=part.production_unit_id or parent.production_unit_id,
            batch_number=child_number,
            name=part.name or f"{parent.batch_number} split {idx}",
            batch_type=parent.batch_type,
            lifecycle_stage=parent.lifecycle_stage,
            stage_started_on=parent.stage_started_on,
            status="active",
            started_on=occurred_on,
            population_estimate=part.population_estimate,
            biomass_estimate_g=bio["value"],
            tags=list(parent.tags or []),
            created_by=user.id,
        )
        db.add(child)
        await db.flush()
        db.add(BsfLifecycleEvent(
            id=uuid.uuid4(), batch_id=child.id, previous_stage=None,
            new_stage=child.lifecycle_stage, occurred_on=occurred_on,
            population_estimate=child.population_estimate,
            biomass_estimate_g=child.biomass_estimate_g, source="manual",
            observations=f"Created by split from {parent.batch_number}.", operator_id=user.id,
        ))
        _append_event(
            db, child.id, "split", f"Split from parent {parent.batch_number}.",
            details={"parent": parent.batch_number, "reason": data.reason}, operator_id=user.id,
        )
        children.append(child)

    parent.status = "split"
    parent.completed_on = occurred_on
    _append_event(
        db, parent.id, "split",
        f"Split into {len(children)} batches: {', '.join(c.batch_number for c in children)}.",
        details={"children": [c.batch_number for c in children],
                 "remainder": validation["remainder"], "reason": data.reason},
        operator_id=user.id,
    )
    await audit_service.log_action(
        db, action="bsf.batch.split", resource_type="bsf_batch",
        resource_id=parent.id, farm_id=farm_id, user_id=user.id,
        new_value={"children": [c.batch_number for c in children]},
    )
    await db.commit()
    for child in children:
        await db.refresh(child)
    return children


# ── Merge (Spec Part 3 §10, Part 4 §4) ────────────────────────────────────────

async def merge_batches(
    db: AsyncSession, farm_id: uuid.UUID, data: BatchMergeInput, user: User,
) -> BsfBatch:
    if len(set(data.source_batch_ids)) < 2:
        raise ValidationException("A merge requires at least two distinct source batches.")
    sources: list[BsfBatch] = []
    for sid in data.source_batch_ids:
        src = await _get_batch_or_404(db, farm_id, sid)
        if src.status in _TERMINAL_STATUSES:
            raise ConflictException(f"Batch {src.batch_number} is {src.status}; it cannot be merged.")
        sources.append(src)

    stages = {s.lifecycle_stage for s in sources}
    if len(stages) > 1:
        raise ValidationException(
            f"Cannot merge batches at different lifecycle stages: {sorted(stages)}. "
            "Align stages before merging."
        )
    if data.production_unit_id is not None:
        await _validate_refs(db, farm_id, None, unit_id=data.production_unit_id)

    totals = prod.merge_totals([s.population_estimate for s in sources],
                               [s.biomass_estimate_g for s in sources])
    occurred_on = data.occurred_on or date.today()
    merged_number = await _generate_batch_number(db, farm_id)
    merged = BsfBatch(
        id=uuid.uuid4(),
        farm_id=farm_id,
        species_id=sources[0].species_id,
        source_colony_id=sources[0].source_colony_id,
        production_unit_id=data.production_unit_id or sources[0].production_unit_id,
        batch_number=merged_number,
        name=data.name or f"Merge of {', '.join(s.batch_number for s in sources)}",
        batch_type=sources[0].batch_type,
        lifecycle_stage=sources[0].lifecycle_stage,
        stage_started_on=occurred_on,
        status="active",
        started_on=occurred_on,
        population_estimate=totals["total_population"]["value"],
        biomass_estimate_g=totals["total_biomass_g"]["value"],
        created_by=user.id,
    )
    db.add(merged)
    await db.flush()
    db.add(BsfLifecycleEvent(
        id=uuid.uuid4(), batch_id=merged.id, previous_stage=None,
        new_stage=merged.lifecycle_stage, occurred_on=occurred_on,
        population_estimate=merged.population_estimate,
        biomass_estimate_g=merged.biomass_estimate_g, source="manual",
        observations=f"Created by merging {len(sources)} batches.", operator_id=user.id,
    ))
    _append_event(
        db, merged.id, "merged", f"Merged from {', '.join(s.batch_number for s in sources)}.",
        details={"sources": [s.batch_number for s in sources], "reason": data.reason},
        operator_id=user.id,
    )
    for src in sources:
        src.status = "merged"
        src.completed_on = occurred_on
        _append_event(
            db, src.id, "merged", f"Merged into {merged_number}.",
            details={"merged_into": merged_number}, related_batch_id=merged.id, operator_id=user.id,
        )
    await audit_service.log_action(
        db, action="bsf.batch.merge", resource_type="bsf_batch",
        resource_id=merged.id, farm_id=farm_id, user_id=user.id,
        new_value={"merged": merged_number, "sources": [s.batch_number for s in sources]},
    )
    await db.commit()
    await db.refresh(merged)
    return merged


# ── Terminate (Spec Part 4 §4) ────────────────────────────────────────────────

async def terminate_batch(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
    data: BatchTerminateInput, user: User,
) -> BsfBatch:
    batch = await _get_batch_or_404(db, farm_id, batch_id)
    if batch.status in _TERMINAL_STATUSES:
        raise ConflictException(f"Batch {batch.batch_number} is already {batch.status}.")
    batch.status = "terminated"
    batch.completed_on = data.occurred_on or date.today()
    _append_event(
        db, batch.id, "terminated", data.reason or "Batch terminated.",
        details={"reason": data.reason}, operator_id=user.id,
    )
    await audit_service.log_action(
        db, action="bsf.batch.terminate", resource_type="bsf_batch",
        resource_id=batch.id, farm_id=farm_id, user_id=user.id,
        new_value={"status": "terminated", "reason": data.reason},
    )
    await db.commit()
    await db.refresh(batch)
    return batch


# ── History & metrics ─────────────────────────────────────────────────────────

async def list_lifecycle_events(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
) -> list[BsfLifecycleEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfLifecycleEvent)
        .where(BsfLifecycleEvent.batch_id == batch_id, BsfLifecycleEvent.deleted_at.is_(None))
        .order_by(BsfLifecycleEvent.occurred_on, BsfLifecycleEvent.created_at)
    )).scalars().all()
    return list(rows)


async def list_batch_events(
    db: AsyncSession, farm_id: uuid.UUID, batch_id: uuid.UUID,
) -> list[BsfBatchEvent]:
    await _get_batch_or_404(db, farm_id, batch_id)
    rows = (await db.execute(
        select(BsfBatchEvent)
        .where(BsfBatchEvent.batch_id == batch_id, BsfBatchEvent.deleted_at.is_(None))
        .order_by(BsfBatchEvent.occurred_at.desc())
    )).scalars().all()
    return list(rows)


async def compute_metrics(db: AsyncSession, batch: BsfBatch) -> tuple[dict, dict]:
    """Deterministic production metrics + lifecycle pacing for a batch.

    Composes the pure engines; recomputes nothing that a caller already has.
    Everything is honesty-labelled and never stored (Spec Part 3 §20).
    """
    profile = await _species_profile(db, batch.species_id)
    today = date.today()

    # Days in production and current stage (recorded intervals).
    days_in_prod = (today - batch.started_on).days if batch.started_on else None

    # First recorded lifecycle snapshot (for initial population → survival).
    first = (await db.execute(
        select(BsfLifecycleEvent)
        .where(BsfLifecycleEvent.batch_id == batch.id, BsfLifecycleEvent.deleted_at.is_(None))
        .order_by(BsfLifecycleEvent.occurred_on, BsfLifecycleEvent.created_at)
        .limit(1)
    )).scalar_one_or_none()
    initial_pop = first.population_estimate if first else None

    capacity = None
    if batch.production_unit_id is not None:
        capacity = (await db.execute(
            select(BsfProductionUnit.capacity_grams).where(BsfProductionUnit.id == batch.production_unit_id)
        )).scalar_one_or_none()

    metrics = {
        "average_weight_mg": prod.average_weight_mg(batch.population_estimate, batch.biomass_estimate_g),
        "survival_rate_pct": prod.survival_rate_pct(initial_pop, batch.population_estimate),
        "capacity_utilisation_pct": prod.capacity_utilisation_pct(batch.biomass_estimate_g, capacity),
        "production_velocity_g_per_day": prod.production_velocity_g_per_day(batch.biomass_estimate_g, days_in_prod),
        "days_in_production": {
            "label": "calculated" if days_in_prod is not None else "unknown",
            "value": days_in_prod, "detail": "today − started_on.",
        },
    }
    pacing = life.stage_pacing(profile, batch.lifecycle_stage, batch.stage_started_on, as_of=today)
    return metrics, pacing
