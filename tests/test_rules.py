"""Unit tests for /rules CRUD."""
import pytest


@pytest.mark.asyncio
async def test_list_rules_empty(client, auth_headers):
    resp = await client.get("/rules", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_rule_requires_contact(client, auth_headers):
    """Create a contact first, then a rule referencing it."""
    contact_resp = await client.post(
        "/contacts",
        json={
            "agency": "Rule Test Agency",
            "role": "response",
            "jurisdiction_id": "county_test",
            "phone": "555-0100",
            "source_url": "https://example.com",
            "last_verified": "2026-01-01",
        },
        headers=auth_headers["admin"],
    )
    contact_id = contact_resp.json()["id"]

    resp = await client.post(
        "/rules",
        json={"jurisdiction_type": "county", "contact_id": contact_id},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    assert "id" in resp.json()


@pytest.mark.asyncio
async def test_create_rule_responder_forbidden(client, auth_headers):
    resp = await client.post(
        "/rules",
        json={"jurisdiction_type": "county", "contact_id": 1},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_rule_missing_field(client, auth_headers):
    resp = await client.post(
        "/rules",
        json={"material": "oil_fuel"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_rule(client, auth_headers):
    contact_resp = await client.post(
        "/contacts",
        json={
            "agency": "Delete Rule Agency",
            "role": "regulatory",
            "jurisdiction_id": "county_test",
            "phone": "555-0200",
            "source_url": "https://example.com",
            "last_verified": "2026-01-01",
        },
        headers=auth_headers["admin"],
    )
    contact_id = contact_resp.json()["id"]
    rule_resp = await client.post(
        "/rules",
        json={"jurisdiction_type": "county", "contact_id": contact_id},
        headers=auth_headers["admin"],
    )
    rule_id = rule_resp.json()["id"]
    del_resp = await client.delete(f"/rules/{rule_id}", headers=auth_headers["admin"])
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_rule_not_found(client, auth_headers):
    resp = await client.delete("/rules/99999", headers=auth_headers["admin"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_rules_unauthenticated(client):
    resp = await client.get("/rules")
    assert resp.status_code == 401
