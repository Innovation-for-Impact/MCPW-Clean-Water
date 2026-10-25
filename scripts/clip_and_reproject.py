"""
Clip downloaded GIS layers to the Macomb County boundary and reproject to EPSG:4326.

Usage:
    python scripts/clip_and_reproject.py

Reads from data/raw/, writes clipped + reprojected layers to data/prepared/.
Uses shapely for spatial clipping. All ArcGIS REST downloads already arrive in
WGS84 (EPSG:4326), so reprojection is a no-op for those; this script still
normalizes CRS metadata in the output.

Requires: shapely (pip install shapely)
"""
import json
import logging
import urllib.request
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
RAW = ROOT / "data" / "raw"
PREPARED = ROOT / "data" / "prepared"


def load_county_boundary() -> "shapely.geometry.base.BaseGeometry":
    """Load and return the Macomb County boundary polygon."""
    path = RAW / "municipalities" / "macomb_county_boundary.geojson"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run: python scripts/download_layers.py --layer county_boundary"
        )
    with open(path) as f:
        data = json.load(f)
    return shape(data["features"][0]["geometry"])


def clip_geojson(input_path: Path, clip_geom, output_path: Path, buffer_m: float = 0.001):
    """Clip a GeoJSON file to the given geometry, with a small buffer for edge cases.

    buffer_m is in degrees (~111m at equator); 0.001 ≈ 111m buffer.
    """
    with open(input_path) as f:
        data = json.load(f)

    clip_buffered = clip_geom.buffer(buffer_m)
    clipped_features = []

    for feat in data.get("features", []):
        geom = shape(feat["geometry"])
        if geom.intersects(clip_buffered):
            clipped = geom.intersection(clip_buffered)
            if not clipped.is_empty:
                feat["geometry"] = mapping(clipped)
                clipped_features.append(feat)

    output = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": clipped_features,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f)

    log.info(f"  {input_path.name}: {len(data.get('features', []))} -> {len(clipped_features)} features")
    return len(clipped_features)


def download_municipalities_for_county(county_geom, output_path: Path):
    """Download municipalities within the county bbox directly from ArcGIS REST."""
    bounds = county_geom.bounds  # (minx, miny, maxx, maxy)
    bbox = f"{bounds[0]-0.01},{bounds[1]-0.01},{bounds[2]+0.01},{bounds[3]+0.01}"
    url = (
        "https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/"
        "michigan_geographic_framework/MapServer/2/query"
        f"?where=1%3D1&geometry={bbox}&geometryType=esriGeometryEnvelope"
        "&inSR=4326&spatialRel=esriSpatialRelIntersects"
        "&outFields=*&f=geojson&resultRecordCount=5000"
    )
    log.info("  Downloading municipalities within county bbox...")
    req = urllib.request.Request(url, headers={"User-Agent": "MCPW-WS3-ETL/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    features = data.get("features", [])
    log.info(f"  Downloaded {len(features)} municipality features")

    # Clip precisely to county boundary
    clipped_features = []
    for feat in features:
        geom = shape(feat["geometry"])
        if geom.intersects(county_geom):
            clipped = geom.intersection(county_geom.buffer(0.001))
            if not clipped.is_empty:
                feat["geometry"] = mapping(clipped)
                clipped_features.append(feat)

    output = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": clipped_features,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f)

    log.info(f"  Clipped to {len(clipped_features)} features within Macomb County")
    return len(clipped_features)


def main():
    log.info("Loading Macomb County boundary...")
    county_geom = load_county_boundary()
    log.info(f"  Bounds: {county_geom.bounds}")

    results = {}

    # 1. Municipalities — re-download with spatial filter + clip
    log.info("\n--- Municipalities ---")
    muni_out = PREPARED / "municipalities.geojson"
    results["municipalities"] = download_municipalities_for_county(county_geom, muni_out)

    # 2. Shoreline — clip existing download
    log.info("\n--- Shoreline ---")
    shoreline_raw = RAW / "shoreline" / "shoreline.geojson"
    if shoreline_raw.exists():
        results["shoreline"] = clip_geojson(
            shoreline_raw, county_geom, PREPARED / "shoreline.geojson"
        )
    else:
        log.warning("  Shoreline not downloaded. Run: python scripts/download_layers.py --layer shoreline")

    # 3. Subwatersheds — clip existing download
    log.info("\n--- Subwatersheds ---")
    subwatersheds_raw = RAW / "subwatersheds" / "subwatersheds.geojson"
    if subwatersheds_raw.exists():
        results["subwatersheds"] = clip_geojson(
            subwatersheds_raw, county_geom, PREPARED / "subwatersheds.geojson"
        )
    else:
        log.warning("  Subwatersheds not downloaded. Run: python scripts/download_layers.py --layer subwatersheds")

    # 4. County boundary — copy as-is (already is the clip boundary)
    log.info("\n--- County boundary ---")
    county_raw = RAW / "municipalities" / "macomb_county_boundary.geojson"
    county_out = PREPARED / "county_boundary.geojson"
    with open(county_raw) as f:
        data = json.load(f)
    data["crs"] = {"type": "name", "properties": {"name": "EPSG:4326"}}
    county_out.parent.mkdir(parents=True, exist_ok=True)
    with open(county_out, "w") as f:
        json.dump(data, f)
    results["county_boundary"] = len(data.get("features", []))
    log.info(f"  Copied county boundary ({results['county_boundary']} features)")

    # Summary
    log.info("\n=== Summary ===")
    for layer, count in results.items():
        log.info(f"  {layer}: {count} features -> data/prepared/{layer}.geojson")

    # Note manual layers
    manual = []
    if not (RAW / "subwatersheds").exists() or not list((RAW / "subwatersheds").glob("*")):
        manual.append("subwatersheds (USGS WBD)")
    if not (RAW / "waterways").exists() or not list((RAW / "waterways").glob("*")):
        manual.append("waterways (NHDPlus HR)")
    if manual:
        log.info("\n  Still need manual download:")
        for m in manual:
            log.info(f"    - {m}")
        log.info("  See scripts/inventory.md for download instructions.")


if __name__ == "__main__":
    main()
