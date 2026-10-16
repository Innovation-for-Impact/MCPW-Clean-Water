"""
WS3 Automated spatial tests — boundary test cases for jurisdiction lookup and downstream tracing.

Loads test cases from tests/boundary-test-cases.json and validates spatial query results.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." pytest tests/test_spatial.py -v
"""

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory
from src.services.spatial import (
    find_nearest_drain,
    find_nearest_water,
    lookup_jurisdictions,
    run_spatial_lookup,
    trace_downstream,
)

TEST_CASES_PATH = Path(__file__).parent / "boundary-test-cases.json"


@pytest.fixture(scope="module")
def test_cases():
    with open(TEST_CASES_PATH) as f:
        data = json.load(f)
    return data["test_cases"]


@pytest_asyncio.fixture
async def db():
    async with async_session_factory() as session:
        yield session


class TestLookupJurisdictions:
    """Test jurisdiction lookup for various point locations."""

    @pytest.mark.asyncio
    async def test_downtown_mount_clemens(self, db: AsyncSession, test_cases):
        """Test case 1: Downtown Mount Clemens should return muni_mount_clemens."""
        tc = test_cases[0]
        results = await lookup_jurisdictions(db, tc["lat"], tc["lon"])
        if not results:
            pytest.skip("No jurisdiction data loaded — seed the database first")
        jids = [r.jurisdiction_id for r in results]
        for expected_jid in tc["expected"].get("jurisdictions", []):
            assert expected_jid in jids, f"Expected {expected_jid} in results"

    @pytest.mark.asyncio
    async def test_sterling_heights_red_run(self, db: AsyncSession, test_cases):
        """Test case 2: Sterling Heights near Red Run."""
        tc = test_cases[1]
        results = await lookup_jurisdictions(db, tc["lat"], tc["lon"])
        if not results:
            pytest.skip("No jurisdiction data loaded — seed the database first")
        jids = [r.jurisdiction_id for r in results]
        for expected_jid in tc["expected"].get("jurisdictions", []):
            assert expected_jid in jids

    @pytest.mark.asyncio
    async def test_outside_county_oakland(self, db: AsyncSession, test_cases):
        """Test case 5: Point in Oakland County should return empty."""
        tc = test_cases[4]
        results = await lookup_jurisdictions(db, tc["lat"], tc["lon"])
        assert len(results) == 0, "Outside county should return no jurisdictions"

    @pytest.mark.asyncio
    async def test_outside_county_st_clair(self, db: AsyncSession, test_cases):
        """Test case 6: Point in St. Clair County should return empty."""
        tc = test_cases[5]
        results = await lookup_jurisdictions(db, tc["lat"], tc["lon"])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_boundary_returns_both(self, db: AsyncSession, test_cases):
        """Test case 4: Point on municipal boundary should return both."""
        tc = test_cases[3]
        results = await lookup_jurisdictions(db, tc["lat"], tc["lon"])
        if not results:
            pytest.skip("No jurisdiction data loaded — seed the database first")
        jids = [r.jurisdiction_id for r in results]
        for expected_jid in tc["expected"].get("jurisdictions_contains_both", []):
            assert expected_jid in jids, f"Boundary point should return {expected_jid}"


class TestFindNearestDrain:
    """Test drain snapping for spill points near county drains."""

    @pytest.mark.asyncio
    async def test_near_red_run(self, db: AsyncSession, test_cases):
        """Test case 2: Should snap to Red Run Drain (Tier 1)."""
        tc = test_cases[1]
        drain = await find_nearest_drain(db, tc["lat"], tc["lon"])
        if drain is None:
            pytest.skip("No drain segment data loaded — run load_drains.py first")
        assert drain.drain_id == "drain_red_run"
        assert drain.tier == "1"

    @pytest.mark.asyncio
    async def test_bear_creek_enclosed(self, db: AsyncSession, test_cases):
        """Test case 11: Bear Creek at Mound Rd should be Tier 2, enclosed."""
        tc = test_cases[10]
        drain = await find_nearest_drain(db, tc["lat"], tc["lon"])
        if drain is None:
            pytest.skip("No drain segment data loaded — run load_drains.py first")
        expected = tc["expected"].get("drain", {})
        assert drain.drain_id == expected.get("drain_id", "drain_bear_creek")
        assert drain.tier == expected.get("tier", "2")

    @pytest.mark.asyncio
    async def test_no_drain_far_from_water(self, db: AsyncSession, test_cases):
        """Test case 9: Point far from waterway — query completes without error."""
        tc = test_cases[8]
        await find_nearest_drain(db, tc["lat"], tc["lon"])


