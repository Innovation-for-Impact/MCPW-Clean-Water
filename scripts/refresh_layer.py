"""
WS3 Task 3.3 — Refresh a single jurisdiction layer from updated source data.

Process:
1. Download updated data into data/raw/{layer}/
2. Run prepare_layers.py to clip, reproject, and assign IDs
3. Run this script to reload the layer into PostGIS
4. Verify row counts and spot-check

Jurisdiction IDs are matched on name (not row order) to ensure stability
across refreshes. New or removed jurisdictions are flagged for WS4 to
update contacts.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/refresh_layer.py municipalities
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"

LAYER_MAP = {
    "municipalities": "municipality",
    "drain_districts": "drain_district",
    "subwatersheds": "subwatershed",
    "water_bodies": "water_body",
    "shoreline": "shoreline",
}


async def refresh(layer_name: str):
    if layer_name not in LAYER_MAP:
        print(f"Unknown layer: {layer_name}")
        print(f"Valid layers: {', '.join(LAYER_MAP.keys())}")
        sys.exit(1)

    db_layer = LAYER_MAP[layer_name]
    filepath = PREPARED_DIR / f"{layer_name}.geojson"

    if not filepath.exists():
        print(f"File not found: {filepath}")
        print(f"Run prepare_layers.py first to generate prepared data.")
        sys.exit(1)

    with open(filepath) as f:
        data = json.load(f)

    new_features = data.get("features", [])
    new_ids = set()
    for feature in new_features:
        jid = feature.get("properties", {}).get("jurisdiction_id")
        if jid:
            new_ids.add(jid)

    async with async_session_factory() as session:
        # Get existing IDs for this layer
        result = await session.execute(
            text("SELECT jurisdiction_id FROM jurisdictions WHERE layer = :layer"),
            {"layer": db_layer},
        )
        existing_ids = {row.jurisdiction_id for row in result.all()}

        added = new_ids - existing_ids
        removed = existing_ids - new_ids
        updated = new_ids & existing_ids

        print(f"Layer: {layer_name} ({db_layer})")
        print(f"  Existing: {len(existing_ids)} | New file: {len(new_ids)}")
        print(f"  Added: {len(added)} | Removed: {len(removed)} | Updated: {len(updated)}")

        if added:
            print(f"\n  NEW jurisdictions (WS4 needs contacts):")
            for jid in sorted(added):
                print(f"    + {jid}")

        if removed:
            print(f"\n  REMOVED jurisdictions (WS4 should review):")
            for jid in sorted(removed):
                print(f"    - {jid}")

        # Upsert features
        for feature in new_features:
            props = feature.get("properties", {})
            geom = json.dumps(feature.get("geometry", {}))
            jurisdiction_id = props.get("jurisdiction_id")
            name = props.get("name", props.get("NAME", "Unknown"))

            if not jurisdiction_id:
                continue

            await session.execute(
                text("""
                    INSERT INTO jurisdictions (layer, jurisdiction_id, name, geometry, last_updated)
                    VALUES (:layer, :jurisdiction_id, :name,
                            ST_GeogFromText(ST_AsText(ST_GeomFromGeoJSON(:geom))),
                            CURRENT_DATE)
                    ON CONFLICT (jurisdiction_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        geometry = EXCLUDED.geometry,
                        last_updated = CURRENT_DATE
                """),
                {"layer": db_layer, "jurisdiction_id": jurisdiction_id, "name": name, "geom": geom},
            )

        # Do NOT delete removed jurisdictions — they may have contacts/rules in WS4.
        # Flag them instead.
        if removed:
            print(f"\n  WARNING: {len(removed)} jurisdictions no longer in source data.")
            print("  They are NOT deleted (may have WS4 contacts). Review manually.")

        await session.commit()
        print(f"\n  Refresh complete: {len(new_ids)} features loaded.")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/refresh_layer.py <layer_name>")
        print(f"Valid layers: {', '.join(LAYER_MAP.keys())}")
        sys.exit(1)

    asyncio.run(refresh(sys.argv[1]))
