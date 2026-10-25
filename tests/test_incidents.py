"""Unit tests for POST /incidents and GET /incidents/{id}."""
import uuid

import pytest

from tests.conftest import SAMPLE_INCIDENT_BODY


@pytest.mark.asyncio
async def test_create_incident_returns_201(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_incident_returns_id(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    assert "id" in data
    # Validate it's a UUID
    uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_create_incident_response_schema(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    assert data["status"] == "open"
    assert data["material"] == "oil_fuel"
    assert data["water_body"] == "clinton_river"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_incident_by_id(client, auth_headers):
    # Create first
    create_resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    incident_id = create_resp.json()["id"]

    # Fetch
    resp = await client.get(
        f"/incidents/{incident_id}",
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == incident_id
    assert data["material"] == "oil_fuel"


@pytest.mark.asyncio
async def test_get_incident_not_found(client, auth_headers):
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/incidents/{fake_id}",
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_incident_missing_required_fields(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json={"notes": "incomplete"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_incident_viewer_forbidden(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_incident_admin_allowed(client, auth_headers):
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_incident_unauthenticated(client):
    resp = await client.post("/incidents", json=SAMPLE_INCIDENT_BODY)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_incident_unauthenticated(client, auth_headers):
    # Create an incident first
    create_resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    incident_id = create_resp.json()["id"]

    # Try to fetch without auth
    resp = await client.get(f"/incidents/{incident_id}")
    assert resp.status_code == 401
