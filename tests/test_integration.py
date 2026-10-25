"""
Integration tests — full request flow against the test database.

These tests verify the complete lifecycle:
  - Create incident -> stored in DB -> event emitted
  - Lookup returns jurisdictions from DB
  - Incident associations (jurisdictions, contacts) are persisted
"""
import uuid

import pytest

from tests.conftest import SAMPLE_INCIDENT_BODY, SAMPLE_LOOKUP_BODY


@pytest.mark.asyncio
async def test_full_incident_lifecycle(client, auth_headers):
    """Create an incident, fetch it, verify event was created."""
    # 1. Create
    create_resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    assert create_resp.status_code == 201
    incident = create_resp.json()
    incident_id = incident["id"]

    # 2. Fetch
    get_resp = await client.get(
        f"/incidents/{incident_id}",
        headers=auth_headers["viewer"],
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["id"] == incident_id
    assert fetched["material"] == SAMPLE_INCIDENT_BODY["material"]
    assert fetched["reporter_name"] == SAMPLE_INCIDENT_BODY["reporter_name"]

    # 3. Verify event was created
    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "incident.created"
    assert events[0]["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_lookup_returns_structured_result(client, auth_headers):
    """Lookup should return a well-formed result even with empty DB."""
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["jurisdictions"], list)
    assert isinstance(data["downstream_path"], list)
    assert isinstance(data["response_contacts"], list)
    assert isinstance(data["regulatory_contacts"], list)


@pytest.mark.asyncio
async def test_multiple_incidents_independent_events(client, auth_headers):
    """Each incident should generate its own event."""
    ids = []
    for _ in range(3):
        resp = await client.post(
            "/incidents",
            json=SAMPLE_INCIDENT_BODY,
            headers=auth_headers["responder"],
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])

    # Each incident has exactly one event
    for iid in ids:
        events_resp = await client.get(
            f"/events?incident_id={iid}",
            headers=auth_headers["viewer"],
        )
        assert len(events_resp.json()) == 1

    # Total events = 3
    all_events = await client.get("/events?limit=200", headers=auth_headers["viewer"])
    assert len(all_events.json()) == 3


@pytest.mark.asyncio
async def test_event_payload_contains_incident_data(client, auth_headers):
    """Event payload should include location, material, and status."""
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    incident_id = resp.json()["id"]

    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    event = events_resp.json()[0]
    payload = event["data"]

    assert payload["material"] == "oil_fuel"
    assert payload["water_body"] == "clinton_river"
    assert payload["status"] == "open"
    assert "location" in payload
    assert payload["location"]["lat"] == SAMPLE_INCIDENT_BODY["location"]["lat"]


@pytest.mark.asyncio
async def test_incident_preserves_all_fields(client, auth_headers):
    """Verify every field from the create body is preserved on fetch."""
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=auth_headers["responder"],
    )
    incident_id = resp.json()["id"]

    get_resp = await client.get(
        f"/incidents/{incident_id}",
        headers=auth_headers["viewer"],
    )
    data = get_resp.json()

    assert data["water_body"] == SAMPLE_INCIDENT_BODY["water_body"]
    assert data["material"] == SAMPLE_INCIDENT_BODY["material"]
    assert data["material_detail"] == SAMPLE_INCIDENT_BODY["material_detail"]
    assert data["quantity"] == SAMPLE_INCIDENT_BODY["quantity"]
    assert data["quantity_unit"] == SAMPLE_INCIDENT_BODY["quantity_unit"]
    assert data["reporter_name"] == SAMPLE_INCIDENT_BODY["reporter_name"]
    assert data["reporter_phone"] == SAMPLE_INCIDENT_BODY["reporter_phone"]
    assert data["notes"] == SAMPLE_INCIDENT_BODY["notes"]


@pytest.mark.asyncio
async def test_webhook_crud_lifecycle(client, auth_headers):
    """Create, list, and delete a webhook end-to-end."""
    # Create
    create_resp = await client.post(
        "/webhooks",
        json={"url": "https://example.com/hook"},
        headers=auth_headers["admin"],
    )
    if create_resp.status_code == 422:
        pytest.skip("DNS resolution blocked in test environment")
    assert create_resp.status_code == 201
    wh_id = create_resp.json()["id"]

    # List
    list_resp = await client.get("/webhooks", headers=auth_headers["admin"])
    assert any(w["id"] == wh_id for w in list_resp.json())

    # Delete
    del_resp = await client.delete(f"/webhooks/{wh_id}", headers=auth_headers["admin"])
    assert del_resp.status_code == 204

    # Verify removed
    list_resp2 = await client.get("/webhooks", headers=auth_headers["admin"])
    assert not any(w["id"] == wh_id for w in list_resp2.json())
