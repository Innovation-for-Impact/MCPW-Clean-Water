"""
Download publicly available GIS layers for WS3.

Usage:
    python scripts/download_layers.py [--layer LAYER_NAME] [--all]

This script downloads data from verified public sources into data/raw/.
Some downloads are large (NHDPlus HR ~500MB). Run with --layer to
download one at a time, or --all for everything.

NOTE: S3 filenames and REST endpoints were verified 2026-10-22 but may
change. If a download fails, check scripts/inventory.md for updated URLs.
"""
import argparse
import logging
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DATA_RAW = Path(__file__).parent.parent / "data" / "raw"

# Each layer: name, target directory, download URL, expected format
LAYERS = {
    "municipalities": {
        "dir": "municipalities",
        "url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/2/query?where=1%3D1&outFields=*&f=geojson",
        "format": "geojson",
        "description": "Michigan Minor Civil Divisions (all municipalities) — REST query as GeoJSON. "
                       "Filter to Macomb County (FIPS 099) after download.",
    },
    "county_boundary": {
        "dir": "municipalities",
        "url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/michigan_geographic_framework/MapServer/0/query?where=NAME%3D%27Macomb%27&outFields=*&f=geojson",
        "format": "geojson",
        "filename": "macomb_county_boundary.geojson",
        "description": "Macomb County boundary polygon for clipping.",
    },
    "shoreline": {
        "dir": "shoreline",
        "url": "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/hydro/MapServer/13/query?where=1%3D1&outFields=*&f=geojson",
        "format": "geojson",
        "description": "Lake St. Clair shoreline from Michigan hydro layer.",
    },
    "subwatersheds": {
        "dir": "subwatersheds",
        "url": "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/6/query"
               "?where=HUC12+LIKE+%2704090003%25%27&outFields=*&f=geojson"
               "&resultRecordCount=5000",
        "format": "geojson",
        "description": "USGS WBD HUC-12 subwatersheds within HUC-8 04090003 "
                       "(Clinton River) via ArcGIS REST query.",
    },
    "waterways": {
        "dir": "waterways",
        "url": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
               "NHDPlusHR/VPU/Current/GDB/NHDPLUS_H_0409_HU4_GDB.zip",
        "format": "zip",
        "description": "USGS NHDPlus HR flowlines + water bodies, HUC-4 0409. "
                       "~500MB download from S3.",
    },
}


def download_geojson(url: str, dest: Path):
    """Download a GeoJSON response from an ArcGIS REST query."""
    log.info(f"  GET {url[:100]}...")
    # ArcGIS REST may paginate; for now do a simple fetch.
    # If >2000 features, need to paginate with resultOffset.
    req = urllib.request.Request(url, headers={"User-Agent": "MCPW-WS3-ETL/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)
    size_mb = len(data) / (1024 * 1024)
    log.info(f"  Saved {dest} ({size_mb:.1f} MB)")


def download_zip(url: str, dest_dir: Path):
    """Download and extract a zip file."""
    zip_path = dest_dir / "download.zip"
    log.info(f"  GET {url[:100]}...")
    req = urllib.request.Request(url, headers={"User-Agent": "MCPW-WS3-ETL/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        zip_path.write_bytes(resp.read())
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    log.info(f"  Downloaded {size_mb:.1f} MB, extracting...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()
    log.info(f"  Extracted to {dest_dir}")


def download_layer(name: str):
    layer = LAYERS[name]
    dest_dir = DATA_RAW / layer["dir"]
    dest_dir.mkdir(parents=True, exist_ok=True)

    if layer["url"] is None:
        log.warning(f"  [{name}] No automated download — manual step required:")
        log.warning(f"  {layer['description']}")
        log.warning(f"  Place downloaded files in: {dest_dir}")
        return False

    if layer["format"] == "geojson":
        filename = layer.get("filename", f"{name}.geojson")
        download_geojson(layer["url"], dest_dir / filename)
    elif layer["format"] in ("zip", "gdb"):
        download_zip(layer["url"], dest_dir)
    else:
        log.error(f"  Unknown format: {layer['format']}")
        return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Download WS3 GIS layers")
    parser.add_argument("--layer", choices=list(LAYERS.keys()), help="Download a specific layer")
    parser.add_argument("--all", action="store_true", help="Download all available layers")
    parser.add_argument("--list", action="store_true", help="List available layers")
    args = parser.parse_args()

    if args.list:
        for name, info in LAYERS.items():
            status = "AUTO" if info["url"] else "MANUAL"
            print(f"  [{status}] {name}: {info['description'][:80]}")
        return

    if not args.layer and not args.all:
        parser.print_help()
        return

    layers_to_download = [args.layer] if args.layer else list(LAYERS.keys())

    for name in layers_to_download:
        log.info(f"--- {name} ---")
        download_layer(name)
        print()

    log.info("Done. Next steps:")
    log.info("  1. Inspect: python -c \"import fiona; print(fiona.open('data/raw/...').schema)\"")
    log.info("  2. Clip to county: ogr2ogr -clipsrc data/raw/municipalities/macomb_county_boundary.geojson ...")
    log.info("  3. Reproject: ogr2ogr -t_srs EPSG:4326 ...")


if __name__ == "__main__":
    main()
