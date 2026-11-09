"""Tests for GET /incidents list endpoint."""

import pytest

from tests.conftest import SAMPLE_INCIDENT_BODY


@pytest.mark.asyncio
async def test_list_incidents_empty(client, auth_headers):
    resp = await client.get("/incidents", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_incidents_after_create(client, auth_headers):
    await client.post("/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers["responder"])
    resp = await client.get("/incidents", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "id" in data[0]
    assert data[0]["material"] == "oil_fuel"


@pytest.mark.asyncio
async def test_list_incidents_filter_by_status(client, auth_headers):
    await client.post("/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers["responder"])
    resp = await client.get("/incidents?status=open", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert all(i["status"] == "open" for i in resp.json())


@pytest.mark.asyncio
async def test_list_incidents_filter_by_material(client, auth_headers):
    await client.post("/incidents", json=SAMPLE_INCIDENT_BODY, headers=auth_headers["responder"])
    resp = await client.get("/incidents?material=sewage", headers=auth_headers["viewer"])
    assert resp.status_code == 200
    assert resp.json() == []  # our sample is oil_fuel, not sewage


@pytest.mark.asyncio
async def test_list_incidents_unauthenticated(client):
    resp = await client.get("/incidents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_incidents_pagination(client, auth_headers):
    resp = await client.get("/incidents?limit=1&offset=0", headers=auth_headers["viewer"])
    assert resp.status_code == 200
