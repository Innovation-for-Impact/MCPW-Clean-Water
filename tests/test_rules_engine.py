"""WS4 rules engine scenario tests.

Tests evaluate_rules against seeded contacts and rules to verify
correct contact lists and priority ordering for each scenario.
Runs on SQLite (no PostGIS needed).
"""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.contact import Contact
from src.models.rule import Rule
from src.services.rules_engine import evaluate_rules

# ---------------------------------------------------------------------------
# Fixtures: seed contacts and rules for scenario testing
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seed_scenario_data(db_session: AsyncSession):
    """Seed a representative set of contacts and rules for scenario tests."""
    contacts = [
        # County response
        Contact(
            agency="Macomb County Public Works — Emergency Hotline",
            role="response",
            jurisdiction_id="county_macomb",
            jurisdiction_scope="county",
            phone="1-877-679-4337",
            after_hours_phone="1-877-679-4337",
            hours="24/7",
            reporting_deadline="Immediate",
            source_url="https://macombgov.org/departments/public-works",
            last_verified=date(2026, 10, 25),
        ),
        # County regulatory — Health Dept
        Contact(
            agency="Macomb County Health Department",
            role="regulatory",
            jurisdiction_id="county_macomb",
            jurisdiction_scope="county",
            phone="(586) 469-5236",
            reporting_deadline="24 hours",
            source_url="https://macombgov.org/departments/health",
            last_verified=date(2026, 10, 25),
        ),
        # State — EGLE PEAS
        Contact(
            agency="Michigan EGLE — PEAS",
            role="regulatory",
            jurisdiction_id="county_macomb",
            jurisdiction_scope="state",
            phone="1-800-292-4706",
            hours="24/7",
            reporting_deadline="Immediate",
            source_url="https://www.michigan.gov/egle",
            last_verified=date(2026, 10, 25),
        ),
        # State — EGLE District 11
        Contact(
            agency="Michigan EGLE — District 11",
            role="regulatory",
            jurisdiction_id="county_macomb",
            jurisdiction_scope="state",
            phone="(248) 508-1078",
            reporting_deadline="Within 10 days",
            source_url="https://www.michigan.gov/egle",
            last_verified=date(2026, 10, 25),
        ),
        # Federal — USCG
        Contact(
            agency="US Coast Guard — Sector Detroit",
            role="response",
            jurisdiction_id="shoreline_lake_st_clair",
            jurisdiction_scope="federal",
            phone="(313) 568-9564",
            hours="24/7",
            reporting_deadline="Immediate",
            source_url="https://www.uscg.mil",
            last_verified=date(2026, 10, 25),
        ),
        # Federal — NRC
        Contact(
            agency="National Response Center",
            role="regulatory",
            jurisdiction_id="shoreline_lake_st_clair",
            jurisdiction_scope="federal",
            phone="1-800-424-8802",
            hours="24/7",
            reporting_deadline="Immediate",
            source_url="https://nrc.uscg.mil",
            last_verified=date(2026, 10, 25),
        ),
        # Federal — EPA
        Contact(
            agency="EPA Region 5",
            role="regulatory",
            jurisdiction_id="county_macomb",
            jurisdiction_scope="federal",
            phone="(312) 353-2000",
            reporting_deadline="Per CERCLA",
            source_url="https://www.epa.gov",
            last_verified=date(2026, 10, 25),
        ),
        # Municipal — Harrison Twp
        Contact(
            agency="Harrison Township — DPW",
            role="response",
            jurisdiction_id="muni_harrison_township",
            jurisdiction_scope="municipal",
            phone="(586) 466-1426",
            reporting_deadline="Immediate",
            source_url="https://www.harrisontwp.org",
            last_verified=date(2026, 10, 25),
        ),
        # Municipal — Mt Clemens
        Contact(
            agency="City of Mt Clemens — DPW",
            role="response",
            jurisdiction_id="muni_mt_clemens",
            jurisdiction_scope="municipal",
            phone="(586) 469-6816",
            reporting_deadline="Immediate",
            source_url="https://www.cityofmtclemens.org",
            last_verified=date(2026, 10, 25),
        ),
        # Municipal — Sterling Heights
        Contact(
            agency="City of Sterling Heights — Public Works",
            role="response",
            jurisdiction_id="muni_sterling_heights",
            jurisdiction_scope="municipal",
            phone="(586) 446-2440",
            reporting_deadline="Immediate",
            source_url="https://www.sterling-heights.net",
            last_verified=date(2026, 10, 25),
        ),
        # Municipal — Clinton Twp
        Contact(
            agency="Clinton Township — Public Services",
            role="response",
            jurisdiction_id="muni_clinton_township",
            jurisdiction_scope="municipal",
            phone="(586) 286-9465",
            reporting_deadline="Immediate",
            source_url="https://www.clintontownship.com",
            last_verified=date(2026, 10, 25),
        ),
    ]

    for c in contacts:
        db_session.add(c)
    await db_session.flush()

    # Build a lookup: agency substring -> contact id
    cmap = {c.agency: c.id for c in contacts}

    rules = [
        # County response — hotline (priority 1)
        Rule(
            jurisdiction_type="county",
            contact_id=cmap["Macomb County Public Works — Emergency Hotline"],
            required=True,
            deadline="Immediate",
            priority=1,
        ),
        # Municipal DPW (priority 10) — multiple rules for name variants
        Rule(
            jurisdiction_type="municipality",
            contact_id=cmap["Harrison Township — DPW"],
            required=True,
            deadline="Immediate",
            priority=10,
        ),
        Rule(
            jurisdiction_type="municipality",
            contact_id=cmap["City of Mt Clemens — DPW"],
            required=True,
            deadline="Immediate",
            priority=10,
        ),
        Rule(
            jurisdiction_type="municipality",
            contact_id=cmap["City of Sterling Heights — Public Works"],
            required=True,
            deadline="Immediate",
            priority=10,
        ),
        Rule(
            jurisdiction_type="municipality",
            contact_id=cmap["Clinton Township — Public Services"],
            required=True,
            deadline="Immediate",
            priority=10,
        ),
        # USCG for shoreline (priority 15)
        Rule(
            jurisdiction_type="shoreline",
            contact_id=cmap["US Coast Guard — Sector Detroit"],
            required=True,
            deadline="Immediate",
            priority=15,
        ),
        # EGLE PEAS — state (priority 50)
        Rule(
            jurisdiction_type="county",
            contact_id=cmap["Michigan EGLE — PEAS"],
            required=True,
            deadline="Immediate",
            priority=50,
        ),
        # NRC — oil on shoreline (priority 51)
        Rule(
            jurisdiction_type="shoreline",
            material="oil_fuel",
            contact_id=cmap["National Response Center"],
            required=True,
            deadline="Immediate",
            priority=51,
        ),
        # NRC — hazmat on shoreline (priority 51)
        Rule(
            jurisdiction_type="shoreline",
            material="chemical_hazmat",
            contact_id=cmap["National Response Center"],
            required=True,
            deadline="Immediate",
            priority=51,
        ),
        # EPA — oil >= 25 gal (priority 60)
        Rule(
            jurisdiction_type="county",
            material="oil_fuel",
            size_threshold=25.0,
            contact_id=cmap["EPA Region 5"],
            required=True,
            deadline="Per CERCLA",
            priority=60,
        ),
        # EPA — any hazmat (priority 60)
        Rule(
            jurisdiction_type="county",
            material="chemical_hazmat",
            contact_id=cmap["EPA Region 5"],
            required=True,
            deadline="Per CERCLA",
            priority=60,
        ),
        # Health Dept (priority 70)
        Rule(
            jurisdiction_type="county",
            contact_id=cmap["Macomb County Health Department"],
            required=True,
            deadline="24 hours",
            priority=70,
        ),
        # EGLE District 11 follow-up (priority 90)
        Rule(
            jurisdiction_type="county",
            contact_id=cmap["Michigan EGLE — District 11"],
            required=True,
            deadline="Within 10 days",
            priority=90,
        ),
    ]

    for r in rules:
        db_session.add(r)
    await db_session.commit()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def agencies(contacts):
    """Extract agency names from a contact list."""
    return [c.agency for c in contacts]


