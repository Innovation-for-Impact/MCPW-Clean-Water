"""
WS5 Phase 4.1 — PostGIS end-to-end integration tests.

Exercises the full chain against a real PostGIS database:
  POST /incidents → spatial lookup → rules engine → contacts → event

Requires TEST_DATABASE_URL pointing to PostGIS with loaded jurisdiction
and waterway data. Skipped entirely on SQLite.

Run with:
    SECRET_KEY=test-key \
    DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" \
    TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater" \
    python -m pytest tests/test_postgis_e2e.py -v
"""
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

POSTGIS_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    "postgresql" not in POSTGIS_URL,
    reason="PostGIS e2e tests require TEST_DATABASE_URL pointing to PostGIS",
)

BOUNDARY_TEST_CASES = json.loads(
    (Path(__file__).parent / "boundary-test-cases.json").read_text()
)

# Use TC1 (Downtown Mount Clemens) as the default — well-understood point
TC1 = next(tc for tc in BOUNDARY_TEST_CASES if tc["id"] == 1)
# Use TC2 (Sterling Heights) for a second scenario with longer downstream path
TC2 = next(tc for tc in BOUNDARY_TEST_CASES if tc["id"] == 2)


# ---------------------------------------------------------------------------
# Fixtures — create a fresh engine per test to avoid asyncpg event loop issues
# (asyncpg connections are bound to the event loop that created them;
# pytest-asyncio creates a new loop per test)
# ---------------------------------------------------------------------------


