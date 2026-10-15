"""
WS3 ETL — Compute intercept points (road × drain intersections) for Tier 2+ drains.

For drains that don't have a response plan (Tier 2, 3), generates response_sites
at each point where a road centerline crosses a drain segment.

Prerequisites:
    - Road centerlines loaded in data/raw/road_centerlines/
    - Drain segments loaded in drain_segments table

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/compute_intercept_points.py
"""

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "road_centerlines"


async def compute_from_postgis(session: AsyncSession) -> int:
    """
    Compute road × drain intersections using PostGIS spatial operations.

    Requires road_centerlines to be loaded into a temp table or the jurisdictions
    table with layer='road_centerline'.
    """
    # This query finds intersections between drain segments and road centerlines,
    # inserting them as computed response sites.
    result = await session.execute(
        text("""
            INSERT INTO response_sites (drain_id, site_order, name, source, geometry)
            SELECT
                ds.drain_id,
                ROW_NUMBER() OVER (PARTITION BY ds.drain_id ORDER BY ST_LineLocatePoint(ds.geometry::geometry, ST_Intersection(ds.geometry::geometry, r.geometry::geometry))),
                'Computed — ' || COALESCE(r.name, 'Road') || ' × ' || d.name,
                'computed',
                ST_GeogFromText(ST_AsText(ST_Intersection(ds.geometry::geometry, r.geometry::geometry)))
            FROM drain_segments ds
            JOIN drains d ON d.drain_id = ds.drain_id
            JOIN jurisdictions r ON r.layer = 'road_centerline'
            WHERE d.has_response_plan = false
              AND ST_Intersects(ds.geometry::geometry, r.geometry::geometry)
              AND ST_GeometryType(ST_Intersection(ds.geometry::geometry, r.geometry::geometry)) = 'ST_Point'
            ON CONFLICT DO NOTHING
        """),
    )
    return result.rowcount


async def main():
    print("=" * 60)
    print("WS3 ETL: Compute road × drain intercept points")
    print("=" * 60)

    async with async_session_factory() as session:
        # Check if drain segments exist
        result = await session.execute(text("SELECT COUNT(*) FROM drain_segments"))
        seg_count = result.scalar()

        if seg_count == 0:
            print("\n  No drain segments loaded yet — run load_drains.py first")
            await engine.dispose()
            return

        print(f"\n  Found {seg_count} drain segments")

        # Check if road centerlines are available
        result = await session.execute(
            text("SELECT COUNT(*) FROM jurisdictions WHERE layer = 'road_centerline'")
        )
        road_count = result.scalar()

        if road_count == 0:
            print("  No road centerlines loaded yet")
            print("  Load road centerlines into jurisdictions table (layer='road_centerline')")
            print("  or download from Michigan GIS Open Data portal")
            await engine.dispose()
            return

        print(f"  Found {road_count} road centerline features")
        print("\n--- Computing intersections ---")
        count = await compute_from_postgis(session)
        print(f"  Generated {count} computed intercept points")

        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
