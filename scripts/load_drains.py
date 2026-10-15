"""
WS3 ETL — Load county drain inventory into PostGIS drains and drain_segments tables.

Reads drain GIS data from data/raw/drains/ (provided by Macomb County Public Works).
Expected attributes: drain name/number, open/enclosed flag, intercounty status.

Until county data arrives, this script can seed known drains from the Red Run plan set
and incident records.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/load_drains.py
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "drains"

# Known drains seeded from Red Run plan set tributaries and incident records.
# These serve as Tier 1/2 seeds until the full county drain inventory arrives.
KNOWN_DRAINS = [
    {"drain_id": "drain_red_run", "drain_number": None, "name": "Red Run Drain", "tier": "1", "conveyance_owner": "county_drain", "intercounty": True, "upstream_counties": "Oakland", "drain_district_id": "dd_red_run", "has_response_plan": True},
    {"drain_id": "drain_bear_creek", "drain_number": "016", "name": "Bear Creek", "tier": "2", "conveyance_owner": "county_drain", "intercounty": False, "upstream_counties": None, "drain_district_id": None, "has_response_plan": False},
    {"drain_id": "drain_plum_brook", "drain_number": "282", "name": "Plum Brook", "tier": "2", "conveyance_owner": "county_drain", "intercounty": False, "upstream_counties": None, "drain_district_id": None, "has_response_plan": False},
    {"drain_id": "drain_sterling_relief", "drain_number": "391", "name": "Sterling Relief Drain", "tier": "2", "conveyance_owner": "county_drain", "intercounty": False, "upstream_counties": None, "drain_district_id": None, "has_response_plan": False},
    {"drain_id": "drain_schoenherr_relief", "drain_number": "340", "name": "Schoenherr Relief Drain", "tier": "2", "conveyance_owner": "county_drain", "intercounty": False, "upstream_counties": None, "drain_district_id": None, "has_response_plan": False},
    {"drain_id": "drain_big_beaver_creek", "drain_number": None, "name": "Big Beaver Creek", "tier": "2", "conveyance_owner": "county_drain", "intercounty": True, "upstream_counties": "Oakland", "drain_district_id": None, "has_response_plan": False},
    {"drain_id": "drain_clinton_river_main", "drain_number": None, "name": "Clinton River (main stem)", "tier": "2", "conveyance_owner": "county_drain", "intercounty": True, "upstream_counties": "Oakland", "drain_district_id": None, "has_response_plan": False},
]


async def seed_known_drains(session: AsyncSession):
    """Insert known drains as baseline until full county inventory arrives."""
    for d in KNOWN_DRAINS:
        await session.execute(
            text("""
                INSERT INTO drains (drain_id, drain_number, name, tier, conveyance_owner, intercounty, upstream_counties, drain_district_id, has_response_plan)
                VALUES (:drain_id, :drain_number, :name, :tier, :conveyance_owner, :intercounty, :upstream_counties, :drain_district_id, :has_response_plan)
                ON CONFLICT (drain_id) DO UPDATE SET
                    tier = EXCLUDED.tier,
                    conveyance_owner = EXCLUDED.conveyance_owner,
                    upstream_counties = EXCLUDED.upstream_counties,
                    has_response_plan = EXCLUDED.has_response_plan
            """),
            d,
        )
    print(f"  Seeded {len(KNOWN_DRAINS)} known drains (Tier 1/2 baseline)")


async def load_drain_segments_from_geojson(session: AsyncSession, filepath: Path) -> int:
    """Load drain segments from a GeoJSON file with drain attributes."""
    with open(filepath) as f:
        data = json.load(f)

    count = 0
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = json.dumps(feature.get("geometry", {}))

        drain_id = props.get("drain_id")
        segment_id = props.get("segment_id")
        conveyance_type = props.get("conveyance_type", "open")

        if not drain_id or not segment_id:
            continue

        await session.execute(
            text("""
                INSERT INTO drain_segments (drain_id, segment_id, conveyance_type, downstream_segment_id, outlet_nhd_comid, geometry)
                VALUES (:drain_id, :segment_id, :conveyance_type, :downstream_segment_id, :outlet_nhd_comid,
                        ST_GeogFromText(ST_AsText(ST_GeomFromGeoJSON(:geom))))
                ON CONFLICT (segment_id) DO UPDATE SET
                    conveyance_type = EXCLUDED.conveyance_type,
                    geometry = EXCLUDED.geometry
            """),
            {
                "drain_id": drain_id,
                "segment_id": segment_id,
                "conveyance_type": conveyance_type,
                "downstream_segment_id": props.get("downstream_segment_id"),
                "outlet_nhd_comid": props.get("outlet_nhd_comid"),
                "geom": geom,
            },
        )
        count += 1

    return count


async def main():
    print("=" * 60)
    print("WS3 ETL: Load county drains into PostGIS")
    print("=" * 60)

    async with async_session_factory() as session:
        # Always seed known drains
        print("\n--- Seeding known drains (Tier 1/2 baseline) ---")
        await seed_known_drains(session)

        # Load segments from GIS data if available
        if RAW_DIR.exists():
            geojson_files = list(RAW_DIR.glob("*.geojson")) + list(RAW_DIR.glob("*.json"))
            if geojson_files:
                for f in geojson_files:
                    print(f"\n--- Loading drain segments: {f.name} ---")
                    count = await load_drain_segments_from_geojson(session, f)
                    print(f"  Loaded {count} drain segments")
            else:
                print("\n  No drain GeoJSON files in data/raw/drains/ yet")
                print("  Waiting for Macomb County Public Works data request")
        else:
            print(f"\n  {RAW_DIR} does not exist — drain segments will be loaded when county GIS arrives")

        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
