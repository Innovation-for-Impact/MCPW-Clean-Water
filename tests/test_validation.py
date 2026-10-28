"""Tests for input validation and edge cases across endpoints."""
import pytest


# ---------------------------------------------------------------------------
# Location validation (lat/lon bounds)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_lat_out_of_range(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={"location": {"lat": 91, "lon": -82.8}, "material": "oil_fuel"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_lon_out_of_range(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={"location": {"lat": 42.5, "lon": -181}, "material": "oil_fuel"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_negative_lat_boundary(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={"location": {"lat": -91, "lon": -82.8}, "material": "oil_fuel"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_incident_lat_out_of_range(client, auth_headers):
    from tests.conftest import SAMPLE_INCIDENT_BODY

    body = {**SAMPLE_INCIDENT_BODY, "location": {"lat": 100, "lon": -82.8}}
    resp = await client.post("/incidents", json=body, headers=auth_headers["responder"])
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Buffer radius validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_buffer_exceeds_cap(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={
            "location": {"lat": 42.5, "lon": -82.8},
            "material": "oil_fuel",
            "buffer_radius_m": 60000,
        },
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_buffer_at_cap(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={
            "location": {"lat": 42.5, "lon": -82.8},
            "material": "oil_fuel",
            "buffer_radius_m": 50000,
        },
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RBAC: admin-only endpoints reject non-admin roles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_webhook_non_admin_forbidden(client, auth_headers):
    resp = await client.delete("/webhooks/1", headers=auth_headers["responder"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_rule_non_admin_forbidden(client, auth_headers):
    resp = await client.delete("/rules/1", headers=auth_headers["responder"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_contact_non_admin_forbidden(client, auth_headers):
    resp = await client.delete("/contacts/1", headers=auth_headers["responder"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_contact_viewer_forbidden(client, auth_headers):
    resp = await client.post(
        "/contacts",
        json={
            "agency": "Test",
            "role": "response",
            "jurisdiction_id": "test",
            "phone": "555-0100",
            "source_url": "https://example.com",
            "last_verified": "2026-01-01",
        },
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_webhooks_responder_forbidden(client, auth_headers):
    resp = await client.get("/webhooks", headers=auth_headers["responder"])
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Events edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_invalid_since_format(client, auth_headers):
    resp = await client.get("/events?since=not-a-date", headers=auth_headers["viewer"])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_events_invalid_incident_id(client, auth_headers):
    resp = await client.get(
        "/events?incident_id=not-a-uuid", headers=auth_headers["viewer"]
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Incident edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_incident_not_found(client, auth_headers):
    resp = await client.get(
        "/incidents/00000000-0000-0000-0000-000000000000",
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_incident_invalid_uuid(client, auth_headers):
    resp = await client.get("/incidents/not-a-uuid", headers=auth_headers["viewer"])
    assert resp.status_code == 422
