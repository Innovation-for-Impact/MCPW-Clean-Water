"""Tests for the /layers GeoJSON endpoints."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.jurisdiction import Jurisdiction
from src.models.waterway import Waterway


@pytest_asyncio.fixture
async def seed_jurisdictions(db_session: AsyncSession):
    """Seed a few jurisdictions across different layers."""
    rows = [
        Jurisdiction(
            layer="municipality",
            jurisdiction_id="muni_mt_clemens",
            name="Mount Clemens",
            geometry="MULTIPOLYGON(((0 0, 1 0, 1 1, 0 1, 0 0)))",
        ),
        Jurisdiction(
            layer="municipality",
            jurisdiction_id="muni_sterling_heights",
            name="Sterling Heights",
            geometry="MULTIPOLYGON(((1 0, 2 0, 2 1, 1 1, 1 0)))",
        ),
        Jurisdiction(
            layer="subwatershed",
            jurisdiction_id="ws_middle_clinton",
            name="Middle Clinton",
            geometry="MULTIPOLYGON(((0 0, 2 0, 2 1, 0 1, 0 0)))",
        ),
        Jurisdiction(
            layer="county",
            jurisdiction_id="county_macomb",
            name="Macomb County",
            geometry="MULTIPOLYGON(((0 0, 3 0, 3 2, 0 2, 0 0)))",
        ),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()


@pytest_asyncio.fixture
async def seed_waterways(db_session: AsyncSession):
    """Seed a few waterway flowlines."""
    rows = [
        Waterway(
            name="Clinton River",
            nhd_comid=1001,
            downstream_comid=1002,
            geometry="LINESTRING(0 0, 1 1)",
            has_beach_downstream=False,
            has_intake_downstream=False,
        ),
        Waterway(
            name="Red Run Drain",
            nhd_comid=1002,
            downstream_comid=None,
            geometry="LINESTRING(1 1, 2 2)",
            has_beach_downstream=True,
            has_intake_downstream=False,
        ),
        Waterway(
            name=None,
            nhd_comid=1003,
            downstream_comid=1001,
            geometry="LINESTRING(0.5 0.5, 0 0)",
            has_beach_downstream=False,
            has_intake_downstream=False,
        ),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()


# ---------- Jurisdiction layer tests ----------


@pytest.mark.asyncio
async def test_list_jurisdiction_layers(client, seed_jurisdictions):
    resp = await client.get("/layers/jurisdictions")
    assert resp.status_code == 200
    data = resp.json()
    layers = {l["name"]: l["count"] for l in data["layers"]}
    assert layers["municipality"] == 2
    assert layers["subwatershed"] == 1
    assert layers["county"] == 1


@pytest.mark.asyncio
async def test_get_municipality_layer(client, seed_jurisdictions):
    resp = await client.get("/layers/jurisdictions/municipality")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2
    names = {f["properties"]["name"] for f in data["features"]}
    assert names == {"Mount Clemens", "Sterling Heights"}
    # Each feature should have geometry and jurisdiction_id
    for feat in data["features"]:
        assert feat["type"] == "Feature"
        assert feat["geometry"] is not None
        assert "jurisdiction_id" in feat["properties"]


@pytest.mark.asyncio
async def test_get_subwatershed_layer(client, seed_jurisdictions):
    resp = await client.get("/layers/jurisdictions/subwatershed")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) == 1
    assert data["features"][0]["properties"]["name"] == "Middle Clinton"


@pytest.mark.asyncio
async def test_get_invalid_layer_returns_404(client, seed_jurisdictions):
    resp = await client.get("/layers/jurisdictions/drain_district")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_empty_layer(client, seed_jurisdictions):
    """Shoreline layer exists but has no data seeded."""
    resp = await client.get("/layers/jurisdictions/shoreline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 0


# ---------- Waterway layer tests ----------


@pytest.mark.asyncio
async def test_get_waterways_named_only(client, seed_waterways):
    resp = await client.get("/layers/waterways")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    # named_only=True by default, so unnamed flowline (1003) excluded
    assert len(data["features"]) == 2
    comids = {f["properties"]["nhd_comid"] for f in data["features"]}
    assert comids == {1001, 1002}


@pytest.mark.asyncio
async def test_get_waterways_all(client, seed_waterways):
    resp = await client.get("/layers/waterways", params={"named_only": False})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["features"]) == 3


@pytest.mark.asyncio
async def test_get_waterways_pagination(client, seed_waterways):
    resp = await client.get("/layers/waterways", params={"named_only": False, "limit": 2, "offset": 0})
    assert resp.status_code == 200
    assert len(resp.json()["features"]) == 2

    resp2 = await client.get("/layers/waterways", params={"named_only": False, "limit": 2, "offset": 2})
    assert resp2.status_code == 200
    assert len(resp2.json()["features"]) == 1


@pytest.mark.asyncio
async def test_waterway_feature_properties(client, seed_waterways):
    resp = await client.get("/layers/waterways")
    data = resp.json()
    for feat in data["features"]:
        props = feat["properties"]
        assert "nhd_comid" in props
        assert "name" in props
        assert "has_beach_downstream" in props
        assert "has_intake_downstream" in props
        assert feat["geometry"] is not None