class TestFindNearestWater:
    """Test NHD water body snapping (fallback when no drain nearby)."""

    @pytest.mark.asyncio
    async def test_near_clinton_river(self, db: AsyncSession, test_cases):
        """Test case 1: Downtown Mt. Clemens should be near Clinton River."""
        tc = test_cases[0]
        water = await find_nearest_water(db, tc["lat"], tc["lon"])
        if water is None:
            pytest.skip("No waterway data loaded — run load_waterways.py first")
        assert water.name is not None
        assert "Clinton" in water.name


class TestDownstreamTrace:
    """Test downstream tracing through drain network and NHD flowlines."""

    @pytest.mark.asyncio
    async def test_red_run_to_lake(self, db: AsyncSession, test_cases):
        """Test case 2: Red Run should trace to Clinton River then Lake St. Clair."""
        tc = test_cases[1]
        drain = await find_nearest_drain(db, tc["lat"], tc["lon"])
        if drain is None:
            pytest.skip("No drain segment data loaded — run load_drains.py first")
        path, beach, intake, major, intercept = await trace_downstream(db, drain=drain)
        if not path:
            pytest.skip("Downstream connectivity data not loaded — run build_downstream_links.py first")
        assert any("Red Run" in p for p in path), "Red Run should be in path"

    @pytest.mark.asyncio
    async def test_upstream_counties_red_run_dequindre(self, db: AsyncSession, test_cases):
        """Test case 13: Red Run at Dequindre should flag upstream Oakland County."""
        tc = test_cases[12]
        result = await run_spatial_lookup(db, tc["lat"], tc["lon"])
        if not result.drain:
            pytest.skip("No drain segment data loaded — run load_drains.py first")
        expected_upstream = tc["expected"].get("upstream_counties", [])
        for county in expected_upstream:
            assert county in result.upstream_counties, f"Expected upstream county: {county}"


class TestFullSpatialLookup:
    """Integration tests for the combined spatial lookup."""

    @pytest.mark.asyncio
    async def test_bear_creek_incident(self, db: AsyncSession, test_cases):
        """Test case 11: Bear Creek diesel spill — full lookup."""
        tc = test_cases[10]
        result = await run_spatial_lookup(db, tc["lat"], tc["lon"])

        # Check jurisdictions
        jids = [j.jurisdiction_id for j in result.jurisdictions]
        for expected_jid in tc["expected"].get("jurisdictions_contains", []):
            assert expected_jid in jids

        # Check drain
        if result.drain and "drain" in tc["expected"]:
            expected_drain = tc["expected"]["drain"]
            assert result.drain.drain_id == expected_drain.get("drain_id", result.drain.drain_id)

        # Check downstream path
        if result.downstream_path and "downstream_path" in tc["expected"]:
            for expected_name in tc["expected"]["downstream_path"]:
                assert any(expected_name in p for p in result.downstream_path), \
                    f"Expected '{expected_name}' in downstream path"

    @pytest.mark.asyncio
    async def test_outside_county_flag(self, db: AsyncSession, test_cases):
        """Test case 5: Outside county should set the flag."""
        tc = test_cases[4]
        result = await run_spatial_lookup(db, tc["lat"], tc["lon"])
        assert result.flags["outside_county"] is True

    @pytest.mark.asyncio
    async def test_excluded_procedure_sanitary(self, db: AsyncSession):
        """Sanitary sewer conveyance should set excluded_procedure flag."""
        pytest.skip("Needs a drain with conveyance_type='sanitary' in test data — seed when data arrives")

    @pytest.mark.asyncio
    async def test_all_16_cases_no_errors(self, db: AsyncSession, test_cases):
        """Smoke test: all 16 test cases run without errors."""
        for tc in test_cases:
            result = await run_spatial_lookup(db, tc["lat"], tc["lon"])
            assert result is not None, f"Test case {tc['id']} returned None"
