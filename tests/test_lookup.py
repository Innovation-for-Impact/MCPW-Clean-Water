"""Unit tests for POST /lookup."""
from datetime import date

import pytest
import pytest_asyncio

from tests.conftest import SAMPLE_LOOKUP_BODY


# ---------------------------------------------------------------------------
# Fixture: seed jurisdiction + contact + rule data for meaningful tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_lookup_data(db_session):
    """Seed a jurisdiction, contact, and rule so /lookup returns real data."""
    from src.models.contact import Contact
    from src.models.jurisdiction import Jurisdiction
    from src.models.rule import Rule

    jur = Jurisdiction(
        layer="county",
        jurisdiction_id="county_macomb",
        name="Macomb County",
        geometry="POINT(-82.8779 42.5973)",
        source_url="https://example.com",
    )
    db_session.add(jur)
    await db_session.flush()

    contact = Contact(
        agency="Test Response Agency",
        role="response",
        jurisdiction_id="county_macomb",
        phone="555-0100",
        source_url="https://example.com",
        last_verified=date(2026, 1, 1),
    )
    db_session.add(contact)
    await db_session.flush()

    rule = Rule(
        jurisdiction_type="county",
        material="oil_fuel",
        contact_id=contact.id,
        required=True,
    )
    db_session.add(rule)
    await db_session.commit()

    return {"jurisdiction": jur, "contact": contact, "rule": rule}


# ---------------------------------------------------------------------------
# Basic API tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_returns_200(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lookup_response_schema(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    assert "jurisdictions" in data
    assert "downstream_path" in data
    assert "response_contacts" in data
    assert "regulatory_contacts" in data
    assert isinstance(data["jurisdictions"], list)
    assert isinstance(data["downstream_path"], list)


@pytest.mark.asyncio
async def test_lookup_admin_can_access(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_lookup_viewer_forbidden(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["viewer"],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_lookup_unauthenticated(client):
    resp = await client.post("/lookup", json=SAMPLE_LOOKUP_BODY)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_lookup_missing_location(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={"material": "oil_fuel"},
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_invalid_material(client, auth_headers):
    resp = await client.post(
        "/lookup",
        json={
            "location": {"lat": 42.5, "lon": -82.8},
            "material": "not_a_real_material",
        },
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_lookup_with_buffer(client, auth_headers):
    body = {**SAMPLE_LOOKUP_BODY, "buffer_radius_m": 500.0}
    resp = await client.post(
        "/lookup",
        json=body,
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Meaningful data tests (seeded jurisdiction + contact + rule)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_returns_seeded_jurisdiction(client, auth_headers, seeded_lookup_data):
    """With a seeded jurisdiction, /lookup should return it."""
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    jur_ids = [j["jurisdiction_id"] for j in data["jurisdictions"]]
    assert "county_macomb" in jur_ids


@pytest.mark.asyncio
async def test_lookup_returns_matched_contacts(client, auth_headers, seeded_lookup_data):
    """With seeded jurisdiction + contact + rule, /lookup should return contacts."""
    resp = await client.post(
        "/lookup",
        json=SAMPLE_LOOKUP_BODY,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    assert len(data["response_contacts"]) >= 1
    assert data["response_contacts"][0]["agency"] == "Test Response Agency"


@pytest.mark.asyncio
async def test_lookup_no_contacts_for_unmatched_material(client, auth_headers, seeded_lookup_data):
    """Contacts should not match when material doesn't match the rule."""
    body = {
        "location": {"lat": 42.5973, "lon": -82.8779},
        "material": "sewage",
    }
    resp = await client.post(
        "/lookup",
        json=body,
        headers=auth_headers["responder"],
    )
    data = resp.json()
    # Rule is for oil_fuel, sewage should not match (rule.material != None and != sewage)
    response_agencies = [c["agency"] for c in data["response_contacts"]]
    assert "Test Response Agency" not in response_agencies
