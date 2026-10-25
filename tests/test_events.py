"""Unit tests for GET /events."""
import pytest

from tests.conftest import SAMPLE_INCIDENT_BODY


async def _create_incident(client, headers):
    """Helper: create an incident and return its ID."""
    resp = await client.post(
        "/incidents",
        json=SAMPLE_INCIDENT_BODY,
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_events_list_empty(client, auth_headers):
    resp = await client.get("/events", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_event_created_on_incident(client, auth_headers):
    """An event should be created when an incident is created."""
    incident_id = await _create_incident(client, auth_headers["responder"])

    resp = await client.get("/events", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "incident.created"
    assert events[0]["incident_id"] == incident_id


@pytest.mark.asyncio
async def test_events_filter_by_incident_id(client, auth_headers):
    id1 = await _create_incident(client, auth_headers["responder"])
    id2 = await _create_incident(client, auth_headers["responder"])

    # Filter to first incident only
    resp = await client.get(
        f"/events?incident_id={id1}",
        headers=auth_headers["viewer"],
    )
    events = resp.json()
    assert all(e["incident_id"] == id1 for e in events)


@pytest.mark.asyncio
async def test_events_limit(client, auth_headers):
    # Create 3 incidents -> 3 events
    for _ in range(3):
        await _create_incident(client, auth_headers["responder"])

    resp = await client.get(
        "/events?limit=2",
        headers=auth_headers["viewer"],
    )
    assert len(resp.json()) <= 2


@pytest.mark.asyncio
async def test_events_since_filter(client, auth_headers):
    await _create_incident(client, auth_headers["responder"])

    # Use a far-future timestamp — should return no events
    resp = await client.get(
        "/events?since=2099-01-01T00:00:00Z",
        headers=auth_headers["viewer"],
    )
    assert resp.json() == []


@pytest.mark.asyncio
async def test_events_unauthenticated(client):
    resp = await client.get("/events")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_events_all_roles_can_read(client, auth_headers):
    for role in ("viewer", "responder", "admin"):
        resp = await client.get("/events", headers=auth_headers[role])
        assert resp.status_code == 200
