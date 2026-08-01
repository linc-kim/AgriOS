"""
Greena — Rabbit Breeding Service (Module 17, Milestone 3)

Orchestrates the breeding cycle, litters, pedigree and genetics. The service owns
DB reads/writes and delegates every calculation to the PURE engines
(:mod:`rabbit_breeding_engine`) and the reused platform genetics engine
(:mod:`rabbit_genetics` → :mod:`pedigree_engine`) — no math lives here
(GMIS §1.3). Registry helpers (event append, ref generation, rabbit lookup) are
reused from :mod:`rabbit_service` rather than duplicated.

Breeding milestones (service, pregnancy check, kindling, weaning) also append to
the doe's ``rabbit_event`` timeline and write audit-log entries.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.auth import User
from app.models.farm import Farm
from app.models.rabbit import (
    Rabbit,
    RabbitBreed,
    RabbitBreeding,
    RabbitLitter,
)
from app.schemas.rabbit import (
    BreedingCreate,
    FosterInput,
    KindlingInput,
    PregnancyCheckInput,
    ServiceInput,
    WeaningInput,
)
from app.services import (
    audit_service,
    rabbit_breeding_engine as beng,
    rabbit_genetics as gen,
    rabbit_service,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_breeding_or_404(db: AsyncSession, farm_id: uuid.UUID, breeding_id: uuid.UUID) -> RabbitBreeding:
    result = await db.execute(
        select(RabbitBreeding).where(
            RabbitBreeding.id == breeding_id,
            RabbitBreeding.farm_id == farm_id,
            RabbitBreeding.deleted_at.is_(None),
        )
    )
    b = result.scalar_one_or_none()
    if b is None:
        raise NotFoundException(f"Breeding {breeding_id} not found on this farm.")
    return b


async def _get_litter_or_404(db: AsyncSession, farm_id: uuid.UUID, litter_id: uuid.UUID) -> RabbitLitter:
    result = await db.execute(
        select(RabbitLitter).where(
            RabbitLitter.id == litter_id,
            RabbitLitter.farm_id == farm_id,
            RabbitLitter.deleted_at.is_(None),
        )
    )
    li = result.scalar_one_or_none()
    if li is None:
        raise NotFoundException(f"Litter {litter_id} not found on this farm.")
    return li


async def _parent_map(db: AsyncSession, farm_id: uuid.UUID) -> dict:
    """Build the ``{rabbit_id: (sire_id, dam_id)}`` map for the whole farm — the
    input the reused pedigree engine needs (ledger CON-M3-1)."""
    rows = await db.execute(
        select(Rabbit.id, Rabbit.sire_id, Rabbit.dam_id).where(
            Rabbit.farm_id == farm_id, Rabbit.deleted_at.is_(None)
        )
    )
    return {row[0]: (row[1], row[2]) for row in rows}


async def _gestation_days(db: AsyncSession, doe: Rabbit) -> int | None:
    """Breed-driven gestation (ledger CON-M3-4); None → engine uses its default."""
    if doe.breed_id is None:
        return None
    result = await db.execute(select(RabbitBreed.profile).where(RabbitBreed.id == doe.breed_id))
    profile = result.scalar_one_or_none()
    if profile and isinstance(profile, dict):
        val = profile.get("gestation_days")
        if isinstance(val, int) and val > 0:
            return val
    return None


async def _doe_has_open_breeding(db: AsyncSession, doe_id: uuid.UUID, exclude_id: uuid.UUID | None = None) -> bool:
    conds = [
        RabbitBreeding.doe_id == doe_id,
        RabbitBreeding.status.in_(("planned", "serviced", "pregnant")),
        RabbitBreeding.deleted_at.is_(None),
    ]
    if exclude_id is not None:
        conds.append(RabbitBreeding.id != exclude_id)
    result = await db.execute(select(func.count(RabbitBreeding.id)).where(*conds))
    return (result.scalar_one() or 0) > 0


async def _generate_litter_code(db: AsyncSession, farm_id: uuid.UUID) -> str:
    result = await db.execute(select(func.count(RabbitLitter.id)).where(RabbitLitter.farm_id == farm_id))
    return f"LT-{(result.scalar_one() or 0) + 1:05d}"


def _dt(on: date | None):
    return datetime.combine(on, datetime.min.time(), tzinfo=timezone.utc) if on else None


# ── Breeding cycle ─────────────────────────────────────────────────────────────

async def create_breeding(db: AsyncSession, farm: Farm, data: BreedingCreate, user: User) -> RabbitBreeding:
    doe = await rabbit_service._get_rabbit_or_404(db, farm.id, data.doe_id)
    buck = await rabbit_service._get_rabbit_or_404(db, farm.id, data.buck_id)

    open_cycle = await _doe_has_open_breeding(db, doe.id)
    verdict = beng.validate_eligibility(
        {"sex": doe.sex, "status": doe.status},
        {"sex": buck.sex, "status": buck.status},
        open_cycle,
    )
    if not verdict["eligible"]:
        raise ValidationException("Breeding not eligible: " + "; ".join(verdict["reasons"]))

    if data.repeat_of_id is not None:
        await _get_breeding_or_404(db, farm.id, data.repeat_of_id)

    serviced = data.service_date is not None
    planned = None
    if serviced:
        planned = beng.expected_kindling_date(data.service_date, await _gestation_days(db, doe))

    breeding = RabbitBreeding(
        id=uuid.uuid4(), farm_id=farm.id, doe_id=doe.id, buck_id=buck.id,
        repeat_of_id=data.repeat_of_id, method=data.method,
        service_date=data.service_date, planned_kindling_date=planned,
        status="serviced" if serviced else "planned", notes=data.notes, created_by=user.id,
    )
    db.add(breeding)
    await db.flush()

    if serviced:
        doe.reproductive_status = "bred"
        await rabbit_service._append_event(
            db, doe.id, "bred", f"Serviced by {buck.internal_ref}",
            occurred_at=_dt(data.service_date), operator_id=user.id,
            details={"breeding_id": str(breeding.id), "buck_id": str(buck.id),
                     "planned_kindling_date": planned.isoformat() if planned else None},
        )
    await audit_service.log_action(
        db, action="rabbit.breeding.create", resource_type="rabbit_breeding",
        resource_id=breeding.id, farm_id=farm.id, user_id=user.id,
        new_value={"doe_id": str(doe.id), "buck_id": str(buck.id), "status": breeding.status},
    )
    await db.commit()
    await db.refresh(breeding)
    return breeding


async def record_service(db, farm_id, breeding_id, data: ServiceInput, user: User) -> RabbitBreeding:
    breeding = await _get_breeding_or_404(db, farm_id, breeding_id)
    if breeding.status not in ("planned",):
        raise ConflictException(f"Cannot record a service on a breeding that is {breeding.status}.")
    doe = await rabbit_service._get_rabbit_or_404(db, farm_id, breeding.doe_id)
    breeding.service_date = data.service_date
    if data.method:
        breeding.method = data.method
    breeding.planned_kindling_date = beng.expected_kindling_date(
        data.service_date, await _gestation_days(db, doe)
    )
    breeding.status = "serviced"
    doe.reproductive_status = "bred"
    await db.flush()
    await rabbit_service._append_event(
        db, doe.id, "bred", "Service recorded",
        occurred_at=_dt(data.service_date), operator_id=user.id,
        details={"breeding_id": str(breeding.id)},
    )
    await audit_service.log_action(
        db, action="rabbit.breeding.service", resource_type="rabbit_breeding",
        resource_id=breeding.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breeding)
    return breeding


async def record_pregnancy_check(db, farm_id, breeding_id, data: PregnancyCheckInput, user: User) -> RabbitBreeding:
    breeding = await _get_breeding_or_404(db, farm_id, breeding_id)
    if breeding.status not in ("serviced", "pregnant"):
        raise ConflictException(f"Cannot record a pregnancy check on a breeding that is {breeding.status}.")
    doe = await rabbit_service._get_rabbit_or_404(db, farm_id, breeding.doe_id)
    breeding.pregnancy_result = data.result
    breeding.pregnancy_checked_on = data.checked_on or date.today()
    if data.result == "pregnant":
        breeding.status = "pregnant"
        doe.reproductive_status = "pregnant"
    else:  # not_pregnant
        breeding.status = "not_pregnant"
        breeding.outcome = "failed"
        doe.reproductive_status = "open"
    await db.flush()
    await rabbit_service._append_event(
        db, doe.id, "note", f"Pregnancy check: {data.result}",
        occurred_at=_dt(breeding.pregnancy_checked_on), operator_id=user.id,
        details={"breeding_id": str(breeding.id), "result": data.result},
    )
    await audit_service.log_action(
        db, action="rabbit.breeding.pregnancy_check", resource_type="rabbit_breeding",
        resource_id=breeding.id, farm_id=farm_id, user_id=user.id, new_value={"result": data.result},
    )
    await db.commit()
    await db.refresh(breeding)
    return breeding


async def prepare_kindling(db, farm_id, breeding_id, on: date | None, user: User) -> RabbitBreeding:
    breeding = await _get_breeding_or_404(db, farm_id, breeding_id)
    if breeding.status not in ("serviced", "pregnant"):
        raise ConflictException(f"Cannot prepare kindling for a breeding that is {breeding.status}.")
    breeding.nest_box_prepared_on = on or date.today()
    await db.flush()
    await rabbit_service._append_event(
        db, breeding.doe_id, "note", "Nest box prepared",
        occurred_at=_dt(breeding.nest_box_prepared_on), operator_id=user.id,
        details={"breeding_id": str(breeding.id)},
    )
    await audit_service.log_action(
        db, action="rabbit.breeding.prepare_kindling", resource_type="rabbit_breeding",
        resource_id=breeding.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breeding)
    return breeding


async def record_kindling(db, farm: Farm, breeding_id, data: KindlingInput, user: User) -> RabbitLitter:
    breeding = await _get_breeding_or_404(db, farm.id, breeding_id)
    if breeding.status in ("kindled", "closed", "failed", "not_pregnant", "cancelled"):
        raise ConflictException(f"Cannot record kindling for a breeding that is {breeding.status}.")

    total = data.total_kits
    stillbirths = data.stillbirths or 0
    live = data.live_kits if data.live_kits is not None else max(total - stillbirths, 0)
    if live + stillbirths > total:
        raise ValidationException("live_kits + stillbirths cannot exceed total_kits.")

    litter = RabbitLitter(
        id=uuid.uuid4(), farm_id=farm.id, breeding_id=breeding.id,
        doe_id=breeding.doe_id, buck_id=breeding.buck_id,
        litter_code=await _generate_litter_code(db, farm.id),
        kindling_date=data.kindling_date, total_kits=total, live_kits=live,
        stillbirths=stillbirths, avg_birth_weight_g=data.avg_birth_weight_g,
        status="active", notes=data.notes, created_by=user.id,
    )
    db.add(litter)

    breeding.status = "kindled"
    breeding.actual_kindling_date = data.kindling_date
    breeding.outcome = "successful"
    if breeding.pregnancy_result == "unknown":
        breeding.pregnancy_result = "pregnant"

    doe = await rabbit_service._get_rabbit_or_404(db, farm.id, breeding.doe_id)
    doe.reproductive_status = "lactating"
    await db.flush()

    # Optional: create individual kit rabbit rows linked to the litter + parents
    # (ledger CON-M3-5). Sequential refs after the current farm rabbit count.
    created_kits = 0
    if data.create_kits and live > 0:
        base = (await db.execute(
            select(func.count(Rabbit.id)).where(Rabbit.farm_id == farm.id)
        )).scalar_one() or 0
        for i in range(live):
            db.add(Rabbit(
                id=uuid.uuid4(), farm_id=farm.id, breed_id=doe.breed_id,
                bloodline_id=doe.bloodline_id, litter_id=litter.id,
                internal_ref=f"RB-{base + 1 + i:05d}", sex="unknown",
                purpose="unknown", lifecycle_stage="kit", status="active",
                reproductive_status="unknown", fertility_status="unknown",
                acquisition_type="bred", date_of_birth=data.kindling_date,
                sire_id=breeding.buck_id, dam_id=breeding.doe_id, created_by=user.id,
            ))
        created_kits = live
        await db.flush()

    await rabbit_service._append_event(
        db, breeding.doe_id, "kindled", f"Kindled {total} kits ({live} live)",
        occurred_at=_dt(data.kindling_date), operator_id=user.id,
        details={"breeding_id": str(breeding.id), "litter_id": str(litter.id),
                 "total_kits": total, "live_kits": live, "kits_created": created_kits},
    )
    await audit_service.log_action(
        db, action="rabbit.kindling.record", resource_type="rabbit_litter",
        resource_id=litter.id, farm_id=farm.id, user_id=user.id,
        new_value={"total_kits": total, "live_kits": live, "kits_created": created_kits},
    )
    await db.commit()
    await db.refresh(litter)
    return litter


async def close_breeding(db, farm_id, breeding_id, user: User) -> RabbitBreeding:
    breeding = await _get_breeding_or_404(db, farm_id, breeding_id)
    if breeding.status == "closed":
        raise ConflictException("Breeding is already closed.")
    breeding.status = "closed"
    if breeding.outcome is None:
        breeding.outcome = "unknown"
    await db.flush()
    await audit_service.log_action(
        db, action="rabbit.breeding.close", resource_type="rabbit_breeding",
        resource_id=breeding.id, farm_id=farm_id, user_id=user.id,
    )
    await db.commit()
    await db.refresh(breeding)
    return breeding


async def list_breedings(db, farm_id, *, doe_id=None, buck_id=None, status=None, limit=50, offset=0):
    conds = [RabbitBreeding.farm_id == farm_id, RabbitBreeding.deleted_at.is_(None)]
    if doe_id:
        conds.append(RabbitBreeding.doe_id == doe_id)
    if buck_id:
        conds.append(RabbitBreeding.buck_id == buck_id)
    if status:
        conds.append(RabbitBreeding.status == status)
    total = (await db.execute(select(func.count(RabbitBreeding.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(RabbitBreeding).where(*conds)
        .order_by(RabbitBreeding.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_breeding(db, farm_id, breeding_id) -> RabbitBreeding:
    return await _get_breeding_or_404(db, farm_id, breeding_id)


# ── Litters ────────────────────────────────────────────────────────────────────

async def list_litters(db, farm_id, *, doe_id=None, status=None, limit=50, offset=0):
    conds = [RabbitLitter.farm_id == farm_id, RabbitLitter.deleted_at.is_(None)]
    if doe_id:
        conds.append(RabbitLitter.doe_id == doe_id)
    if status:
        conds.append(RabbitLitter.status == status)
    total = (await db.execute(select(func.count(RabbitLitter.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(RabbitLitter).where(*conds)
        .order_by(RabbitLitter.kindling_date.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def get_litter_detail(db, farm_id, litter_id) -> tuple[RabbitLitter, dict]:
    litter = await _get_litter_or_404(db, farm_id, litter_id)
    performance = beng.litter_performance({
        "total_kits": litter.total_kits, "live_kits": litter.live_kits,
        "stillbirths": litter.stillbirths, "weaned_kits": litter.weaned_kits,
        "mortality": litter.mortality, "avg_birth_weight_g": litter.avg_birth_weight_g,
        "status": litter.status,
    })
    return litter, performance


async def record_foster(db, farm_id, litter_id, data: FosterInput, user: User) -> RabbitLitter:
    litter = await _get_litter_or_404(db, farm_id, litter_id)
    if litter.status != "active":
        raise ConflictException("Fostering can only be recorded on an active litter.")
    litter.fostered_in += data.fostered_in or 0
    litter.fostered_out += data.fostered_out or 0
    await db.flush()
    await audit_service.log_action(
        db, action="rabbit.litter.foster", resource_type="rabbit_litter",
        resource_id=litter.id, farm_id=farm_id, user_id=user.id,
        new_value={"fostered_in": litter.fostered_in, "fostered_out": litter.fostered_out},
    )
    await db.commit()
    await db.refresh(litter)
    return litter


async def record_weaning(db, farm_id, litter_id, data: WeaningInput, user: User) -> RabbitLitter:
    litter = await _get_litter_or_404(db, farm_id, litter_id)
    if litter.status != "active":
        raise ConflictException(f"Litter is already {litter.status}.")
    if data.weaned_kits > litter.live_kits + litter.fostered_in:
        raise ValidationException("weaned_kits exceeds the live + fostered-in kits.")
    litter.weaned_kits = data.weaned_kits
    litter.weaning_date = data.weaning_date or date.today()
    litter.status = "weaned"

    # Advance surviving kit rabbits linked to this litter to the weaner stage.
    kit_rows = await db.execute(
        select(Rabbit).where(
            Rabbit.litter_id == litter.id, Rabbit.status == "active",
            Rabbit.lifecycle_stage == "kit", Rabbit.deleted_at.is_(None),
        )
    )
    for kit in kit_rows.scalars().all():
        kit.lifecycle_stage = "weaner"

    if litter.doe_id is not None:
        doe = await rabbit_service._get_rabbit_or_404(db, farm_id, litter.doe_id)
        doe.reproductive_status = "resting"
        await db.flush()
        await rabbit_service._append_event(
            db, doe.id, "weaned", f"Weaned {data.weaned_kits} kits",
            occurred_at=_dt(litter.weaning_date), operator_id=user.id,
            details={"litter_id": str(litter.id), "weaned_kits": data.weaned_kits},
        )
    else:
        await db.flush()
    await audit_service.log_action(
        db, action="rabbit.litter.weaning", resource_type="rabbit_litter",
        resource_id=litter.id, farm_id=farm_id, user_id=user.id, new_value={"weaned_kits": data.weaned_kits},
    )
    await db.commit()
    await db.refresh(litter)
    return litter


# ── Pedigree & genetics (reuse the platform pedigree engine) ───────────────────

async def get_pedigree(db, farm_id, rabbit_id, generations: int = 4) -> dict:
    await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
    parents = await _parent_map(db, farm_id)
    return gen.pedigree_tree(rabbit_id, parents, max_generations=generations)


async def check_compatibility(db, farm_id, buck_id, doe_id) -> dict:
    buck = await rabbit_service._get_rabbit_or_404(db, farm_id, buck_id)
    doe = await rabbit_service._get_rabbit_or_404(db, farm_id, doe_id)
    parents = await _parent_map(db, farm_id)
    return gen.assess_pairing(
        {"id": buck.id, "sex": buck.sex}, {"id": doe.id, "sex": doe.sex}, parents
    )


# ── Reproduction analytics (Spec Part 7 §4-5) ──────────────────────────────────

async def _breedings_as_dicts(db, farm_id, *, doe_id=None, buck_id=None) -> list[dict]:
    conds = [RabbitBreeding.farm_id == farm_id, RabbitBreeding.deleted_at.is_(None)]
    if doe_id:
        conds.append(RabbitBreeding.doe_id == doe_id)
    if buck_id:
        conds.append(RabbitBreeding.buck_id == buck_id)
    rows = await db.execute(
        select(RabbitBreeding.service_date, RabbitBreeding.pregnancy_result, RabbitBreeding.status).where(*conds)
    )
    return [{"service_date": r[0], "pregnancy_result": r[1], "status": r[2]} for r in rows]


async def _litters_as_dicts(db, farm_id, *, doe_id=None) -> list[dict]:
    conds = [RabbitLitter.farm_id == farm_id, RabbitLitter.deleted_at.is_(None)]
    if doe_id:
        conds.append(RabbitLitter.doe_id == doe_id)
    rows = await db.execute(
        select(
            RabbitLitter.kindling_date, RabbitLitter.total_kits, RabbitLitter.live_kits,
            RabbitLitter.weaned_kits, RabbitLitter.stillbirths, RabbitLitter.mortality, RabbitLitter.status,
        ).where(*conds)
    )
    return [
        {"kindling_date": r[0], "total_kits": r[1], "live_kits": r[2], "weaned_kits": r[3],
         "stillbirths": r[4], "mortality": r[5], "status": r[6]}
        for r in rows
    ]


async def get_breeding_performance(db, farm_id, rabbit_id) -> dict:
    r = await rabbit_service._get_rabbit_or_404(db, farm_id, rabbit_id)
    if r.sex == "buck":
        breedings = await _breedings_as_dicts(db, farm_id, buck_id=rabbit_id)
        return {"role": "buck", "internal_ref": r.internal_ref, "performance": beng.buck_fertility(breedings)}
    # Default to doe productivity (does + unknown-sex rabbits with litters).
    breedings = await _breedings_as_dicts(db, farm_id, doe_id=rabbit_id)
    litters = await _litters_as_dicts(db, farm_id, doe_id=rabbit_id)
    return {"role": "doe", "internal_ref": r.internal_ref,
            "performance": beng.doe_productivity(breedings, litters)}


async def reproduction_summary(db, farm_id) -> dict:
    breedings = await _breedings_as_dicts(db, farm_id)
    litters = await _litters_as_dicts(db, farm_id)
    return beng.reproduction_summary(breedings, litters)


async def genetic_overview(db, farm_id, limit: int = 100) -> dict:
    """Advisory genetic analytics (Spec Part 7 §5): a breeding-value ranking of
    does and an inbreeding watch-list. Deterministic and honesty-labelled; every
    figure is evidence-based (recorded litters / computed F) — never a directive."""
    # Breeding-value ranking of does with at least one recorded breeding or litter.
    doe_rows = await db.execute(
        select(Rabbit.id, Rabbit.internal_ref).where(
            Rabbit.farm_id == farm_id, Rabbit.sex == "doe",
            Rabbit.status == "active", Rabbit.deleted_at.is_(None),
        ).limit(limit)
    )
    does = []
    for rid, ref in doe_rows:
        litters = await _litters_as_dicts(db, farm_id, doe_id=rid)
        prod = beng.doe_productivity(await _breedings_as_dicts(db, farm_id, doe_id=rid), litters)
        does.append({
            "rabbit_id": str(rid), "internal_ref": ref,
            "kindlings": prod["kindlings"]["value"],
            "total_kits_weaned": prod["total_kits_weaned"]["value"],
            "kit_survival_pct": prod["kit_survival_pct"]["value"],
        })
    ranking = beng.breeding_value_ranking(does)

    # Inbreeding watch-list: active rabbits whose computed F is at least moderate.
    parents = await _parent_map(db, farm_id)
    watch = []
    for rid in list(parents)[:limit]:
        f = gen.pe.inbreeding_coefficient(rid, parents)
        if f >= gen._F_MODERATE:
            watch.append({"rabbit_id": str(rid), "inbreeding_coefficient": f})
    watch.sort(key=lambda w: w["inbreeding_coefficient"], reverse=True)

    return {
        "breeding_value_ranking": ranking,
        "inbreeding_watch": watch,
        "note": "Advisory only — evidence-based rankings and computed inbreeding "
                "coefficients. Breeding and culling decisions remain the farmer's.",
    }
