"""
Load prepared GeoJSON layers into the PostGIS jurisdictions table.

Usage:
    python -m scripts.load_layers [--dry-run]

Reads clipped/reprojected GeoJSON from data/prepared/ and upserts rows into
the `jurisdictions` table. Uses jurisdiction_id as the stable key for upserts
(insert or update on conflict).

Requires a running PostgreSQL/PostGIS database via DATABASE_URL env var.
"""
import argparse
import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from shapely.geometry import shape

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

PREPARED = Path(__file__).parent.parent / "data" / "prepared"

# Map each prepared file to its layer code and source URL
LAYER_CONFIG = {
    "municipalities.geojson": {
        "layer": "municipality",
        "name_field": "LABEL",
        "source_url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/2",
    },
    "shoreline.geojson": {
        "layer": "shoreline",
        "name_field": "LAKE_NAME",
        "source_url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/hydro/MapServer/13",
    },
    "county_boundary.geojson": {
        "layer": "county",
        "name_field": "LABEL",
        "source_url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/0",
    },
    "subwatersheds.geojson": {
        "layer": "subwatershed",
        "name_field": "name",
        "source_url": "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/6",
    },
}


def load_features(filename: str, config: dict) -> list[dict]:
    """Read a prepared GeoJSON file and return rows for the jurisdictions table."""
    path = PREPARED / filename
    if not path.exists():
        log.warning(f"  {filename} not found, skipping")
        return []

    with open(path) as f:
        data = json.load(f)

    rows = []
    for feat in data.get("features", []):
        props = feat["properties"]
        geom = shape(feat["geometry"])
        wkt = geom.wkt

        jurisdiction_id = props.get("jurisdiction_id")
        if not jurisdiction_id:
            log.warning(f"  Feature missing jurisdiction_id: {props}")
            continue

        name = props.get(config["name_field"], jurisdiction_id)

        rows.append({
            "layer": config["layer"],
            "jurisdiction_id": jurisdiction_id,
            "name": name,
            "geometry_wkt": wkt,
            "source_url": config["source_url"],
            "last_updated": date.today(),
        })

    return rows


async def upsert_rows(rows: list[dict], dry_run: bool = False):
    """Insert or update jurisdiction rows in the database."""
    import os

    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/cleanwater")

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, echo=False)

    if dry_run:
        log.info(f"  DRY RUN: would upsert {len(rows)} rows")
        for r in rows[:5]:
            log.info(f"    {r['jurisdiction_id']}: {r['name']} ({r['layer']})")
        if len(rows) > 5:
            log.info(f"    ... and {len(rows) - 5} more")
        await engine.dispose()
        return

    upsert_sql = text("""
        INSERT INTO jurisdictions (layer, jurisdiction_id, name, geometry, source_url, last_updated)
        VALUES (:layer, :jurisdiction_id, :name, ST_GeomFromText(:geometry_wkt, 4326), :source_url, :last_updated)
        ON CONFLICT (jurisdiction_id) DO UPDATE SET
            layer = EXCLUDED.layer,
            name = EXCLUDED.name,
            geometry = EXCLUDED.geometry,
            source_url = EXCLUDED.source_url,
            last_updated = EXCLUDED.last_updated
    """)

    async with engine.begin() as conn:
        for row in rows:
            await conn.execute(upsert_sql, row)

    log.info(f"  Upserted {len(rows)} rows")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Load prepared GeoJSON into PostGIS jurisdictions table")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be loaded without writing to DB")
    args = parser.parse_args()

    all_rows = []
    for filename, config in LAYER_CONFIG.items():
        log.info(f"--- {filename} ---")
        rows = load_features(filename, config)
        log.info(f"  {len(rows)} features")
        all_rows.extend(rows)

    log.info(f"\nTotal: {len(all_rows)} jurisdiction rows")

    if not all_rows:
        log.warning("No features to load. Run scripts/clip_and_reproject.py first.")
        return

    asyncio.run(upsert_rows(all_rows, dry_run=args.dry_run))
    log.info("Done.")


if __name__ == "__main__":
    main()
