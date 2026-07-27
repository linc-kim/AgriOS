"""
Aviculture Collection Management — over HTTP, against a real database.

These confirm the endpoints wire real farm data through the service: the catalog
is data-driven, a bird gets a complete digital identity (auto reference, initial
ownership, a 'created' timeline event), edits/transfers/sales/deaths are recorded
as permanent history, permissions hold (viewer read-only, worker can care but not
transact), duplicate rings are rejected, terminal birds cannot transition again,
and one farm can never read another farm's bird (organisation isolation).
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _avi(farm_id) -> str:
    return f"/api/v1/farms/{farm_id}/aviculture"


async def _make_species(client, farm_id, headers, name="African Grey") -> str:
    r = await client.post(
        f"{_avi(farm_id)}/species",
        json={"common_name": name, "species_group": "parrot", "scientific_name": "Psittacus erithacus"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _make_bird(client, farm_id, headers, species_id, **overrides) -> dict:
    body = {"species_id": species_id, "name": "Apollo", "sex": "male"}
    body.update(overrides)
    r = await client.post(f"{_avi(farm_id)}/birds", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestCatalog:
    async def test_owner_creates_and_lists_species(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner, name="Budgerigar")
        r = await async_client.get(f"{_avi(workspace.farm.id)}/species", headers=auth_headers_owner)
        assert r.status_code == 200
        assert any(s["id"] == sid for s in r.json()["data"])

    async def test_breed_and_mutation_under_species(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner, name="Lovebird")
        rb = await async_client.post(
            f"{_avi(workspace.farm.id)}/breeds",
            json={"species_id": sid, "name": "Peach-faced"}, headers=auth_headers_owner,
        )
        assert rb.status_code == 201, rb.text
        rm = await async_client.post(
            f"{_avi(workspace.farm.id)}/mutations",
            json={"species_id": sid, "name": "Lutino", "inheritance": "sex_linked"}, headers=auth_headers_owner,
        )
        assert rm.status_code == 201, rm.text

    async def test_viewer_cannot_create_species(self, async_client, workspace, auth_headers_viewer):
        r = await async_client.post(
            f"{_avi(workspace.farm.id)}/species",
            json={"common_name": "Canary", "species_group": "canary"}, headers=auth_headers_viewer,
        )
        assert r.status_code == 403

    async def test_invalid_species_group_rejected(self, async_client, workspace, auth_headers_owner):
        r = await async_client.post(
            f"{_avi(workspace.farm.id)}/species",
            json={"common_name": "X", "species_group": "not_a_group"}, headers=auth_headers_owner,
        )
        assert r.status_code == 422


class TestBirdIdentity:
    async def test_create_gives_full_identity(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid,
                                ring_number=f"R-{uuid.uuid4().hex[:8]}")
        assert bird["internal_ref"].startswith("AV-")
        assert bird["status"] == "active"
        assert bird["species_name"] == "African Grey"

        # Detail carries current owner + a created timeline event.
        detail = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{bird['id']}", headers=auth_headers_owner)
        assert detail.status_code == 200
        assert detail.json()["data"]["current_owner"] is not None

        tl = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/timeline", headers=auth_headers_owner)
        assert any(e["event_type"] == "created" for e in tl.json()["data"])

    async def test_worker_can_create_viewer_cannot(self, async_client, workspace, auth_headers_owner, auth_headers_worker, auth_headers_viewer):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        rw = await async_client.post(f"{_avi(workspace.farm.id)}/birds",
                                     json={"species_id": sid, "name": "Kazi"}, headers=auth_headers_worker)
        assert rw.status_code == 201, rw.text
        rv = await async_client.post(f"{_avi(workspace.farm.id)}/birds",
                                     json={"species_id": sid, "name": "Nope"}, headers=auth_headers_viewer)
        assert rv.status_code == 403

    async def test_duplicate_ring_rejected(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        ring = f"R-{uuid.uuid4().hex[:8]}"
        await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid, ring_number=ring)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds",
                                    json={"species_id": sid, "ring_number": ring}, headers=auth_headers_owner)
        assert r.status_code == 409, r.text

    async def test_update_records_change_on_timeline(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        r = await async_client.patch(f"{_avi(workspace.farm.id)}/birds/{bird['id']}",
                                     json={"name": "Apollo II", "lifecycle_stage": "adult"}, headers=auth_headers_owner)
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Apollo II"
        tl = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/timeline", headers=auth_headers_owner)
        assert any(e["event_type"] == "updated" for e in tl.json()["data"])


class TestLifecycleTransitions:
    async def test_transfer_appends_ownership_and_blocks_worker(
        self, async_client, workspace, auth_headers_owner, auth_headers_worker
    ):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)

        # Worker lacks AVI_BIRD_TRANSACT.
        rw = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/transfer",
                                     json={"to_owner_name": "Zoo"}, headers=auth_headers_worker)
        assert rw.status_code == 403

        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/transfer",
                                    json={"to_owner_name": "National Zoo", "to_owner_type": "other"},
                                    headers=auth_headers_owner)
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "transferred"

        own = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/ownership", headers=auth_headers_owner)
        rows = own.json()["data"]
        assert len(rows) == 2  # original (closed) + new (current)
        assert sum(1 for o in rows if o["is_current"]) == 1

    async def test_sell_then_cannot_transition_again(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/sell",
                                    json={"buyer_name": "Jane", "price": "15000"}, headers=auth_headers_owner)
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "sold"
        # Terminal → further transition rejected.
        r2 = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/death",
                                     json={"cause": "x"}, headers=auth_headers_owner)
        assert r2.status_code == 409

    async def test_death_and_archive_restore(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        dead = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{dead['id']}/death",
                                    json={"cause": "old age"}, headers=auth_headers_owner)
        assert r.status_code == 200 and r.json()["data"]["status"] == "deceased"

        keep = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        ra = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{keep['id']}/archive",
                                     json={"reason": "not breeding"}, headers=auth_headers_owner)
        assert ra.status_code == 200 and ra.json()["data"]["status"] == "archived"
        rr = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{keep['id']}/restore",
                                     json={}, headers=auth_headers_owner)
        assert rr.status_code == 200 and rr.json()["data"]["status"] == "active"


class TestAttachmentsAndScoping:
    async def test_media_and_document_attach(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        rm = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/media",
                                     json={"media_type": "photo", "url": "https://x/p.jpg", "is_primary": True},
                                     headers=auth_headers_owner)
        assert rm.status_code == 201, rm.text
        rd = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/documents",
                                     json={"document_type": "dna_certificate", "url": "https://x/dna.pdf",
                                           "title": "DNA Sexing"}, headers=auth_headers_owner)
        assert rd.status_code == 201, rd.text
        lm = await async_client.get(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/media", headers=auth_headers_owner)
        assert len(lm.json()["data"]) == 1

    async def test_media_requires_source(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        r = await async_client.post(f"{_avi(workspace.farm.id)}/birds/{bird['id']}/media",
                                    json={"media_type": "photo"}, headers=auth_headers_owner)
        assert r.status_code in (400, 422)

    async def test_bird_not_visible_from_another_farm(self, async_client, workspace, auth_headers_owner):
        sid = await _make_species(async_client, workspace.farm.id, auth_headers_owner)
        bird = await _make_bird(async_client, workspace.farm.id, auth_headers_owner, sid)
        # farm_b belongs to the same org/members but is a different farm scope.
        r = await async_client.get(f"{_avi(workspace.farm_b.id)}/birds/{bird['id']}", headers=auth_headers_owner)
        assert r.status_code == 404