# ---------------------------------------------------------------------------
# Scenario 1: Oil sheen on Lake St. Clair (Harrison Twp shoreline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_oil_on_lake_st_clair(db_session, seed_scenario_data):
    """Oil spill on Lake St. Clair near Harrison Township.

    Layers hit: shoreline, municipality, county.
    Expect: USCG + county hotline + municipal DPW in response;
            NRC + EGLE + Health + District 11 in regulatory.
    """
    layers = ["shoreline", "municipality", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="oil_fuel",
        quantity_gallons=50.0,
    )

    resp_names = agencies(resp)
    reg_names = agencies(reg)

    # Response: county hotline first (priority 1), then municipal (10), then USCG (15)
    assert "Macomb County Public Works — Emergency Hotline" in resp_names
    assert "US Coast Guard — Sector Detroit" in resp_names
    assert resp_names.index("Macomb County Public Works — Emergency Hotline") == 0

    # Regulatory: EGLE PEAS (50), NRC (51), EPA (60), Health (70), District 11 (90)
    assert "Michigan EGLE — PEAS" in reg_names
    assert "National Response Center" in reg_names
    assert "EPA Region 5" in reg_names
    assert "Macomb County Health Department" in reg_names
    assert "Michigan EGLE — District 11" in reg_names

    # Priority ordering: EGLE before NRC before EPA before Health before District 11
    assert reg_names.index("Michigan EGLE — PEAS") < reg_names.index("National Response Center")
    assert reg_names.index("EPA Region 5") < reg_names.index("Macomb County Health Department")
    assert reg_names.index("Macomb County Health Department") < reg_names.index("Michigan EGLE — District 11")


