"""
Seed a demo organization for browsing the Operations Center (Module 13 Part 7).

Idempotent-ish: safe to re-run; it upserts the demo user and recreates the org.
Run against the local dev database:

    DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/agrios \
      .venv/Scripts/python.exe scripts/seed_operations_demo.py
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.auth import Role, User, UserRole
from app.models.automation import Reminder
from app.models.farm import Farm, FarmMember, FarmUnit, ProductionHouse, SubscriptionPlan
from app.models.flock import DailyLog, Flock, ProductionRecord
from app.models.organization import Organization, OrganizationMember

EMAIL = "demo@greena.test"
PASSWORD = "Demo1234!"


async def main() -> None:
    now = datetime.now(timezone.utc)
    today = date.today()
    async with AsyncSessionLocal() as s:
        roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
        plan = (await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))).scalar_one()

        # Demo user (owner/administrator).
        user = (await s.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if user is None:
            user = User(email=EMAIL, full_name="Dana Director", is_active=True,
                        email_verified=True, email_verified_at=now,
                        password_hash=hash_password(PASSWORD))
            s.add(user)
            await s.flush()
            s.add(UserRole(user_id=user.id, role_id=roles["farm_owner"].id, farm_id=None))
            await s.flush()

        # A worker to assign tasks to.
        worker = (await s.execute(select(User).where(User.email == "worker@greena.test"))).scalar_one_or_none()
        if worker is None:
            worker = User(email="worker@greena.test", full_name="Wanjiru Worker", is_active=True,
                          email_verified=True, email_verified_at=now,
                          password_hash=hash_password(PASSWORD))
            s.add(worker)
            await s.flush()
            s.add(UserRole(user_id=worker.id, role_id=roles["farm_worker"].id, farm_id=None))
            await s.flush()

        # Fresh organization each run.
        org = Organization(name="Green Valley Group", slug=f"green-valley-{now.strftime('%H%M%S')}",
                            owner_id=user.id, plan_id=plan.id, currency="KES", timezone="Africa/Nairobi")
        s.add(org)
        await s.flush()
        s.add(OrganizationMember(organization_id=org.id, user_id=user.id,
                                 role_id=roles["enterprise_owner"].id, status="active", accepted_at=now))

        specs = [
            ("Kiambu Layer Farm", 500, 380, 2600, 2500, Decimal("400"), Decimal("820"), 2),
            ("Nakuru Broiler Farm", 800, 0, 0, 0, Decimal("620"), Decimal("1100"), 6),
            ("Thika Mixed Farm", 300, 210, 1400, 1500, Decimal("240"), None, 1),
        ]
        for name, birds, eggs_today, _ew, _ep, feed_wk, water_wk, mort in specs:
            farm = Farm(name=name, county="Nairobi", owner_id=user.id, plan_id=plan.id,
                        organization_id=org.id, is_active=True, timezone="Africa/Nairobi")
            s.add(farm)
            await s.flush()
            for uid, rname in ((user.id, "farm_owner"), (worker.id, "farm_worker")):
                s.add(FarmMember(farm_id=farm.id, user_id=uid, role_id=roles[rname].id,
                                 status="active", invited_by=user.id, accepted_at=now))
            unit = FarmUnit(farm_id=farm.id, name="Unit A", sort_order=0)
            s.add(unit)
            await s.flush()
            house = ProductionHouse(farm_id=farm.id, unit_id=unit.id, name="House 1",
                                    capacity=1000, house_type="layer", sort_order=0)
            s.add(house)
            await s.flush()
            flock = Flock(farm_id=farm.id, house_id=house.id, species_key="poultry",
                          name=f"{name} Flock", initial_count=birds,
                          placement_date=today - timedelta(days=90), status="active")
            s.add(flock)
            await s.flush()
            house.current_flock_id = flock.id

            # Two weeks of daily logs + production so aggregates are non-trivial.
            for i in range(14):
                d = today - timedelta(days=i)
                s.add(DailyLog(flock_id=flock.id, farm_id=farm.id, log_date=d,
                               mortality_count=(mort if i < 7 else max(0, mort - 1)),
                               feed_consumed_kg=feed_wk / 7, logged_by=user.id))
                if eggs_today:
                    s.add(ProductionRecord(flock_id=flock.id, farm_id=farm.id, record_date=d,
                                           eggs_collected=eggs_today - (i * 2),
                                           logged_by=user.id))

            # A couple of tasks per farm.
            s.add(Reminder(farm_id=farm.id, user_id=worker.id, title="Record today's eggs",
                           due_at=now + timedelta(days=1), created_by=user.id))
            s.add(Reminder(farm_id=farm.id, user_id=None, title="Reorder feed",
                           due_at=now - timedelta(days=1), created_by=user.id))  # overdue, unassigned

        await s.commit()
        print(f"Seeded org {org.name} ({org.id}) with 3 farms.")
        print(f"Login: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
