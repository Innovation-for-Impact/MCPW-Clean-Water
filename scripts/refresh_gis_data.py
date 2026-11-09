"""Quarterly GIS data refresh — download, clip, and reload jurisdiction + waterway data.

Usage:
    python -m scripts.refresh_gis_data [--dry-run]

This script orchestrates the full data pipeline:
  1. Download latest layers (municipalities, subwatersheds, waterways)
  2. Clip and reproject to Macomb County extent
  3. Reload into PostGIS (jurisdictions + waterways + downstream links)

Designed to be run as a cron job or scheduled task (quarterly).
Requires DATABASE_URL pointing to a PostGIS database.

Set ENVIRONMENT=production to require explicit --confirm flag.
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPTS_DIR)


def run_step(description: str, cmd: list[str], dry_run: bool = False) -> bool:
    """Run a subprocess step. Returns True on success, False on failure."""
    log.info("STEP: %s", description)
    log.info("  cmd: %s", " ".join(cmd))

    if dry_run:
        log.info("  [DRY RUN] Skipping execution")
        return True

    try:
        result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            log.error("  FAILED (exit code %d)", result.returncode)
            if result.stderr:
                log.error("  stderr: %s", result.stderr[:500])
            return False
        log.info("  OK")
        return True
    except subprocess.TimeoutExpired:
        log.error("  TIMEOUT after 30 minutes")
        return False


def main():
    parser = argparse.ArgumentParser(description="Quarterly GIS data refresh")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--confirm", action="store_true", help="Required in production to proceed")
    parser.add_argument("--skip-download", action="store_true", help="Skip download step (use existing data)")
    args = parser.parse_args()

    if os.environ.get("ENVIRONMENT", "").lower() == "production" and not args.confirm:
        log.error("Production environment detected. Pass --confirm to proceed.")
        sys.exit(1)

    log.info("=" * 60)
    log.info("GIS Data Refresh — %s", date.today())
    log.info("=" * 60)

    python = sys.executable
    steps = []

    # Step 1: Download layers
    if not args.skip_download:
        steps.append(("Download GIS layers", [python, "scripts/download_layers.py", "--all"]))

    # Step 2: Clip and reproject
    steps.append(("Clip and reproject to Macomb County", [python, "scripts/clip_and_reproject.py"]))

    # Step 3: Load jurisdictions
    steps.append(("Load jurisdiction layers into PostGIS", [python, "-m", "scripts.load_layers"]))

    # Step 4: Load waterways
    nhd_gdb = "data/raw/waterways/NHDPLUS_H_0409_HU4_GDB.gdb"
    clip_file = "data/raw/municipalities/macomb_county_boundary.geojson"
    steps.append(
        (
            "Load NHDPlus waterways",
            [python, "-m", "scripts.load_waterways", "-i", nhd_gdb, "--layer", "NHDFlowline", "--clip", clip_file],
        )
    )

    # Step 5: Build downstream links
    steps.append(
        (
            "Build downstream links",
            [python, "-m", "scripts.build_downstream_links", "-i", nhd_gdb, "--layer", "NHDPlusFlow"],
        )
    )

    # Execute pipeline
    failed = []
    for description, cmd in steps:
        success = run_step(description, cmd, dry_run=args.dry_run)
        if not success:
            failed.append(description)
            log.warning("Continuing despite failure in: %s", description)

    # Summary
    log.info("=" * 60)
    log.info("Refresh complete — %d/%d steps succeeded", len(steps) - len(failed), len(steps))
    if failed:
        log.warning("Failed steps:")
        for f in failed:
            log.warning("  - %s", f)
        sys.exit(1)
    else:
        log.info("All steps succeeded.")


if __name__ == "__main__":
    main()