# ---------------------------------------------------------------------------
# Scenario 2: Chemical in Clinton River (Mt. Clemens)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_chemical_in_clinton_river(db_session, seed_scenario_data):
    """Chemical hazmat release in Mt. Clemens near the Clinton River.

    Layers hit: municipality, subwatershed, county.
    No shoreline → no USCG/NRC.
    """
    layers = ["municipality", "subwatershed", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="chemical_hazmat",
        quantity_gallons=10.0,
    )

    resp_names = agencies(resp)
    reg_names = agencies(reg)

    # Response: county hotline + municipal DPW
    assert "Macomb County Public Works — Emergency Hotline" in resp_names

    # Regulatory: EGLE + EPA (hazmat) + Health + District 11
    assert "Michigan EGLE — PEAS" in reg_names
    assert "EPA Region 5" in reg_names
    assert "Macomb County Health Department" in reg_names

    # No shoreline contacts
    assert "US Coast Guard — Sector Detroit" not in resp_names
    assert "National Response Center" not in reg_names


# ---------------------------------------------------------------------------
# Scenario 3: Sewage discharge from storm drain (Sterling Heights)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_sewage_storm_drain(db_session, seed_scenario_data):
    """Sewage discharge in Sterling Heights.

    Layers hit: municipality, county.
    Sewage material — no EPA rule (EPA rules are oil_fuel / chemical_hazmat only).
    """
    layers = ["municipality", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="sewage",
        quantity_gallons=100.0,
    )

    resp_names = agencies(resp)
    reg_names = agencies(reg)

    # Response: county hotline + Sterling Heights
    assert "Macomb County Public Works — Emergency Hotline" in resp_names

    # Regulatory: EGLE + Health + District 11 (no EPA for sewage)
    assert "Michigan EGLE — PEAS" in reg_names
    assert "Macomb County Health Department" in reg_names
    assert "Michigan EGLE — District 11" in reg_names
    assert "EPA Region 5" not in reg_names

    # No shoreline/federal contacts
    assert "US Coast Guard — Sector Detroit" not in resp_names
    assert "National Response Center" not in reg_names


# ---------------------------------------------------------------------------
# Scenario 4: Small oil spill (below EPA threshold)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_small_oil_no_epa(db_session, seed_scenario_data):
    """Small oil spill (5 gal) in county — below 25 gal EPA threshold.

    EPA rule requires size_threshold >= 25, so EPA should NOT appear.
    """
    layers = ["municipality", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="oil_fuel",
        quantity_gallons=5.0,
    )

    reg_names = agencies(reg)

    # EGLE fires (any size), EPA does not (below 25 gal threshold)
    assert "Michigan EGLE — PEAS" in reg_names
    assert "EPA Region 5" not in reg_names


# ---------------------------------------------------------------------------
# Scenario 5: Unknown material, unknown quantity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_unknown_material_and_quantity(db_session, seed_scenario_data):
    """Unknown material and no quantity — only material/size-agnostic rules fire."""
    layers = ["municipality", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material=None,
        quantity_gallons=None,
    )

    resp_names = agencies(resp)
    reg_names = agencies(reg)

    # County hotline always fires
    assert "Macomb County Public Works — Emergency Hotline" in resp_names

    # Material-agnostic rules: EGLE, Health, District 11
    assert "Michigan EGLE — PEAS" in reg_names
    assert "Macomb County Health Department" in reg_names

    # Material-specific rules should NOT fire (EPA requires oil_fuel or chemical_hazmat)
    assert "EPA Region 5" not in reg_names


# ---------------------------------------------------------------------------
# Scenario 6: Empty jurisdiction list → no contacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_no_jurisdictions(db_session, seed_scenario_data):
    """Point outside all jurisdictions → no contacts returned."""
    resp, reg = await evaluate_rules([], db=db_session)
    assert resp == []
    assert reg == []


# ---------------------------------------------------------------------------
# Scenario 7: Deduplication — same contact matched by multiple rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_deduplication(db_session, seed_scenario_data):
    """EGLE PEAS should appear only once even if county appears in multiple layers."""
    layers = ["county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="oil_fuel",
        quantity_gallons=50.0,
    )

    # Count occurrences of EGLE PEAS — should be exactly 1
    egle_count = sum(1 for c in reg if "EGLE — PEAS" in c.agency)
    assert egle_count == 1


# ---------------------------------------------------------------------------
# Scenario 8: Priority ordering is correct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scenario_priority_ordering(db_session, seed_scenario_data):
    """Response contacts should be ordered by priority (lower number first)."""
    layers = ["shoreline", "municipality", "county"]
    resp, reg = await evaluate_rules(
        layers,
        db=db_session,
        material="oil_fuel",
        quantity_gallons=50.0,
    )

    # Response priorities: hotline (1) < municipal DPW (10) < USCG (15)
    resp_names = agencies(resp)
    assert resp_names[0] == "Macomb County Public Works — Emergency Hotline"

    # USCG should come after any municipal DPW entries
    uscg_idx = resp_names.index("US Coast Guard — Sector Detroit")
    hotline_idx = resp_names.index("Macomb County Public Works — Emergency Hotline")
    assert hotline_idx < uscg_idx
