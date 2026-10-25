"""
Parse NHDPlus flow table to populate downstream_comid for each waterway segment.
Also flags known beaches and drinking-water intakes.

Usage:
    DATABASE_URL="postgresql+asyncpg://..." python scripts/build_downstream_links.py \
        --input data/prepared/waterways/NHDPlusFlowlineVAA.dbf

The NHDPlus HR "NHDPlusFlowlineVAA" table contains the flow network:
  - NHDPlusID (or COMID): the segment identifier
  - DnHydroseq / DnLevelPathI / ToNode: downstream connectivity fields

This script reads the flow table and updates waterways.downstream_comid
for each segment already loaded in the database.

Requires: fiona (or dbfread for .dbf files)
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# Known beaches downstream — NHD COMIDs of waterway segments adjacent to beaches.
# Upstream propagation in flag_beaches_and_intakes() marks all feeding segments.
KNOWN_BEACHES = {
    60001500030913: "Clinton River near Memorial Park Beach",
    60001500030716: "Lake St. Clair Metropark Beach area",
    60001500027768: "Peltier Drain near Blossom Heath Beach",
    60001500017882: "Crapaud Creek near New Baltimore Civic Beach",
    60001500021069: "Selfridge ANG Base Beach area",
    60001500009496: "Metro Beach / Huron Point area",
}

# Known drinking-water intakes downstream — NHD COMIDs near intake locations.
# GLWA Lake St. Clair intake is the primary public water source for Macomb County.
KNOWN_INTAKES = {
    60001500030738: "GLWA Lake St. Clair Water Intake (approx)",
}


def read_flow_table_fiona(input_path: str, layer: str | None = None, loaded_comids: set | None = None):
    """Read NHDPlus flow table and build a from_comid -> to_comid mapping.

    Supports two table formats:
    - NHDPlusFlow: direct FromNHDPID -> ToNHDPID mapping (preferred)
    - NHDPlusFlowlineVAA: HydroSeq -> DnHydroSeq chain (fallback)

    If loaded_comids is provided, only include links where from_comid is in the set.
    """
    import fiona

    open_kwargs = {"fp": input_path}
    if layer:
        open_kwargs["layer"] = layer

    with fiona.open(**open_kwargs) as src:
        log.info(f"Reading flow table: {len(src)} records")
        fields = list(src.schema['properties'].keys())
        log.info(f"Fields: {fields[:20]}")

        # Detect format: NHDPlusFlow has FromNHDPID/ToNHDPID
        if "FromNHDPID" in fields:
            return _read_nhdplus_flow(src, loaded_comids)
        elif "HydroSeq" in fields or "Hydroseq" in fields:
            return _read_vaa_flow(src, loaded_comids)
        else:
            log.error(f"Unrecognized flow table format. Fields: {fields}")
            sys.exit(1)


def _read_nhdplus_flow(src, loaded_comids: set | None = None) -> dict[int, int]:
    """Parse NHDPlusFlow table (FromNHDPID -> ToNHDPID)."""
    downstream = {}
    for feature in src:
        props = feature["properties"]
        from_id = props.get("FromNHDPID")
        to_id = props.get("ToNHDPID")
        if from_id is None or to_id is None or to_id == 0:
            continue
        from_id, to_id = int(from_id), int(to_id)
        if loaded_comids is not None and from_id not in loaded_comids:
            continue
        downstream[from_id] = to_id

    log.info(f"Built {len(downstream)} downstream links from NHDPlusFlow table")
    return downstream


def _read_vaa_flow(src, loaded_comids: set | None = None) -> dict[int, int]:
    """Parse NHDPlusFlowlineVAA table using HydroSeq chain."""
    flow_map = {}
    for feature in src:
        props = feature["properties"]
        from_id = props.get("NHDPlusID") or props.get("COMID")
        if from_id is None:
            continue

        hydroseq = props.get("HydroSeq") or props.get("Hydroseq")
        dn_hydroseq = props.get("DnHydroSeq") or props.get("DnHydroseq")

        if hydroseq and dn_hydroseq:
            flow_map[int(from_id)] = {
                "hydroseq": int(hydroseq),
                "dn_hydroseq": int(dn_hydroseq),
            }

    # Build hydroseq -> comid reverse lookup
    hydroseq_to_comid = {info["hydroseq"]: comid for comid, info in flow_map.items()}

    # Resolve downstream COMIDs
    downstream = {}
    for comid, info in flow_map.items():
        if loaded_comids is not None and comid not in loaded_comids:
            continue
        dn_comid = hydroseq_to_comid.get(info["dn_hydroseq"])
        if dn_comid:
            downstream[comid] = dn_comid

    log.info(f"Built downstream links for {len(downstream)} / {len(flow_map)} segments")
    return downstream


_session_factory = None
_engine = None


def _init_db():
    global _session_factory, _engine
    if _session_factory is not None:
        return
    import os
    if "DATABASE_URL" not in os.environ:
        log.error("DATABASE_URL environment variable is required")
        sys.exit(1)
    from src.models.database import async_session_factory, engine
    _session_factory = async_session_factory
    _engine = engine


async def update_downstream_links(downstream: dict[int, int]):
    """Update waterways.downstream_comid in the database."""
    _init_db()
    async with _session_factory() as session:
        updated = 0
        for from_comid, to_comid in downstream.items():
            result = await session.execute(
                text("""
                    UPDATE waterways
                    SET downstream_comid = :to_comid
                    WHERE nhd_comid = :from_comid
                      AND (downstream_comid IS NULL OR downstream_comid != :to_comid)
                """),
                {"from_comid": from_comid, "to_comid": to_comid},
            )
            updated += result.rowcount

        await session.commit()
        log.info(f"Updated downstream_comid for {updated} waterway segments")


async def flag_beaches_and_intakes():
    """Mark segments that have beaches or intakes downstream using recursive trace."""
    _init_db()
    async with _session_factory() as session:
        # Flag direct beach/intake segments
        for comid, name in KNOWN_BEACHES.items():
            await session.execute(
                text("""
                    UPDATE waterways SET has_beach_downstream = true
                    WHERE nhd_comid = :comid
                """),
                {"comid": comid},
            )
            log.info(f"  Flagged beach: {name} (COMID {comid})")

        for comid, name in KNOWN_INTAKES.items():
            await session.execute(
                text("""
                    UPDATE waterways SET has_intake_downstream = true
                    WHERE nhd_comid = :comid
                """),
                {"comid": comid},
            )
            log.info(f"  Flagged intake: {name} (COMID {comid})")

        # Propagate flags upstream: any segment whose downstream path
        # includes a flagged segment should also be flagged
        if KNOWN_BEACHES:
            result = await session.execute(text("""
                WITH RECURSIVE upstream AS (
                    SELECT nhd_comid FROM waterways WHERE has_beach_downstream = true
                    UNION
                    SELECT w.nhd_comid FROM waterways w
                    JOIN upstream u ON w.downstream_comid = u.nhd_comid
                )
                UPDATE waterways SET has_beach_downstream = true
                WHERE nhd_comid IN (SELECT nhd_comid FROM upstream)
            """))
            log.info(f"  Propagated beach flag to {result.rowcount} upstream segments")

        if KNOWN_INTAKES:
            result = await session.execute(text("""
                WITH RECURSIVE upstream AS (
                    SELECT nhd_comid FROM waterways WHERE has_intake_downstream = true
                    UNION
                    SELECT w.nhd_comid FROM waterways w
                    JOIN upstream u ON w.downstream_comid = u.nhd_comid
                )
                UPDATE waterways SET has_intake_downstream = true
                WHERE nhd_comid IN (SELECT nhd_comid FROM upstream)
            """))
            log.info(f"  Propagated intake flag to {result.rowcount} upstream segments")

        await session.commit()


async def verify():
    """Print summary statistics."""
    _init_db()
    async with _session_factory() as session:
        total = (await session.execute(text("SELECT COUNT(*) FROM waterways"))).scalar()
        linked = (await session.execute(
            text("SELECT COUNT(*) FROM waterways WHERE downstream_comid IS NOT NULL")
        )).scalar()
        beaches = (await session.execute(
            text("SELECT COUNT(*) FROM waterways WHERE has_beach_downstream = true")
        )).scalar()
        intakes = (await session.execute(
            text("SELECT COUNT(*) FROM waterways WHERE has_intake_downstream = true")
        )).scalar()

        log.info(f"Verification:")
        log.info(f"  Total waterway segments: {total}")
        log.info(f"  With downstream link:    {linked} ({linked/total*100:.1f}%)" if total else "  No segments")
        log.info(f"  Beach downstream flag:   {beaches}")
        log.info(f"  Intake downstream flag:  {intakes}")


async def main():
    parser = argparse.ArgumentParser(description="Build downstream connectivity links")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to NHDPlus flow/VAA table (DBF, GDB layer, or CSV)",
    )
    parser.add_argument("--layer", default=None, help="Layer name within a GDB file")
    parser.add_argument("--dry-run", action="store_true", help="Parse flow table but don't update DB")
    args = parser.parse_args()

    downstream = read_flow_table_fiona(args.input, args.layer)

    if args.dry_run:
        log.info("Dry run — sample links:")
        for i, (k, v) in enumerate(list(downstream.items())[:5]):
            log.info(f"  {k} -> {v}")
        return

    await update_downstream_links(downstream)
    await flag_beaches_and_intakes()
    await verify()
    await _engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
