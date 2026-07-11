"""
Greena — Phase 3 Flock Management: edit, source, archive.

Exercises the endpoints added for the flock lifecycle against the shared
workspace harness (an active flock in test_farm).
"""

from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def test_edit_flock_updates_fields(async_client, test_farm, test_flock, auth_headers_owner):
    resp = await async_client.patch(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}",
        json={"name": "Renamed Batch", "source": "Kenchic Hatchery", "breed": "Cobb 500"},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Renamed Batch"
    assert data["source"] == "Kenchic Hatchery"
    assert data["breed"] == "Cobb 500"


async def test_edit_flock_requires_a_field(async_client, test_farm, test_flock, auth_headers_owner):
    resp = await async_client.patch(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}",
        json={},
        headers=auth_headers_owner,
    )
    assert resp.status_code == 422


async def test_edit_flock_forbidden_for_viewer(async_client, test_farm, test_flock, auth_headers_viewer):
    resp = await async_client.patch(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}",
        json={"name": "Nope"},
        headers=auth_headers_viewer,
    )
    assert resp.status_code == 403


async def test_archive_active_flock_rejected(async_client, test_farm, test_flock, auth_headers_owner):
    """An active flock cannot be archived — it must be closed first."""
    resp = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/archive",
        headers=auth_headers_owner,
    )
    assert resp.status_code == 409


async def test_close_then_archive_flow(async_client, test_farm, test_flock, auth_headers_owner):
    # Close the flock first.
    close = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/close",
        json={"status": "closed", "close_date": str(date.today())},
        headers=auth_headers_owner,
    )
    assert close.status_code == 200, close.text

    # Now archiving is allowed.
    arch = await async_client.post(
        f"/api/v1/farms/{test_farm.id}/flocks/{test_flock.id}/archive",
        headers=auth_headers_owner,
    )
    assert arch.status_code == 200, arch.text
    assert arch.json()["data"]["archived_at"] is not None

    # Archived flock is excluded from the default list, included when asked.
    default_list = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks", headers=auth_headers_owner
    )
    ids = [f["id"] for f in default_list.json()["data"]]
    assert str(test_flock.id) not in ids

    with_archived = await async_client.get(
        f"/api/v1/farms/{test_farm.id}/flocks?include_archived=true",
        headers=auth_headers_owner,
    )
    ids2 = [f["id"] for f in with_archived.json()["data"]]
    assert str(test_flock.id) in ids2
