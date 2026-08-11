"""
Gate 5 — staging load-test seeder.

Creates an isolated population (one org, N users each owning a farm, active
memberships) in the STAGING database and writes ``loadtest/data/tokens.json`` for
the k6 scenarios: ``[{email, password, farm_id, token}, ...]``.

Safety: refuses to run without ``--yes`` and prints the target host first. NEVER
point this at production — it writes rows. Run it against the staging DATABASE_URL.

Usage (from the backend/ directory so ``app`` is importable):
    DATABASE_URL=<staging> python ../loadtest/seed_staging.py --users 1000 --yes

Richer per-module data (flocks, logs, finance) can be layered later via the app's
own creation endpoints; users+farms already exercise the auth/farm-access floor and
the data-independent composite endpoints (e.g. ai:dashboard aggregations).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

# Make the backend package importable when run from the repo root or loadtest/.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine.url import make_url  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.auth import Role, User, UserRole  # noqa: E402
from app.models.farm import Farm, FarmMember, SubscriptionPlan  # noqa: E402
from app.models.organization import Organization  # noqa: E402

_PASSWORD = "LoadTest-12345"  # meets the length-first policy
_OUT = Path(__file__).resolve().parent / "data" / "tokens.json"


async def seed(n_users: int) -> None:
    # Unique per run so the seeder can be run repeatedly against the same staging
    # DB without colliding on the email unique constraint.
    run = uuid.uuid4().hex[:6]
    out: list[dict] = []
    async with AsyncSessionLocal() as s:
        roles = {r.name: r for r in (await s.execute(select(Role))).scalars().all()}
        free = (
            await s.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == "free"))
        ).scalar_one()

        anchor = User(
            email=f"loadtest-owner-{run}@greena-staging.co", full_name="Load Owner",
            password_hash=hash_password(_PASSWORD), is_active=True, email_verified=True,
        )
        s.add(anchor)
        await s.flush()
        org = Organization(name="Load Test Org", slug=f"loadtest-{run}",
                           owner_id=anchor.id)
        s.add(org)
        await s.flush()

        for i in range(n_users):
            email = f"load{i}-{run}@greena-staging.co"
            u = User(email=email, full_name=f"Load User {i}",
                     password_hash=hash_password(_PASSWORD), is_active=True, email_verified=True)
            s.add(u)
            await s.flush()
            s.add(UserRole(user_id=u.id, role_id=roles["farm_owner"].id, farm_id=None))
            farm = Farm(name=f"Load Farm {i}", county="Nairobi", location="Staging",
                        owner_id=u.id, plan_id=free.id, is_active=True,
                        timezone="Africa/Nairobi", organization_id=org.id)
            s.add(farm)
            await s.flush()
            s.add(FarmMember(farm_id=farm.id, user_id=u.id, role_id=roles["farm_owner"].id,
                             status="active", invited_by=u.id))
            out.append({
                "email": email, "password": _PASSWORD,
                "farm_id": str(farm.id), "token": create_access_token(str(u.id)),
            })
            if i % 200 == 0:
                await s.commit()
        await s.commit()

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2))
    print(f"Seeded {len(out)} users/farms -> {_OUT}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=1000)
    ap.add_argument("--yes", action="store_true", help="confirm writing to the target DB")
    args = ap.parse_args()

    host = make_url(settings.DATABASE_URL).host or "?"
    db = make_url(settings.DATABASE_URL).database or "?"
    print(f"Target DB host={host} name={db}")
    if not args.yes:
        print("Refusing to seed without --yes. Point DATABASE_URL at STAGING, not production.")
        raise SystemExit(2)
    if "prod" in (db or "").lower():
        print("Refusing: target database name contains 'prod'.")
        raise SystemExit(2)

    asyncio.run(seed(args.users))


if __name__ == "__main__":
    main()
