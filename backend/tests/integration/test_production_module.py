"""
Greena — Module 11 (Production Readiness) integration tests.

Covers the properties that matter operationally rather than every endpoint:

  * Backups capture data, checksum it, and refuse to restore when tampered.
  * A restore actually recovers deleted data (the reason backups exist).
  * A dry run reports without writing.
  * Imports validate before writing, and report per-row errors.
  * Exported files import back cleanly (round trip).
  * Diagnostics, version, metrics and deployment/rollback verification respond.
  * The production surface is authenticated, and RBAC is enforced.
"""

import csv
import io
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.models.finance import Expense, ExpenseCategory

pytestmark = pytest.mark.asyncio


def _data(farm_id: str) -> str:
    return f"/api/v1/farms/{farm_id}/data"


async def _live_expense_count(conn, farm_id: str) -> int:
    """Count live expenses over the raw connection, avoiding a second ORM session."""
    result = await conn.execute(
        text("SELECT count(*) FROM expenses WHERE farm_id = :f AND deleted_at IS NULL"),
        {"f": farm_id},
    )
    return int(result.scalar())


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def farm_with_expenses(integration_session, workspace) -> dict:
    """The shared farm with three expenses, so backups have something to capture."""
    category = (
        await integration_session.execute(select(ExpenseCategory).limit(1))
    ).scalar_one()

    ids = []
    for i in range(3):
        expense = Expense(
            farm_id=workspace.farm.id,
            category_id=category.id,
            expense_date=date.today() - timedelta(days=i),
            amount=Decimal(f"{100 + i}.50"),
            description=f"Test expense {i}",
        )
        integration_session.add(expense)
        await integration_session.flush()
        ids.append(str(expense.id))

    await integration_session.commit()
    return {"farm_id": str(workspace.farm.id), "expense_ids": ids}


# ── Version / diagnostics / metrics ───────────────────────────────────────────

