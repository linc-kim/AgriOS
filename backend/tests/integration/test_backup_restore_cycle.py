"""
Gate 6 — real backup → data-loss → restore → verify cycle (not code inspection).

``backup_service`` commits internally (a restore even takes a safety backup first),
which the savepoint-rollback integration harness cannot undo. So the applied-restore
test runs against a **throwaway farm on a committing session** and cleans up after
itself; the read-only failure-scenario tests use the normal rolled-back harness.

Exercises real rows: create backup → verify checksum → destroy data → dry-run →
applied restore → assert data integrity + app operability. Prints timings/sizes for
the Gate 6 report. Failure scenarios: missing backup, corrupted (tampered) backup.
"""

import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, select

from app.core.security import create_access_token, hash_password
from app.exceptions import NotFoundException
from app.models.auth import Role, User, UserRole
from app.models.farm import Farm, FarmMember, FarmUnit, ProductionHouse, SubscriptionPlan
from app.models.flock import DailyLog, Flock
from app.models.organization import Organization
from app.models.production import Backup, RestoreRun
from app.services import backup_service
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_throwaway_farm(s):
    """A self-contained farm (org/user/unit/house/flock + 3 logs), committed."""
    roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
    plan = (await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))).scalar_one()
    tag = uuid.uuid4().hex[:8]
    owner = User(email=f"bk-{tag}@greena-test.co", full_name="Backup Owner",
                 password_hash=hash_password("LoadTest-12345"), is_active=True, email_verified=True)
    s.add(owner)
    await s.flush()
    s.add(UserRole(user_id=owner.id, role_id=roles["farm_owner"].id, farm_id=None))
    org = Organization(name="Backup Org", slug=f"bk-{tag}", owner_id=owner.id)
    s.add(org)
    await s.flush()
    farm = Farm(name="Backup Farm", county="Nairobi", location="x", owner_id=owner.id,
                plan_id=plan.id, is_active=True, timezone="Africa/Nairobi", organization_id=org.id)
    s.add(farm)
    await s.flush()
    s.add(FarmMember(farm_id=farm.id, user_id=owner.id, role_id=roles["farm_owner"].id,
                     status="active", invited_by=owner.id))
    unit = FarmUnit(farm_id=farm.id, name="U", sort_order=0)
    s.add(unit)
    await s.flush()
    house = ProductionHouse(farm_id=farm.id, unit_id=unit.id, name="H", capacity=1000,
                            house_type="broiler", sort_order=0)
    s.add(house)
    await s.flush()
    flock = Flock(farm_id=farm.id, house_id=house.id, species_key="poultry", name="Backup Flock",
                  initial_count=500, placement_date=date.today() - timedelta(days=30), status="active")
    s.add(flock)
    await s.flush()
    today = date.today()
    for d in range(3, 0, -1):
        s.add(DailyLog(farm_id=farm.id, flock_id=flock.id, log_date=today - timedelta(days=d),
                       morning_count=500, mortality_count=1,
                       feed_consumed_kg=Decimal("25.000"), water_litres=Decimal("50.000")))
    await s.commit()
    return owner, org, farm, flock, unit, house


async def _cleanup(s, owner_id, org_id, farm_id, unit_id):
    """Best-effort teardown of everything the throwaway farm touched (by id)."""
    try:
        for tbl in (RestoreRun, Backup, DailyLog):
            await s.execute(delete(tbl).where(tbl.farm_id == farm_id))
        await s.execute(delete(Flock).where(Flock.farm_id == farm_id))
        await s.execute(delete(ProductionHouse).where(ProductionHouse.farm_id == farm_id))
        await s.execute(delete(FarmUnit).where(FarmUnit.id == unit_id))
        await s.execute(delete(FarmMember).where(FarmMember.farm_id == farm_id))
        await s.execute(delete(Farm).where(Farm.id == farm_id))
        await s.execute(delete(Organization).where(Organization.id == org_id))
        await s.execute(delete(UserRole).where(UserRole.user_id == owner_id))
        await s.execute(delete(User).where(User.id == owner_id))
        await s.commit()
    except Exception:
        await s.rollback()


