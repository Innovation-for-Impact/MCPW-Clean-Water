"""
WS3 ETL — Load NHDPlus HR flowlines into PostGIS waterways table.

Reads NHDPlus HR geodatabase from data/raw/waterways/ and loads flowlines
clipped to the Macomb County area into the waterways table.

Prerequisites:
    pip install fiona shapely pyproj

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/load_waterways.py
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import async_session_factory, engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "waterways"

# Macomb County approximate bounding box for filtering
MACOMB_BBOX = {
    "min_lon": -83.11,
    "max_lon": -82.68,
    "min_lat": 42.44,
    "max_lat": 42.73,
}


async def load_from_geojson(session: AsyncSession, filepath: Path) -> int:
    """Load waterway features from a GeoJSON file."""
    with open(filepath) as f:
        data = json.load(f)

    count = 0
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geom = json.dumps(feature.get("geometry", {}))

        name = props.get("GNIS_Name") or props.get("name") or props.get("GNIS_NAME")
        comid = props.get("NHDPlusID") or props.get("COMID") or props.get("nhd_comid")

        if comid is not None:
            comid = int(comid)

        await session.execute(
            text("""
                INSERT INTO waterways (name, nhd_comid, geometry)
                VALUES (:name, :nhd_comid, ST_GeogFromText(ST_AsText(ST_GeomFromGeoJSON(:geom))))
                ON CONFLICT (nhd_comid) DO UPDATE SET
                    name = EXCLUDED.name,
                    geometry = EXCLUDED.geometry
            """),
            {"name": name, "nhd_comid": comid, "geom": geom},
        )
        count += 1

    return count


async def load_from_fiona(session: AsyncSession, gdb_path: Path, layer_name: str = "NHDFlowline") -> int:
    """Load waterway features from an NHDPlus GDB using Fiona."""
    try:
        import fiona
        from shapely.geometry import shape, mapping
        from pyproj import Transformer
    except ImportError:
        print("  ERROR: fiona, shapely, and pyproj required. Install with: pip install fiona shapely pyproj")
        return 0

    count = 0
    transformer = None

    with fiona.open(gdb_path, layer=layer_name) as src:
        src_crs = src.crs
        if src_crs and str(src_crs).upper() != "EPSG:4326":
            transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)

        for feature in src:
            props = feature.get("properties", {})
            geom = shape(feature["geometry"])

            # Filter to Macomb County bbox
            centroid = geom.centroid
            lon, lat = centroid.x, centroid.y
            if transformer:
                lon, lat = transformer.transform(lon, lat)
            if not (MACOMB_BBOX["min_lon"] <= lon <= MACOMB_BBOX["max_lon"]
                    and MACOMB_BBOX["min_lat"] <= lat <= MACOMB_BBOX["max_lat"]):
                continue

            # Reproject if needed
            if transformer:
                from shapely.ops import transform
                geom = transform(transformer.transform, geom)

            geom_json = json.dumps(mapping(geom))
            name = props.get("GNIS_Name") or props.get("GNIS_NAME")
            comid = props.get("NHDPlusID") or props.get("COMID")
            if comid is not None:
                comid = int(comid)

            await session.execute(
                text("""
                    INSERT INTO waterways (name, nhd_comid, geometry)
                    VALUES (:name, :nhd_comid, ST_GeogFromText(ST_AsText(ST_GeomFromGeoJSON(:geom))))
                    ON CONFLICT (nhd_comid) DO UPDATE SET
                        name = EXCLUDED.name,
                        geometry = EXCLUDED.geometry
                """),
                {"name": name, "nhd_comid": comid, "geom": geom_json},
            )
            count += 1

    return count


async def main():
    print("=" * 60)
    print("WS3 ETL: Load NHDPlus flowlines into waterways table")
    print("=" * 60)

    if not RAW_DIR.exists():
        print(f"\n  SKIP: {RAW_DIR} does not exist. Download NHDPlus HR data first.")
        print("  Source: https://www.usgs.gov/national-hydrography/nhdplus-high-resolution")
        return

    # Try GeoJSON first, then GDB
    geojson_files = list(RAW_DIR.glob("*.geojson")) + list(RAW_DIR.glob("*.json"))
    gdb_dirs = [d for d in RAW_DIR.iterdir() if d.suffix == ".gdb" and d.is_dir()]

    async with async_session_factory() as session:
        count = 0

        if geojson_files:
            for f in geojson_files:
                print(f"\n  Loading GeoJSON: {f.name}")
                count += await load_from_geojson(session, f)
        elif gdb_dirs:
            for gdb in gdb_dirs:
                print(f"\n  Loading GDB: {gdb.name}")
                count += await load_from_fiona(session, gdb)
        else:
            print("\n  No GeoJSON or GDB files found in data/raw/waterways/")
            print("  Download NHDPlus HR for HUC-4 0403 (Clinton River watershed)")

        if count > 0:
            await session.commit()
            print(f"\nLoaded {count} waterway flowlines")
        else:
            print("\nNo flowlines loaded")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