def _make_session_factory():
    engine = create_async_engine(POSTGIS_URL, echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def postgis_seed():
    """Seed contacts + rules for known jurisdictions, clean up after.

    Creates a fresh engine per invocation so asyncpg connections are on
    the current test's event loop.
    """
    from src.models.association import IncidentContact, incident_jurisdictions
    from src.models.contact import Contact
    from src.models.event import Event
    from src.models.incident import Incident
    from src.models.rule import Rule

    engine, factory = _make_session_factory()
    contact_ids = []
    rule_ids = []

    async with factory() as session:
        contact_defs = [
            {
                "agency": "E2E Test Response Agency",
                "role": "response",
                "jurisdiction_id": "county_macomb",
                "phone": "555-0001",
                "reporting_deadline": "immediate",
                "source_url": "https://e2e-test.example.com",
                "last_verified": date(2026, 1, 1),
            },
            {
                "agency": "E2E Test Regulatory Agency",
                "role": "regulatory",
                "jurisdiction_id": "county_macomb",
                "phone": "555-0002",
                "reporting_deadline": "within 24 hours",
                "source_url": "https://e2e-test.example.com",
                "last_verified": date(2026, 1, 1),
            },
            {
                "agency": "E2E Mt Clemens DPW",
                "role": "response",
                "jurisdiction_id": "muni_mt_clemens",
                "phone": "555-0003",
                "source_url": "https://e2e-test.example.com",
                "last_verified": date(2026, 1, 1),
            },
        ]

        for cdef in contact_defs:
            session.add(Contact(**cdef))
        await session.flush()

        # Get IDs for the contacts we just created
        result = await session.execute(
            select(Contact.id, Contact.agency).where(Contact.agency.like("E2E %"))
        )
        contact_map = {agency: cid for cid, agency in result.fetchall()}
        contact_ids = list(contact_map.values())

        rule_defs = [
            {"jurisdiction_type": "county", "material": "oil_fuel",
             "contact_id": contact_map["E2E Test Response Agency"], "required": True},
            {"jurisdiction_type": "county", "material": "oil_fuel",
             "contact_id": contact_map["E2E Test Regulatory Agency"], "required": True},
            {"jurisdiction_type": "municipality", "material": None,
             "contact_id": contact_map["E2E Mt Clemens DPW"], "required": True},
        ]
        for rdef in rule_defs:
            session.add(Rule(**rdef))
        await session.flush()

        result = await session.execute(
            select(Rule.id).where(Rule.contact_id.in_(contact_ids))
        )
        rule_ids = [row[0] for row in result.fetchall()]

        await session.commit()

    await engine.dispose()

    yield {"contact_ids": contact_ids, "rule_ids": rule_ids}

    # Cleanup with a fresh engine/session
    engine2, factory2 = _make_session_factory()
    async with factory2() as session:
        await session.execute(delete(IncidentContact))
        await session.execute(delete(incident_jurisdictions))
        await session.execute(delete(Event))
        await session.execute(delete(Incident))
        if rule_ids:
            await session.execute(delete(Rule).where(Rule.id.in_(rule_ids)))
        if contact_ids:
            await session.execute(delete(Contact).where(Contact.id.in_(contact_ids)))
        await session.commit()
    await engine2.dispose()


def _incident_body(tc):
    """Build an IncidentCreate-compatible dict for a boundary test case."""
    return {
        "location": {"lat": tc["lat"], "lon": tc["lon"], "address": f"E2E test - {tc['description']}"},
        "water_body": "clinton_river",
        "material": "oil_fuel",
        "material_detail": "diesel",
        "quantity": 50.0,
        "quantity_unit": "gal",
        "quantity_gallons": 50.0,
        "time_observed": datetime.now(timezone.utc).isoformat(),
        "reporter_name": "E2E Test Reporter",
        "reporter_phone": "555-9999",
        "notes": f"PostGIS e2e test - TC{tc['id']}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incident_resolves_jurisdictions(client, auth_headers, postgis_seed):
    """POST /incidents at TC1 resolves the correct jurisdictions via PostGIS."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    # Check event payload for resolved jurisdictions
    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == 1

    payload = events[0]["data"]
    resolved_ids = {j["jurisdiction_id"] for j in payload["jurisdictions"]}
    expected_ids = {j["jurisdiction_id"] for j in TC1["expected_jurisdictions"]}

    assert resolved_ids == expected_ids, (
        f"Expected jurisdictions {expected_ids}, got {resolved_ids}"
    )


@pytest.mark.asyncio
async def test_incident_resolves_contacts(client, auth_headers, postgis_seed):
    """POST /incidents at TC1 matches contacts via rules engine."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    payload = events_resp.json()[0]["data"]

    contact_agencies = {c["agency"] for c in payload["contacts"]}

    # County contacts should match (county_macomb is in TC1 jurisdictions, material=oil_fuel)
    assert "E2E Test Response Agency" in contact_agencies
    assert "E2E Test Regulatory Agency" in contact_agencies
    # Municipality contact should match (muni_mt_clemens, material=None matches any)
    assert "E2E Mt Clemens DPW" in contact_agencies


@pytest.mark.asyncio
async def test_incident_contact_roles_correct(client, auth_headers, postgis_seed):
    """Contacts are classified into correct response/regulatory roles."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    payload = events_resp.json()[0]["data"]

    response_agencies = {c["agency"] for c in payload["contacts"] if c["role"] == "response"}
    regulatory_agencies = {c["agency"] for c in payload["contacts"] if c["role"] == "regulatory"}

    assert "E2E Test Response Agency" in response_agencies
    assert "E2E Mt Clemens DPW" in response_agencies
    assert "E2E Test Regulatory Agency" in regulatory_agencies


@pytest.mark.asyncio
async def test_incident_downstream_path(client, auth_headers, postgis_seed):
    """POST /lookup at TC2 returns correct downstream path from PostGIS."""
    lookup_body = {
        "location": {"lat": TC2["lat"], "lon": TC2["lon"]},
        "material": "oil_fuel",
        "quantity_gallons": 50.0,
    }
    resp = await client.post(
        "/lookup",
        json=lookup_body,
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["downstream_path"] == TC2["expected_downstream"], (
        f"Expected {TC2['expected_downstream']}, got {data['downstream_path']}"
    )


@pytest.mark.asyncio
async def test_incident_persists_jurisdiction_associations(client, auth_headers, postgis_seed):
    """incident_jurisdictions join table is populated with the correct rows."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    # Query the join table directly with a fresh engine/session
    from src.models.association import incident_jurisdictions
    engine, factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(incident_jurisdictions.c.jurisdiction_id).where(
                incident_jurisdictions.c.incident_id == incident_id
            )
        )
        stored_ids = {row[0] for row in result.fetchall()}
    await engine.dispose()

    expected_ids = {j["jurisdiction_id"] for j in TC1["expected_jurisdictions"]}

    assert stored_ids == expected_ids, (
        f"Join table has {stored_ids}, expected {expected_ids}"
    )


@pytest.mark.asyncio
async def test_incident_persists_contact_associations(client, auth_headers, postgis_seed):
    """incident_contacts join table is populated with matched contacts."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    from src.models.association import IncidentContact
    engine, factory = _make_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(IncidentContact).where(IncidentContact.incident_id == incident_id)
        )
        associations = result.scalars().all()
    await engine.dispose()

    # Should have 3 contacts: 2 county + 1 municipality
    assert len(associations) == 3, (
        f"Expected 3 contact associations, got {len(associations)}"
    )

    roles = {a.role for a in associations}
    assert roles == {"response", "regulatory"}


@pytest.mark.asyncio
async def test_event_payload_complete(client, auth_headers, postgis_seed):
    """Event payload contains all required fields from the full chain."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201, resp.text
    incident_id = resp.json()["id"]

    events_resp = await client.get(
        f"/events?incident_id={incident_id}",
        headers=auth_headers["viewer"],
    )
    event = events_resp.json()[0]
    payload = event["data"]

    # Verify event structure
    assert event["event_type"] == "incident.created"
    assert event["incident_id"] == incident_id

    # Verify payload has all fields from the full chain
    assert payload["material"] == "oil_fuel"
    assert payload["material_detail"] == "diesel"
    assert payload["water_body"] == "clinton_river"
    assert payload["quantity_gallons"] == 50.0
    assert payload["status"] == "open"
    assert payload["location"]["lat"] == TC1["lat"]
    assert payload["location"]["lon"] == TC1["lon"]

    # Jurisdictions resolved by PostGIS
    assert len(payload["jurisdictions"]) == len(TC1["expected_jurisdictions"])

    # Contacts matched by rules engine
    assert len(payload["contacts"]) == 3


@pytest.mark.asyncio
async def test_different_location_different_jurisdictions(client, auth_headers, postgis_seed):
    """TC1 and TC2 should resolve to different municipalities."""
    resp1 = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    resp2 = await client.post(
        "/incidents",
        json=_incident_body(TC2),
        headers=auth_headers["responder"],
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201

    events1 = await client.get(
        f"/events?incident_id={resp1.json()['id']}",
        headers=auth_headers["viewer"],
    )
    events2 = await client.get(
        f"/events?incident_id={resp2.json()['id']}",
        headers=auth_headers["viewer"],
    )

    juris1 = {j["jurisdiction_id"] for j in events1.json()[0]["data"]["jurisdictions"]}
    juris2 = {j["jurisdiction_id"] for j in events2.json()[0]["data"]["jurisdictions"]}

    # Both should have county_macomb
    assert "county_macomb" in juris1
    assert "county_macomb" in juris2

    # But different municipalities
    assert "muni_mt_clemens" in juris1
    assert "muni_mt_clemens" not in juris2
    assert "muni_sterling_heights" in juris2
    assert "muni_sterling_heights" not in juris1


@pytest.mark.asyncio
async def test_incident_fetch_returns_correct_coordinates(client, auth_headers, postgis_seed):
    """GET /incidents/{id} extracts lat/lon from PostGIS geometry correctly."""
    resp = await client.post(
        "/incidents",
        json=_incident_body(TC1),
        headers=auth_headers["responder"],
    )
    assert resp.status_code == 201
    incident_id = resp.json()["id"]

    get_resp = await client.get(
        f"/incidents/{incident_id}",
        headers=auth_headers["viewer"],
    )
    assert get_resp.status_code == 200
    data = get_resp.json()

    # PostGIS ST_Y/ST_X should extract the exact coordinates back
    assert abs(data["location"]["lat"] - TC1["lat"]) < 1e-4
    assert abs(data["location"]["lon"] - TC1["lon"]) < 1e-4