async def test_full_backup_restore_cycle(async_client):
    async with TestSessionLocal() as s:
        owner, org, farm, flock, unit, house = await _make_throwaway_farm(s)
        # Capture IDs as plain values now — commits/expire below expire the ORM
        # instances, and reading `.id` off an expired instance is a lazy load that
        # raises MissingGreenlet on an async session.
        fid, flock_id, owner_id, org_id, unit_id = farm.id, flock.id, owner.id, org.id, unit.id
        try:
            # 1) CREATE
            backup = await backup_service.create_backup(s, farm, label="gate6-verify")
            assert backup.status == "success"
            counts = backup.record_counts
            print(f"\nBACKUP: size={backup.size_bytes} bytes, duration={backup.duration_ms} ms, counts={counts}")
            assert counts.get("flocks", 0) >= 1 and counts.get("daily_logs", 0) >= 3

            # 2) VERIFY (checksum)
            v = await backup_service.verify_backup(s, fid, backup.id)
            assert v["valid"] is True, v

            # 3) DATA LOSS: soft-delete flock, hard-delete logs
            (await s.get(Flock, flock_id)).deleted_at = datetime.now(timezone.utc)
            await s.execute(delete(DailyLog).where(DailyLog.farm_id == fid))
            await s.commit()
            assert (await s.get(Flock, flock_id)).deleted_at is not None

            # 4) DRY-RUN writes nothing
            dry = await backup_service.restore_backup(s, farm, backup.id, dry_run=True)
            print(f"DRY-RUN summary: {dry.summary}")
            assert (await s.get(Flock, flock_id)).deleted_at is not None

            # 5) APPLIED restore (RTO)
            t0 = time.perf_counter()
            applied = await backup_service.restore_backup(s, farm, backup.id, dry_run=False, overwrite=True)
            print(f"RESTORE (RTO): service={applied.duration_ms} ms, wall={int((time.perf_counter()-t0)*1000)} ms, "
                  f"safety_backup={applied.safety_backup_id}, checksum_verified={applied.checksum_verified}")
            assert applied.status == "success"

            # 6) DATA INTEGRITY
            s.expire_all()
            revived = await s.get(Flock, flock_id)
            assert revived is not None and revived.deleted_at is None
            n_logs = len((await s.execute(select(DailyLog).where(
                DailyLog.farm_id == fid, DailyLog.deleted_at.is_(None)))).scalars().all())
            assert n_logs >= 3, f"logs not restored: {n_logs}"

            # 7) APP OPERABILITY after restore (committed data, real HTTP via ASGI)
            headers = {"Authorization": f"Bearer {create_access_token(str(owner_id))}"}
            r = await async_client.get(f"/api/v1/farms/{fid}/flocks", headers=headers)
            assert r.status_code == 200 and len(r.json()["data"]) >= 1
        finally:
            await _cleanup(s, owner_id, org_id, fid, unit_id)


async def test_restore_missing_backup_raises_not_found(workspace, integration_session):
    farm = await integration_session.get(Farm, workspace.farm.id)
    with pytest.raises(NotFoundException):
        await backup_service.restore_backup(integration_session, farm, uuid.uuid4(), dry_run=True)


async def test_corrupted_backup_is_verified_invalid_and_restore_refuses(workspace, integration_session):
    farm = await integration_session.get(Farm, workspace.farm.id)
    backup = await backup_service.create_backup(integration_session, farm, label="corrupt-test")
    tampered = dict(backup.payload)
    tampered["farm"] = {**tampered["farm"], "name": "TAMPERED"}
    backup.payload = tampered
    await integration_session.commit()

    v = await backup_service.verify_backup(integration_session, farm.id, backup.id)
    assert v["valid"] is False

    with pytest.raises(Exception):
        await backup_service.restore_backup(integration_session, farm, backup.id, dry_run=False, overwrite=True)
