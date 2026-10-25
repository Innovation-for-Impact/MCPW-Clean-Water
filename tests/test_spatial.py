"""
WS3 boundary tests.

Runs against PostGIS with loaded spatial + waterway data.
Requires TEST_DATABASE_URL pointing to a PostGIS connection string.
"""
import json
import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BOUNDARY_TEST_CASES = json.loads(
    (Path(__file__).parent / "boundary-test-cases.json").read_text()
)

# Skip entire module if no PostGIS URL is configured
POSTGIS_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    "postgresql" not in POSTGIS_URL,
    reason="Spatial tests require TEST_DATABASE_URL pointing to PostGIS",
)


@pytest_asyncio.fixture
async def spatial_db() -> AsyncSession:
    """Provide a DB session connected to PostGIS for spatial queries."""
    engine = create_async_engine(POSTGIS_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(params=BOUNDARY_TEST_CASES, ids=lambda tc: f"TC{tc['id']}_{tc['description'][:40]}")
def test_case(request):
    return request.param


@pytest.mark.asyncio
async def test_lookup_jurisdictions(test_case, spatial_db):
    """Call lookup_jurisdictions and verify returned jurisdictions match expected."""
    from src.services.spatial import lookup_jurisdictions

    result = await lookup_jurisdictions(test_case["lat"], test_case["lon"], db=spatial_db)

    expected_ids = {
        j["jurisdiction_id"] for j in test_case["expected_jurisdictions"]
    }
    actual_ids = {j["jurisdiction_id"] for j in result}

    assert actual_ids == expected_ids, (
        f"TC{test_case['id']}: expected {expected_ids}, got {actual_ids}"
    )


@pytest.mark.asyncio
async def test_find_nearest_water(test_case, spatial_db):
    """Call find_nearest_water and verify result matches expected."""
    from src.services.spatial import find_nearest_water

    expected = test_case.get("expected_nearest_water")
    max_distance = expected["max_distance_m"] if expected else 500
    result = await find_nearest_water(
        test_case["lat"], test_case["lon"], db=spatial_db, max_distance_m=max_distance
    )

    if expected is None:
        assert result is None or result.get("distance_m", 999) > 500, (
            f"TC{test_case['id']}: expected no nearby water, got {result}"
        )
    else:
        assert result is not None, f"TC{test_case['id']}: expected water body, got None"
        if expected["name"] is not None:
            assert result["name"] == expected["name"], (
                f"TC{test_case['id']}: expected {expected['name']}, got {result['name']}"
            )
        assert result["distance_m"] <= expected["max_distance_m"], (
            f"TC{test_case['id']}: water too far: {result['distance_m']}m"
        )


@pytest.mark.asyncio
async def test_trace_downstream(test_case, spatial_db):
    """Call trace_downstream and verify the downstream path matches expected."""
    from src.services.spatial import find_nearest_water, trace_downstream

    expected_path = test_case.get("expected_downstream", [])
    if not expected_path:
        pytest.skip("No downstream path expected for this test case")

    expected_water = test_case.get("expected_nearest_water")
    max_distance = expected_water["max_distance_m"] if expected_water else 500
    nearest = await find_nearest_water(
        test_case["lat"], test_case["lon"], db=spatial_db, max_distance_m=max_distance
    )
    assert nearest is not None, f"TC{test_case['id']}: need nearest water for trace"

    result = await trace_downstream(nearest["nhd_comid"], db=spatial_db)

    # Extract unique named waterways in order
    actual_names = []
    seen = set()
    for w in result:
        if w["name"] and w["name"] not in seen:
            seen.add(w["name"])
            actual_names.append(w["name"])

    assert actual_names == expected_path, (
        f"TC{test_case['id']}: expected path {expected_path}, got {actual_names}"
    )


@pytest.mark.asyncio
async def test_downstream_flags(test_case, spatial_db):
    """Verify beach_downstream and intake_downstream flags."""
    from src.services.spatial import find_nearest_water, trace_downstream

    expected_flags = test_case.get("expected_flags", {})
    expected_path = test_case.get("expected_downstream", [])
    if not expected_path:
        pytest.skip("No downstream path for flag testing")

    expected_water = test_case.get("expected_nearest_water")
    max_distance = expected_water["max_distance_m"] if expected_water else 500
    nearest = await find_nearest_water(
        test_case["lat"], test_case["lon"], db=spatial_db, max_distance_m=max_distance
    )
    assert nearest is not None

    result = await trace_downstream(nearest["nhd_comid"], db=spatial_db)

    has_beach = any(w.get("has_beach_downstream") for w in result)
    has_intake = any(w.get("has_intake_downstream") for w in result)

    assert has_beach == expected_flags.get("beach_downstream", False), (
        f"TC{test_case['id']}: beach_downstream mismatch"
    )
    assert has_intake == expected_flags.get("intake_downstream", False), (
        f"TC{test_case['id']}: intake_downstream mismatch"
    )
