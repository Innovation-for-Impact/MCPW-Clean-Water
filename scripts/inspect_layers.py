"""
Inspect downloaded GIS datasets in data/raw/.

Usage:
    python scripts/inspect_layers.py [--dir data/raw/municipalities]

For each file found, reports: geometry type, feature count, CRS,
attribute fields, and sample values. Helps verify data before
clipping and reprojection.

Requires: fiona
"""
import argparse
import logging
from pathlib import Path

import fiona

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_RAW = Path(__file__).parent.parent / "data" / "raw"

# File extensions to scan
SPATIAL_EXTENSIONS = {".shp", ".geojson", ".json", ".gdb", ".gpkg"}


def find_spatial_files(search_dir: Path) -> list[Path]:
    """Find spatial data files recursively."""
    files = []
    for p in sorted(search_dir.rglob("*")):
        if p.suffix.lower() in SPATIAL_EXTENSIONS:
            files.append(p)
        # .gdb is a directory, detect by looking for a known file inside
        if p.is_dir() and p.suffix.lower() == ".gdb":
            files.append(p)
    # Deduplicate (gdb dirs may appear twice)
    return list(dict.fromkeys(files))


def inspect_file(path: Path, layer: str | None = None):
    """Inspect and report on a single spatial file/layer."""
    open_kwargs = {"fp": str(path)}
    if layer:
        open_kwargs["layer"] = layer

    try:
        with fiona.open(**open_kwargs) as src:
            print(f"\n{'='*60}")
            print(f"File:     {path}")
            if layer:
                print(f"Layer:    {layer}")
            print(f"Driver:   {src.driver}")
            print(f"CRS:      {src.crs}")
            print(f"Features: {len(src)}")
            print(f"Bounds:   {src.bounds}")

            schema = src.schema
            print(f"Geometry: {schema['geometry']}")
            print(f"Fields:   ({len(schema['properties'])} total)")
            for name, dtype in list(schema["properties"].items())[:15]:
                print(f"  - {name}: {dtype}")
            if len(schema["properties"]) > 15:
                print(f"  ... and {len(schema['properties']) - 15} more")

            # Sample first record
            for i, feature in enumerate(src):
                if i == 0:
                    print(f"Sample record properties:")
                    for k, v in list(feature["properties"].items())[:10]:
                        print(f"  {k}: {v}")
                    geom = feature["geometry"]
                    print(f"  geometry type: {geom['type']}")
                break

            print(f"{'='*60}")

    except Exception as e:
        log.error(f"Failed to inspect {path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Inspect downloaded GIS layers")
    parser.add_argument(
        "--dir", "-d",
        default=str(DATA_RAW),
        help=f"Directory to scan (default: {DATA_RAW})",
    )
    parser.add_argument(
        "--layer", "-l",
        default=None,
        help="Specific layer name within a GDB file",
    )
    args = parser.parse_args()

    search_dir = Path(args.dir)
    if not search_dir.exists():
        log.error(f"Directory not found: {search_dir}")
        return

    files = find_spatial_files(search_dir)

    if not files:
        log.warning(f"No spatial files found in {search_dir}")
        log.info("Have you run 'python scripts/download_layers.py --all' yet?")
        return

    log.info(f"Found {len(files)} spatial file(s) in {search_dir}")

    for f in files:
        if f.suffix.lower() == ".gdb" and f.is_dir():
            # List layers in GDB
            layers = fiona.listlayers(str(f))
            log.info(f"GDB {f.name} has {len(layers)} layers: {layers[:10]}")
            if args.layer:
                inspect_file(f, args.layer)
            else:
                for lyr in layers[:5]:
                    inspect_file(f, lyr)
                if len(layers) > 5:
                    log.info(f"  ... {len(layers) - 5} more layers. Use --layer to inspect a specific one.")
        else:
            inspect_file(f, args.layer)


if __name__ == "__main__":
    main()
