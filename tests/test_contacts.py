"""Unit tests for /contacts CRUD."""
import pytest


SAMPLE_CONTACT = {
    "agency": "Test Agency",
    "role": "response",
    "jurisdiction_id": "county_test",
    "phone": "555-0100",
    "source_url": "https://example.com",
    "last_verified": "2026-01-01",
}


@pytest.mark.asyncio
async def test_list_contacts_empty(client, auth_headers):
    resp = await client.get("/contacts", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_contact_admin(client, auth_headers):
    resp = await client.post(
        "/contacts", json=SAMPLE_CONTACT, headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["agency"] == "Test Agency"


@pytest.mark.asyncio
async def test_create_contact_responder_forbidden(client, auth_headers):
    resp = await client.post(
        "/contacts", json=SAMPLE_CONTACT, headers=auth_headers["responder"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_contact_missing_field(client, auth_headers):
    resp = await client.post(
        "/contacts", json={"agency": "Incomplete"}, headers=auth_headers["admin"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_contacts_after_create(client, auth_headers):
    await client.post("/contacts", json=SAMPLE_CONTACT, headers=auth_headers["admin"])
    resp = await client.get("/contacts", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_delete_contact(client, auth_headers):
    create_resp = await client.post(
        "/contacts", json=SAMPLE_CONTACT, headers=auth_headers["admin"],
    )
    contact_id = create_resp.json()["id"]
    del_resp = await client.delete(
        f"/contacts/{contact_id}", headers=auth_headers["admin"],
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_contact_not_found(client, auth_headers):
    resp = await client.delete("/contacts/99999", headers=auth_headers["admin"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_contact_viewer_forbidden(client, auth_headers):
    resp = await client.delete("/contacts/1", headers=auth_headers["viewer"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_contacts_unauthenticated(client):
    resp = await client.get("/contacts")
    assert resp.status_code == 401
