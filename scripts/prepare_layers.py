"""
WS3 Task 1.2b — Clip, reproject, and assign stable jurisdiction IDs to raw GIS layers.

Reads raw data from data/raw/{layer}/, clips to Macomb County boundary + 500m buffer,
reprojects to EPSG:4326, assigns stable jurisdiction_id values, and writes to data/prepared/.

Prerequisites:
    pip install fiona shapely pyproj

Usage:
    python scripts/prepare_layers.py
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PREPARED_DIR = PROJECT_ROOT / "data" / "prepared"

# Macomb County approximate bounding box (used as clipsrc when no boundary polygon available)
# Actual boundary polygon should be downloaded and placed in data/raw/county_boundary/
MACOMB_BBOX = "-83.11,42.44,-82.68,42.73"
BUFFER_M = 500  # buffer around county boundary for edge cases

# Layer definitions: raw subdirectory -> output filename prefix + ID scheme
LAYER_DEFS = [
    {
        "name": "municipalities",
        "raw_subdir": "municipalities",
        "output": "municipalities.geojson",
        "geometry_type": "MULTIPOLYGON",
        "id_prefix": "muni",
        "id_field": "NAME",  # field in source data to build stable ID from
    },
    {
        "name": "drain_districts",
        "raw_subdir": "drain_districts",
        "output": "drain_districts.geojson",
        "geometry_type": "MULTIPOLYGON",
        "id_prefix": "dd",
        "id_field": "NAME",
    },
    {
        "name": "subwatersheds",
        "raw_subdir": "subwatersheds",
        "output": "subwatersheds.geojson",
        "geometry_type": "MULTIPOLYGON",
        "id_prefix": "ws",
        "id_field": "NAME",
    },
    {
        "name": "water_bodies",
        "raw_subdir": "water_bodies",
        "output": "water_bodies.geojson",
        "geometry_type": "MULTIPOLYGON",
        "id_prefix": "wb",
        "id_field": "GNIS_NAME",
    },
    {
        "name": "shoreline",
        "raw_subdir": "shoreline",
        "output": "shoreline.geojson",
        "geometry_type": "MULTIPOLYGON",
        "id_prefix": "shore",
        "id_field": "NAME",
    },
]


def slugify(name: str) -> str:
    """Convert a name to a stable slug for jurisdiction IDs."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s


def find_source_file(subdir: Path) -> Path | None:
    """Find the first shapefile or geojson in a directory."""
    for ext in ("*.shp", "*.geojson", "*.json", "*.gdb"):
        files = list(subdir.glob(ext))
        if files:
            return files[0]
    # Check for .gdb directories
    for item in subdir.iterdir():
        if item.suffix == ".gdb" and item.is_dir():
            return item
    return None


def run_ogr2ogr(src: Path, dst: Path, geometry_type: str) -> bool:
    """Clip to Macomb County bbox, reproject to EPSG:4326, force geometry type."""
    cmd = [
        "ogr2ogr",
        "-f", "GeoJSON",
        "-t_srs", "EPSG:4326",
        "-clipdst", *MACOMB_BBOX.split(","),
        "-nlt", geometry_type,
        "-lco", "RFC7946=YES",
        str(dst),
        str(src),
    ]
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return False
    return True


def assign_jurisdiction_ids(geojson_path: Path, id_prefix: str, id_field: str):
    """Add jurisdiction_id to each feature based on id_field."""
    with open(geojson_path) as f:
        data = json.load(f)

    seen_ids = set()
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        name = props.get(id_field, "unknown") or "unknown"
        base_id = f"{id_prefix}_{slugify(name)}"

        # Ensure uniqueness
        jid = base_id
        counter = 2
        while jid in seen_ids:
            jid = f"{base_id}_{counter}"
            counter += 1
        seen_ids.add(jid)

        props["jurisdiction_id"] = jid
        if "name" not in props:
            props["name"] = name

    with open(geojson_path, "w") as f:
        json.dump(data, f)

    print(f"  Assigned {len(seen_ids)} jurisdiction IDs (prefix: {id_prefix}_)")


def main():
    PREPARED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("WS3 Layer Preparation: clip, reproject, assign IDs")
    print("=" * 60)

    for layer_def in LAYER_DEFS:
        name = layer_def["name"]
        subdir = RAW_DIR / layer_def["raw_subdir"]
        output = PREPARED_DIR / layer_def["output"]

        print(f"\n--- {name} ---")

        if not subdir.exists():
            print(f"  SKIP: {subdir} does not exist (data not yet downloaded)")
            continue

        src = find_source_file(subdir)
        if src is None:
            print(f"  SKIP: no shapefile/geojson/gdb found in {subdir}")
            continue

        print(f"  Source: {src}")
        if not run_ogr2ogr(src, output, layer_def["geometry_type"]):
            continue

        assign_jurisdiction_ids(output, layer_def["id_prefix"], layer_def["id_field"])
        print(f"  Output: {output}")

    print("\n--- Jurisdiction ID Scheme ---")
    print("  Format: {layer_code}_{slugified_name}")
    print("  Examples: muni_mount_clemens, dd_clinton_river, ws_middle_clinton")
    print("  These IDs are the foreign key WS4 uses in the rules table.")
    print("  They MUST remain stable across data refreshes (match on name, not row order).")
    print()


if __name__ == "__main__":
    main()
