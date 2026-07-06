# AGRIOS — Development Environment (Mandatory)

This is the permanent local environment used to verify **every** implementation
phase before commit. Two interchangeable backends provide Postgres; both expose
the same databases (`agrios`, `agrios_test`) and credentials.

## Option A — Docker (canonical, portable)

`infrastructure/docker-compose.yml` is the source-of-truth definition:

```bash
docker compose -f infrastructure/docker-compose.yml up -d db db_test redis
```

- `db`  → Postgres 16, `agrios/agrios_dev`, db `agrios`, port **5432**
- `db_test` → Postgres 16, db `agrios_test`, port **5433** (tmpfs, fast)
- `redis` → reserved for the future job queue

When using Docker, set the test URL explicitly:
`TEST_DATABASE_URL=postgresql+asyncpg://agrios:agrios_dev@localhost:5433/agrios_test`

## Option B — Native Postgres (this machine)

Docker Desktop is not installed here, so a native Postgres 16 cluster is the
live instance. It is managed by `scripts/dev/pg.ps1`:

```powershell
./scripts/dev/pg.ps1 start       # start cluster (port 5432)
./scripts/dev/pg.ps1 bootstrap   # create agrios + agrios_test databases
./scripts/dev/pg.ps1 status
./scripts/dev/pg.ps1 stop
```

Binaries live in `%LOCALAPPDATA%\AGRIOS\pgsql`; data in `%LOCALAPPDATA%\AGRIOS\pgdata`.
The `postgres` superuser (password `postgres`) is used locally so the test-DB
name derivation resolves cleanly. Both databases sit on the one cluster (port
5432), which matches how `conftest.py` derives the test URL.

## Environment files

- `backend/.env` — the only file the app reads (git-ignored). Copy from
  `backend/.env.development.example` and fill in secrets.
- `backend/.env.development.example` / `.env.test.example` — committed templates.
- Real `.env`, `.env.development`, `.env.test` are git-ignored.

## Python

Backend runs on **Python 3.12** (matches the pinned wheels). The venv lives at
`backend/.venv`. Recreate with:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements-dev.txt
```

## Per-phase verification (mandatory before every commit)

```powershell
./scripts/dev/verify.ps1            # backend + frontend
./scripts/dev/verify.ps1 backend
./scripts/dev/verify.ps1 frontend
```

Stages: `alembic upgrade head` → `pytest` → `ruff` → `mypy` (backend);
`lint` → `tsc --noEmit` → `build` (frontend). Any failure aborts non-zero.

## Baseline status (2026-07-05)

Migrations `001–031` apply cleanly (31 tables). The existing test suite is
**not yet fully green in this environment**: 227 pass, with pre-existing
failures unrelated to any feature work —

1. **Test isolation** — `app.database.get_db` commits on success, so the
   `client` fixture (which yields the per-test session) persists seeded rows;
   the next test's role seed then hits `duplicate key ix_roles_name`. Fix:
   SAVEPOINT-per-test binding in the `db` fixture.
2. **`test_hardening`** assigns the read-only `Settings.is_production` property.
3. A few schema tests (`ExpenseCreate`, `RevenueRecordCreate`) drifted from
   current Pydantic models.

Getting the suite to green is the first task of implementation Phase 0.