class TestPlatformEndpoints:
    async def test_version_is_public(self, async_client):
        """Uptime checks and deploy tooling cannot carry a user token."""
        resp = await async_client.get("/api/v1/production/version")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["version"]
        assert data["environment"]
        assert data["uptime_seconds"] >= 0

    async def test_metrics_is_prometheus_text(self, async_client):
        resp = await async_client.get("/api/v1/production/metrics")
        assert resp.status_code == 200
        body = resp.text
        assert "greena_http_requests_total" in body
        assert "greena_build_info" in body
        assert "# TYPE" in body

    async def test_metrics_histogram_is_monotonic(self, async_client):
        """Prometheus requires cumulative buckets; a non-monotonic histogram is
        silently wrong rather than obviously broken, so it is asserted here."""
        await async_client.get("/api/v1/production/version")
        body = (await async_client.get("/api/v1/production/metrics")).text

        counts, inf = [], None
        for line in body.splitlines():
            if "duration_seconds_bucket" not in line or 'path="/api/v1/production/version"' not in line:
                continue
            value = int(line.rsplit(" ", 1)[1])
            if 'le="+Inf"' in line:
                inf = value
            else:
                counts.append(value)

        assert counts, "no histogram buckets emitted"
        assert counts == sorted(counts), "buckets must be non-decreasing"
        assert inf is not None and inf >= counts[-1], "+Inf must be the total"

    async def test_diagnostics_requires_auth(self, async_client):
        resp = await async_client.get("/api/v1/production/diagnostics")
        assert resp.status_code == 401

    async def test_diagnostics_reports_checks(self, async_client, auth_headers_owner):
        resp = await async_client.get("/api/v1/production/diagnostics", headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert len(data["checks"]) >= 5
        names = {c["name"] for c in data["checks"]}
        assert {"database", "schema", "migrations", "environment"} <= names

    async def test_database_and_schema_checks_pass(self, async_client, auth_headers_owner):
        """The test database is migrated, so these must pass — if they do not,
        the schema has drifted from the models."""
        resp = await async_client.get("/api/v1/production/diagnostics", headers=auth_headers_owner)
        checks = {c["name"]: c for c in resp.json()["data"]["checks"]}
        assert checks["database"]["passed"], checks["database"]["detail"]
        assert checks["schema"]["passed"], checks["schema"]["detail"]

    async def test_status_includes_metrics_and_entities(self, async_client, auth_headers_owner):
        resp = await async_client.get("/api/v1/production/status", headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "metrics" in data and "entities" in data
        assert data["metrics"]["total_requests"] >= 0
        assert "users" in data["entities"]

    async def test_deployment_verification(self, async_client, auth_headers_owner):
        resp = await async_client.post("/api/v1/production/deployment/verify", headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert {c["name"] for c in data["checks"]} >= {"database", "migrations", "environment", "schema"}

    async def test_rollback_verification(self, async_client, auth_headers_owner):
        resp = await async_client.post("/api/v1/production/rollback/verify", headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "is_rollback" in data
        assert any(c["name"] == "schema_compatible" for c in data["checks"])

    async def test_release_info(self, async_client, auth_headers_owner):
        resp = await async_client.get("/api/v1/production/release", headers=auth_headers_owner)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["current"]["version"]
        # The test database is migrated to head by conftest.
        assert data["migrations_at_head"] is True


# ── Backups ───────────────────────────────────────────────────────────────────

class TestBackups:
    async def test_create_captures_rows(self, async_client, farm_with_expenses, auth_headers_owner):
        farm_id = farm_with_expenses["farm_id"]
        resp = await async_client.post(
            f"{_data(farm_id)}/backups", json={"label": "Test backup"}, headers=auth_headers_owner
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["status"] == "success"
        assert data["record_counts"]["expenses"] >= 3
        assert data["checksum"]
        assert data["size_bytes"] > 0

    async def test_backup_serialises_metadata_column(
        self, async_client, farm_with_expenses, auth_headers_owner
    ):
        """Every model maps a "metadata" column via the attribute `metadata_`.
        Reading it by column name returns SQLAlchemy's MetaData object, which is
        not JSON-serialisable and broke every backup of a non-empty farm."""
        farm_id = farm_with_expenses["farm_id"]
        resp = await async_client.post(
            f"{_data(farm_id)}/backups", json={}, headers=auth_headers_owner
        )
        assert resp.status_code == 201
        backup_id = resp.json()["data"]["id"]

        dl = await async_client.get(
            f"{_data(farm_id)}/backups/{backup_id}/download", headers=auth_headers_owner
        )
        payload = json.loads(dl.content)
        row = payload["data"]["expenses"][0]
        assert isinstance(row["metadata"], dict)

    async def test_verify_reports_intact(self, async_client, farm_with_expenses, auth_headers_owner):
        farm_id = farm_with_expenses["farm_id"]
        created = await async_client.post(f"{_data(farm_id)}/backups", json={}, headers=auth_headers_owner)
        backup_id = created.json()["data"]["id"]

        resp = await async_client.get(
            f"{_data(farm_id)}/backups/{backup_id}/verify", headers=auth_headers_owner
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["valid"] is True

    async def test_tampered_backup_is_refused(
        self, async_client, farm_with_expenses, integration_conn, auth_headers_owner
    ):
        """The integrity gate: a mutated snapshot must never be restored."""
        farm_id = farm_with_expenses["farm_id"]
        created = await async_client.post(f"{_data(farm_id)}/backups", json={}, headers=auth_headers_owner)
        backup_id = created.json()["data"]["id"]

        # Written straight onto the shared connection rather than through a
        # second ORM session: two sessions on one connection each manage their
        # own savepoints, and interleaving their commits invalidates the
        # savepoint the request session later rolls back to.
        row = (await integration_conn.execute(
            text("SELECT payload FROM backups WHERE id = :id"), {"id": backup_id}
        )).first()
        payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        payload["data"]["expenses"].append({"id": "tampered", "amount": "999999"})
        await integration_conn.execute(
            text("UPDATE backups SET payload = CAST(:p AS jsonb) WHERE id = :id"),
            {"p": json.dumps(payload), "id": backup_id},
        )

        verify = await async_client.get(
            f"{_data(farm_id)}/backups/{backup_id}/verify", headers=auth_headers_owner
        )
        assert verify.json()["data"]["valid"] is False

        restore = await async_client.post(
            f"{_data(farm_id)}/restore",
            json={"backup_id": backup_id, "dry_run": False},
            headers=auth_headers_owner,
        )
        assert restore.status_code == 422
        assert "checksum" in restore.json()["error"]["message"].lower()

    async def test_dry_run_writes_nothing(
        self, async_client, farm_with_expenses, integration_conn, auth_headers_owner
    ):
        farm_id = farm_with_expenses["farm_id"]
        created = await async_client.post(f"{_data(farm_id)}/backups", json={}, headers=auth_headers_owner)
        backup_id = created.json()["data"]["id"]

        before = await _live_expense_count(integration_conn, farm_id)

        resp = await async_client.post(
            f"{_data(farm_id)}/restore",
            json={"backup_id": backup_id, "dry_run": True},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        run = resp.json()["data"]
        assert run["dry_run"] is True
        assert run["checksum_verified"] is True

        assert await _live_expense_count(integration_conn, farm_id) == before

    async def test_restore_recovers_deleted_rows(
        self, async_client, farm_with_expenses, integration_conn, auth_headers_owner
    ):
        """The point of the whole subsystem: delete data, restore, get it back.

        A soft-deleted row keeps its primary key, so a naive "does this id exist"
        check counts it as present and restores nothing — which would make
        restore useless for the case it exists to serve.
        """
        farm_id = farm_with_expenses["farm_id"]
        created = await async_client.post(f"{_data(farm_id)}/backups", json={}, headers=auth_headers_owner)
        backup_id = created.json()["data"]["id"]

        await integration_conn.execute(
            text("UPDATE expenses SET deleted_at = now() "
                 "WHERE farm_id = :f AND deleted_at IS NULL"),
            {"f": farm_id},
        )
        assert await _live_expense_count(integration_conn, farm_id) == 0, \
            "setup failed — expenses were not deleted"

        resp = await async_client.post(
            f"{_data(farm_id)}/restore",
            json={"backup_id": backup_id, "dry_run": False},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        run = resp.json()["data"]
        assert run["status"] == "success"
        assert run["summary"]["expenses"]["revived"] >= 3
        # An applied restore always snapshots current state first.
        assert run["safety_backup_id"] is not None

        assert await _live_expense_count(integration_conn, farm_id) >= 3

    async def test_retention_sweep(self, async_client, farm_with_expenses, auth_headers_owner):
        farm_id = farm_with_expenses["farm_id"]
        resp = await async_client.post(
            f"{_data(farm_id)}/backups/retention", headers=auth_headers_owner
        )
        assert resp.status_code == 200
        assert "expired_removed" in resp.json()["data"]


# ── Imports ───────────────────────────────────────────────────────────────────

def _csv_bytes(rows: list[dict], columns: list[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


class TestImports:
    async def test_entities_and_template(self, async_client, test_farm, auth_headers_owner):
        farm_id = str(test_farm.id)
        entities = await async_client.get(f"{_data(farm_id)}/imports/entities", headers=auth_headers_owner)
        assert entities.status_code == 200
        names = {e["entity"] for e in entities.json()["data"]}
        assert {"expenses", "revenue", "daily_logs", "inventory_items"} <= names

        template = await async_client.get(
            f"{_data(farm_id)}/imports/template", params={"entity": "expenses"},
            headers=auth_headers_owner,
        )
        assert template.status_code == 200
        assert "expense_date" in template.text

    async def test_dry_run_validates_without_writing(self, async_client, test_farm, auth_headers_owner):
        farm_id = str(test_farm.id)
        content = _csv_bytes(
            [{"expense_date": "2026-05-01", "category": "feed_purchase", "amount": "1500.50",
              "description": "Starter feed", "payment_method": "mpesa", "supplier": "", "notes": ""}],
            ["expense_date", "category", "amount", "description", "payment_method", "supplier", "notes"],
        )
        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "expenses", "source_format": "csv", "dry_run": True},
            files={"file": ("expenses.csv", content, "text/csv")},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        job = resp.json()["data"]
        assert job["status"] == "success"
        assert job["valid_rows"] == 1
        assert job["imported_rows"] == 0  # dry run writes nothing

    async def test_invalid_rows_reported_and_rejected(self, async_client, test_farm, auth_headers_owner):
        """A bad row must fail the whole import by default — partial application
        is what produces duplicated and half-missing records."""
        farm_id = str(test_farm.id)
        content = _csv_bytes(
            [
                {"expense_date": "not-a-date", "category": "feed_purchase", "amount": "100", "description": "Bad date"},
                {"expense_date": "2026-05-03", "category": "labour", "amount": "abc", "description": "Bad amount"},
            ],
            ["expense_date", "category", "amount", "description"],
        )
        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "expenses", "source_format": "csv", "dry_run": True},
            files={"file": ("bad.csv", content, "text/csv")},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        job = resp.json()["data"]
        assert job["status"] == "failed"
        assert job["failed_rows"] == 2
        assert job["imported_rows"] == 0
        # Row numbers must match the file, counting the header line.
        assert {e["row"] for e in job["errors"]} == {2, 3}

    async def test_apply_writes_rows(self, async_client, test_farm, integration_session, auth_headers_owner):
        farm_id = str(test_farm.id)
        content = _csv_bytes(
            [{"expense_date": "2026-05-05", "category": "labour", "amount": "800",
              "description": "Casual labour import"}],
            ["expense_date", "category", "amount", "description"],
        )
        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "expenses", "source_format": "csv", "dry_run": False},
            files={"file": ("ok.csv", content, "text/csv")},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["imported_rows"] == 1

        found = (await integration_session.execute(
            select(Expense).where(Expense.description == "Casual labour import")
        )).scalars().all()
        assert len(found) == 1

    async def test_unknown_entity_rejected(self, async_client, test_farm, auth_headers_owner):
        farm_id = str(test_farm.id)
        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "not_a_thing", "source_format": "csv", "dry_run": True},
            files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 422


# ── Exports ───────────────────────────────────────────────────────────────────

class TestExports:
    async def test_datasets_listed(self, async_client, test_farm, auth_headers_owner):
        farm_id = str(test_farm.id)
        resp = await async_client.get(f"{_data(farm_id)}/exports/datasets", headers=auth_headers_owner)
        assert resp.status_code == 200
        names = {d["dataset"] for d in resp.json()["data"]}
        assert {"daily_logs", "expenses", "revenue", "flocks"} <= names

    @pytest.mark.parametrize("fmt,marker", [("csv", b"expense_date"), ("json", b'"dataset"'), ("excel", b"PK")])
    async def test_export_formats(self, async_client, farm_with_expenses, auth_headers_owner, fmt, marker):
        farm_id = farm_with_expenses["farm_id"]
        resp = await async_client.get(
            f"{_data(farm_id)}/exports/download",
            params={"dataset": "expenses", "export_format": fmt},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        assert marker in resp.content
        assert "attachment" in resp.headers["content-disposition"]

    async def test_export_imports_back(self, async_client, farm_with_expenses, auth_headers_owner):
        """Round trip: an exported file must be readable by the importer, so
        export → edit in a spreadsheet → import is a supported workflow."""
        farm_id = farm_with_expenses["farm_id"]
        exported = await async_client.get(
            f"{_data(farm_id)}/exports/download",
            params={"dataset": "expenses", "export_format": "csv"},
            headers=auth_headers_owner,
        )
        assert exported.status_code == 200

        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "expenses", "source_format": "csv", "dry_run": True},
            files={"file": ("roundtrip.csv", exported.content, "text/csv")},
            headers=auth_headers_owner,
        )
        assert resp.status_code == 200
        job = resp.json()["data"]
        assert job["failed_rows"] == 0, f"round trip failed: {job['errors']}"
        assert job["valid_rows"] >= 3

    async def test_json_export_imports_back(self, async_client, farm_with_expenses, auth_headers_owner):
        farm_id = farm_with_expenses["farm_id"]
        exported = await async_client.get(
            f"{_data(farm_id)}/exports/download",
            params={"dataset": "expenses", "export_format": "json"},
            headers=auth_headers_owner,
        )
        resp = await async_client.post(
            f"{_data(farm_id)}/imports",
            params={"entity": "expenses", "source_format": "json", "dry_run": True},
            files={"file": ("roundtrip.json", exported.content, "application/json")},
            headers=auth_headers_owner,
        )
        assert resp.json()["data"]["failed_rows"] == 0


# ── Security hardening ────────────────────────────────────────────────────────

class TestSecurityHardening:
    async def test_auth_endpoints_are_rate_limited(self, async_client):
        """Login is unauthenticated and guessable, so it is the endpoint an
        attacker actually hammers. Past the window it must return 429 with a
        Retry-After the client can honour."""
        statuses = []
        for _ in range(26):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong-password"},
            )
            statuses.append(resp.status_code)

        assert 429 in statuses, "rate limiter did not engage"
        # Everything before the first 429 must have been handled normally.
        first_429 = statuses.index(429)
        assert first_429 >= 15, f"limiter engaged too early (after {first_429})"
        assert all(s == 429 for s in statuses[first_429:]), "limiter let requests through again"

        limited = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password"},
        )
        assert limited.status_code == 429
        assert "retry-after" in limited.headers
        assert limited.json()["error"]["code"] == "RATE_LIMITED"

    async def test_rate_limit_does_not_affect_other_routes(self, async_client):
        """Authenticated routes are bounded by tokens and plan limits already;
        throttling them would break normal use."""
        for _ in range(25):
            await async_client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
            )
        resp = await async_client.get("/api/v1/production/version")
        assert resp.status_code == 200

    async def test_security_headers_present(self, async_client):
        resp = await async_client.get("/api/v1/production/version")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert "referrer-policy" in resp.headers
        assert "content-security-policy" in resp.headers

    async def test_request_id_and_timing_headers(self, async_client):
        resp = await async_client.get("/api/v1/production/version")
        assert resp.headers.get("x-request-id")
        assert resp.headers.get("x-process-time")


# ── RBAC ──────────────────────────────────────────────────────────────────────

class TestProductionRBAC:
    async def test_viewer_can_read_status(self, async_client, auth_headers_viewer):
        resp = await async_client.get("/api/v1/production/diagnostics", headers=auth_headers_viewer)
        assert resp.status_code == 200

    async def test_viewer_cannot_create_backup(self, async_client, test_farm, auth_headers_viewer):
        """Restoring overwrites live data, so backups are owner-only."""
        resp = await async_client.post(
            f"{_data(str(test_farm.id))}/backups", json={}, headers=auth_headers_viewer
        )
        assert resp.status_code == 403

    async def test_worker_cannot_import(self, async_client, test_farm, auth_headers_worker):
        resp = await async_client.post(
            f"{_data(str(test_farm.id))}/imports",
            params={"entity": "expenses", "source_format": "csv", "dry_run": True},
            files={"file": ("x.csv", b"expense_date,amount\n", "text/csv")},
            headers=auth_headers_worker,
        )
        assert resp.status_code == 403

    async def test_worker_cannot_export(self, async_client, test_farm, auth_headers_worker):
        resp = await async_client.get(
            f"{_data(str(test_farm.id))}/exports/download",
            params={"dataset": "expenses", "export_format": "csv"},
            headers=auth_headers_worker,
        )
        assert resp.status_code == 403

    async def test_backups_require_auth(self, async_client, test_farm):
        resp = await async_client.get(f"{_data(str(test_farm.id))}/backups")
        assert resp.status_code == 401
