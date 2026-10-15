"""
WS3 Task 1.1b — Verify data source availability.

Checks public download URLs for each layer in the inventory.
Layers requiring direct requests to Macomb County Public Works are
logged as pending and must be followed up manually.

Usage:
    python scripts/check_sources.py
"""

import urllib.request
import urllib.error

SOURCES = [
    {
        "layer": "Municipal boundaries",
        "source": "Macomb County GIS Open Data",
        "url": "https://gis-macomb.opendata.arcgis.com/",
        "check_type": "portal",
    },
    {
        "layer": "Road centerlines",
        "source": "Michigan GIS Open Data",
        "url": "https://gis-michigan.opendata.arcgis.com/",
        "check_type": "portal",
    },
    {
        "layer": "Clinton River subwatersheds (HUC-12)",
        "source": "USGS WBD via National Map",
        "url": "https://apps.nationalmap.gov/downloader/",
        "check_type": "portal",
    },
    {
        "layer": "Water bodies + Stream flowlines",
        "source": "USGS NHD / NHDPlus HR",
        "url": "https://www.usgs.gov/national-hydrography/nhdplus-high-resolution",
        "check_type": "portal",
    },
    {
        "layer": "Lake St. Clair shoreline",
        "source": "Michigan GIS Open Data",
        "url": "https://gis-michigan.opendata.arcgis.com/",
        "check_type": "portal",
    },
]

MANUAL_REQUESTS = [
    {
        "layer": "County drains (centerlines + attributes)",
        "source": "Macomb County Public Works",
        "status": "PENDING — direct request required",
    },
    {
        "layer": "Large known drains list (Tier 1/2)",
        "source": "Macomb County Public Works",
        "status": "PENDING — direct request required",
    },
    {
        "layer": "County drain districts",
        "source": "Macomb County Public Works",
        "status": "PENDING — direct request required",
    },
    {
        "layer": "Storm sewer outfalls",
        "source": "Macomb County Public Works",
        "status": "PENDING — may not be shared",
    },
    {
        "layer": "Drain response plans",
        "source": "MCPWO / HRC",
        "status": "Red Run plan set received (Sept 2026 draft); others TBD",
    },
    {
        "layer": "USCG/EPA response zone line",
        "source": "USCG / EPA",
        "status": "RESEARCH NEEDED — no known public GIS source",
    },
]


def check_url(url: str, timeout: int = 10) -> bool:
    """Return True if the URL responds with 2xx."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "MCPW-CleanWater-SourceCheck/1.0")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return 200 <= resp.status < 400
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return False


def main():
    print("=" * 70)
    print("WS3 Data Source Availability Check")
    print("=" * 70)

    print("\n--- Public portals (URL reachability) ---\n")
    for s in SOURCES:
        ok = check_url(s["url"])
        status = "REACHABLE" if ok else "UNREACHABLE"
        print(f"  [{status:>11}]  {s['layer']}")
        print(f"                  {s['source']}: {s['url']}")

    print("\n--- Manual data requests ---\n")
    for s in MANUAL_REQUESTS:
        print(f"  [{s['status']}]")
        print(f"      {s['layer']} — {s['source']}")

    print("\n--- Gaps requiring action ---\n")
    print("  1. Send data-sharing request to Macomb County Public Works for:")
    print("     - County drain GIS inventory (centerlines, drain numbers, open/enclosed, intercounty)")
    print("     - Large known drains list (Tier 1/2) or size/flow threshold")
    print("     - Drain district boundaries (Shapefile)")
    print("     - Storm sewer outfalls (if available)")
    print("  2. Confirm USCG/EPA response zone boundary source (federal jurisdiction on Lake St. Clair)")
    print("  3. Download NHDPlus HR for HUC-4 0403 (Clinton River watershed) from USGS National Map")
    print("  4. Download WBD HUC-12 boundaries for Clinton River watershed")
    print("  5. Download municipal boundaries from Macomb County GIS Open Data portal")
    print()


if __name__ == "__main__":
    main()
