"""Tests for POST /incidents/parse endpoint."""

import pytest


@pytest.mark.asyncio
async def test_parse_diesel_spill(client, auth_headers):
    resp = await client.post(
        "/incidents/parse",
        json={"text": "about 50 gallons of diesel in the Clinton River near Mount Clemens"},
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["water_body"] == "clinton_river"
    assert data["material"] == "oil_fuel"
    assert data["material_detail"] == "diesel"
    assert data["quantity"] == 50.0
    assert data["address_hint"] == "Mount Clemens"


@pytest.mark.asyncio
async def test_parse_empty_text(client, auth_headers):
    resp = await client.post(
        "/incidents/parse",
        json={"text": ""},
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["material"] == "unknown_other"


@pytest.mark.asyncio
async def test_parse_requires_auth(client):
    resp = await client.post("/incidents/parse", json={"text": "diesel spill"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_parse_sewage_with_location(client, auth_headers):
    resp = await client.post(
        "/incidents/parse",
        json={"text": "sewage overflow into storm drain at Sterling Heights, about 200 gallons"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["material"] == "sewage"
    assert data["water_body"] == "storm_sewer"
    assert data["address_hint"] == "Sterling Heights"
