"""
WS3 ETL — Load prepared jurisdiction layers (GeoJSON) into PostGIS jurisdictions table.

Reads from data/prepared/*.geojson (output of prepare_layers.py).
Each feature must have a 'jurisdiction_id' and 'name' property.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/load_layers.py
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"

# Map filename stem to jurisdiction layer name
LAYER_MAP = {
    "municipalities": "municipality",
    "drain_districts": "drain_district",
    "subwatersheds": "subwatershed",
    "water_bodies": "water_body",
    "shoreline": "shoreline",
}


async def load_geojson(session: AsyncSession, filepath: Path, layer: str):
    """Load a single GeoJSON file into the jurisdictions table."""
    with open(filepath) as f:
        data = json.load(f)

    features = data.get("features", [])
    count = 0
    for feature in features:
        props = feature.get("properties", {})
        geom = json.dumps(feature.get("geometry", {}))
        jurisdiction_id = props.get("jurisdiction_id")
        name = props.get("name", props.get("NAME", "Unknown"))

        if not jurisdiction_id:
            print(f"  SKIP: feature missing jurisdiction_id in {filepath.name}")
            continue

        await session.execute(
            text("""
                INSERT INTO jurisdictions (layer, jurisdiction_id, name, geometry)
                VALUES (:layer, :jurisdiction_id, :name, ST_GeogFromText(ST_AsText(ST_GeomFromGeoJSON(:geom))))
                ON CONFLICT (jurisdiction_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    geometry = EXCLUDED.geometry
            """),
            {
                "layer": layer,
                "jurisdiction_id": jurisdiction_id,
                "name": name,
                "geom": geom,
            },
        )
        count += 1

    print(f"  Loaded {count} features from {filepath.name} as layer '{layer}'")
    return count


async def main():
    print("=" * 60)
    print("WS3 ETL: Load jurisdiction layers into PostGIS")
    print("=" * 60)

    total = 0
    async with async_session_factory() as session:
        for stem, layer in LAYER_MAP.items():
            filepath = PREPARED_DIR / f"{stem}.geojson"
            if not filepath.exists():
                print(f"\n  SKIP: {filepath} not found (data not yet prepared)")
                continue
            print(f"\n--- Loading {stem} ---")
            count = await load_geojson(session, filepath, layer)
            total += count

        await session.commit()

    print(f"\nTotal: {total} jurisdiction features loaded")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
