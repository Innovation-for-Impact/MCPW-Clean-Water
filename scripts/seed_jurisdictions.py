"""
Seed script for jurisdiction data.
Coordinate with WS3 on actual spatial data imports.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/seed_jurisdictions.py
"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine


SAMPLE_JURISDICTIONS = [
    {
        "layer": "municipality",
        "jurisdiction_id": "muni_clinton_twp",
        "name": "Clinton Township",
        # Approximate centroid of Clinton Township, Macomb County
        "wkt": "POLYGON((-82.95 42.58, -82.88 42.58, -82.88 42.63, -82.95 42.63, -82.95 42.58))",
    },
    {
        "layer": "municipality",
        "jurisdiction_id": "muni_mt_clemens",
        "name": "Mt. Clemens",
        "wkt": "POLYGON((-82.89 42.59, -82.86 42.59, -82.86 42.60, -82.89 42.60, -82.89 42.59))",
    },
    {
        "layer": "drain_district",
        "jurisdiction_id": "drain_clinton_river",
        "name": "Clinton River Drain District",
        "wkt": "POLYGON((-82.99 42.55, -82.80 42.55, -82.80 42.68, -82.99 42.68, -82.99 42.55))",
    },
    {
        "layer": "county",
        "jurisdiction_id": "county_macomb",
        "name": "Macomb County",
        "wkt": "POLYGON((-83.10 42.45, -82.70 42.45, -82.70 42.72, -83.10 42.72, -83.10 42.45))",
    },
]


async def seed():
    async with async_session_factory() as session:  # type: AsyncSession
        for j in SAMPLE_JURISDICTIONS:
            await session.execute(
                text(
                    """
                    INSERT INTO jurisdictions (layer, jurisdiction_id, name, geometry)
                    VALUES (:layer, :jurisdiction_id, :name, ST_GeogFromText(:wkt))
                    ON CONFLICT (jurisdiction_id) DO NOTHING
                    """
                ),
                {
                    "layer": j["layer"],
                    "jurisdiction_id": j["jurisdiction_id"],
                    "name": j["name"],
                    "wkt": j["wkt"],
                },
            )
        await session.commit()
        print(f"Seeded {len(SAMPLE_JURISDICTIONS)} jurisdictions")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
