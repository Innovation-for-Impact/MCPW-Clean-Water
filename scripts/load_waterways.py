"""
ETL script: Load NHDPlus HR flowlines into the waterways table.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/load_waterways.py \
        --input data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb \
        --layer NHDFlowline \
        --clip data/raw/municipalities/macomb_county_boundary.geojson

Requires: fiona, shapely
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import fiona
from shapely.geometry import mapping, shape
from shapely.ops import linemerge
from shapely import force_2d
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Load NHDPlus HR flowlines into PostGIS")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to prepared flowline file (Shapefile, GeoJSON, or GDB layer)",
    )
    parser.add_argument(
        "--layer",
        default=None,
        help="Layer name within a GDB file (e.g., 'NHDFlowline')",
    )
    parser.add_argument(
        "--clip",
        default=None,
        help="Path to a GeoJSON polygon to spatially filter flowlines (e.g., county boundary)",
    )
    parser.add_argument(
        "--clip-buffer-km",
        type=float,
        default=2.0,
        help="Buffer around clip polygon in km (default 2.0)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of rows per INSERT batch (default 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate but do not write to DB",
    )
    return parser.parse_args()


def load_clip_geometry(clip_path: str, buffer_km: float = 2.0):
    """Load a GeoJSON polygon and return it with an optional buffer."""
    with open(clip_path) as f:
        data = json.load(f)
    geom = shape(data["features"][0]["geometry"])
    # Buffer in degrees (~0.009 per km at this latitude)
    buffer_deg = buffer_km * 0.009
    return geom.buffer(buffer_deg)


def read_flowlines(input_path: str, layer: str | None = None, clip_geom=None):
    """Read flowlines from a spatial file, yield dicts.

    If clip_geom is provided, only yield features that intersect it.
    """
    open_kwargs = {"fp": input_path}
    if layer:
        open_kwargs["layer"] = layer

    with fiona.open(**open_kwargs) as src:
        log.info(f"CRS: {src.crs}")
        log.info(f"Schema fields: {list(src.schema['properties'].keys())[:15]}")
        log.info(f"Total features in source: {len(src)}")

        skipped = 0
        clipped = 0

        for feature in src:
            props = feature["properties"]
            geom = shape(feature["geometry"])

            # Spatial filter — skip features outside clip boundary
            if clip_geom is not None and not geom.intersects(clip_geom):
                skipped += 1
                continue
            clipped += 1

            # NHDPlus HR uses NHDPlusID or COMID — try both
            comid = props.get("NHDPlusID") or props.get("COMID") or props.get("nhdplusid")
            if comid is None:
                continue

            name = props.get("GNIS_Name") or props.get("gnis_name") or props.get("GNIS_NAME")

            # Normalize geometry: force 2D and merge MultiLineString to LineString
            geom = force_2d(geom)
            if geom.geom_type == "MultiLineString":
                merged = linemerge(geom)
                if merged.geom_type == "LineString":
                    geom = merged
                else:
                    # Take the longest part if merge doesn't produce a single line
                    geom = max(geom.geoms, key=lambda g: g.length)

            flow_dir = props.get("FlowDir", None)
            if flow_dir is not None:
                flow_dir = str(flow_dir)

            yield {
                "nhd_comid": int(comid),
                "name": name,
                "flow_direction": flow_dir,
                "downstream_comid": None,  # Populated by build_downstream_links.py
                "wkt": geom.wkt,
            }

        if clip_geom is not None:
            log.info(f"Clip filter: {clipped} kept, {skipped} skipped")


async def load_batch(session, batch: list[dict]):
    """Insert a batch of waterway records."""
    for row in batch:
        await session.execute(
            text("""
                INSERT INTO waterways (nhd_comid, name, flow_direction, downstream_comid, geometry)
                VALUES (:nhd_comid, :name, :flow_direction, :downstream_comid,
                        ST_GeogFromText(:wkt))
                ON CONFLICT (nhd_comid) DO UPDATE SET
                    name = EXCLUDED.name,
                    flow_direction = EXCLUDED.flow_direction
            """),
            {
                "nhd_comid": row["nhd_comid"],
                "name": row["name"],
                "flow_direction": row["flow_direction"],
                "downstream_comid": row["downstream_comid"],
                "wkt": row["wkt"],
            },
        )


async def main():
    args = parse_args()

    # Load clip geometry if specified
    clip_geom = None
    if args.clip:
        log.info(f"Loading clip boundary from: {args.clip} (buffer: {args.clip_buffer_km}km)")
        clip_geom = load_clip_geometry(args.clip, args.clip_buffer_km)

    log.info(f"Reading flowlines from: {args.input}")
    flowlines = list(read_flowlines(args.input, args.layer, clip_geom=clip_geom))
    log.info(f"Read {len(flowlines)} flowline features")

    named = sum(1 for f in flowlines if f["name"])
    log.info(f"  Named flowlines: {named}")

    if not flowlines:
        log.error("No flowlines found — check input file and COMID field names")
        sys.exit(1)

    if args.dry_run:
        log.info("Dry run — skipping database insert")
        log.info(f"Sample records:")
        for r in flowlines[:5]:
            log.info(f"  COMID {r['nhd_comid']}: {r['name'] or '(unnamed)'}")
        return

    # Lazy import — only needed for actual DB writes
    import os
    if "DATABASE_URL" not in os.environ:
        log.error("DATABASE_URL environment variable is required for DB writes")
        sys.exit(1)
    from src.models.database import async_session_factory, engine

    inserted = 0
    async with async_session_factory() as session:
        for i in range(0, len(flowlines), args.batch_size):
            batch = flowlines[i : i + args.batch_size]
            await load_batch(session, batch)
            inserted += len(batch)
            log.info(f"  Inserted {inserted}/{len(flowlines)}")
        await session.commit()

    log.info(f"Done. {inserted} waterway records loaded.")

    # Verify count
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM waterways"))
        count = result.scalar()
        log.info(f"Verification: {count} rows in waterways table")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
